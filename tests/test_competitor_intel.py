"""竞对情报库的回归测试。

钉住的都是**真出过问题或真会出问题**的点，不为覆盖率写测试：

1. `TRIP` 是 Tripadvisor 的合法键，`Trip` 才是禁用写法 —— 不区分大小写会让自动打标
   产出的键被自己的防歧义规则拒掉（实测 39 条里第 32 条因此被拒）。
2. 配对可信度不能用 `SequenceMatcher.ratio()` —— 来源表标题是正文标题的刻意缩写，
   按总长归一会把四条正确配对判成疑似错位（实测四条假警告）。
3. 幂等靠确定性 id —— 每周沉淀会重跑，同一条不能入两次。
4. 主题必须受控 —— 自由造词会让跨公司横切失效，这是词表存在的唯一理由。
5. TCOM 一沾就是内部级 —— 这条是对外交付物的防线（ADR 0002 §9）。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from modules.competitor_intel import backfill, profiles, query, vocab
from modules.competitor_intel.entry import Entry, EntryError, make_id, normalize, normalize_url
from modules.competitor_intel.store import Store
from workbench.paths import Paths


def make_root(tmp: str) -> Paths:
    root = Path(tmp)
    (root / "workbench").mkdir()
    (root / "docs").mkdir()
    (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
    paths = Paths(root)
    paths.ensure_containers()
    return paths


def action(**over) -> Entry:
    base = dict(
        kind="action",
        date="2026-08-12",
        title="某公司做了某事",
        body="正文一段，含具体数字 12%。",
        companies=["ABNB"],
        topics=["distribution"],
        media="Skift",
        url="https://skift.com/2026/08/12/example/",
    )
    base.update(over)
    return Entry(**base)


class TestVocab(unittest.TestCase):
    def test_uppercase_trip_is_tripadvisor(self):
        """ADR 0002 §2 把 TRIP 钉给 Tripadvisor。它必须是合法键。"""
        self.assertEqual(vocab.resolve_company("TRIP"), "TRIP")
        self.assertEqual(vocab.resolve_company("tripadvisor"), "TRIP")

    def test_bare_trip_is_rejected(self):
        """`Trip` 两边都像，禁止用它指代任何一方。"""
        for form in ("Trip", "trip", "tRiP"):
            with self.assertRaises(vocab.VocabError) as caught:
                vocab.resolve_company(form)
            self.assertIn("TCOM", str(caught.exception), "错误消息要告诉人该用哪个键")

    def test_tcom_is_ctrip(self):
        self.assertEqual(vocab.resolve_company("携程"), "TCOM")
        self.assertEqual(vocab.resolve_company("Trip.com"), "TCOM")

    def test_unknown_company_is_not_an_error(self):
        """不认识的公司交给其他桶登记，不是错误——否则这条情报根本进不了库。"""
        self.assertIsNone(vocab.resolve_company("SomeNewStartup"))
        self.assertEqual(vocab.normalize_other("Get Your Guide"), "GET-YOUR-GUIDE")

    def test_unknown_topic_is_rejected_with_options(self):
        with self.assertRaises(vocab.VocabError) as caught:
            vocab.resolve_topic("随手造的主题")
        message = str(caught.exception)
        self.assertIn("distribution", message, "拒绝时要把可选值摆出来")
        self.assertIn("vocab.py", message, "要说清改哪儿才能加新主题")

    def test_seeded_others_stay_in_other_tier(self):
        """种子只为让打标认得出来，不改变覆盖承诺——不能悄悄变成第三层受控名单。"""
        self.assertEqual(vocab.tier_of("GOOGLE"), "other")
        self.assertEqual(vocab.tier_of("ABNB"), "profiled")
        self.assertEqual(vocab.tier_of("HTHT"), "indexed")
        self.assertNotIn("GOOGLE", vocab.PROFILED_KEYS + vocab.INDEXED_KEYS)


class TestEntry(unittest.TestCase):
    def test_url_normalization_strips_tracking(self):
        left = normalize_url("https://Skift.com/a/b/?utm_source=x&id=7#top")
        self.assertEqual(left, "https://skift.com/a/b?id=7")

    def test_id_is_stable_across_title_rewrites(self):
        """「延续上期」类条目标题会改写，URL 不会。用 URL 才不会变成两条。"""
        url = "https://skift.com/2026/08/10/x/"
        self.assertEqual(
            make_id("2026-08-10", url, "原标题"),
            make_id("2026-08-10", url + "?utm_source=news", "改写后的标题"),
        )

    def test_statement_requires_quote_and_location(self):
        with self.assertRaises(EntryError) as caught:
            normalize(action(kind="statement", quote="AEO 不是 GEO"))
        self.assertIn("quote_where", str(caught.exception))

    def test_action_requires_a_checkable_source(self):
        with self.assertRaises(EntryError):
            normalize(action(url=None, media=None))

    def test_topic_is_mandatory(self):
        """没主题的条目查不到，等于没入库。"""
        with self.assertRaises(EntryError):
            normalize(action(topics=[]))

    def test_macro_entry_needs_no_company(self):
        """宏观与政策类没有公司归属，schema 不得强制非空（ADR 0002 §6）。"""
        item, _ = normalize(action(companies=[], mentions=[], topics=["policy-macro"]))
        self.assertEqual(item.companies, [])

    def test_tcom_forces_internal_sensitivity(self):
        item, _ = normalize(action(companies=["ABNB"], mentions=["携程"]))
        self.assertEqual(item.mentions, ["TCOM"])
        self.assertEqual(item.sensitivity, "internal")

    def test_lead_wins_over_mention_for_same_company(self):
        """同一家既主角又提及会让档案与索引各记一次。"""
        item, _ = normalize(action(companies=["ABNB"], mentions=["Airbnb"]))
        self.assertEqual((item.companies, item.mentions), (["ABNB"], []))

    def test_unregistered_company_is_reported_not_dropped(self):
        item, unregistered = normalize(action(companies=["SomeNewStartup"]))
        self.assertEqual(item.companies, ["SOMENEWSTARTUP"])
        self.assertEqual(unregistered, ["SomeNewStartup"])


class TestStore(unittest.TestCase):
    def test_add_is_idempotent(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            store = Store(paths)
            self.assertEqual(len(store.add([action()], commit=True).added), 1)
            again = store.add([action(title="标题改了")], commit=True)
            self.assertEqual((len(again.added), len(again.skipped)), (0, 1))
            self.assertEqual(len(store.load()), 1)

    def test_dry_run_has_no_side_effects(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            store = Store(paths)
            store.add([action(companies=["BrandNewCo"])], commit=False)
            self.assertFalse(store.entries_file.exists())
            self.assertFalse(store.registry_file.exists(), "dry-run 不该登记新公司")

    def test_rejected_entries_do_not_block_the_rest(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            outcome = Store(paths).add([action(), action(topics=[], url="https://x.com/2")], commit=True)
            self.assertEqual((len(outcome.added), len(outcome.rejected)), (1, 1))
            self.assertEqual(outcome.rejected[0][0], 2, "要报出是第几条")

    def test_broken_line_names_its_line_number(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            store = Store(paths)
            store.add([action()], commit=True)
            with open(store.entries_file, "a", encoding="utf-8", newline="\n") as handle:
                handle.write("{not json}\n")
            with self.assertRaises(EntryError) as caught:
                store.load()
            self.assertIn("第 2 行", str(caught.exception))

    def test_replace_keeps_ids_so_add_stays_idempotent(self):
        """改标签走整份重写。重写后再追加同一条仍要被跳过，否则「事后可改」会带来重复。"""
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            store = Store(paths)
            store.add([action()], commit=True)
            first = store.load()[0]
            store.replace([Entry.from_dict({**first.to_dict(), "topics": ["b2b"]})])
            self.assertEqual(store.load()[0].topics, ["b2b"])
            self.assertEqual(store.load()[0].id, first.id)
            again = store.add([action()], commit=True)
            self.assertEqual((len(again.added), len(again.skipped)), (0, 1))

    def test_deposit_closes_the_news_digest_step_too(self):
        """「写完自动沉淀」是一个动作，跨两个域。不联动就会在汇总里留一条假待办。

        实测过：情报库这边 2/2 完成、条目在库，news-digest 那边的「沉淀进竞对情报库」
        仍停在待办，于是汇总报「需要你说『沉淀这期新闻』」——而那件事刚做完。
        """
        from modules.competitor_intel import cli as intel_cli
        from modules.news_digest import steps as news_steps

        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            (paths.root / "modules" / "news_digest").mkdir(parents=True, exist_ok=True)
            intel_cli._close_news_digest_step(paths, "2026-08-W3", 10)
            states = news_steps.progress(paths, "2026-08-W3")["states"]
            self.assertEqual(states["deposit"], "done")
            note = news_steps.open_manifest(paths, "2026-08-W3").load()["steps"]["deposit"]["note"]
            self.assertIn("intel deposit", note, "要写清是谁替它记完的")

    def test_closing_news_digest_step_never_breaks_the_main_flow(self):
        """周期键不合规（比如季度通道的条目）时，联动要静默跳过而不是把入库弄失败。"""
        from modules.competitor_intel import cli as intel_cli

        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            intel_cli._close_news_digest_step(paths, "26Q2", 3)   # 不是 month_week 键

    def test_reviewed_flag_survives_a_roundtrip(self):
        """人核过的标记必须能存下来——存不下来，retag 下一轮就把人的改动算回去了。"""
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            store = Store(paths)
            store.add([action()], commit=True)
            first = store.load()[0]
            store.replace([Entry.from_dict({**first.to_dict(), "topics_reviewed": True})])
            self.assertTrue(store.load()[0].topics_reviewed)

    def test_jsonl_is_written_with_lf(self):
        """这份文件进 git。CRLF 会让每周新增显示成全文改写。"""
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            store = Store(paths)
            store.add([action()], commit=True)
            store.add([action(url="https://skift.com/other/")], commit=True)
            self.assertNotIn(b"\r\n", store.entries_file.read_bytes())


class TestQuery(unittest.TestCase):
    def _entries(self):
        rows = [
            action(companies=["ABNB"], mentions=["EXPE"], topics=["supply"],
                   url="https://x.com/1", title="Airbnb 租车"),
            action(companies=["BKNG"], topics=["b2b"], url="https://x.com/2", title="Booking B2B"),
            action(companies=[], topics=["policy-macro"], url="https://x.com/3",
                   title="美国入境下滑"),
            action(companies=["TCOM"], topics=["b2b"], url="https://x.com/4", title="携程商旅"),
            action(companies=["GOOGLE"], topics=["b2b"], url="https://x.com/5", title="Google 商旅"),
        ]
        return [normalize(r)[0] for r in rows]

    def test_mentions_are_findable(self):
        """ADR 0002 §5：Airbnb 那条主角是 ABNB，但对 EXPE 是实质信息。"""
        rows = query.by_company(self._entries(), "EXPE")
        self.assertEqual([e.title for e in rows], ["Airbnb 租车"])
        self.assertEqual(query.by_company(self._entries(), "EXPE", include_mentions=False), [])

    def test_topic_groups_by_company_with_macro_bucket(self):
        sliced = query.by_topic(self._entries(), "policy-macro")
        self.assertEqual(list(sliced.by_company), [query.MACRO_BUCKET])

    def test_profiled_companies_come_first(self):
        """横切结果里建档层要排在其他桶之前，否则人得自己找重点。"""
        order = list(query.by_topic(self._entries(), "b2b").by_company)
        self.assertLess(order.index("BKNG"), order.index("GOOGLE"))

    def test_digest_supply_excludes_tcom(self):
        """情报库反向给新闻精选供料时 TCOM 一律排除（ADR 0002 §9 派生的方向闸）。"""
        titles = [e.title for e in query.for_digest_supply(self._entries())]
        self.assertNotIn("携程商旅", titles)
        self.assertIn("Booking B2B", titles)

    def test_shareable_excludes_internal(self):
        self.assertNotIn("携程商旅", [e.title for e in query.shareable(self._entries())])


DIGEST = """# 📬 旅行行业新闻精选 | 2026年8月第2周

> 发布：2026/08/18（周二）
> 情报主周：2026/08/10–08/16

## 一、OTA/旅游行业新闻精选

> **本周概览**
> - 一条概览，不是条目

**🎫 Airbnb 接入 Tripadvisor 体验，放弃纯自建路线**
Tripadvisor 宣布其部分 tours 与体验年内可在 Airbnb 预订。

**🌍 美国海外入境连续四月下滑，世界杯未能扭转**
7 月海外入境约 300 万人次、同比 -7%，连续第四个月下滑。

## 二、新闻来源与数据说明

### 新闻来源

| 中文标题 | 英文原标题 | 媒体, 日期, URL |
| --- | --- | --- |
| Airbnb 接入 Tripadvisor 体验 | Airbnb Partners With Tripadvisor | Skift, 2026/08/11, https://skift.com/a/ |
| 美国海外入境连续四月下滑 | Overseas Travel to the U.S. Has Fallen | Skift, 2026/08/13, https://skift.com/b/ |
"""


class TestBackfill(unittest.TestCase):
    def _write(self, tmp: str, text: str) -> Path:
        path = Path(tmp) / "digest.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_period_key_is_ascii(self):
        """中文当目录名与命令行参数在 Windows 上都不安全（ADR 0007）。"""
        self.assertEqual(backfill.period_key("2026", "8", "2"), "2026-08-W2")

    def test_parses_items_and_pairs_sources(self):
        with TemporaryDirectory() as tmp:
            parsed = backfill.parse_digest(self._write(tmp, DIGEST))
            self.assertEqual(parsed.period, "2026-08-W2")
            self.assertEqual(parsed.problems, [])
            self.assertEqual(len(parsed.entries), 2)
            first = parsed.entries[0]
            self.assertEqual(first.date, "2026-08-11", "日期取自来源表，不是发布日")
            self.assertEqual(first.media, "Skift")
            self.assertIn("Tripadvisor 宣布", first.body)

    def test_overview_block_is_not_an_item(self):
        with TemporaryDirectory() as tmp:
            titles = [e.title for e in backfill.parse_digest(self._write(tmp, DIGEST)).entries]
            self.assertNotIn("本周概览", titles)

    def test_title_in_heading_is_subject_body_only_is_mention(self):
        """精选标题本来就写「谁做了什么」，所以这条规则在精选上成立。"""
        with TemporaryDirectory() as tmp:
            first = backfill.parse_digest(self._write(tmp, DIGEST)).entries[0]
            self.assertEqual(sorted(first.companies), ["ABNB", "TRIP"])

    def test_count_mismatch_refuses_instead_of_partial_pairing(self):
        """条数不等就不配对——张冠李戴比不回填坏得多。"""
        broken = DIGEST.replace(
            "| 美国海外入境连续四月下滑 | Overseas Travel to the U.S. Has Fallen "
            "| Skift, 2026/08/13, https://skift.com/b/ |\n",
            "",
        )
        with TemporaryDirectory() as tmp:
            parsed = backfill.parse_digest(self._write(tmp, broken))
            self.assertEqual(parsed.entries, [])
            self.assertTrue(any("无法可靠配对" in p for p in parsed.problems))

    def test_coverage_metric_accepts_real_shortened_titles(self):
        """这四对都是真成品里的。用 SequenceMatcher.ratio() 会把它们全判成疑似错位。"""
        pairs = [
            ("Hilton、Marriott 和 IHG 在英国推出联名借记卡", "三家酒店集团在英国推出联名借记卡"),
            ("财报季：旅游企业盈利分化，票价与费用传导成主线", "财报季揭示旅游业现状"),
            ("印度航空双雄换帅：Air India 与 IndiGo 各怀全球野心", "印度航空双雄换帅"),
            ("Airbnb 租车上线一月：日均数百单，库存与数据走 CarTrawler", "Airbnb 租车合作一个月细节"),
        ]
        for body_title, row_title in pairs:
            with self.subTest(body_title):
                self.assertGreaterEqual(
                    backfill.title_coverage(body_title, row_title),
                    backfill.COVERAGE_FLOOR,
                )

    def test_coverage_metric_still_catches_real_mismatch(self):
        """放宽不能放到失去检出能力。"""
        self.assertLess(
            backfill.title_coverage("豆包对酒店订单收取约 12% 渠道费", "印度航空双雄换帅"),
            backfill.COVERAGE_FLOOR,
        )

    def test_one_incidental_body_word_is_not_enough_for_a_topic(self):
        """抽查 39 条时发现：只靠正文一个词命中的标签约一半是错的。

        真例：「财报季：旅游企业盈利分化」因为正文提到「联名卡」被挂上忠诚度主题。
        """
        topics, _ = backfill._guess_topics(
            "财报季：旅游企业盈利分化，票价与费用传导成主线",
            "多家公司披露季度业绩；其中一家提到联名卡收入。",
        )
        self.assertNotIn("loyalty", topics)
        self.assertIn("financials", topics, "标题命中的主题要保住")

    def test_two_distinct_body_signals_are_enough(self):
        """门槛定 2 而不是 3 的原因：设 3 会把正确的也砍掉。

        真例：「Airbnb 接入 Tripadvisor 体验」标题里没有词表里的词，
        但正文命中「分发」「入口」两个独立信号，判断站得住。
        """
        topics, _ = backfill._guess_topics(
            "Airbnb 接入 Tripadvisor 体验，放弃纯自建路线",
            "此次合作意味着转向主流第三方库存；分发合作比自建更快，体验要扩展成出行入口。",
        )
        self.assertIn("distribution", topics)

    def test_ambiguous_keywords_do_not_fire(self):
        """三个实测误命中的词：Skift 的「独家」报道标签、企业差旅「政策」、引用「CEO」。"""
        cases = [
            ("Accor 终止收购 Treebo，印度中端市场整合遇挫",
             "Skift 独家：交易终止。", "distribution"),
            ("商旅「合规手册」成 AI 预订竞争壁垒",
             "企业差旅政策与交易闭环仍是护城河。", "policy-macro"),
            ("Google 开始在 Search AI Mode 测试 agentic 酒店预订",
             "公司 CEO 表示这是长期方向。", "org"),
        ]
        for title, body, forbidden in cases:
            with self.subTest(title):
                topics, _ = backfill._guess_topics(title, body)
                self.assertNotIn(forbidden, topics)

    def test_at_most_three_topics(self):
        topics, _ = backfill._guess_topics(
            "财报 收购 监管 会员 佣金 分发 AI 商旅 组织架构",
            "财报 季度 收购 并购 监管 处罚 会员 积分 佣金 费率 分发 入口 AI 大模型 商旅 差旅",
        )
        self.assertLessEqual(len(topics), backfill.MAX_TOPICS)

    def test_english_alias_needs_word_boundary(self):
        """短别名不加词边界会在英文原标题里乱命中。"""
        lead, mentioned = backfill.detect_companies("MARGIN 与 TRIPLE 无关", "正文")
        self.assertEqual((lead, mentioned), ([], []))


class TestProfiles(unittest.TestCase):
    def test_projection_carries_do_not_edit_banner(self):
        """不写这句，半年后一定有人手改 markdown 然后发现改动消失。"""
        text = profiles.render("ABNB", [normalize(action())[0]])
        self.assertIn("不要手改", text)

    def test_lead_and_mentioned_are_separate_sections(self):
        lead = normalize(action(companies=["ABNB"], url="https://x.com/1"))[0]
        mention = normalize(action(companies=["EXPE"], mentions=["ABNB"], url="https://x.com/2"))[0]
        text = profiles.render("ABNB", [lead, mention])
        self.assertIn("本公司为主角", text)
        self.assertIn("被提及", text)

    def test_rebuild_writes_only_profiled_tier(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            written = profiles.rebuild(paths, [normalize(action())[0]])
            self.assertEqual(len(written), len(vocab.PROFILED_KEYS))
            self.assertFalse((profiles.profiles_dir(paths) / "GOOGLE.md").exists())


class TestHealth(unittest.TestCase):
    def test_stale_projection_is_reported(self):
        """落后的投影看起来像最新的，比没有投影更坏。"""
        from modules.competitor_intel import health

        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            store = Store(paths)
            store.add([action()], commit=True)
            profiles.rebuild(paths, store.load())
            # 让真源比投影新
            import os
            import time

            future = time.time() + 60
            os.utime(store.entries_file, (future, future))
            rows = {r["name"]: r for r in health.checks(paths)}
            self.assertEqual(rows["公司档案投影"]["level"], "warn")

    def test_empty_store_is_warn_not_fail(self):
        from modules.competitor_intel import health

        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            self.assertEqual(health.checks(paths)[0]["level"], "warn")


if __name__ == "__main__":
    unittest.main()
