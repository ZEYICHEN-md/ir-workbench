"""新闻精选自动考卷：夹具拦截、卷面齐全、第一期能跑。"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from modules.news_digest import digest, recall
from modules.news_digest.exam import PAPER_IDS, PAPERS_DIR
from modules.news_digest.exam.harness import run_search
from modules.news_digest.exam.loader import load_paper
from workbench.paths import Paths

ROOT = Path(__file__).resolve().parents[1]


class TestExamPapers(unittest.TestCase):
    def test_four_papers_are_self_contained(self):
        for paper_id in PAPER_IDS:
            paper = load_paper(paper_id)
            self.assertTrue((PAPERS_DIR / paper_id / "task.md").is_file())
            self.assertTrue((PAPERS_DIR / paper_id / "rubric.md").is_file())
            self.assertEqual(paper.period, "2026-10-W1")
            self.assertIn("2026-10-14", paper.clock)

    def test_human_draft_passes_structural_validate(self):
        path = PAPERS_DIR / "nd-trunk-pending-publish" / "fixtures" / "human-draft.md"
        result = digest.review_file(path, expect_period="2026-10-W1")
        self.assertTrue(result.ok, [f.message for f in result.errors])

    def test_bad_draft_fails_expected_codes(self):
        path = PAPERS_DIR / "nd-resilience-blocked" / "fixtures" / "bad-human-draft.md"
        result = digest.review_file(path, expect_period="2026-10-W1")
        codes = {f.code for f in result.errors}
        for expected in ("tcom-as-subject", "five-part-deprecated", "item-source-mismatch"):
            self.assertIn(expected, codes, codes)


class TestFixtureIntercept(unittest.TestCase):
    def test_recall_fixture_does_not_hit_network(self):
        fixture = PAPERS_DIR / "nd-trunk-pending-publish" / "fixtures" / "news-recall-2026-10-W1.json"
        previous = os.environ.get("IR_NEWS_RECALL_FIXTURE")
        os.environ["IR_NEWS_RECALL_FIXTURE"] = str(fixture)
        try:
            with patch(
                "modules.news_digest.recall.fetch_feed",
                side_effect=AssertionError("live RSS must not run"),
            ):
                rows, problems = recall.gather(since="2026-10-05", until="2026-10-11")
            self.assertGreaterEqual(len(rows), 4)
            self.assertTrue(any("夹具" in item for item in problems))
            self.assertTrue(any("携程" in row["title"] for row in rows))
        finally:
            if previous is None:
                os.environ.pop("IR_NEWS_RECALL_FIXTURE", None)
            else:
                os.environ["IR_NEWS_RECALL_FIXTURE"] = previous

    def test_tavily_descriptive_replays_empty(self):
        paper = load_paper("nd-trunk-pending-publish")
        with TemporaryDirectory() as tmp:
            from modules.news_digest.exam.harness import ExamState

            state = ExamState(paper=paper, paths=Paths(Path(tmp)), source_root=ROOT)
            record = run_search(
                state, "tavily", "请找出本周在线旅游平台发生了什么大事", kind="A",
            )
            self.assertEqual(record.hit_count, 0)


class TestJudgeIsNotAlwaysPass(unittest.TestCase):
    def test_missing_validate_fails_resilience(self):
        from modules.news_digest.exam.judge import judge
        from modules.news_digest.exam.loader import load_paper

        paper = load_paper("nd-resilience-blocked")
        transcript = {
            "paper_id": paper.id,
            "commands": [{"argv": ["ir", "news", "plan"], "status": "success", "summary": "ok"}],
            "searches": [],
            "turns": [{"role": "candidate", "text": "看起来能发。【状态：success】", "four_state": "success"}],
            "digest_titles": [],
            "tcom_in_titles": False,
            "lark_invocations": [],
            "four_state_final": "success",
            "paths": {},
            "roles": {},
        }
        scorecard = judge(paper, transcript)
        self.assertFalse(scorecard["hard_pass"])
        self.assertEqual(scorecard["quality"], 0)


class TestExamRun(unittest.TestCase):
    def test_first_period_four_questions(self):
        from modules.news_digest.exam.runner import run_exam

        with TemporaryDirectory() as tmp:
            keep = Path(tmp) / "keep"
            # 沙箱写在仓库 scratch/ 下（gitignore），题目跑完可核对成绩单
            result = run_exam(Paths(ROOT), keep=str(keep))
            self.assertEqual(len(result.data["papers"]), 4, result.summary)
            by_id = {row["id"]: row for row in result.data["papers"]}
            self.assertEqual(set(by_id), set(PAPER_IDS))
            failed = [row["id"] for row in result.data["papers"] if not row["hard_pass"]]
            self.assertEqual(failed, [], result.summary)
            summary = json.loads((keep / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["hard_pass_count"], 4)


if __name__ == "__main__":
    unittest.main()
