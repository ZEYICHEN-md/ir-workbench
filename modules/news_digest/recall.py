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
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

UA = {"User-Agent": "Mozilla/5.0 (compatible; ir-workbench/news-digest)"}

FEEDS: dict[str, tuple[str, str]] = {
    "skift": ("Skift", "https://skift.com/feed/"),
    "36kr": ("36氪", "https://www.36kr.com/feed"),
}

#: 行业类目词（发现层）。覆盖 OTA / 酒店 / 航司 / 分发 / 渠道商业化，**不写死单家公司**。
IN_SCOPE_TERMS: tuple[str, ...] = (
    "旅游", "酒旅", "酒店", "民宿", "航司", "机票", "航空", "出行", "OTA", "在线旅游",
    "同程", "美团", "飞猪", "抖音", "千问", "Booking", "Expedia", "Airbnb", "Agoda",
    "佣金", "抽佣", "渠道费", "分发", "入境", "出境", "签证", "GDS", "Amadeus", "Sabre",
    "华住", "锦江", "万豪", "希尔顿", "洲际", "IHG", "雅高", "民航", "铁路", "暑运",
    "AI", "大模型", "智能体",
)
_IN_SCOPE = re.compile("|".join(re.escape(t) for t in IN_SCOPE_TERMS), re.I)

#: 类目补充检索清单（每期必跑，与枚举对账）。**只打印，不执行**。
SUPPLEMENT_QUERIES: tuple[dict[str, str], ...] = (
    {"engine": "exa", "label": "36氪·酒旅OTA", "query": "site:36kr.com 在线旅游 酒店 OTA 渠道 佣金"},
    {"engine": "exa", "label": "36氪·AI分发", "query": "site:36kr.com AI 旅游 分发 渠道 商业化"},
    {"engine": "exa", "label": "虎嗅·酒旅", "query": "site:huxiu.com 旅游 酒店 OTA 佣金 渠道"},
    {"engine": "exa", "label": "界面·酒旅", "query": "site:jiemian.com 旅游 酒店 OTA 平台"},
    {
        "engine": "tavily",
        "label": "中文短词补充",
        "query": "在线旅游 酒店 佣金 渠道",
        "note": "country=China；勿用 time_range=week（实测 0 条），用 month 再本地按日期筛",
    },
)


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw.strip())
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def in_scope(text: str) -> tuple[bool, list[str]]:
    hits = sorted(
        {m.group(0) for m in _IN_SCOPE.finditer(text or "")},
        key=lambda s: (text or "").index(s),
    )
    return bool(hits), hits


def fetch_feed(source: str, cutoff: datetime, *, timeout: int = 30) -> tuple[list[dict], str | None]:
    """抓一个源。返回 (条目, 出错说明)。**单源失败不抛**——一个源挂了不该让整期召回失败。"""
    import requests

    label, url = FEEDS[source]
    try:
        response = requests.get(url, headers=UA, timeout=timeout)
    except requests.RequestException as error:
        return [], f"{label} 请求失败：{error}"
    if response.status_code != 200:
        return [], f"{label} 抓取失败 HTTP {response.status_code}"
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as error:
        return [], f"{label} 解析失败：{error}"

    out: list[dict] = []
    seen: set[str] = set()
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        when = _parse_date(item.findtext("pubDate"))
        if not title or not link or link in seen:
            continue
        if when and when < cutoff:
            continue
        seen.add(link)
        scoped, terms = in_scope(f"{title} {description}")
        out.append(
            {
                "title": title,
                "url": link.split("?")[0],
                "date": when.strftime("%Y-%m-%d") if when else "",
                "source": label,
                "in_scope": scoped,
                "match_terms": terms,
            }
        )
    return out, None


def gather(
    *,
    since: str | None = None,
    days: int = 10,
    sources: list[str] | None = None,
    scoped_only: bool = False,
) -> tuple[list[dict], list[str]]:
    """枚举全部源。返回 (条目, 告警)。"""
    if since:
        cutoff = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows: list[dict] = []
    problems: list[str] = []
    for source in sources or list(FEEDS):
        got, error = fetch_feed(source, cutoff)
        rows.extend(got)
        if error:
            problems.append(error)
    if scoped_only:
        rows = [r for r in rows if r["in_scope"]]
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
