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
import json
import math
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
EVIDENCE_TYPES = {
    "company_reported", "internal_actual", "platform_observation", "operational_estimate",
    "external_estimate", "personal_guess", "forecast", "interviewer_led",
}
SOURCE_PROXIMITIES = {
    "direct_management", "direct_owner", "direct_team", "adjacent_function", "external_observer",
}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
QUARTERLY_SOURCE_TYPES = {
    "regulatory-filing", "company-ir", "third-party-transcript", "derived",
}
SOURCE_AUTHORITIES = {"P0", "P1", "P2"}

#: URL 里对「是不是同一条」毫无意义的追踪参数。归一时剥掉。
_TRACKING = re.compile(
    r"^(utm_|ref$|ref_|from$|source$|spm$|share|fbclid$|gclid$|_ga$)", re.I
)
_DATE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
_METRIC_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


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
    """确定性 id = 日期 + （URL 归一后 或 标题）的指纹。"""
    basis = normalize_url(url) or title
    return f"{date.replace('-', '')}-{_slug(basis)}"


def make_entry_id(entry: "Entry") -> str:
    """普通条目沿用旧 id；数据主张加入来源、口径和值，避免同一 PDF 多指标碰撞。"""
    if not entry.claim:
        return make_id(entry.date, entry.url, entry.title)
    source = normalize_url(entry.url) or entry.quote_where or entry.media or entry.title
    keys = ("metric_key", "scope", "period", "value", "unit", "basis")
    signature = json.dumps(
        {key: entry.claim.get(key) for key in keys},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    )
    return f"{entry.date.replace('-', '')}-{_slug(f'{source}|{signature}')}"


def _finite_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _normalize_claim(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    """校验可独立检索的数据主张；冲突状态由 Store 相对当前库动态计算。"""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise EntryError("claim 必须是 object")
    required = {
        "metric_key", "scope", "period", "value", "unit", "evidence_type",
        "source_proximity", "confidence", "confidence_reasons",
    }
    missing = [key for key in required if key not in raw]
    if missing:
        raise EntryError("claim 缺字段：" + "、".join(sorted(missing)))
    metric_key = str(raw["metric_key"]).strip().lower()
    if not _METRIC_KEY.fullmatch(metric_key):
        raise EntryError("claim.metric_key 必须是稳定 ASCII slug")
    scope = raw["scope"]
    if not isinstance(scope, dict) or not scope:
        raise EntryError("claim.scope 必须是非空 object")
    normalized_scope: dict[str, str] = {}
    for key, value in sorted(scope.items()):
        if not isinstance(key, str) or not key.strip() or not isinstance(value, str) or not value.strip():
            raise EntryError("claim.scope 的键和值必须是非空字符串")
        normalized_scope[key.strip()] = value.strip()
    period = raw["period"]
    unit = raw["unit"]
    if not isinstance(period, str) or not period.strip():
        raise EntryError("claim.period 必须说明数据期；不知道时也要明确写 unknown")
    if not isinstance(unit, str) or not unit.strip():
        raise EntryError("claim.unit 不能为空")
    value = raw["value"]
    valid_range = (
        isinstance(value, list) and len(value) == 2
        and all(_finite_number(item) for item in value) and value[0] <= value[1]
    )
    if not (_finite_number(value) or valid_range or isinstance(value, str) and value.strip()):
        raise EntryError("claim.value 只能是有限数字、[下限, 上限]或非空原始值")
    evidence_type = raw["evidence_type"]
    source_proximity = raw["source_proximity"]
    confidence = raw["confidence"]
    if evidence_type not in EVIDENCE_TYPES:
        raise EntryError("claim.evidence_type 不在受控分类中")
    if source_proximity not in SOURCE_PROXIMITIES:
        raise EntryError("claim.source_proximity 不在受控分类中")
    if confidence not in CONFIDENCE_LEVELS:
        raise EntryError("claim.confidence 只能是 high/medium/low")
    reasons = raw["confidence_reasons"]
    if not isinstance(reasons, list) or not reasons or not all(
        isinstance(reason, str) and reason.strip() for reason in reasons
    ):
        raise EntryError("claim.confidence_reasons 必须是非空字符串数组")
    basis = raw.get("basis")
    if basis is not None and (not isinstance(basis, str) or not basis.strip()):
        raise EntryError("claim.basis 如提供必须是非空字符串")
    tolerance = raw.get("tolerance", 0)
    if not _finite_number(tolerance) or tolerance < 0:
        raise EntryError("claim.tolerance 必须是非负有限数字")
    return {
        "metric_key": metric_key,
        "scope": normalized_scope,
        "period": period.strip(),
        "value": value.strip() if isinstance(value, str) else value,
        "unit": unit.strip().lower(),
        "basis": basis.strip() if isinstance(basis, str) else None,
        "tolerance": tolerance,
        "evidence_type": evidence_type,
        "source_proximity": source_proximity,
        "confidence": confidence,
        "confidence_reasons": [reason.strip() for reason in reasons],
    }


@dataclass
class Entry:
    kind: Kind
    date: str
    title: str
    body: str
    companies: list[str] = field(default_factory=list)
    mentions: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    media: str | None = None
    url: str | None = None
    title_en: str | None = None
    quote: str | None = None
    quote_where: str | None = None
    speaker: str | None = None
    sensitivity: Sensitivity = "shareable"
    channel: Channel = "weekly"
    period: str | None = None       # 采集期次；数据期在 claim.period
    source_type: str | None = None
    source_authority: str | None = None
    source_path: str | None = None
    note: str | None = None
    claim: dict[str, Any] | None = None
    review_flags: list[str] = field(default_factory=list)
    topics_reviewed: bool = False
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
        if self.tags:
            out["tags"] = self.tags
        if self.review_flags:
            out["review_flags"] = self.review_flags
        for key in (
            "media", "url", "title_en", "quote", "quote_where", "speaker",
            "period", "source_type", "source_authority", "source_path", "note", "claim",
            "topics_reviewed", "added",
        ):
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
    """校验并补齐。返回 (条目, 需要登记进其他桶的公司原名)。"""
    if entry.kind not in ("action", "statement"):
        raise EntryError(f"kind 只能是 action 或 statement，收到 {entry.kind!r}")
    if not _DATE.match(entry.date or ""):
        raise EntryError(f"date 必须是 YYYY-MM-DD，收到 {entry.date!r}")
    if not (entry.title or "").strip():
        raise EntryError("title 不能为空")
    if not (entry.body or "").strip():
        raise EntryError("body 不能为空")
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

    if entry.channel == "quarterly":
        if entry.kind != "statement":
            raise EntryError("季度通道只收表述类条目（statement）")
        if not (entry.period or "").strip():
            raise EntryError("季度通道必须填写 period，如 26Q2")
        if entry.source_type not in QUARTERLY_SOURCE_TYPES:
            raise EntryError(
                "季度通道 source_type 必须是 regulatory-filing/company-ir/"
                "third-party-transcript/derived"
            )
        if entry.source_authority not in SOURCE_AUTHORITIES:
            raise EntryError("季度通道 source_authority 必须是 P0/P1/P2")
        source_path = (entry.source_path or "").strip().replace("\\", "/")
        if not source_path or source_path.startswith("/") or re.match(r"^[A-Za-z]:", source_path):
            raise EntryError("季度通道 source_path 必须是工作区内相对路径")
        if ".." in source_path.split("/"):
            raise EntryError("季度通道 source_path 不得越出工作区")
        if not entry.topics_reviewed:
            raise EntryError("季度通道 topics 必须人工核过，并标 topics_reviewed=true")
        entry.period = entry.period.strip()
        entry.source_path = source_path

    unregistered: list[str] = []
    entry.companies = _resolve_list(entry.companies, unregistered)
    entry.mentions = _resolve_list(entry.mentions, unregistered)
    entry.mentions = [key for key in entry.mentions if key not in entry.companies]
    entry.topics = _dedupe([vocab.resolve_topic(topic) for topic in entry.topics])
    entry.tags = _dedupe([tag.strip() for tag in (entry.tags or []) if tag and tag.strip()])
    entry.review_flags = _dedupe([
        flag.strip() for flag in (entry.review_flags or []) if flag and flag.strip()
    ])
    if not entry.topics:
        raise EntryError(
            "至少要有一个主题——没有主题的条目查不到，也就等于没入库。可选：\n  "
            + "、".join(f"{topic.key}（{topic.zh}）" for topic in vocab.TOPICS)
        )
    if "TCOM" in entry.all_companies or entry.channel == "expert-call":
        entry.sensitivity = "internal"

    entry.claim = _normalize_claim(entry.claim)
    entry.url = normalize_url(entry.url)
    entry.id = entry.id or make_entry_id(entry)
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
