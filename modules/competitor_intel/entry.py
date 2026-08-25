"""情报条目：schema、校验、稳定 id。

## 两类条目（ADR 0002 §4）

| 类型 | 记什么 | 典型来源 |
|---|---|---|
| `action` 动作 | 做了什么 | 新闻、公告、公开动作 |
| `statement` 表述 | 怎么说的（原话 + 位置） | 电话会、财报、公开演讲 |

表述类同样重要甚至更重要：做 IR 定位时「peers 怎么框定这件事」常比事实本身有用
（例：Expedia 在电话会上把生成式回答那一层叫 AEO 而非 GEO）。所以 `statement`
必须带原话与位置指针，否则它退化成一条没法回原文核对的转述。

## 主角与提及是放置规则，不是过滤器（ADR 0002 §5）

`companies` = 主角，进公司档案正文；`mentions` = 仅被提及，只进检索索引。
两者都记录。例：Airbnb–CarTrawler 租车那条，ABNB 是主角，但「Expedia 年内完成对
CarTrawler 的收购」对 EXPE 是实质信息，必须能在 EXPE 的检索结果里出现。

## 公司字段可以为空（ADR 0002 §6）

宏观与政策类条目没有公司归属（例「美国海外入境连续四月下滑」），但对写出境需求侧风险
有用。schema **不得**强制公司字段非空。

## id 为什么要确定性

每周的沉淀是自动的，回填也可能重跑。**幂等靠 id 保证**：同一条新闻算出同一个 id，
重复追加直接跳过。用相似度去判重在这里是错的工具——那是给「选稿时别写重复新闻」用的
（见 news-digest 的台账），不是给「同一条别入两次」用的。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

from . import vocab

Kind = Literal["action", "statement"]
Sensitivity = Literal["internal", "shareable"]
Channel = Literal["weekly", "quarterly", "expert-call", "manual"]

KIND_ZH = {"action": "动作", "statement": "表述"}
CHANNEL_ZH = {
    "weekly": "周度通道",
    "quarterly": "季度通道",
    "expert-call": "专家访谈",
    "manual": "手工补录",
}

#: URL 里对「是不是同一条」毫无意义的追踪参数。归一时剥掉。
_TRACKING = re.compile(
    r"^(utm_|ref$|ref_|from$|source$|spm$|share|fbclid$|gclid$|_ga$)", re.I
)
_DATE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")


class EntryError(ValueError):
    """条目不合规。消息必须说清缺什么。"""


def normalize_url(url: str | None) -> str | None:
    """剥掉追踪参数与锚点，小写域名，去掉末尾斜杠。"""
    if not url:
        return None
    parts = urlsplit(url.strip())
    if not parts.netloc:
        return url.strip() or None
    query = "&".join(
        piece for piece in parts.query.split("&")
        if piece and not _TRACKING.match(piece.split("=")[0])
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", parts.netloc.lower(), path, query, ""))


def _slug(text: str) -> str:
    """标题 → 短指纹。中文标题没法做可读 slug，就用哈希，够稳定就行。"""
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:10]


def make_id(date: str, url: str | None, title: str) -> str:
    """确定性 id = 日期 + （URL 归一后 或 标题）的指纹。

    有 URL 就用 URL：同一条新闻被两个期次分别沉淀（例「延续上期」）时，标题会改写，
    URL 不会。用标题会让它变成两条。
    """
    basis = normalize_url(url) or title
    return f"{date.replace('-', '')}-{_slug(basis)}"


@dataclass
class Entry:
    kind: Kind
    date: str                       # 事件日期，YYYY-MM-DD
    title: str
    body: str
    companies: list[str] = field(default_factory=list)   # 主角
    mentions: list[str] = field(default_factory=list)    # 仅被提及
    topics: list[str] = field(default_factory=list)
    media: str | None = None
    url: str | None = None
    title_en: str | None = None
    quote: str | None = None        # statement 必填：原话
    quote_where: str | None = None  # statement 必填：位置指针
    speaker: str | None = None
    sensitivity: Sensitivity = "shareable"
    channel: Channel = "weekly"
    period: str | None = None       # 采集期次（周度 = month_week 键）
    note: str | None = None
    id: str | None = None
    added: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "date": self.date,
            "title": self.title,
            "body": self.body,
            "companies": self.companies,
            "mentions": self.mentions,
            "topics": self.topics,
            "sensitivity": self.sensitivity,
            "channel": self.channel,
        }
        for key in ("media", "url", "title_en", "quote", "quote_where",
                    "speaker", "period", "note", "added"):
            value = getattr(self, key)
            if value:
                out[key] = value
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Entry":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    @property
    def all_companies(self) -> list[str]:
        """主角 + 提及。检索时两者都要命中。"""
        seen, out = set(), []
        for key in [*self.companies, *self.mentions]:
            if key not in seen:
                seen.add(key)
                out.append(key)
        return out


def normalize(
    entry: Entry,
    *,
    registry: dict[str, str] | None = None,
) -> tuple[Entry, list[str]]:
    """校验并补齐。返回 (条目, 需要登记进其他桶的公司原名)。

    公司名归一到受控键；不在前两层的返回给调用方去登记——**不在这里直接写注册表**，
    因为 dry-run 也要走同一条校验路径，而 dry-run 不该产生副作用。
    """
    if entry.kind not in ("action", "statement"):
        raise EntryError(f"kind 只能是 action 或 statement，收到 {entry.kind!r}")
    if not _DATE.match(entry.date or ""):
        raise EntryError(f"date 必须是 YYYY-MM-DD，收到 {entry.date!r}")
    if not (entry.title or "").strip():
        raise EntryError("title 不能为空")
    if not (entry.body or "").strip():
        raise EntryError("body 不能为空")

    # 入库门槛（ADR 0002 §3）：已发生的事实 + 有可核对来源 + 有明确日期。
    # 日期上面已查；来源这里查。表述类的「来源」是位置指针，不是 URL。
    if entry.kind == "statement":
        if not (entry.quote or "").strip():
            raise EntryError("表述类必须带原话（quote），否则无法回原文核对")
        if not (entry.quote_where or "").strip():
            raise EntryError(
                "表述类必须带位置指针（quote_where），如「26Q2 电话会 Q&A」或"
                "「26Q2 10-Q 第 12 页」"
            )
    elif not (entry.url or entry.media):
        raise EntryError("动作类必须有可核对来源（url 或 media 至少给一个）")

    unregistered: list[str] = []
    entry.companies = _resolve_list(entry.companies, unregistered)
    entry.mentions = _resolve_list(entry.mentions, unregistered)
    # 同一家既是主角又被提及时，只留主角——否则档案与索引会各记一次。
    entry.mentions = [k for k in entry.mentions if k not in entry.companies]

    entry.topics = _dedupe([vocab.resolve_topic(t) for t in entry.topics])
    if not entry.topics:
        raise EntryError(
            "至少要有一个主题——没有主题的条目查不到，也就等于没入库。可选：\n  "
            + "、".join(f"{t.key}（{t.zh}）" for t in vocab.TOPICS)
        )

    # TCOM 默认内部级（ADR 0002 §9），不进公开作品集仓。
    if "TCOM" in entry.all_companies:
        entry.sensitivity = "internal"

    entry.url = normalize_url(entry.url)
    entry.id = entry.id or make_id(entry.date, entry.url, entry.title)
    entry.added = entry.added or datetime.now(timezone.utc).astimezone().isoformat(
        timespec="seconds"
    )
    return entry, _dedupe(unregistered)


def _resolve_list(names: list[str], unregistered: list[str]) -> list[str]:
    out: list[str] = []
    for name in names or []:
        key = vocab.resolve_company(name)
        if key is None:
            key = vocab.normalize_other(name)
            unregistered.append(name.strip())
        out.append(key)
    return _dedupe(out)


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out
