"""Synthetic regression tests for the expert-calls migration; never calls Lark."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from modules.expert_calls import pipeline
from workbench.paths import Paths


def make_root(tmp: str) -> Paths:
    root = Path(tmp)
    (root / "workbench").mkdir()
    (root / "docs").mkdir()
    (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
    paths = Paths(root)
    paths.ensure_containers()
    return paths


def record(**over):
    row = {
        "include": True,
        "title": "分发效率改善",
        "expert_background": "前某平台业务负责人",
        "interview_time": "2026 年 6 月",
        "anchor_numbers": [
            {
                "value": f"{n * 10}%",
                "so_what": "改变渠道效率判断",
                "source_quote": f"指标约为 {n * 10}%",
                "quote_where": f"第 {n} 页，中段",
            }
            for n in range(1, 5)
        ],
        "paragraphs": ["样本中转化率为 10%，来自渠道调整。", "第二阶段份额达到 20%，但仅限该样本。"],
        "left_out": ["30%：不改变主结论"],
        "pdf_name": "synthetic-interview.pdf",
        "pdf_href": "https://trip.larkenterprise.com/file/SYNTHETIC",
        "value_reason": "补充渠道效率机制",
        "inclusion_evidence": {
            "quantified_content": {"anchors": 4},
            "causal_mechanism": "渠道调整改善转化",
            "relevant_information_gain": False,
        },
    }
    row.update(over)
    if "intel_entries" not in row:
        row["intel_entries"] = [
            {
                "kind": "statement",
                "date": "2026-06-18",
                "title": row["title"],
                "body": row["paragraphs"][0],
                "companies": ["ABNB"],
                "topics": ["distribution"],
                "media": row["pdf_name"],
                "quote": row["anchor_numbers"][0]["source_quote"],
                "quote_where": f"{row['pdf_name']} · {row['anchor_numbers'][0]['quote_where']}",
                "speaker": row["expert_background"],
            }
        ]
    return row


def manifest(*rows):
    return {"run_id": "20260822-143015", "interviews": list(rows)}


ANCHOR_CONTENT = (
    '<grid id="grid-1680"><h2 align="center">'
    '<span text-color="rgb(245,74,69)">Expert Call 精选</span></h2></grid>'
)
class TestManifestGate(unittest.TestCase):
    def test_synthetic_example_manifest_is_valid(self):
        example = pipeline.TEMPLATE.with_name("expert_calls.manifest.example.json")
        payload = pipeline.validate_manifest(example)
        self.assertEqual(payload["run_id"], "20260901-120000")

    def test_manifest_requires_stable_run_id(self):
        with self.assertRaisesRegex(pipeline.ManifestValidationError, "run_id"):
            pipeline.validate_manifest({"interviews": [record()]})

    def test_two_of_three_evidence_passes(self):
        payload = pipeline.validate_manifest(manifest(record()))
        self.assertEqual(len(payload["interviews"]), 1)

    def test_one_of_three_evidence_is_blocked(self):
        row = record(inclusion_evidence={
            "quantified_content": True,
            "causal_mechanism": False,
            "relevant_information_gain": False,
        })
        with self.assertRaisesRegex(pipeline.ManifestValidationError, "至少需要 2/3"):
            pipeline.validate_manifest(manifest(row))

    def test_fewer_than_four_anchor_numbers_is_blocked(self):
        with self.assertRaisesRegex(pipeline.ManifestValidationError, "少于 4"):
            pipeline.validate_manifest(manifest(record(anchor_numbers=record()["anchor_numbers"][:3])))

    def test_each_paragraph_requires_a_number(self):
        with self.assertRaisesRegex(pipeline.ManifestValidationError, "每段至少一个"):
            pipeline.validate_manifest(
                manifest(record(paragraphs=["第一段有 10%。", "第二段只有泛泛判断。"]))
            )

    def test_anchor_requires_quote_and_location(self):
        anchors = record()["anchor_numbers"]
        anchors[0] = {"value": "10%", "source_quote": "约 10%"}
        valid_intel = record()["intel_entries"]
        with self.assertRaisesRegex(pipeline.ManifestValidationError, "quote_where"):
            pipeline.validate_manifest(
                manifest(record(anchor_numbers=anchors, intel_entries=valid_intel))
            )

    def test_included_schema_and_excluded_skip_reason(self):
        pipeline.validate_manifest(manifest(record(), {"include": False, "skip_reason": "缺乏数字"}))
        with self.assertRaisesRegex(pipeline.ManifestValidationError, "skip_reason"):
            pipeline.validate_manifest(manifest({"include": False}))


class TestPdfExtraction(unittest.TestCase):
    def _opened(self, texts):
        pages = []
        for text in texts:
            page = MagicMock()
            page.extract_text.return_value = text
            pages.append(page)
        opened = MagicMock()
        opened.__enter__.return_value.pages = pages
        return opened

    def test_page_numbers_and_boundaries_are_preserved(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "extracted.txt"
            with patch("pdfplumber.open", return_value=self._opened(["alpha 10%", "beta 20%"])):
                pipeline.extract_pdf(Path(tmp) / "synthetic.pdf", out)
            text = out.read_text(encoding="utf-8")
            self.assertIn("=== Page 1 ===\nalpha 10%", text)
            self.assertIn("=== Page 2 ===\nbeta 20%", text)

    def test_empty_or_scanned_pdf_is_explicitly_blocked(self):
        with TemporaryDirectory() as tmp:
            with patch("pdfplumber.open", return_value=self._opened([None, "  "])):
                with self.assertRaisesRegex(pipeline.EmptyOrScannedPDFError, "扫描件或空 PDF"):
                    pipeline.extract_pdf(Path(tmp) / "scanned.pdf", Path(tmp) / "out.txt")
class TestRendering(unittest.TestCase):
    def test_exact_revision_1680_structure_and_xml_escaping(self):
        row = record(
            title='A&B <测试> "标题"',
            expert_background="前 A&B 负责人",
            paragraphs=["转化 < 10% & 改善。", "费率 > 20%。"],
            pdf_href="https://example.invalid/file?a=1&b=2",
        )
        xml = pipeline.render_callout(row)
        self.assertTrue(xml.startswith('<callout border-color="rgb(239,240,241)" emoji="📌">'))
        self.assertIn("<p><b>A&amp;B &lt;测试&gt; &quot;标题&quot;</b></p>", xml)
        self.assertIn("<blockquote><p>转化 &lt; 10% &amp; 改善。</p><p>费率 &gt; 20%。</p></blockquote>", xml)
        self.assertIn("更多详情请见：</span></em>https://example.invalid/file?a=1&amp;b=2</p>", xml)
        self.assertNotIn("background-color", xml)
        self.assertNotIn("bookmark", xml)


class TestLarkPlanning(unittest.TestCase):
    def test_resolves_whole_grid_anchor(self):
        self.assertEqual(pipeline.resolve_anchor(ANCHOR_CONTENT), "grid-1680")

    def test_resolves_grid_from_lark_keyword_excerpt(self):
        excerpt = (
            '<fragment mode="keyword" keyword="Expert Call">'
            '<excerpt top-block-id="doxcnVteWKe6Z00sUkUyVd50VPb">'
            '<column><h2 align="center"><span text-color="rgb(216,57,49)">'
            'Expert Call 精选</span></h2></column></excerpt></fragment>'
        )
        self.assertEqual(
            pipeline.resolve_anchor(excerpt),
            "doxcnVteWKe6Z00sUkUyVd50VPb",
        )

    def test_exact_title_or_pdf_link_is_duplicate(self):
        existing = (
            ANCHOR_CONTENT
            + '<callout id="c1"><p><b>已有标题</b></p><p>https://x.invalid/file/1</p></callout>'
        )
        self.assertEqual(pipeline.duplicate_reason(existing, "已有标题", "https://new.invalid"), "title")
        self.assertEqual(pipeline.duplicate_reason(existing, "别的标题", "https://x.invalid/file/1"), "pdf_href")
        self.assertFalse(pipeline.is_duplicate(existing, "已有", "https://x.invalid/file"))

    def test_plan_preserves_order_and_filters_duplicates(self):
        first = record(title="第一条", pdf_href="https://x.invalid/1")
        duplicate = record(title="已有标题", pdf_href="https://x.invalid/2")
        third = record(title="第三条", pdf_href="https://x.invalid/3")
        content = ANCHOR_CONTENT + '<callout id="old"><p><b>已有标题</b></p></callout>'
        planned = pipeline.plan_insertions([first, duplicate, third], content)
        self.assertEqual([row["title"] for row in planned], ["第一条", "第三条"])

    def test_missing_intel_projection_blocks_before_lark(self):
        def forbidden_lark(*_args):
            self.fail("missing intel_entries must block before any Lark call")

        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            source = Path(tmp) / "callouts.json"
            source.write_text(
                json.dumps(manifest(record(intel_entries=[])), ensure_ascii=False),
                encoding="utf-8",
            )
            result = pipeline.publish_manifest(
                source, paths, "20260822-143015", confirm=True, lark=forbidden_lark
            )
        self.assertEqual(result.status, "blocked")
        self.assertIn("intel_entries", result.missing[0])

    def test_no_confirmation_means_no_lark_write(self):
        calls = []

        def fake_lark(*args):
            calls.append(args)
            if "+update" in args:
                self.fail("dry-run must never call lark update")
            return {"ok": True, "data": {"document": {"content": ANCHOR_CONTENT}}}

        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            source = Path(tmp) / "callouts.json"
            source.write_text(json.dumps(manifest(record()), ensure_ascii=False), encoding="utf-8")
            result = pipeline.publish_manifest(source, paths, "20260822-143015", lark=fake_lark)
        self.assertEqual(result.status, "partial")
        self.assertTrue(calls)
        self.assertFalse(any("+update" in call for call in calls))
        self.assertEqual(result.data["written_block_ids"], [])

    def test_run_lark_uses_windows_cmd_shim_user_argv_and_shell_false(self):
        completed = MagicMock(returncode=0, stdout='{"ok": true}', stderr="")
        resolved = r"D:\\Users\\synthetic\\AppData\\Roaming\\npm\\lark-cli.CMD"
        with (
            patch("modules.expert_calls.pipeline.shutil.which", return_value=resolved),
            patch("modules.expert_calls.pipeline.subprocess.run", return_value=completed) as called,
        ):
            pipeline.run_lark("docs", "+fetch", "--doc", "synthetic")
        argv = called.call_args.args[0]
        self.assertEqual(argv[:5], ["cmd.exe", "/d", "/s", "/c", resolved])
        self.assertEqual(argv[-2:], ["--as", "user"])
        self.assertFalse(called.call_args.kwargs["shell"])

    def test_run_lark_blocks_when_cli_is_missing(self):
        with patch("modules.expert_calls.pipeline.shutil.which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "找不到 lark-cli"):
                pipeline.run_lark("docs", "+fetch")

    def test_confirmed_batch_refetches_and_chains_new_block_ids(self):
        calls = []
        content = ANCHOR_CONTENT
        inserted = 0

        def fake_lark(*args):
            nonlocal content, inserted
            calls.append(args)
            if "+update" in args:
                inserted += 1
                relative_xml = args[args.index("--content") + 1][1:]
                xml = (paths.root / relative_xml).read_text(encoding="utf-8")
                content += xml.replace("<callout ", f'<callout id="callout-{inserted}" ', 1)
                return {"ok": True, "data": {"result": "success"}}
            return {"ok": True, "data": {"document": {"content": content}}}

        rows = [
            record(title="第一条", pdf_href="https://x.invalid/1"),
            record(title="第二条", pdf_href="https://x.invalid/2"),
        ]
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            source = Path(tmp) / "callouts.json"
            source.write_text(json.dumps(manifest(*rows), ensure_ascii=False), encoding="utf-8")
            result = pipeline.publish_manifest(
                source, paths, "20260822-143015", confirm=True, lark=fake_lark
            )
            self.assertTrue(Path(result.data["intel_draft"]).is_file())
        updates = [call for call in calls if "+update" in call]
        anchors = [call[call.index("--block-id") + 1] for call in updates]
        self.assertEqual(anchors, ["grid-1680", "callout-1"])
        self.assertEqual(result.data["written_block_ids"], ["callout-1", "callout-2"])

    def test_mid_batch_failure_preserves_verified_block_ids(self):
        content = ANCHOR_CONTENT
        update_count = 0

        def fake_lark(*args):
            nonlocal content, update_count
            if "+update" in args:
                update_count += 1
                if update_count == 2:
                    raise RuntimeError("synthetic second write failure")
                relative_xml = args[args.index("--content") + 1][1:]
                xml = (paths.root / relative_xml).read_text(encoding="utf-8")
                content += xml.replace("<callout ", '<callout id="callout-1" ', 1)
                return {"ok": True, "data": {"result": "success"}}
            return {"ok": True, "data": {"document": {"content": content}}}

        rows = [
            record(title="第一条", pdf_href="https://x.invalid/1"),
            record(title="第二条", pdf_href="https://x.invalid/2"),
        ]
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            source = Path(tmp) / "callouts.json"
            source.write_text(json.dumps(manifest(*rows), ensure_ascii=False), encoding="utf-8")
            result = pipeline.publish_manifest(
                source, paths, "20260822-143015", confirm=True, lark=fake_lark
            )
            saved = json.loads(source.read_text(encoding="utf-8"))["publish_result"]
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.data["written_block_ids"], ["callout-1"])
        self.assertEqual(saved["written_block_ids"], ["callout-1"])


class TestRunIdAndIntelDraft(unittest.TestCase):
    def test_expert_calls_domain_uses_run_id_period(self):
        from workbench.domains import get

        domain = get("expert-calls")
        self.assertEqual(domain.period_kind, "run_id")
        self.assertTrue(domain.validate_period("20260822-143015"))
        self.assertFalse(domain.validate_period("2026-08-22"))

    def test_intel_draft_forces_channel_and_internal_without_commit(self):
        entry = {
            "kind": "action", "date": "2026-06-18", "title": "渠道调整",
            "body": "样本转化改善 12%。", "companies": ["ABNB"],
            "topics": ["distribution"], "media": "synthetic interview",
            "url": "https://example.invalid/source", "channel": "weekly",
            "sensitivity": "shareable",
        }
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "draft.json"
            pipeline.write_intelligence_draft(
                {"interviews": [record()], "intel_entries": [entry]}, target
            )
            draft = json.loads(target.read_text(encoding="utf-8"))
        self.assertFalse(draft["committed"])
        self.assertEqual(draft["entries"][0]["channel"], "expert-call")
        self.assertEqual(draft["entries"][0]["sensitivity"], "internal")


if __name__ == "__main__":
    unittest.main()
