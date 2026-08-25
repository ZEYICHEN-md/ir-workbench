"""「有什么在等我」的测试。

这套东西是为了修一次真实失误：航空 7 月 dry-run 跑完后使用者回「OK」，门禁正确地
没放行，但**之后十几轮没人再提起**，使用者以为已经写入。两周后线上月度航空还断在
6 月，是偶然问起才发现。

门禁停住是对的，缺的是出口。所以要钉住三件事：
1. 卡住的（blocked/failed，以及无门禁的 running）必须报，多久以前的都报；
2. 等人说话的必须给出**具体措辞**——只说「须明确确认」，人看完仍不知道该说什么；
3. 同一个步骤只归一类。有门禁的 running 归「等你说话」而不是「卡住」，否则
   `ir status` 顶上会写「有 1 处卡住」，把「说句话就能继续」误报成故障。
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench import pending, status
from workbench.paths import Paths


def make_root(tmp: str) -> Paths:
    root = Path(tmp)
    (root / "workbench").mkdir()
    (root / "docs" / "adr").mkdir(parents=True)
    (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
    (root / "router").mkdir()
    (root / "conventions").mkdir()
    # 只让 industry-data 与 aviation-monthly 算「已迁入」
    for name in ("industry_data", "aviation_monthly"):
        (root / "modules" / name).mkdir(parents=True)
    paths = Paths(root)
    paths.ensure_containers()
    return paths


def seed(paths: Paths, domain: str, period: str, states: dict[str, str], notes=None):
    """按域与周期写一份 manifest。"""
    from workbench.manifest import Manifest

    order = list(states)
    manifest = Manifest(paths, domain, period)
    manifest.ensure_steps(order)
    for key, state in states.items():
        manifest.set_step(key, state, (notes or {}).get(key))
    return manifest


class TestCollect(unittest.TestCase):
    def test_blocked_step_is_reported(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            seed(paths, "aviation-monthly", "202607",
                 {"dry-run": "done", "commit": "blocked", "resync": "pending"},
                 notes={"commit": "校验未过"})
            waiting = pending.collect(paths)
            stuck = [w for w in waiting if w.kind == "卡住"]
            self.assertEqual(len(stuck), 1)
            self.assertEqual(stuck[0].step, "commit")
            self.assertIn("校验未过", stuck[0].describe())

    def test_running_counts_as_stuck(self):
        """running = 开始了但没收尾，比 pending 更需要人看一眼。"""
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            seed(paths, "industry-data", "2026-08-15",
                 {"merge": "done", "dashboard": "running", "insights": "pending",
                  "feishu": "pending", "publish": "pending"})
            kinds = {w.step: w.kind for w in pending.collect(paths)}
            self.assertEqual(kinds.get("dashboard"), "卡住")

    def test_next_step_with_gate_gives_exact_phrase(self):
        """dry-run 做完、commit 在等——必须告诉人说「写入」，不能只说「须确认」。"""
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            seed(paths, "aviation-monthly", "202607",
                 {"dry-run": "done", "commit": "running", "resync": "pending"})
            waiting = [w for w in pending.collect(paths) if w.step == "commit"]
            self.assertTrue(waiting)
            self.assertIn("写入", waiting[0].describe())

    def test_unstarted_gated_step_asks_for_the_starting_phrase(self):
        """还没开始的步骤，措辞必须是「让它开始」的话。

        洞察那一步的措辞原本写成「确认这些洞察」，可草稿还没生成——人看到这句只会
        莫名其妙。正确的是「刷新洞察」：说完之后 Agent 先出草稿，中文确认在那一步
        自己的输出里再提。
        """
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            seed(paths, "industry-data", "2026-08-15",
                 {"merge": "done", "dashboard": "done", "insights": "pending",
                  "feishu": "pending", "publish": "pending"})
            waiting = [w for w in pending.collect(paths) if w.step == "insights"]
            self.assertTrue(waiting)
            self.assertEqual(waiting[0].kind, "等确认")
            self.assertIn("刷新洞察", waiting[0].describe())
            self.assertNotIn("确认这些洞察", waiting[0].describe())

    def test_gated_running_step_is_not_reported_as_stuck(self):
        """有门禁的 running 是「在等你说话」，不是故障。

        两者都报会让 `ir status` 顶上写「有 1 处卡住」——人会去查日志，
        而他其实只需要说一句「写入」。
        """
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            seed(paths, "aviation-monthly", "202607",
                 {"dry-run": "done", "commit": "running", "resync": "pending"})
            kinds = [w.kind for w in pending.collect(paths) if w.step == "commit"]
            self.assertEqual(kinds, ["等确认"])

    def test_old_period_gated_running_still_reports_stuck(self):
        """航空 7 月没写入、8 月已开期时，7 月那一步不能因为「不是最新期」就消失。"""
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            seed(paths, "aviation-monthly", "202607",
                 {"dry-run": "done", "commit": "running", "resync": "pending"})
            seed(paths, "aviation-monthly", "202608",
                 {"dry-run": "done", "commit": "done", "resync": "done"})
            stuck = [w for w in pending.collect(paths) if w.kind == "卡住"]
            self.assertEqual([(w.period, w.step) for w in stuck], [("202607", "commit")])

    def test_blocked_next_step_is_stuck_not_awaiting(self):
        """blocked 的下一步不算在等人说话——先解决它，别让人以为说句话就行。"""
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            seed(paths, "aviation-monthly", "202607",
                 {"dry-run": "done", "commit": "blocked", "resync": "pending"})
            kinds = [w.kind for w in pending.collect(paths) if w.step == "commit"]
            self.assertEqual(kinds, ["卡住"])

    def test_step_without_gate_is_not_reported(self):
        """没有门禁的下一步不需要人说话，不该出现在这张表里。"""
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            seed(paths, "industry-data", "2026-08-15",
                 {"merge": "done", "dashboard": "pending", "insights": "pending",
                  "feishu": "pending", "publish": "pending"})
            steps = {w.step for w in pending.collect(paths)}
            self.assertNotIn("dashboard", steps, "dashboard 无门禁，不该报")

    def test_only_latest_period_reports_awaiting(self):
        """旧期次的未完成步骤属于历史，一直报会变噪音。"""
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            done_all = {"merge": "done", "dashboard": "done", "insights": "done",
                        "feishu": "done", "publish": "done"}
            seed(paths, "industry-data", "2026-08-08",
                 {**done_all, "publish": "pending"})   # 旧期次还差 publish
            seed(paths, "industry-data", "2026-08-15", done_all)
            periods = {w.period for w in pending.collect(paths)}
            self.assertNotIn("2026-08-08", periods)

    def test_old_period_still_reports_blocked(self):
        """但旧期次真卡住了要报——那是没解决的问题，不是历史。"""
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            seed(paths, "industry-data", "2026-08-08",
                 {"merge": "blocked", "dashboard": "pending", "insights": "pending",
                  "feishu": "pending", "publish": "pending"})
            seed(paths, "industry-data", "2026-08-15",
                 {"merge": "done", "dashboard": "done", "insights": "skipped",
                  "feishu": "skipped", "publish": "done"})
            stuck = [w for w in pending.collect(paths) if w.kind == "卡住"]
            self.assertEqual([w.period for w in stuck], ["2026-08-08"])

    def test_nothing_waiting_when_all_settled(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            seed(paths, "aviation-monthly", "202607",
                 {"dry-run": "done", "commit": "done", "resync": "done"})
            self.assertEqual(pending.collect(paths), [])

    def test_domain_without_runs_is_skipped(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            self.assertEqual(pending.collect(paths), [])


class TestStatusIntegration(unittest.TestCase):
    def test_blocked_dominates_summary(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            seed(paths, "aviation-monthly", "202607",
                 {"dry-run": "done", "commit": "blocked", "resync": "pending"})
            result = status.run(paths)
            self.assertIn("卡住", result.summary)
            self.assertEqual(result.status, "partial")

    def test_awaiting_confirmation_surfaces_in_summary_and_next_steps(self):
        """这是整件事的目的：一眼看到有事在等我，且知道要说什么。"""
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            seed(paths, "aviation-monthly", "202607",
                 {"dry-run": "done", "commit": "running", "resync": "pending"})
            result = status.run(paths)
            self.assertIn("等你说话", result.summary)
            self.assertTrue(any("写入" in s for s in result.next_steps))
            self.assertTrue(any("写入" in w for w in result.warnings))

    def test_waiting_rows_come_first(self):
        """排在各域状态之前——沉到底部就等于没有。"""
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            seed(paths, "aviation-monthly", "202607",
                 {"dry-run": "done", "commit": "running", "resync": "pending"})
            result = status.run(paths)
            self.assertIn(result.checks[0]["name"], {"卡住", "等你确认"})

    def test_json_carries_waiting_for_agents(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            seed(paths, "aviation-monthly", "202607",
                 {"dry-run": "done", "commit": "running", "resync": "pending"})
            data = status.run(paths).data
            self.assertTrue(any(w["step"] == "commit" and w["phrase"] == "写入"
                                for w in data["waiting"]))


if __name__ == "__main__":
    unittest.main()
