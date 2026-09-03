"""industry-data 回归测试。

重点覆盖两件被 ADR 承诺过的行为：
1. 看板投影的 JSON 与原 Node 实现字节一致（迁移等价性）
2. 全量重建的 diff 门禁真的会拦住清空
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from modules.industry_data import excel, snapshot
from modules.industry_data.jsonio import dumps, dumps_canonical
from modules.industry_data.paths import DomainPaths
from workbench.paths import Paths
from workbench.result import Result


class TestJsonEquivalence(unittest.TestCase):
    """看板投影必须沿用 JS 的数字写法，权威文件必须沿用 Python 的。"""

    def test_integral_float_renders_like_js(self):
        self.assertEqual(dumps(0.0), "0")
        self.assertEqual(dumps(-0.0), "0")
        self.assertEqual(dumps(3.0), "3")

    def test_canonical_keeps_python_float(self):
        self.assertEqual(dumps_canonical(0.0), "0.0")

    def test_non_ascii_not_escaped(self):
        self.assertEqual(dumps({"月": "1月"}), '{\n  "月": "1月"\n}')

    def test_bool_and_none(self):
        self.assertEqual(dumps({"a": True, "b": None}), '{\n  "a": true,\n  "b": null\n}')

    def test_nested_indent_matches_stringify(self):
        payload = {"weekly": {"weeks": ["1/4-1/10"], "hotelADR": [0.05, None]}}
        expected = (
            "{\n"
            '  "weekly": {\n'
            '    "weeks": [\n'
            '      "1/4-1/10"\n'
            "    ],\n"
            '    "hotelADR": [\n'
            "      0.05,\n"
            "      null\n"
            "    ]\n"
            "  }\n"
            "}"
        )
        self.assertEqual(dumps(payload), expected)

    def test_empty_containers(self):
        self.assertEqual(dumps({"a": [], "b": {}}), '{\n  "a": [],\n  "b": {}\n}')


class TestMonthLabelParsing(unittest.TestCase):
    """底稿里「7月 (preliminary)」这类带后缀的标签必须能读到。

    旧实现用 ^\\d{1,2}月$ 严格匹配，会在 7 月处提前 break，月度只剩 6 个月；
    该缺陷此前被 merge 的「空值保留旧值」掩盖。
    """

    def test_month_suffix_is_normalised(self):
        import re

        for raw, expected in (
            ("1月", "1月"),
            ("7月 (preliminary)", "7月"),
            ("12月 ", "12月"),
        ):
            match = re.match(r"^(\d{1,2})月", raw.strip())
            self.assertIsNotNone(match, raw)
            self.assertEqual(f"{int(match.group(1))}月", expected)

    def test_non_month_label_stops_parsing(self):
        import re

        self.assertIsNone(re.match(r"^(\d{1,2})月", "季度"))
        self.assertIsNone(re.match(r"^(\d{1,2})月", "QTD周度"))


class TestWeekNormalisation(unittest.TestCase):
    def test_leading_zero_stripped(self):
        self.assertEqual(excel.norm_week("6/07-6/13"), "6/7-6/13")

    def test_festival_label_kept(self):
        self.assertEqual(excel.norm_week("春节(日均)"), "春节(日均)")


class TestDataUpdateInference(unittest.TestCase):
    def test_uses_latest_week_end(self):
        self.assertEqual(excel.infer_data_update(["7/26-8/1", "8/2-8/8"]), "2026-08-08")

    def test_skips_festival(self):
        self.assertEqual(excel.infer_data_update(["8/2-8/8", "春节(日均)"]), "2026-08-08")

    def test_year_wrap(self):
        self.assertEqual(excel.infer_data_update(["12/27-1/2"]), "2027-01-02")


class TestDiffGate(unittest.TestCase):
    """清空必须被拦住；超阈值必须直接 blocked。"""

    @staticmethod
    def _block(weeks, values):
        return {"weekly": {"weeks": weeks, "hotelADR": values}}

    def test_clear_is_detected(self):
        diff = snapshot.compute_diff(
            self._block(["1/4-1/10"], [0.05]),
            self._block(["1/4-1/10"], [None]),
        )
        self.assertEqual(len(diff.cleared), 1)
        self.assertEqual(diff.cleared[0].old, 0.05)
        self.assertIsNone(diff.cleared[0].new)

    def test_addition_is_not_a_clear(self):
        diff = snapshot.compute_diff(
            self._block(["1/4-1/10"], [None]),
            self._block(["1/4-1/10"], [0.05]),
        )
        self.assertEqual(diff.cleared, [])
        self.assertEqual(len(diff.added), 1)

    def test_new_week_is_reported_as_new_label(self):
        diff = snapshot.compute_diff(
            self._block(["1/4-1/10"], [0.05]),
            self._block(["1/4-1/10", "1/11-1/17"], [0.05, 0.06]),
        )
        self.assertEqual(diff.cleared, [])
        self.assertEqual(diff.new_labels, ["weekly · 1/11-1/17"])
        self.assertEqual(diff.changed_periods, ["weekly"])

    def test_changed_periods_only_names_layers_that_really_changed(self):
        old = {
            "weekly": {"weeks": ["1/4-1/10"], "hotelADR": [0.05]},
            "monthly": {"months": ["1月"], "railway": [0.01]},
            "quarterly": {"q1": {"hotelRevPAR": 0.02}},
        }
        monthly_only = {
            "weekly": {"weeks": ["1/4-1/10"], "hotelADR": [0.05]},
            "monthly": {"months": ["1月"], "railway": [0.03]},
            "quarterly": {"q1": {"hotelRevPAR": 0.02}},
        }
        mixed = {
            "weekly": {"weeks": ["1/4-1/10", "1/11-1/17"], "hotelADR": [0.05, 0.06]},
            "monthly": {"months": ["1月"], "railway": [0.03]},
            "quarterly": {"q1": {"hotelRevPAR": 0.02}},
        }

        self.assertEqual(snapshot.compute_diff(old, monthly_only).changed_periods, ["monthly"])
        self.assertEqual(snapshot.compute_diff(old, mixed).changed_periods, ["weekly", "monthly"])
        self.assertEqual(snapshot.compute_diff(old, old).changed_periods, [])

    def test_quarterly_change_is_detected_as_quarterly_only(self):
        old = {"quarterly": {"q1": {"hotelRevPAR": 0.02}}}
        new = {"quarterly": {"q1": {"hotelRevPAR": 0.03}}}
        self.assertEqual(snapshot.compute_diff(old, new).changed_periods, ["quarterly"])

    def test_few_clears_are_not_blocked(self):
        weeks = [f"1/{i}-1/{i + 6}" for i in range(1, 4)]
        diff = snapshot.compute_diff(
            self._block(weeks, [0.05, 0.06, 0.07]),
            self._block(weeks, [None, 0.06, 0.07]),
        )
        self.assertEqual(diff.blocked_reasons, [])

    def test_many_clears_are_blocked_by_count(self):
        weeks = [f"w{i}" for i in range(40)]
        diff = snapshot.compute_diff(
            self._block(weeks, [0.01] * 40),
            self._block(weeks, [None] * 11 + [0.01] * 29),
        )
        self.assertTrue(any("超过阈值" in reason for reason in diff.blocked_reasons))

    def test_clears_blocked_by_ratio(self):
        weeks = [f"w{i}" for i in range(9)]
        diff = snapshot.compute_diff(
            self._block(weeks, [0.01] * 9),
            self._block(weeks, [None] * 4 + [0.01] * 5),
        )
        self.assertTrue(any("%" in reason for reason in diff.blocked_reasons))

    def test_short_series_not_blocked_by_ratio(self):
        """序列太短时比例没有判别力（1/1 = 100%），不应误伤。"""
        diff = snapshot.compute_diff(
            self._block(["w0"], [0.01]),
            self._block(["w0"], [None]),
        )
        self.assertEqual(diff.blocked_reasons, [])


class TestRebuildRefusesToWriteOnClear(unittest.TestCase):
    """门禁未确认时不得落盘——这是 ADR 0001 成立的必要条件。"""

    def test_snapshot_untouched_when_clear_pending(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workbench").mkdir()
            (root / "docs").mkdir()
            (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
            paths = DomainPaths(Paths(root))
            paths.snapshot.parent.mkdir(parents=True, exist_ok=True)
            original = {"weekly": {"weeks": ["1/4-1/10"], "hotelADR": [0.05]}, "meta": {}}
            paths.snapshot.write_text(json.dumps(original), encoding="utf-8")

            def fake_build(workbook, previous):
                return {"weekly": {"weeks": ["1/4-1/10"], "hotelADR": [None]}, "meta": {}}

            real_build = snapshot.build
            snapshot.build = fake_build
            try:
                result = snapshot.rebuild(paths, root / "fake.xlsx")
            finally:
                snapshot.build = real_build

            self.assertEqual(result.status, "partial")
            self.assertEqual(json.loads(paths.snapshot.read_text(encoding="utf-8")), original)

    def test_writes_when_clear_confirmed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workbench").mkdir()
            (root / "docs").mkdir()
            (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
            paths = DomainPaths(Paths(root))
            paths.snapshot.parent.mkdir(parents=True, exist_ok=True)
            paths.snapshot.write_text(
                json.dumps({"weekly": {"weeks": ["1/4-1/10"], "hotelADR": [0.05]}, "meta": {}}),
                encoding="utf-8",
            )
            fresh = {"weekly": {"weeks": ["1/4-1/10"], "hotelADR": [None]}, "meta": {}}
            real_build = snapshot.build
            snapshot.build = lambda workbook, previous: fresh
            try:
                result = snapshot.rebuild(paths, root / "fake.xlsx", confirm_clears=True)
            finally:
                snapshot.build = real_build

            self.assertEqual(result.status, "success")
            written = json.loads(paths.snapshot.read_text(encoding="utf-8"))
            self.assertIsNone(written["weekly"]["hotelADR"][0])


if __name__ == "__main__":
    unittest.main()


class TestLineEndings(unittest.TestCase):
    """生成文件一律 LF。

    Python 在 Windows 上默认写 CRLF，而这些文件历史上由 Node 写出（LF）。
    不统一的话每次生成都会产生「全部行都变了」的 diff 噪音，把真正的内容变化埋掉。
    """

    def test_write_text_uses_lf(self):
        from workbench.fileio import write_text

        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "sub" / "a.txt"
            write_text(target, "line1\nline2\n")
            raw = target.read_bytes()
            self.assertNotIn(b"\r\n", raw)
            self.assertEqual(raw, b"line1\nline2\n")

    def test_write_text_atomic_uses_lf(self):
        from workbench.fileio import write_text_atomic

        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "a.json"
            write_text_atomic(target, '{\n  "a": 1\n}\n')
            self.assertNotIn(b"\r\n", target.read_bytes())
            self.assertFalse((Path(tmp) / "a.json.tmp").exists())

    def test_generated_dashboard_files_are_lf(self):
        """已生成的看板投影必须是 LF（对上线 diff 直接可见）。"""
        root = Path(__file__).resolve().parents[1]
        for name in ("data.js", "insights.js"):
            path = root / "dashboard" / "travel" / name
            if not path.is_file():
                self.skipTest(f"{name} 尚未生成")
            self.assertNotIn(b"\r\n", path.read_bytes(), f"{name} 含 CRLF")


class TestPeriodKeys(unittest.TestCase):
    """周期键一律 ASCII；中文只作标签（ADR 0007）。"""

    def test_all_period_examples_are_ascii(self):
        from workbench import domains

        for kind, example in domains.PERIOD_EXAMPLES.items():
            if kind == "none":
                continue
            self.assertTrue(example.isascii(), f"{kind} 的周期键示例含非 ASCII：{example}")

    def test_all_domain_period_keys_are_ascii(self):
        from workbench import domains

        for domain in domains.DOMAINS.values():
            example = domain.period_example
            if domain.period_kind == "none":
                continue
            self.assertTrue(example.isascii(), f"{domain.key} 的周期键含非 ASCII：{example}")

    def test_month_week_validates_and_labels(self):
        from workbench import domains

        news = domains.get("news-digest")
        self.assertTrue(news.validate_period("2026-08-W2"))
        self.assertFalse(news.validate_period("2026年8月第2周"))
        self.assertFalse(news.validate_period("2026-8-W2"))
        self.assertFalse(news.validate_period("2026-08-W6"))
        self.assertEqual(news.label("2026-08-W2"), "2026年8月第2周")

    def test_year_month_label(self):
        from workbench import domains

        self.assertEqual(domains.get("aviation-monthly").label("202607"), "2026年7月")

    def test_fiscal_quarter_label(self):
        from workbench import domains

        self.assertEqual(domains.period_label("fiscal_quarter", "26Q2"), "2026 Q2")


class TestStepMachine(unittest.TestCase):
    """步骤序列必须先种进 manifest，否则 status 看不到「还差几步」。"""

    def _paths(self, tmp: str):
        root = Path(tmp)
        (root / "workbench").mkdir()
        (root / "docs").mkdir()
        (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
        return Paths(root)

    def test_ensure_steps_seeds_pending(self):
        from modules.industry_data import steps

        with TemporaryDirectory() as tmp:
            base = self._paths(tmp)
            manifest = steps.open_manifest(base, "2026-08-08")
            states = manifest.load()["steps"]
            self.assertEqual(set(states), set(steps.STEP_ORDER))
            self.assertTrue(all(v["state"] == "pending" for v in states.values()))
            self.assertEqual(manifest.load()["order"], steps.STEP_ORDER)

    def test_progress_and_next(self):
        from modules.industry_data import steps

        with TemporaryDirectory() as tmp:
            base = self._paths(tmp)
            steps.record(base, "2026-08-08", "merge", "done")
            info = steps.progress(base, "2026-08-08")
            self.assertEqual(info["done"], 1)
            self.assertEqual(info["total"], len(steps.STEP_ORDER))
            self.assertEqual(info["next"], "dashboard")

    def test_merge_changed_periods_survive_across_sessions(self):
        """洞察选层不能只活在当前对话里；换会话后仍应读到最近一次逐格 diff。"""
        from modules.industry_data import steps

        with TemporaryDirectory() as tmp:
            base = self._paths(tmp)
            steps.record(
                base,
                "2026-08-08",
                "merge",
                "done",
                result_data={"changedPeriods": ["weekly", "monthly"]},
            )

            # 重新构造 Manifest（模拟换会话），仍能恢复选层
            self.assertEqual(steps.changed_periods(base, "2026-08-08"), ["weekly", "monthly"])

    def test_skipped_counts_as_settled(self):
        from modules.industry_data import steps

        with TemporaryDirectory() as tmp:
            base = self._paths(tmp)
            for key in steps.STEP_ORDER:
                steps.record(base, "2026-08-08", key, "skipped" if key != "merge" else "done")
            info = steps.progress(base, "2026-08-08")
            self.assertIsNone(info["next"])
            self.assertEqual(info["done"], len(steps.STEP_ORDER))

    def test_blocked_step_is_reported_as_stuck(self):
        from modules.industry_data import steps

        with TemporaryDirectory() as tmp:
            base = self._paths(tmp)
            steps.record(base, "2026-08-08", "merge", "blocked", note="清空超阈值")
            info = steps.progress(base, "2026-08-08")
            self.assertEqual(info["stuck"], ["merge"])

    def test_manifest_rejects_wrong_period_format(self):
        from workbench.manifest import Manifest

        with TemporaryDirectory() as tmp:
            base = self._paths(tmp)
            with self.assertRaises(SystemExit):
                Manifest(base, "industry-data", "2026年8月8日")


class TestSelectiveInsightDraft(unittest.TestCase):
    """更新后只出实际变动粒度，不再每次周/月/季全量重写。"""

    @staticmethod
    def _paths(tmp: str) -> DomainPaths:
        root = Path(tmp)
        (root / "workbench").mkdir()
        (root / "docs").mkdir()
        (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
        paths = DomainPaths(Paths(root))
        paths.snapshot.parent.mkdir(parents=True, exist_ok=True)
        paths.snapshot.write_text(
            json.dumps(
                {
                    "meta": {"dataUpdate": "2026-08-15"},
                    "weekly": {"weeks": ["8/9-8/15"], "aviationPax": [0.04]},
                    "monthly": {"months": ["7月"], "railway": [-0.026]},
                    "quarterly": {"q2": {"railway": 0.046}},
                }
            ),
            encoding="utf-8",
        )
        paths.insights_canonical.write_text(
            json.dumps({"meta": {}, "weekly": {"zh": []}, "monthly": {"zh": []}}),
            encoding="utf-8",
        )
        return paths

    def test_prepare_only_includes_selected_periods(self):
        from modules.industry_data import drafts

        with TemporaryDirectory() as tmp:
            paths = self._paths(tmp)
            result = drafts.prepare(paths, periods=["weekly", "monthly"])
            package = json.loads(Path(result.data["draft"]).read_text(encoding="utf-8"))

            self.assertEqual(result.status, "success")
            self.assertEqual(result.data["periods"], ["weekly", "monthly"])
            self.assertEqual(list(package["periods"]), ["weekly", "monthly"])
            self.assertNotIn("quarterly", package["periods"])

    def test_empty_selection_does_not_create_draft(self):
        from modules.industry_data import drafts

        with TemporaryDirectory() as tmp:
            result = drafts.prepare(self._paths(tmp), periods=[])
            self.assertEqual(result.status, "success")
            self.assertEqual(result.data["periods"], [])
            self.assertNotIn("draft", result.data)


class TestUpdateWorkflowOrchestration(unittest.TestCase):
    """更新数据后自动备草稿，只在最终写入上线处问人。"""

    def test_merge_auto_prepares_changed_layers_and_resets_downstream(self):
        from modules.industry_data import cli, drafts, insights, snapshot as snapshot_mod, steps

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workbench").mkdir()
            (root / "docs").mkdir()
            (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
            base = Paths(root)
            paths = DomainPaths(base)
            paths.snapshot.parent.mkdir(parents=True, exist_ok=True)
            paths.snapshot.write_text(
                json.dumps({"meta": {"dataUpdate": "2026-08-15"}}), encoding="utf-8"
            )
            workbook = root / "data" / "workbooks" / "国内行业数据_0830.xlsx"
            workbook.parent.mkdir(parents=True)
            workbook.write_bytes(b"fixture")
            draft_path = root / "scratch" / "auto-draft.json"

            calls: dict[str, object] = {}
            originals = (
                cli._resolve_workbook,
                snapshot_mod.rebuild,
                insights.mark_stale_if_outdated,
                drafts.prepare,
            )
            cli._resolve_workbook = lambda _base: (workbook, None)
            snapshot_mod.rebuild = lambda *_args, **_kwargs: Result(
                status="success",
                summary="重建完成",
                domain="industry-data",
                data={"changedPeriods": ["weekly", "monthly"]},
            )

            def fake_stale(_paths, periods):
                calls["stale"] = list(periods)
                return list(periods)

            def fake_prepare(_paths, period=None, *, periods=None):
                calls["draft"] = list(periods or [])
                return Result(
                    status="success",
                    summary="草稿已生成",
                    domain="industry-data",
                    data={"draft": str(draft_path), "periods": list(periods or [])},
                )

            insights.mark_stale_if_outdated = fake_stale
            drafts.prepare = fake_prepare
            try:
                result = cli.cmd_merge(SimpleNamespace(confirm_clears=False), base)
            finally:
                (
                    cli._resolve_workbook,
                    snapshot_mod.rebuild,
                    insights.mark_stale_if_outdated,
                    drafts.prepare,
                ) = originals

            self.assertEqual(calls["stale"], ["weekly", "monthly"])
            self.assertEqual(calls["draft"], ["weekly", "monthly"])
            self.assertEqual(result.data["insightsDraft"], str(draft_path))
            self.assertTrue(any("不要问" in item for item in result.next_steps), result.next_steps)

            manifest = steps.open_manifest(base, "2026-08-15").load()
            self.assertEqual(
                manifest["steps"]["merge"]["result"]["changedPeriods"],
                ["weekly", "monthly"],
            )
            self.assertEqual(manifest["steps"]["dashboard"]["state"], "pending")
            self.assertEqual(manifest["steps"]["insights"]["state"], "pending")
            self.assertEqual(manifest["steps"]["publish"]["state"], "pending")
            self.assertEqual(manifest["steps"]["feishu"]["state"], "skipped")


class TestValueTolerance(unittest.TestCase):
    """浮点尾数差异不算「修改」。

    真实事故：换一份底稿（同一批数据，被 Excel 重新保存过）后，merge 报「修改 14」，
    逐格核对发现 14 处全是 `-0.10400000000000009` 对 `-0.104` 这类尾数差异。
    而 runbook 让使用者盯的关键信号正是「修改应为 0」——假修改会把真修改淹掉。
    """

    @staticmethod
    def _block(values):
        return {"monthly": {"months": ["1月"], "intlCapacity": values}}

    def test_excel_float_tail_is_not_a_change(self):
        for old, new in (
            (-0.10400000000000009, -0.104),
            (-0.06799999999999995, -0.0679999999999999),
            (-0.1267375454145524, -0.126737545414552),
            (0.02033333333333333, 0.0203333333333333),
            (0.05666666666666667, 0.0566666666666667),
        ):
            diff = snapshot.compute_diff(self._block([old]), self._block([new]))
            self.assertEqual(diff.changed, [], f"{old!r} → {new!r} 不该算修改")

    def test_real_change_is_still_detected(self):
        """容差不能大到吞掉真实修正。0.1% 的改动必须报出来。"""
        diff = snapshot.compute_diff(self._block([-0.104]), self._block([-0.105]))
        self.assertEqual(len(diff.changed), 1)

    def test_sign_flip_is_detected(self):
        diff = snapshot.compute_diff(self._block([0.001]), self._block([-0.001]))
        self.assertEqual(len(diff.changed), 1)

    def test_zero_to_nonzero_is_detected(self):
        diff = snapshot.compute_diff(self._block([0.0]), self._block([0.0001]))
        self.assertEqual(len(diff.changed), 1)

    def test_both_zero_is_not_a_change(self):
        diff = snapshot.compute_diff(self._block([0.0]), self._block([-0.0]))
        self.assertEqual(diff.changed, [])

    def test_quarterly_uses_same_tolerance(self):
        old = {"quarterly": {"q2": {"hotelRevPAR": 0.02033333333333333}}}
        new = {"quarterly": {"q2": {"hotelRevPAR": 0.0203333333333333}}}
        self.assertEqual(snapshot.compute_diff(old, new).changed, [])

    def test_changed_details_are_reported(self):
        """只报数量不够——快照被覆盖后无处可查改了哪一格。"""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workbench").mkdir()
            (root / "docs").mkdir()
            (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
            paths = DomainPaths(Paths(root))
            paths.snapshot.parent.mkdir(parents=True, exist_ok=True)
            paths.snapshot.write_text(
                json.dumps({"monthly": {"months": ["1月"], "railway": [0.05]}, "meta": {}}),
                encoding="utf-8",
            )
            fresh = {"monthly": {"months": ["1月"], "railway": [0.09]}, "meta": {}}
            real_build = snapshot.build
            snapshot.build = lambda workbook, previous: fresh
            try:
                result = snapshot.rebuild(paths, root / "fake.xlsx")
            finally:
                snapshot.build = real_build

            self.assertEqual(result.status, "success")
            self.assertTrue(any("历史值被改动" in w for w in result.warnings))
            self.assertTrue(
                any(c["name"] == "已修改" and "railway" in c["detail"] for c in result.checks)
            )


class TestInsightsStaleOnMerge(unittest.TestCase):
    """指标更新后洞察必须被标为可能过期。

    真实缺陷：SKILL 写着「指标快照更新后…会被标为可能过期」，但 `mark_all_stale` 只有
    手动命令会调用，merge 完全不碰它。实测洞察 basedOn 停在 2026-08-08、快照已到
    2026-08-15，而 stale 三项全是 False——看板拿上一周的洞察配这一周的图表且无提示。
    """

    def _paths(self, tmp: str, *, based_on: str, snapshot_date: str, stale=None):
        root = Path(tmp)
        (root / "workbench").mkdir()
        (root / "docs").mkdir()
        (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
        paths = DomainPaths(Paths(root))
        paths.snapshot.parent.mkdir(parents=True, exist_ok=True)
        paths.snapshot.write_text(
            json.dumps({"meta": {"dataUpdate": snapshot_date}}), encoding="utf-8"
        )
        paths.insights_canonical.write_text(
            json.dumps(
                {
                    "meta": {
                        "basedOnTravelJsonUpdatedAt": based_on,
                        "stale": stale if stale is not None else dict.fromkeys(("weekly", "monthly", "quarterly"), False),
                    }
                }
            ),
            encoding="utf-8",
        )
        return paths

    def test_outdated_insights_are_marked(self):
        from modules.industry_data import insights

        with TemporaryDirectory() as tmp:
            paths = self._paths(tmp, based_on="2026-08-08", snapshot_date="2026-08-15")
            newly = insights.mark_stale_if_outdated(paths)
            self.assertEqual(sorted(newly), ["monthly", "quarterly", "weekly"])
            saved = json.loads(paths.insights_canonical.read_text(encoding="utf-8"))
            self.assertTrue(all(saved["meta"]["stale"].values()))

    def test_up_to_date_insights_are_left_alone(self):
        """洞察已基于最新数据确认时不能误标——否则每次 doctor 都在喊过期。"""
        from modules.industry_data import insights

        with TemporaryDirectory() as tmp:
            paths = self._paths(tmp, based_on="2026-08-15", snapshot_date="2026-08-15")
            self.assertEqual(insights.mark_stale_if_outdated(paths), [])
            saved = json.loads(paths.insights_canonical.read_text(encoding="utf-8"))
            self.assertFalse(any(saved["meta"]["stale"].values()))

    def test_explicit_changed_periods_work_even_when_data_date_is_unchanged(self):
        """同一期底稿修订月度值时 dataUpdate 不动；只看日期会漏标，逐格 diff 不会。"""
        from modules.industry_data import insights

        with TemporaryDirectory() as tmp:
            paths = self._paths(tmp, based_on="2026-08-15", snapshot_date="2026-08-15")
            newly = insights.mark_stale_if_outdated(paths, ["monthly"])

            self.assertEqual(newly, ["monthly"])
            saved = json.loads(paths.insights_canonical.read_text(encoding="utf-8"))
            self.assertEqual(
                saved["meta"]["stale"],
                {"weekly": False, "monthly": True, "quarterly": False},
            )

    def test_explicit_weekly_change_does_not_mark_monthly_or_quarterly(self):
        from modules.industry_data import insights

        with TemporaryDirectory() as tmp:
            paths = self._paths(tmp, based_on="2026-08-08", snapshot_date="2026-08-15")
            newly = insights.mark_stale_if_outdated(paths, ["weekly"])

            self.assertEqual(newly, ["weekly"])
            saved = json.loads(paths.insights_canonical.read_text(encoding="utf-8"))
            self.assertEqual(
                saved["meta"]["stale"],
                {"weekly": True, "monthly": False, "quarterly": False},
            )

    def test_already_stale_is_not_reported_twice(self):
        from modules.industry_data import insights

        with TemporaryDirectory() as tmp:
            paths = self._paths(
                tmp,
                based_on="2026-08-08",
                snapshot_date="2026-08-15",
                stale=dict.fromkeys(("weekly", "monthly", "quarterly"), True),
            )
            self.assertEqual(insights.mark_stale_if_outdated(paths), [])

    def test_missing_insights_file_is_tolerated(self):
        """洞察底稿不存在不该拖垮 merge。"""
        from modules.industry_data import insights

        with TemporaryDirectory() as tmp:
            paths = self._paths(tmp, based_on="2026-08-08", snapshot_date="2026-08-15")
            paths.insights_canonical.unlink()
            self.assertEqual(insights.mark_stale_if_outdated(paths), [])


class TestStepStateFromResult(unittest.TestCase):
    """`partial` 有两种含义，不能一刀切。

    真实缺陷：`generate-dashboard` 因洞察过期提醒返回 partial，四个投影文件其实都写出了，
    但步骤被记成 running。后果是进度少算一步，而且 publish 成功之后状态机还提示回头去
    `generate-dashboard`——提示自相矛盾，使用者会以为哪里没做完。
    """

    def test_success_is_done(self):
        from modules.industry_data import steps

        self.assertEqual(steps.step_state("success"), "done")

    def test_partial_with_complete_output_is_done(self):
        from modules.industry_data import steps

        self.assertEqual(steps.step_state("partial", {steps.COMPLETE_KEY: True}), "done")

    def test_partial_without_flag_stays_running(self):
        """merge 遇到清空未确认时根本没写入——这种 partial 必须留在未完成。"""
        from modules.industry_data import steps

        self.assertEqual(steps.step_state("partial"), "running")
        self.assertEqual(steps.step_state("partial", {}), "running")
        self.assertEqual(steps.step_state("partial", {steps.COMPLETE_KEY: False}), "running")

    def test_blocked_and_failed_unchanged(self):
        from modules.industry_data import steps

        self.assertEqual(steps.step_state("blocked"), "blocked")
        self.assertEqual(steps.step_state("failed"), "failed")

    def test_dashboard_declares_complete_when_insights_present(self):
        """洞察过期只是提醒，产出是完整的。"""
        from modules.industry_data import dashboard, steps

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workbench").mkdir()
            (root / "docs").mkdir()
            (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
            paths = DomainPaths(Paths(root))
            paths.snapshot.parent.mkdir(parents=True, exist_ok=True)
            paths.snapshot.write_text(json.dumps({"meta": {"dataUpdate": "2026-08-15"}}), encoding="utf-8")
            paths.insights_canonical.write_text(
                json.dumps({"meta": {"stale": {"weekly": True, "monthly": True, "quarterly": True}}}),
                encoding="utf-8",
            )
            result = dashboard.generate(paths)

            self.assertEqual(result.status, "partial")
            self.assertTrue(result.data[steps.COMPLETE_KEY])
            self.assertEqual(steps.step_state(result.status, result.data), "done")

    def test_dashboard_declares_incomplete_without_insights_source(self):
        """缺洞察底稿时 insights.js 根本没生成，不能算做完。"""
        from modules.industry_data import dashboard, steps

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workbench").mkdir()
            (root / "docs").mkdir()
            (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
            paths = DomainPaths(Paths(root))
            paths.snapshot.parent.mkdir(parents=True, exist_ok=True)
            paths.snapshot.write_text(json.dumps({"meta": {"dataUpdate": "2026-08-15"}}), encoding="utf-8")
            result = dashboard.generate(paths)

            self.assertEqual(result.status, "partial")
            self.assertFalse(result.data[steps.COMPLETE_KEY])
            self.assertEqual(steps.step_state(result.status, result.data), "running")
