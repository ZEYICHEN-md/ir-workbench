"""召回层：RSS 枚举 + 补充检索清单。

## 为什么要有确定性枚举层

实测：单条 exa 中文描述式 query 会被当周最大声量话题（例携程罚单）挤占，**稳定漏掉**
同周其他酒旅/OTA 重点，即便 36氪已经报道过。搜索排序做不到确定性，RSS 枚举可以。
所以枚举是候选主干，检索是补充，两者对账。

旧仓那条「中文侧主发现 = 单条 exa 描述式」已在 2026-08-11 实测 4/4 漏报后废弃。

## 覆盖（诚实说明，不要美化）

| 源 | 状态 |
|---|---|
| Skift（英文） | ✅ RSS 可用 |
| 36氪（中文） | ✅ RSS 可用，含「8点1氪」早报里的酒旅条目 |
| 环球旅讯 / 晚点 / 虎嗅 | ⛔ RSS 403 / 超时 / 证书问题，只能走补充检索清单 |

## 脚本不调搜索 API

`SUPPLEMENT_QUERIES` **只打印清单**。exa / tavily / firecrawl 是 Agent 侧的工具，
由 Agent 拿这份清单去跑。这一点最容易误判——文档里检索工具出现频率很高，
但这个模块一行都没调用它们。

`in_scope` 按**行业类目词**标记，不写死公司名：写死公司名会漏掉「新玩家进场」这类
最该看到的新闻。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

UA = {"User-Agent": "Mozilla/5.0 (compatible; ir-workbench/news-digest)"}


@dataclass(frozen=True)
class Feed:
    key: str
    label: str
    url: str
    #: 支持 `?paged=N` 翻页。**这个属性是召回层能不能成立的关键**：
    #: 一页只有 10 条（Skift）或 30 条（36氪），按每天 5 篇算就是 2 天和 1 天。
    #: 情报主周是 7 天，不翻页就只能看到最后一两天——「当周全量枚举」名不副实。
    paged: bool = False


FEEDS_LIST: tuple[Feed, ...] = (
    Feed("skift", "Skift", "https://skift.com/feed/", paged=True),
    Feed("36kr", "36氪", "https://www.36kr.com/feed", paged=False),
)

FEEDS: dict[str, Feed] = {f.key: f for f in FEEDS_LIST}

#: 默认最多翻几页。8 页 × 10 条 ≈ 80 篇，够覆盖 7 天。
#: 整页都早于窗口下限就提前停，所以正常情况翻不到 8 页。
DEFAULT_MAX_PAGES = 8

#: Skift 这类 WordPress 站的链接里带 `/YYYY/MM/DD/`，可作日期兜底。
_DATE_IN_URL = re.compile(r"/(20\d{2})/(\d{2})/(\d{2})/")

#: 行业类目词（发现层）。覆盖 OTA / 酒店 / 航司 / 分发 / 渠道商业化，**不写死单家公司**。
IN_SCOPE_TERMS: tuple[str, ...] = (
    "旅游", "酒旅", "酒店", "民宿", "航司", "机票", "航空", "出行", "OTA", "在线旅游",
    "同程", "美团", "飞猪", "抖音", "千问", "Booking", "Expedia", "Airbnb", "Agoda",
    "佣金", "抽佣", "渠道费", "分发", "入境", "出境", "签证", "GDS", "Amadeus", "Sabre",
    "华住", "锦江", "万豪", "希尔顿", "洲际", "IHG", "雅高", "民航", "铁路", "暑运",
    "AI", "大模型", "智能体",
    # B 类「旅行中断 / 外部冲击」的类目词。第一次迁移漏了整类——只有「签证」，
    # 没有罢工/中断/天气/机场关闭。这类事件直接影响出行需求与运力，
    # 却常不在行业媒体覆盖内（反例：2026/06 末欧洲热浪致铁路胀轨停运）。
    "罢工", "停运", "取消", "机场关闭", "台风", "地震", "暴雨", "热浪",
    "边境", "口岸", "免签", "地缘", "冲突", "宕机", "限流",
)
_IN_SCOPE = re.compile("|".join(re.escape(t) for t in IN_SCOPE_TERMS), re.I)

#: 每期必跑的补充检索清单（与枚举对账）。**只打印，不执行**。
#:
#: 分 A / B 两类。**B 类必须放开域名**——这类事件直接影响出行需求与运力，却常不在行业
#: 媒体覆盖内，只锁 Skift/PhocusWire 会整条漏掉（反例：2026/06 末欧洲热浪致多国铁路
#: 胀轨停运）。第一次迁移漏了整个 B 类，而情报库里已有「台风红霞致香港机场约 350 航班取消」
#: 一条，证明它确实该收。
#:
#: 参数级禁令见 `references/retrieval.md`：描述式 query 只喂 exa 不喂 tavily；
#: tavily 只用短词且不锁域名。本次会话现场重犯过后者。
SUPPLEMENT_QUERIES: tuple[dict[str, str], ...] = (
    {"engine": "exa", "kind": "A", "label": "36氪·酒旅OTA",
     "query": "site:36kr.com 在线旅游 酒店 OTA 渠道 佣金"},
    {"engine": "exa", "kind": "A", "label": "36氪·AI分发",
     "query": "site:36kr.com AI 旅游 分发 渠道 商业化"},
    {"engine": "exa", "kind": "A", "label": "虎嗅·酒旅",
     "query": "site:huxiu.com 旅游 酒店 OTA 佣金 渠道"},
    {"engine": "exa", "kind": "A", "label": "界面·酒旅",
     "query": "site:jiemian.com 旅游 酒店 OTA 平台"},
    {"engine": "exa", "kind": "A", "label": "环球旅讯·OTA",
     "query": "site:traveldaily.cn OTA 酒店 分销 渠道",
     "note": "环球旅讯 RSS 拿不到，但它是携程主场必扫的检索目标源"},
    {
        "engine": "tavily", "kind": "A", "label": "中文短词补充",
        "query": "在线旅游 酒店 佣金 渠道",
        "note": "country=China；**短词、不锁域名**；勿用 time_range=week（实测 0 条），"
                "用 month 再本地按日期筛；描述式 query 不要喂 tavily",
    },
    {
        "engine": "exa", "kind": "B", "label": "中断·航班与机场",
        "query": "airport closure flights cancelled travel disruption this week",
        "note": "**放开域名**（reuters/apnews/bbc/theguardian/cnn），别锁行业站",
    },
    {
        "engine": "exa", "kind": "B", "label": "中断·罢工与铁路",
        "query": "airline airport rail strike travel disruption",
        "note": "**放开域名**",
    },
    {
        "engine": "exa", "kind": "B", "label": "中断·签证与边境",
        "query": "visa policy border entry change outbound travel China",
        "note": "**放开域名**",
    },
    {
        "engine": "exa", "kind": "B", "label": "中断·极端天气与地缘",
        "query": "extreme weather geopolitical conflict impact on air travel demand",
        "note": "**放开域名**；没命中重量级事件属正常，但要记「B 类扫过、无事」",
    },
)


def _parse_date(raw: str | None, link: str = "") -> datetime | None:
    """解析条目日期。三层：RFC 2822 → ISO 变体 → 链接里的 `/YYYY/MM/DD/`。

    为什么要三层：

    - **RFC 2822** 是 RSS 规范里的 `pubDate` 格式，Skift 用的是这个。
    - **ISO 变体**是 36氪 实际发的格式：`2026-08-24 15:07:48  +0800`（注意时区前有**两个**空格）。
      `parsedate_to_datetime` 认不了它，于是 36氪 的每一条日期都是空的——**窗口过滤对中文侧
      整个失效**（`if when and when < cutoff` 里 `when` 为 None 就直接放过）。这个缺陷是从
      旧仓继承的，实测四期精选里 36氪 来源只出现过一条，大概率与此有关。
      更麻烦的是：无日期的条目沉淀时会被 `normalize()` 拒收（date 必填），也就是采到了也进不了库。
    - **链接兜底**：WordPress 站的 URL 里带日期。旧仓 `news_recall.py` 有这层，我移植时漏了。
    """
    text = (raw or "").strip()
    if text:
        try:
            parsed = parsedate_to_datetime(text)
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
        except (TypeError, ValueError):
            pass
        # `2026-08-24 15:07:48  +0800` / `2026-08-24 15:07:48` / `2026-08-24T15:07:48+08:00`
        squeezed = re.sub(r"\s+", " ", text).replace("T", " ")
        for pattern in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(squeezed, pattern)
            except ValueError:
                continue
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    match = _DATE_IN_URL.search(link or "")
    if match:
        try:
            return datetime(int(match[1]), int(match[2]), int(match[3]), tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def in_scope(text: str) -> tuple[bool, list[str]]:
    hits = sorted(
        {m.group(0) for m in _IN_SCOPE.finditer(text or "")},
        key=lambda s: (text or "").index(s),
    )
    return bool(hits), hits


def fetch_feed(
    source: str,
    cutoff: datetime,
    *,
    until: datetime | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
    timeout: int = 30,
) -> tuple[list[dict], str | None]:
    """抓一个源，必要时翻页。返回 (条目, 出错说明)。

    **单源失败不抛**——一个源挂了不该让整期召回失败。
    整页都早于 `cutoff` 就停止翻页，正常一周翻两三页就够。
    """
    import requests

    feed = FEEDS[source]
    out: list[dict] = []
    seen: set[str] = set()
    pages = max_pages if feed.paged else 1

    for page in range(1, pages + 1):
        url = feed.url if page == 1 else (
            f"{feed.url}{'&' if '?' in feed.url else '?'}paged={page}"
        )
        try:
            response = requests.get(url, headers=UA, timeout=timeout)
        except requests.RequestException as error:
            return out, f"{feed.label} 第 {page} 页请求失败：{error}"
        if response.status_code != 200:
            if page == 1:
                return out, f"{feed.label} 抓取失败 HTTP {response.status_code}"
            break                      # 翻到没有更多页是正常结束
        try:
            items = ET.fromstring(response.content).findall(".//item")
        except ET.ParseError as error:
            return out, f"{feed.label} 第 {page} 页解析失败：{error}"
        if not items:
            break

        page_oldest: datetime | None = None
        for item in items:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            description = (item.findtext("description") or "").strip()
            when = _parse_date(item.findtext("pubDate"), link)
            if when and (page_oldest is None or when < page_oldest):
                page_oldest = when
            if not title or not link or link in seen:
                continue
            if when and (when < cutoff or (until and when > until)):
                continue
            seen.add(link)
            scoped, terms = in_scope(f"{title} {description}")
            out.append(
                {
                    "title": title,
                    "url": link.split("?")[0],
                    "date": when.strftime("%Y-%m-%d") if when else "",
                    "source": feed.label,
                    "in_scope": scoped,
                    "match_terms": terms,
                }
            )
        if page_oldest and page_oldest < cutoff:
            break
    return out, None


def gather(
    *,
    since: str | None = None,
    until: str | None = None,
    days: int = 10,
    sources: list[str] | None = None,
    scoped_only: bool = False,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> tuple[list[dict], list[str]]:
    """枚举全部源。返回 (条目, 告警)。

    `until` 是上限。旧仓只有下限，因为旧流程总是做刚结束的当周，窗口右端就是「现在」。
    补做过去的期次时会露馅：实测给 08-W3（8/17–8/23）跑召回，拿回来的是 8/24–8/25
    的稿子——那些属于下一期。
    """
    if since:
        cutoff = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    ceiling = None
    if until:
        # 上限含当天：给的是日期，意思是那一整天都要
        ceiling = datetime.strptime(until, "%Y-%m-%d").replace(
            tzinfo=timezone.utc, hour=23, minute=59, second=59
        )

    rows: list[dict] = []
    problems: list[str] = []
    for source in sources or list(FEEDS):
        got, error = fetch_feed(source, cutoff, until=ceiling, max_pages=max_pages)
        rows.extend(got)
        if error:
            problems.append(error)
    if scoped_only:
        rows = [r for r in rows if r["in_scope"]]
    undated = [r for r in rows if not r["date"]]
    if undated:
        problems.append(
            f"{len(undated)} 条没能解析出日期，窗口过滤对它们无效，且沉淀时会被拒收"
            "（date 必填）。若集中在某一个源，多半是那个源的日期格式变了。"
        )
    rows.sort(key=lambda r: (r["date"], r["title"]), reverse=True)
    return rows, problems


def filter_by_window(
    rows: list[dict], since: str, until: str | None = None, *, keep_undated: bool = False
) -> list[dict]:
    """把检索工具（exa / tavily）返回的条目按日期窗口筛一遍。

    本环境的 exa 没有可靠的服务端时间过滤，所以窗口在本地兜。无日期的默认丢弃——
    留着会让「本周新闻」里混进半年前的稿子，而那种错很难在成稿阶段发现。
    """
    out = []
    for row in rows:
        date = (row.get("date") or "").strip()
        if not date:
            if keep_undated:
                out.append(row)
            continue
        normalized = date.replace("/", "-")
        if normalized < since:
            continue
        if until and normalized > until:
            continue
        out.append(row)
    return out
