"""从新闻精选 Markdown 解析情报条目。

## 为什么不重写摘要（ADR 0002 §1）

沉淀时**原样复用**精选已写好的正文段落。重写等于额外劳动 + 信息损耗，且会引入
「摘要与原文不一致」这类无人可查的错误。所以本模块只做搬运和打标，一个字不改。

## 精选的结构契约

四期成品（`2026年7月第3周` 起）结构完全一致，解析依赖这三条：

1. 抬头 `# 📬 旅行行业新闻精选 | {年}年{月}月第{周}周`
2. `## 一、…` 里逐条 `**{图标} {中文标题}**` + 空行 + 一段正文
3. 末尾来源表 `| 中文标题 | 英文原标题 | 媒体, 日期, URL |`

**正文条目与来源表行是一一对应、同序的**，这是唯一可靠的配对依据——表里的中文标题是
正文标题的**缩写**（正文「豆包对酒店订单收取约 12% 渠道费，国内 AI 对话入口开始抽佣」
对表里「豆包对酒店订单收取约 12% 渠道费」），做不了精确匹配。所以按序配对 + 相似度校验：
相似度过低就报出来让人看，**不猜**。条数不等也直接报错，不做部分配对。

## 打标是草稿，不是结论

公司靠别名匹配，规则明确：**标题里出现的算主角，只在正文里出现的算提及**（对应
ADR 0002 §5 的放置规则）。这条规则在精选上成立，因为精选标题本来就写「谁做了什么」。

主题靠关键词猜，**明确是启发式**。因此产出是一份草稿 JSON，附上每条命中了哪个关键词，
供人核对后再入库；猜不出主题的条目留空，`normalize()` 会拒收，于是它必然出现在
待处理清单里而不会被悄悄丢掉。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from . import vocab
from .entry import Entry

_HEADING = re.compile(r"^#\s*.*新闻精选\s*\|\s*(20\d{2})年(\d{1,2})月第(\d)周")
_SECTION_ONE = re.compile(r"^##\s*一、", re.M)
_NEXT_SECTION = re.compile(r"^##\s+", re.M)
_ITEM = re.compile(r"^\*\*(.+?)\*\*\s*$", re.M)
_TABLE_ROW = re.compile(r"^\|\s*(?![-\s|]+\|)(.+?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$", re.M)
_EMOJI_PREFIX = re.compile(r"^[^\w\u4e00-\u9fff]+")
_SOURCE = re.compile(r"^(.*?),\s*(20\d{2})/(\d{2})/(\d{2}),\s*(https?://\S+)\s*$")

#: 配对可信度下限。低于这个值就认为按序配对不可信，报出来让人看。
COVERAGE_FLOOR = 0.5


def title_coverage(body_title: str, row_title: str) -> float:
    """来源表标题被正文标题覆盖了多少。

    **不能用 `SequenceMatcher.ratio()`**：它按两串总长归一，而来源表标题是正文标题的
    刻意缩写，长度差本身就大，于是四条完全对得上的配对被判成 0.36–0.42 的「疑似错位」——
    实测报出四条假警告。假警告的坏处不是烦，是让人开始整体忽略这一栏。

    改成「短的那串有多少被长的覆盖」：
    「印度航空双雄换帅」被「印度航空双雄换帅：Air India 与 IndiGo 各怀全球野心」
    完全覆盖 → 1.0，符合直觉。
    """
    short, long = sorted((body_title, row_title), key=len)
    if not short:
        return 0.0
    matcher = SequenceMatcher(None, short, long, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched / len(short)


@dataclass
class Parsed:
    period: str                       # ASCII 周期键，如 2026-08-W2
    entries: list[Entry]
    problems: list[str] = field(default_factory=list)
    #: 每条的打标依据，写进草稿供人核对
    trace: list[dict] = field(default_factory=list)


#: `body_items` / `source_rows` / `title_coverage` 三个函数是**新闻精选结构契约的唯一实现**，
#: 刻意公开：`modules/news_digest/digest.py` 的交付物校验必须用同一份解析。
#: 两边各写一份的后果是校验通过而沉淀配对失败——那种不一致最难查。


def period_key(year: str, month: str, week: str) -> str:
    """`2026年8月第2周` → `2026-08-W2`。

    旧实现三处目录都直接用中文期次名。中文当目录名与命令行参数在 Windows 上都不安全
    （ADR 0007），所以键一律 ASCII，中文标签由 `domains.period_label()` 生成。
    """
    return f"{year}-{int(month):02d}-W{week}"


def parse_digest(path: Path) -> Parsed:
    text = path.read_text(encoding="utf-8")
    head = _HEADING.search(text)
    if not head:
        return Parsed("", [], [f"{path.name}：抬头里找不到「新闻精选 | ...年...月第...周」"])
    period = period_key(*head.groups())

    items = body_items(text)
    rows = source_rows(text)
    problems: list[str] = []

    if not items:
        problems.append(f"{path.name}：§一 里没解析到任何条目")
        return Parsed(period, [], problems)
    if len(items) != len(rows):
        problems.append(
            f"{path.name}：正文 {len(items)} 条与来源表 {len(rows)} 行不等，"
            "无法可靠配对。请核对后再回填（不做部分配对，避免张冠李戴）。"
        )
        return Parsed(period, [], problems)

    entries: list[Entry] = []
    trace: list[dict] = []
    for (title, body), row in zip(items, rows):
        sim = title_coverage(title, row["title_cn"])
        if sim < COVERAGE_FLOOR:
            problems.append(
                f"{path.name}：正文「{title}」与来源行「{row['title_cn']}」重合度 "
                f"{sim:.2f}，低于 {COVERAGE_FLOOR}，按序配对可能错位，请人工核对。"
            )
        lead, mentioned = detect_companies(title, body)
        topics, hits = _guess_topics(title, body)
        entries.append(
            Entry(
                kind="action",
                date=row["date"],
                title=title,
                body=body,
                companies=lead,
                mentions=mentioned,
                topics=topics,
                media=row["media"],
                url=row["url"],
                title_en=row["title_en"] or None,
                channel="weekly",
                period=period,
            )
        )
        trace.append(
            {
                "title": title,
                "pair_similarity": round(sim, 3),
                "companies": lead,
                "mentions": mentioned,
                "topics": topics,
                "topic_hits": hits,
            }
        )
    return Parsed(period, entries, problems, trace)


def body_items(text: str) -> list[tuple[str, str]]:
    """§一 里的 `**标题**` + 紧跟的一段正文。"""
    start = _SECTION_ONE.search(text)
    if not start:
        return []
    rest = text[start.end():]
    stop = _NEXT_SECTION.search(rest)
    section = rest[: stop.start()] if stop else rest

    out: list[tuple[str, str]] = []
    marks = list(_ITEM.finditer(section))
    for index, mark in enumerate(marks):
        raw_title = mark.group(1).strip()
        # `> **本周概览**` 之类在引用块里，不是条目
        line_start = section.rfind("\n", 0, mark.start()) + 1
        if section[line_start:mark.start()].strip().startswith(">"):
            continue
        end = marks[index + 1].start() if index + 1 < len(marks) else len(section)
        chunk = section[mark.end():end]
        body = "\n".join(
            line.strip() for line in chunk.strip().splitlines() if line.strip()
        )
        if not body:
            continue
        out.append((_EMOJI_PREFIX.sub("", raw_title).strip(), body))
    return out


def source_rows(text: str) -> list[dict]:
    rows: list[dict] = []
    for match in _TABLE_ROW.finditer(text):
        title_cn, title_en, source = (g.strip() for g in match.groups())
        if title_cn in ("中文标题",) or not source:
            continue
        parsed = _SOURCE.match(source)
        if not parsed:
            continue
        media, year, month, day, url = parsed.groups()
        rows.append(
            {
                "title_cn": title_cn,
                "title_en": title_en,
                "media": media.strip(),
                "date": f"{year}-{month}-{day}",
                "url": url,
            }
        )
    return rows


def detect_companies(title: str, body: str) -> tuple[list[str], list[str]]:
    """标题里出现的算主角，只在正文出现的算提及。

    认前两层 + 其他桶种子（`vocab.OTHERS_SEED`）。不认的公司不自动登记——自动登记一堆
    只出现过一次的名字会把注册表变成垃圾场。需要时人工在草稿里补一个名字，
    `intel add` 会把它登记进其他桶。
    """
    lead: list[str] = []
    mentioned: list[str] = []
    for company in vocab.PROFILED + vocab.INDEXED + vocab.OTHERS_SEED:
        needles = [company.key, company.zh, *company.aliases]
        in_title = any(_contains(title, n) for n in needles)
        in_body = any(_contains(body, n) for n in needles)
        if in_title:
            lead.append(company.key)
        elif in_body:
            mentioned.append(company.key)
    return lead, mentioned


def _contains(haystack: str, needle: str) -> bool:
    """英文别名要求词边界，中文别名直接子串。

    不加词边界会让 `IHG` 命中 `...IHG...` 之外的东西，也会让短别名（如 `MAR`）
    在英文原标题里乱命中。
    """
    if re.fullmatch(r"[A-Za-z0-9.\- ]+", needle):
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(needle)}(?![A-Za-z0-9])",
                         haystack, re.I) is not None
    return needle in haystack


#: 主题关键词表。**这是启发式**，命中的词会写进草稿的 `topic_hits` 供人核对。
#: 排在前面的优先——一条新闻可以挂多个主题，但要避免每条都挂满。
TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "distribution": (
        "渠道费", "抽佣", "分发", "流量", "入口", "SEO", "AEO", "自然流量",
        "搜索", "比价", "广告", "获客", "分销", "AI Mode", "Overviews",
        # 「独家」必须带上下文。单独一个词会命中 Skift 的「独家/Scoop」报道标签，
        # 实测误给「Accor 终止收购 Treebo」和「Airbnb 租车上线一月」挂上了分发主题。
        "独家合作", "独家 OTA", "独家分销", "上架",
    ),
    "supply": (
        "体验", "租车", "库存", "供给", "品类", "短租", "票务", "机票", "景点",
        "tours", "activities", "邮轮",
    ),
    "b2b": ("B2B", "企业差旅", "商旅", "协议价", "差旅", "GBT", "Concur", "企业客户"),
    "loyalty": ("会员", "忠诚度", "互认", "联名卡", "Bonvoy", "积分", "借记卡"),
    "unit-economics": (
        "佣金", "费率", "加盟", "业主", "利润率", "降费", "返利", "费用", "抽成",
        "商户", "结算",
    ),
    "ai-stack": (
        "AI", "智能体", "agentic", "大模型", "算法", "技术底座", "API", "自动化",
        "工程团队", "生成式",
    ),
    "ma-capital": ("收购", "并购", "投资", "融资", "分拆", "回购", "交易终止", "终止收购"),
    # 「CEO」单独一个词会命中任何引用了 CEO 说法的稿子（实测误标了 Google agentic 预订
    # 与 IHG 业主服务包两条）。改成只认真正表示人事变动的词。
    "org": ("任命", "兼任", "换帅", "出任", "新任", "组织架构", "裁员", "人事"),
    # 「同比」几乎每条带数字的都有，太弱（实测误给「美国入境下滑」「出境飞机不够」
    # 挂上财务主题）。财务主题要的是公司业绩本身。
    "financials": (
        "财报", "季度", "EBIT", "利润", "收入", "指引", "盈利", "亏损",
        "Q1", "Q2", "Q3", "Q4",
    ),
    # 「政策」有歧义：商旅稿里的「政策」多指**企业差旅政策**，不是政府政策
    # （实测误标了「商旅合规手册成 AI 预订壁垒」）。靠监管/签证/宏观这些明确的词就够。
    "policy-macro": (
        "监管", "处罚", "反垄断", "签证", "宏观", "入境", "战争", "地缘",
        "台风", "航班取消", "IATA", "商务部", "关税",
    ),
}

#: 一条最多挂几个主题。不设限的话关键词法会给每条挂五六个，横切检索就被噪音填满。
MAX_TOPICS = 3

#: 标题命中记 3 分，正文命中记 1 分。
TITLE_WEIGHT = 3
BODY_WEIGHT = 1

#: 采纳主题的最低分。等于「标题命中一次，或正文命中两个不同的词」。
#:
#: 这道门槛是抽查 39 条的结论：28 个标签只靠正文里**一个**词命中，约一半是错的
#: （「财报季」靠「联名卡」挂上忠诚度、「美国入境下滑」靠「同比」挂上财务）。
#: 光修关键词表治不了根——任何词表都会有边缘命中，问题在于**一次弱命中就被当成结论**。
#:
#: 定 2 而不是 3 是实测校准的：设 3 会连正确的也砍掉——「Airbnb 接入 Tripadvisor 体验」
#: 的分发主题（正文命中「分发」「入口」）、「Google 在 Ask Maps 上线对话式酒店搜索」
#: 的 AI 主题（正文命中「AI」「agentic」）都会丢。这两条的标题里没有词表里的词，
#: 但正文有两个独立信号，判断是站得住的。
#:
#: 代价是有些条目一个主题都猜不出来，于是被 `normalize()` 拒收、进待处理清单。
#: 这是想要的：让人补一个准的，比自动挂一个错的好——错标签会一直污染横切检索，没人会去查。
MIN_TOPIC_SCORE = 2


def _guess_topics(title: str, body: str) -> tuple[list[str], dict[str, list[str]]]:
    """关键词猜主题。标题命中权重更高，弱命中直接不采纳。"""
    scores: dict[str, int] = {}
    hits: dict[str, list[str]] = {}
    for topic, words in TOPIC_KEYWORDS.items():
        if topic not in vocab.TOPIC_BY_KEY:
            continue
        for word in words:
            in_title = _contains(title, word)
            if not in_title and not _contains(body, word):
                continue
            scores[topic] = scores.get(topic, 0) + (TITLE_WEIGHT if in_title else BODY_WEIGHT)
            hits.setdefault(topic, []).append(word)
    ranked = [
        (topic, score) for topic, score in
        sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        if score >= MIN_TOPIC_SCORE
    ][:MAX_TOPICS]
    chosen = [topic for topic, _ in ranked]
    return chosen, {t: hits[t] for t in chosen}


def parse_many(paths: list[Path]) -> tuple[list[Entry], list[str], list[dict]]:
    entries: list[Entry] = []
    problems: list[str] = []
    trace: list[dict] = []
    for path in sorted(paths):
        parsed = parse_digest(path)
        entries.extend(parsed.entries)
        problems.extend(parsed.problems)
        for row in parsed.trace:
            trace.append({"source": path.name, "period": parsed.period, **row})
    return entries, problems, trace
