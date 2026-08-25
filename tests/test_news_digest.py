"""news-digest 的回归测试。

钉住的点：

1. **期次键是 ASCII 且可排序**——旧仓用中文键，`2026年7月第3周` 与 `2026年10月第1周`
   字典序会排反，所以当初只能按文件顺序取「最近几期」。改 ASCII 后能按键排序，
   补录历史才不会把台账查重搞坏。
2. **五部分周报要被主动拦住**。只在文档里写「已停用」不够——半年后有人照旧模板写，
   工具默默接受，对外就发出去了。
3. **条目数必须等于来源表行数**。情报库靠同序配对拿日期和 URL，数不等就会挂错来源。
4. **携程当事方不进标题**。这是唯一对外交付物上最硬的编辑纪律。
5. **台账拒绝重复写入**，且补录历史走单独模式（查重方向反了）。
"""

from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from modules.news_digest import calendar_, digest, ledger, recall
from workbench.paths import Paths


def make_root(tmp: str) -> Paths:
    root = Path(tmp)
    (root / "workbench").mkdir()
    (root / "docs").mkdir()
    (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
    (root / "modules" / "news_digest").mkdir(parents=True)
    paths = Paths(root)
    paths.ensure_containers()
    return paths


GOOD = """# 📬 旅行行业新闻精选 | 2026年8月第2周

> 发布：2026/08/18（周二）
> 情报主周：2026/08/10–08/16

## 一、OTA/旅游行业新闻精选

> **本周概览**
> - 一条概览

**🎫 Airbnb 接入 Tripadvisor 体验，放弃纯自建路线**
Tripadvisor 宣布其旗下部分 tours、activities 与景点将于年内可在 Airbnb 预订，转向主流第三方库存。

**🌍 美国海外入境连续四月下滑，世界杯未能扭转**
美国商务部 I-94 数据显示，7 月海外入境约 300 万人次、同比 -7%，已是连续第四个月下滑。

## 二、新闻来源与数据说明

### 新闻来源

| 中文标题 | 英文原标题 | 媒体, 日期, URL |
| --- | --- | --- |
| Airbnb 接入 Tripadvisor 体验 | Airbnb Partners With Tripadvisor | Skift, 2026/08/11, https://skift.com/a/ |
| 美国海外入境连续四月下滑 | Overseas Travel Has Fallen | Skift, 2026/08/13, https://skift.com/b/ |
"""


class TestCalendar(unittest.TestCase):
    def test_key_is_ascii_and_sortable(self):
        keys = ["2026-10-W1", "2026-07-W3", "2026-08-W1"]
        self.assertEqual(
            sorted(keys), ["2026-07-W3", "2026-08-W1", "2026-10-W1"],
            "ASCII 键的字典序必须等于时间序——台账取「最近几期」依赖这个",
        )

    def test_label_roundtrip(self):
        self.assertEqual(calendar_.key_from_label("2026年8月第2周"), "2026-08-W2")
        self.assertEqual(calendar_.label_from_key("2026-08-W2"), "2026年8月第2周")

    def test_intelligence_week_is_nth_monday_week(self):
        """期次 = 当月第 N 个周一所在自然周。2026 年 8 月第一个周一是 8/3。"""
        monday, sunday = calendar_.intelligence_week("2026-08-W2")
        self.assertEqual((monday, sunday), (date(2026, 8, 10), date(2026, 8, 16)))

    def test_publish_is_tuesday_after(self):
        self.assertEqual(calendar_.publish_date("2026-08-W2"), date(2026, 8, 18))

    def test_week_that_does_not_exist_is_rejected(self):
        """2026 年 9 月只有 4 个周一。"""
        with self.assertRaises(calendar_.PeriodError):
            calendar_.intelligence_week("2026-09-W5")

    def test_key_from_monday_crosses_month_by_monday(self):
        """周一落在几月就计入几月。2026-08-31 是周一 → 8 月第 5 周。"""
        self.assertEqual(calendar_.key_from_monday(date(2026, 8, 31)), "2026-08-W5")

    def test_chinese_key_is_rejected(self):
        with self.assertRaises(calendar_.PeriodError):
            calendar_.parse_key("2026年8月第2周")


class TestDigestReview(unittest.TestCase):
    def test_good_digest_passes_clean(self):
        result = digest.review(GOOD, expect_period="2026-08-W2")
        self.assertTrue(result.ok)
        self.assertEqual(result.findings, [], "干净的稿子不该有任何提醒——假警告会让人开始忽略这一栏")
        self.assertEqual(len(result.items), 2)

    def test_five_part_skeleton_is_blocked(self):
        text = GOOD + "\n## 三、卖方行业跟踪\n\n正文\n"
        result = digest.review(text)
        self.assertFalse(result.ok)
        codes = [f.code for f in result.errors]
        self.assertIn("five-part-deprecated", codes)

    def test_item_and_source_count_must_match(self):
        text = GOOD.replace(
            "| 美国海外入境连续四月下滑 | Overseas Travel Has Fallen "
            "| Skift, 2026/08/13, https://skift.com/b/ |\n",
            "",
        )
        result = digest.review(text)
        self.assertIn("item-source-mismatch", [f.code for f in result.errors])

    def test_tcom_in_item_title_is_an_error(self):
        text = GOOD.replace(
            "**🎫 Airbnb 接入 Tripadvisor 体验，放弃纯自建路线**",
            "**🎫 携程上线新的国际机票产品**",
        )
        result = digest.review(text)
        self.assertIn("tcom-as-subject", [f.code for f in result.errors])

    def test_tcom_in_body_is_allowed(self):
        """写 so-what 时提到对携程的影响是允许的，也是应该的。"""
        text = GOOD.replace(
            "转向主流第三方库存。", "转向主流第三方库存；对携程的体验品类是直接对标。"
        )
        self.assertNotIn("tcom-as-subject", [f.code for f in digest.review(text).findings])

    def test_period_mismatch_is_caught(self):
        result = digest.review(GOOD, expect_period="2026-08-W1")
        self.assertIn("period-mismatch", [f.code for f in result.errors])

    def test_wrong_intelligence_week_line_warns(self):
        text = GOOD.replace("情报主周：2026/08/10–08/16", "情报主周：2026/08/03–08/09")
        codes = [f.code for f in digest.review(text).findings]
        self.assertIn("week-mismatch", codes)

    def test_inline_link_in_body_warns(self):
        text = GOOD.replace(
            "转向主流第三方库存。", "转向主流第三方库存，详见[原文](https://skift.com/a/)。"
        )
        self.assertIn("inline-link", [f.code for f in digest.review(text).findings])

    def test_missing_heading_is_an_error(self):
        result = digest.review(GOOD.replace("# 📬 旅行行业新闻精选 | 2026年8月第2周", "# 随便写的标题"))
        self.assertIn("heading-missing", [f.code for f in result.errors])

    def test_deliverable_name_uses_chinese_label(self):
        """目录名用 ASCII 键，文件名用中文标签——交付给人的东西中文才对。"""
        self.assertEqual(
            digest.deliverable_name("2026-08-W2"), "旅行行业新闻精选-2026年8月第2周.md"
        )


class TestLedger(unittest.TestCase):
    def _items(self, *titles, url_prefix="https://skift.com/"):
        return [
            {"title": t, "url": f"{url_prefix}{i}", "date": "2026-08-11", "source": "Skift"}
            for i, t in enumerate(titles, 1)
        ]

    def test_url_normalization_ignores_tracking(self):
        self.assertEqual(
            ledger.normalize_url("https://WWW.Skift.com/a/b/?utm_source=x&id=7"),
            "skift.com/a/b?id=7",
        )

    def test_duplicate_is_refused_not_warned(self):
        """登记是「以后据此判重」的动作。登进一条重复的，下一期就查不出来了。"""
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            ledger.add(paths, "2026-08-W1", self._items("Airbnb 接入 Tripadvisor 体验"))
            outcome = ledger.add(paths, "2026-08-W2", self._items("Airbnb 接入 Tripadvisor 体验"))
            self.assertEqual(len(outcome.blocked), 1)
            self.assertEqual(outcome.written, [])

    def test_force_requires_a_reason(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            with self.assertRaises(ledger.LedgerError):
                ledger.add(paths, "2026-08-W2", self._items("x"), force=True, reason="  ")

    def test_force_records_the_reason_in_the_ledger(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            ledger.add(paths, "2026-08-W1", self._items("Booking 合并 B2B 单元"))
            ledger.add(paths, "2026-08-W2", self._items("Booking 合并 B2B 单元"),
                       force=True, reason="实质跟进：补上人事与技术路线")
            rows = ledger.load(paths)
            self.assertIn("实质跟进", rows[-1]["forced_reason"])

    def test_backfill_skips_the_inverted_dedupe_check(self):
        """补录的期次比台账已有的都早，判重方向反了——实测 10 条里 7 条命中后续跟进报道。"""
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            ledger.add(paths, "2026-08-W1", self._items("Google 垂直搜索公平性仍受关注"))
            outcome = ledger.add(
                paths, "2026-07-W3", self._items("Google 垂直搜索公平分发再受关注"),
                backfill=True,
            )
            self.assertEqual(len(outcome.written), 1)
            self.assertTrue(ledger.load(paths)[-1]["backfilled"])
            self.assertNotIn("forced_reason", ledger.load(paths)[-1],
                             "补录历史与强收重复稿是两件事，不共用一个字段")

    def test_recent_uses_period_order_not_file_order(self):
        """补录会把早期次追加到文件末尾。按文件顺序取「最近 N 期」会把它当成最新。"""
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            # 标题必须彼此差别足够大，否则会被查重正确地拦下来，测不到本条要测的东西
            ledger.add(paths, "2026-08-W1",
                       self._items("Hilton 下调加盟费", url_prefix="https://x.com/w1/"))
            ledger.add(paths, "2026-08-W2",
                       self._items("TUI 三季度利润下滑", url_prefix="https://x.com/w2/"))
            ledger.add(paths, "2026-06-W4",
                       self._items("Wyndham 调整经济型组合", url_prefix="https://x.com/old/"),
                       backfill=True)
            kept = {ledger.row_period(r) for r in ledger.recent(ledger.load(paths), 2)}
            self.assertEqual(kept, {"2026-08-W1", "2026-08-W2"})

    def test_legacy_chinese_week_field_is_still_readable(self):
        """旧仓那 31 条不改写，让 git 历史里的记录保持可核对。"""
        self.assertEqual(ledger.row_period({"week": "2026年7月第1周"}), "2026-07-W1")
        self.assertEqual(ledger.row_period({"period": "2026-07-W1"}), "2026-07-W1")

    def test_broken_line_names_its_line_number(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            ledger.add(paths, "2026-08-W2", self._items("x"))
            path = ledger.ledger_path(paths)
            path.write_text(path.read_text(encoding="utf-8") + "{oops}\n", encoding="utf-8")
            with self.assertRaises(ledger.LedgerError) as caught:
                ledger.load(paths)
            self.assertIn("第 2 行", str(caught.exception))

    def test_ledger_is_written_with_lf(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            ledger.add(paths, "2026-08-W2", self._items("a", "b"))
            self.assertNotIn(b"\r\n", ledger.ledger_path(paths).read_bytes())

    def test_missing_url_warns_but_does_not_block(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            outcome = ledger.add(paths, "2026-08-W2", [{"title": "没有链接的一条", "url": ""}])
            self.assertEqual(len(outcome.written), 1)
            self.assertEqual(outcome.no_url, ["没有链接的一条"])


class TestRecall(unittest.TestCase):
    def test_in_scope_uses_category_terms_not_company_names(self):
        """写死公司名会漏掉「新玩家进场」这类最该看到的新闻。"""
        scoped, terms = recall.in_scope("某不知名公司拿下酒店渠道费独家结算")
        self.assertTrue(scoped)
        self.assertIn("酒店", terms)

    def test_out_of_scope_is_marked_not_dropped(self):
        scoped, terms = recall.in_scope("某新能源车企发布财报")
        self.assertFalse(scoped)
        self.assertEqual(terms, [])

    def test_window_filter_drops_undated_by_default(self):
        """无日期的留着会让「本周新闻」混进半年前的稿子，成稿阶段发现不了。"""
        rows = [{"title": "a", "date": ""}, {"title": "b", "date": "2026/08/12"}]
        self.assertEqual(
            [r["title"] for r in recall.filter_by_window(rows, "2026-08-10", "2026-08-16")],
            ["b"],
        )
        self.assertEqual(
            len(recall.filter_by_window(rows, "2026-08-10", "2026-08-16", keep_undated=True)), 2
        )

    def test_window_filter_accepts_both_date_separators(self):
        rows = [{"title": "a", "date": "2026-08-12"}, {"title": "b", "date": "2026/08/12"}]
        self.assertEqual(len(recall.filter_by_window(rows, "2026-08-10", "2026-08-16")), 2)

    def test_supplement_queries_are_not_executed_here(self):
        """exa / tavily 是 Agent 侧工具。这个模块一行都不该调用它们。"""
        source = Path(recall.__file__).read_text(encoding="utf-8")
        for tool in ("exa_search", "tavily_search", "web_search"):
            self.assertNotIn(f"{tool}(", source)
        self.assertTrue(recall.SUPPLEMENT_QUERIES, "但清单本身要在，Agent 每期照它跑")


if __name__ == "__main__":
    unittest.main()
