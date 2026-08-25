"""检索：按公司纵切、按主题横切。

两个消费场景决定了只需要这两种切法（ADR 0002）：

1. **Appendix 撰写**——按公司纵切：这家公司这季度干了什么，一家一段。
2. **季报定位研究**——按主题横切：所有 peers 在某个主题上分别做了什么、怎么说的。

场景 2 是主题受控词表存在的唯一理由，所以横切必须**按公司分组返回**，
而不是返回一个混在一起的列表——混在一起等于把比较工作又推回给人。

## 方向闸

`for_digest_supply()` 是 ADR 0002 §9 派生的那道闸：情报库反向给新闻精选供料时，
**TCOM 条目必须被排除**。当前精选是情报库的上游，还没有泄漏路径；这道闸是为将来预留的。
留在代码里而不是只写在文档里，是因为它的执行成本几乎为零，而漏一次的代价是对外交付物
里出现携程自己的动作。
"""

from __future__ import annotations

from dataclasses import dataclass

from . import vocab
from .entry import Entry


def _in_window(entry: Entry, since: str | None, until: str | None) -> bool:
    if since and entry.date < since:
        return False
    if until and entry.date > until:
        return False
    return True


def by_company(
    entries: list[Entry],
    company: str,
    *,
    since: str | None = None,
    until: str | None = None,
    kind: str | None = None,
    include_mentions: bool = True,
) -> list[Entry]:
    """某家公司的条目，时间倒序。

    `include_mentions=True` 时连「仅被提及」的一起返回——ADR 0002 §5 的例子就是这个：
    Airbnb–CarTrawler 那条主角是 ABNB，但对 EXPE 是实质信息，查 EXPE 必须能看到。
    """
    key = vocab.resolve_company(company) or vocab.normalize_other(company)
    out = [
        e for e in entries
        if (key in e.all_companies if include_mentions else key in e.companies)
        and _in_window(e, since, until)
        and (kind is None or e.kind == kind)
    ]
    return sorted(out, key=lambda e: (e.date, e.title), reverse=True)


@dataclass
class TopicSlice:
    topic: str
    topic_zh: str
    #: 公司键 → 该公司在此主题下的条目（时间倒序）。无公司归属的条目归到 `_macro`。
    by_company: dict[str, list[Entry]]
    total: int


#: 无公司归属条目的归属桶。宏观与政策类没有公司主角（ADR 0002 §6），
#: 但对写出境需求侧风险有用，不能因为没公司就查不到。
MACRO_BUCKET = "_macro"
MACRO_ZH = "无公司归属（宏观 / 政策）"


def by_topic(
    entries: list[Entry],
    topic: str,
    *,
    since: str | None = None,
    until: str | None = None,
    tiers: tuple[str, ...] = ("profiled", "indexed", "other"),
) -> TopicSlice:
    """某主题下所有公司分别做了什么，按公司分组。"""
    key = vocab.resolve_topic(topic)
    grouped: dict[str, list[Entry]] = {}
    total = 0
    for entry in entries:
        if key not in entry.topics or not _in_window(entry, since, until):
            continue
        total += 1
        targets = entry.all_companies or [MACRO_BUCKET]
        for company in targets:
            if company != MACRO_BUCKET and vocab.tier_of(company) not in tiers:
                continue
            grouped.setdefault(company, []).append(entry)
    for items in grouped.values():
        items.sort(key=lambda e: (e.date, e.title), reverse=True)
    ordered = _order_companies(grouped)
    return TopicSlice(key, vocab.TOPIC_BY_KEY[key].zh, ordered, total)


def _order_companies(grouped: dict[str, list[Entry]]) -> dict[str, list[Entry]]:
    """建档层在前、索引层次之、其他桶最后，宏观桶垫底。同层按条目数倒序。"""
    rank = {"profiled": 0, "indexed": 1, "other": 2}

    def sort_key(item):
        company, items = item
        if company == MACRO_BUCKET:
            return (3, 0, company)
        return (rank[vocab.tier_of(company)], -len(items), company)

    return dict(sorted(grouped.items(), key=sort_key))


def for_digest_supply(entries: list[Entry]) -> list[Entry]:
    """给新闻精选反向供料时用这个入口——**TCOM 条目一律排除**（ADR 0002 §9）。

    只要 TCOM 出现在主角或提及里就排除。不做「只排主角」这种细分：精选里出现携程
    自己的表述，无论以什么身份出现都是违规。
    """
    return [e for e in entries if "TCOM" not in e.all_companies]


def shareable(entries: list[Entry]) -> list[Entry]:
    """可进公开作品集仓的条目。内部级（含全部 TCOM 条目）排除。"""
    return [e for e in entries if e.sensitivity == "shareable"]


def stats(entries: list[Entry]) -> dict:
    """库的体检数据，给 status / doctor 用。"""
    by_tier: dict[str, int] = {}
    by_topic_count: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    periods: set[str] = set()
    for entry in entries:
        by_kind[entry.kind] = by_kind.get(entry.kind, 0) + 1
        if entry.period:
            periods.add(entry.period)
        for topic in entry.topics:
            by_topic_count[topic] = by_topic_count.get(topic, 0) + 1
        for company in entry.all_companies:
            tier = vocab.tier_of(company)
            by_tier[tier] = by_tier.get(tier, 0) + 1
    covered = {
        key for e in entries for key in e.all_companies
    } & set(vocab.PROFILED_KEYS)
    return {
        "total": len(entries),
        "by_kind": by_kind,
        "by_tier": by_tier,
        "by_topic": by_topic_count,
        "periods": sorted(periods),
        "profiled_covered": sorted(covered),
        "profiled_missing": [k for k in vocab.PROFILED_KEYS if k not in covered],
        "topics_unused": [t.key for t in vocab.TOPICS if t.key not in by_topic_count],
    }
