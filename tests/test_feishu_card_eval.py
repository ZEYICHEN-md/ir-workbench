"""飞书周报卡片质量评估。

钉住三件不靠裁判模型的事：切句、隐喻排除名单、基线比较。
没有裁判密钥时不得出现信息量或隐喻率数字。
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from modules.news_digest import card_eval
from workbench.paths import Paths

FIXTURE_CARD = """# 周报 | 8月第4周

新闻情报主周 8/24–8/30。行业数据截至 8/22。

## 本周概览

华住 8 月 RevPAR 同比 +3.1%。这很重要。

| 指标 | 数值 |
| --- | --- |
| 酒店 RevPAR | +3.1% |

https://datamax.fun

[打开行业数据看板](https://datamax.fun)

**[华住上调指引](https://example.com/huazhu)**

<https://datamax.fun/week>

Skift 称 8 月 RevPAR +3.1% 已连续两周
注意!这仍是一句
国内酒店仍在修复。门票价格是 99 元！需求回来了吗？
正文里出现字段、运行、面对挑战、神经网络时也不计隐喻。
"""

EXPECTED_SENTENCES = [
    "新闻情报主周 8/24–8/30",
    "行业数据截至 8/22",
    "华住 8 月 RevPAR 同比 +3.1%",
    "这很重要",
    "Skift 称 8 月 RevPAR +3.1% 已连续两周",
    "注意!这仍是一句",
    "国内酒店仍在修复",
    "门票价格是 99 元",
    "需求回来了吗",
    "正文里出现字段、运行、面对挑战、神经网络时也不计隐喻",
]

#: 裁判若把排除项、空替换、文中不存在的词交回来，本地要丢掉。
JUDGE_PAYLOAD = {
    "fact_points": [
        "华住 8 月 RevPAR 同比 +3.1%",
        "行业数据截至 8/22",
        "门票价格是 99 元",
    ],
    "metaphors": [
        {"phrase": "字段", "plainer": "栏"},
        {"phrase": "运行", "plainer": "执行"},
        {"phrase": "面对挑战", "plainer": "遇到问题"},
        {"phrase": "神经网络", "plainer": "模型"},
        {"phrase": "「字段」", "plainer": "栏"},
        {"phrase": "仍在修复", "plainer": ""},
        {"phrase": "仍在修复", "plainer": "还在下降"},
        {"phrase": "不在文中的浪", "plainer": "增加"},
    ],
}


def make_root(tmp: str) -> Paths:
    root = Path(tmp)
    (root / "workbench").mkdir()
    (root / "docs").mkdir()
    (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
    (root / "modules" / "news_digest").mkdir(parents=True)
    paths = Paths(root)
    paths.ensure_containers()
    return paths


class TestSentenceSplit(unittest.TestCase):
    def test_fixture_drops_headings_tables_and_links(self):
        self.assertEqual(card_eval.split_sentences(FIXTURE_CARD), EXPECTED_SENTENCES)

    def test_halfwidth_punctuation_does_not_split(self):
        self.assertEqual(
            card_eval.split_sentences("注意!这仍是一句\nAsk? Still one. Sentence."),
            ["注意!这仍是一句", "Ask? Still one. Sentence."],
        )

    def test_heading_without_space_is_excluded(self):
        self.assertEqual(card_eval.split_sentences("#周报。\n正文一句。"), ["正文一句"])

    def test_prose_with_a_url_still_counts(self):
        self.assertEqual(
            card_eval.split_sentences("详见 https://datamax.fun。"),
            ["详见 https://datamax.fun"],
        )

    def test_pipe_row_without_edge_pipes_is_a_table(self):
        text = "指标 | 数值 | 备注\n正文一句。"
        self.assertEqual(card_eval.split_sentences(text), ["正文一句"])


class TestMetaphorExclusion(unittest.TestCase):
    def setUp(self):
        self.sentences = card_eval.split_sentences(FIXTURE_CARD)

    def test_exclusion_list_empty_plainer_and_missing_phrase(self):
        reasons = [
            card_eval.metaphor_rejection(item["phrase"], item["plainer"], self.sentences)
            for item in JUDGE_PAYLOAD["metaphors"]
        ]
        self.assertEqual(
            reasons,
            [
                "excluded",
                "excluded",
                "excluded",
                "excluded",
                "excluded",
                "no-plainer",
                None,
                "not-in-text",
            ],
        )

    def test_fixture_metrics_keep_one_metaphor(self):
        metrics = card_eval.metrics_for(self.sentences, JUDGE_PAYLOAD)
        self.assertEqual(metrics["信息量"], 3)
        self.assertEqual(metrics["metaphor_count"], 1)
        self.assertEqual(metrics["sentence_count"], 10)
        self.assertEqual(metrics["隐喻率"], 10.0)
        self.assertEqual(metrics["metaphors"], [{"phrase": "仍在修复", "plainer": "还在下降"}])
        self.assertNotIn("这很重要", metrics["fact_points"])

    def test_longer_phrase_is_not_excluded_by_substring(self):
        """排除名单按整词。更长的短语不因里面含有「面对挑战」被名单去掉。"""
        sentences = ["团队面对挑战的浪潮已经过去。"]
        reason = card_eval.metaphor_rejection("面对挑战的浪潮", "遇到困难", sentences)
        self.assertIsNone(reason)


class TestGateMath(unittest.TestCase):
    def test_fixture_against_baseline(self):
        current = card_eval.metrics_for(
            card_eval.split_sentences(FIXTURE_CARD), JUDGE_PAYLOAD
        )
        first = card_eval.decide_recommendation(None, current)
        self.assertEqual(first["recommendation"], "baseline")
        self.assertFalse(first["pending_confirm"])
        self.assertFalse(first["merged"])

        same = {
            "信息量": 3,
            "metaphor_count": 1,
            "sentence_count": 10,
        }
        pending = card_eval.decide_recommendation(same, current)
        self.assertEqual(pending["recommendation"], "pending-confirm")
        self.assertTrue(pending["pending_confirm"])
        self.assertFalse(pending["merged"])

        lower_info = dict(same, 信息量=4)
        rejected = card_eval.decide_recommendation(lower_info, current)
        self.assertEqual(rejected["recommendation"], "reject")
        self.assertIn("信息量下降", rejected["reasons"])
        self.assertFalse(rejected["merged"])

        higher_rate = dict(same, metaphor_count=0)
        rejected_rate = card_eval.decide_recommendation(higher_rate, current)
        self.assertEqual(rejected_rate["recommendation"], "reject")
        self.assertIn("隐喻率上升", rejected_rate["reasons"])
        self.assertFalse(rejected_rate["merged"])

    def test_equal_rate_with_different_sentence_counts_does_not_rise(self):
        baseline = {"信息量": 2, "metaphor_count": 1, "sentence_count": 3}
        current = {"信息量": 2, "metaphor_count": 2, "sentence_count": 6, "隐喻率": 33.33}
        decision = card_eval.decide_recommendation(baseline, current)
        self.assertEqual(decision["recommendation"], "pending-confirm")
        self.assertTrue(
            card_eval.rate_not_higher(current, baseline),
            "1/3 与 2/6 的隐喻率相同，不得判成上升",
        )

    def test_rate_display_rounds_half_up(self):
        self.assertEqual(card_eval.metaphor_rate_percent(2, 3), 66.67)
        self.assertEqual(card_eval.metaphor_rate_percent(1, 8), 12.5)


class TestCommand(unittest.TestCase):
    def test_names_are_ascii(self):
        self.assertEqual(card_eval.DRAFT_FILENAME, "feishu-card-draft.txt")
        self.assertEqual(card_eval.FINAL_FILENAME, "feishu-card-final.txt")
        self.assertTrue(card_eval.DRAFT_FILENAME.isascii())
        self.assertTrue(card_eval.FINAL_FILENAME.isascii())
        self.assertEqual(card_eval.SCOPE, "feishu-im-card")

    def test_blocked_without_key_saves_draft_and_invents_no_score(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            draft = Path(tmp) / "incoming.txt"
            draft.write_text(FIXTURE_CARD, encoding="utf-8")
            final = Path(tmp) / "pasted.txt"
            final.write_text("人改过的一句。\n", encoding="utf-8")
            args = SimpleNamespace(
                period="2026-08-W4",
                draft_file=str(draft),
                final_file=str(final),
                writer_model="writer-model",
            )
            with patch.dict(os.environ, {"IR_CARD_JUDGE_API_KEY": ""}, clear=False):
                result = card_eval.cmd_card_eval(args, paths)
            self.assertEqual(result.status, "blocked")
            self.assertIn("IR_CARD_JUDGE_API_KEY", result.summary)
            self.assertIn("IR_CARD_JUDGE_API_KEY", result.missing)
            self.assertIsNone(result.data["scores"])
            self.assertNotIn("信息量", result.data)
            self.assertNotRegex(result.summary, r"信息量 \d")
            self.assertNotRegex(result.summary, r"隐喻率 \d")
            saved = card_eval.draft_path(paths, "2026-08-W4")
            self.assertEqual(saved.read_text(encoding="utf-8").replace("\r\n", "\n"), FIXTURE_CARD)
            self.assertTrue(card_eval.final_path(paths, "2026-08-W4").is_file())
            self.assertFalse(card_eval.record_path(paths, "2026-08-W4").exists())

            args.final_file = None
            with patch.dict(os.environ, {"IR_CARD_JUDGE_API_KEY": ""}, clear=False):
                again = card_eval.cmd_card_eval(args, paths)
            self.assertEqual(again.status, "blocked")
            self.assertFalse(
                card_eval.final_path(paths, "2026-08-W4").exists(),
                "本次没有粘回稿，终稿文件不得留下",
            )

    def test_empty_final_does_not_delete_existing_final(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            draft = Path(tmp) / "incoming.txt"
            draft.write_text(FIXTURE_CARD, encoding="utf-8")
            final = Path(tmp) / "pasted.txt"
            final.write_text("人改过的一句。\n", encoding="utf-8")
            args = SimpleNamespace(
                period="2026-08-W4",
                draft_file=str(draft),
                final_file=str(final),
                writer_model="writer-model",
            )
            with patch.dict(os.environ, {"IR_CARD_JUDGE_API_KEY": ""}, clear=False):
                card_eval.cmd_card_eval(args, paths)
            empty = Path(tmp) / "empty.txt"
            empty.write_text("  \n", encoding="utf-8")
            args.final_file = str(empty)
            with patch.dict(os.environ, {"IR_CARD_JUDGE_API_KEY": ""}, clear=False):
                result = card_eval.cmd_card_eval(args, paths)
            self.assertEqual(result.status, "blocked")
            self.assertTrue(card_eval.final_path(paths, "2026-08-W4").is_file())

    def test_peers_path_is_refused(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            peers = Path(tmp) / "outputs" / "peers-model" / "card.txt"
            peers.parent.mkdir(parents=True)
            peers.write_text(FIXTURE_CARD, encoding="utf-8")
            args = SimpleNamespace(
                period="2026-08-W4",
                draft_file=str(peers),
                final_file=None,
                writer_model="writer-model",
            )
            result = card_eval.cmd_card_eval(args, paths)
            self.assertEqual(result.status, "blocked")
            self.assertIn("Peers", result.summary)
            self.assertFalse(card_eval.draft_path(paths, "2026-08-W4").exists())

    def test_same_writer_and_judge_does_not_call_api(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            draft = Path(tmp) / "incoming.txt"
            draft.write_text(FIXTURE_CARD, encoding="utf-8")
            args = SimpleNamespace(
                period="2026-08-W4",
                draft_file=str(draft),
                final_file=None,
                writer_model="gpt-4.1",
            )

            def fail_if_called(*_args, **_kwargs):
                raise AssertionError("模型相同时不得请求裁判")

            with patch.object(card_eval, "post_chat", fail_if_called):
                with patch.dict(
                    os.environ,
                    {"IR_CARD_JUDGE_API_KEY": "test-key", "IR_CARD_JUDGE_MODEL": "gpt-4.1"},
                    clear=False,
                ):
                    result = card_eval.cmd_card_eval(args, paths)
            self.assertEqual(result.status, "blocked")
            self.assertIsNone(result.data["scores"])
            self.assertFalse(card_eval.record_path(paths, "2026-08-W4").exists())
            self.assertTrue(card_eval.draft_path(paths, "2026-08-W4").is_file())

    def test_same_period_gate_and_other_period_is_its_own_baseline(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            calls = {"n": 0, "seen": ""}

            def fake_post(_key, _model, card_sentences):
                calls["n"] += 1
                calls["seen"] = card_sentences
                if calls["n"] == 1:
                    return JUDGE_PAYLOAD
                if calls["n"] == 2:
                    return {
                        "fact_points": ["华住 8 月 RevPAR 同比 +3.1%"],
                        "metaphors": [
                            {"phrase": "仍在修复", "plainer": "还在下降"},
                            {"phrase": "需求回来了", "plainer": "需求增加"},
                        ],
                    }
                return JUDGE_PAYLOAD

            draft = Path(tmp) / "incoming.txt"
            draft.write_text(FIXTURE_CARD, encoding="utf-8")
            final = Path(tmp) / "pasted.txt"
            final.write_text("只归档，不参与打分。\n", encoding="utf-8")
            env = {"IR_CARD_JUDGE_API_KEY": "test-key", "IR_CARD_JUDGE_MODEL": "judge-model"}

            def run(period, *, with_final):
                args = SimpleNamespace(
                    period=period,
                    draft_file=str(draft),
                    final_file=str(final) if with_final else None,
                    writer_model="writer-model",
                )
                with patch.object(card_eval, "post_chat", fake_post):
                    with patch.dict(os.environ, env, clear=False):
                        return card_eval.cmd_card_eval(args, paths)

            first = run("2026-08-W4", with_final=True)
            self.assertEqual(first.status, "success")
            self.assertEqual(first.data["recommendation"], "baseline")
            self.assertEqual(first.data["scores"]["信息量"], 3)
            self.assertEqual(first.data["scores"]["隐喻率"], 10.0)
            self.assertFalse(first.data["merged"])
            self.assertNotIn("8月第4周", calls["seen"])
            self.assertNotIn("https://datamax.fun", calls["seen"])
            self.assertIn("仍在修复", calls["seen"])
            record = json.loads(
                card_eval.record_path(paths, "2026-08-W4").read_text(encoding="utf-8")
            )
            self.assertFalse(record["merged"])
            self.assertFalse(record["runs"][0]["final_scored"])
            self.assertEqual(record["runs"][0]["final"], card_eval.FINAL_FILENAME)
            self.assertNotIn("test-key", json.dumps(record))
            self.assertTrue(card_eval.final_path(paths, "2026-08-W4").is_file())

            second = run("2026-08-W4", with_final=False)
            self.assertEqual(second.status, "partial")
            self.assertEqual(second.data["recommendation"], "reject")
            self.assertFalse(second.data["merged"])
            self.assertEqual(second.data["baseline"]["信息量"], 3)
            self.assertFalse(card_eval.final_path(paths, "2026-08-W4").exists())
            record = json.loads(
                card_eval.record_path(paths, "2026-08-W4").read_text(encoding="utf-8")
            )
            self.assertEqual(record["baseline"]["信息量"], 3)
            self.assertEqual(record["baseline"]["隐喻率"], 10.0)
            self.assertEqual(len(record["runs"]), 2)
            self.assertIn("信息量下降", record["runs"][1]["reasons"])

            other = run("2026-08-W3", with_final=False)
            self.assertEqual(other.data["recommendation"], "baseline")
            self.assertEqual(other.data["scores"]["信息量"], 3)
            other_record = json.loads(
                card_eval.record_path(paths, "2026-08-W3").read_text(encoding="utf-8")
            )
            self.assertEqual(other_record["period"], "2026-08-W3")
            self.assertEqual(len(other_record["runs"]), 1)

    def test_pending_confirm_does_not_merge(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            draft = Path(tmp) / "incoming.txt"
            draft.write_text(FIXTURE_CARD, encoding="utf-8")
            env = {"IR_CARD_JUDGE_API_KEY": "test-key", "IR_CARD_JUDGE_MODEL": "judge-model"}

            def fake_post(_key, _model, _text):
                return JUDGE_PAYLOAD

            def run():
                args = SimpleNamespace(
                    period="2026-08-W4",
                    draft_file=str(draft),
                    final_file=None,
                    writer_model="writer-model",
                )
                with patch.object(card_eval, "post_chat", fake_post):
                    with patch.dict(os.environ, env, clear=False):
                        return card_eval.cmd_card_eval(args, paths)

            self.assertEqual(run().data["recommendation"], "baseline")
            second = run()
            self.assertEqual(second.status, "partial")
            self.assertEqual(second.data["recommendation"], "pending-confirm")
            self.assertFalse(second.data["merged"])
            self.assertTrue(any("不合并" in step for step in second.next_steps))

    def test_module_does_not_send_or_merge(self):
        source = Path(card_eval.__file__).read_text(encoding="utf-8")
        self.assertNotIn("lark-cli", source)
        self.assertNotIn("open-apis", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("modules.peers_model", source)
        self.assertNotRegex(source, r"\bgit merge\b")


if __name__ == "__main__":
    unittest.main()
