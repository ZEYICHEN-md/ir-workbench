"""JSONL 真源 + 其他桶注册表。

## 为什么是 JSONL 而不是一个大 JSON 数组

沿用工作台已验证的「真源 + 投影」（ADR 0002 §10）。JSONL 的三个好处都是这里真需要的：

- **可追加**：每周沉淀是往后加，不该重写整份文件；
- **diff 干净**：新增 9 条就是 +9 行，一眼看得出这周加了什么。大 JSON 数组重排序会让
  diff 变成整份重写——这个坑在 `industry-data` 上已经付过一次代价（浮点尾数那次）；
- **坏一行不毁全库**：解析失败只丢那一行，且能指出是第几行。

## 幂等

追加按 `id` 去重。同一条重复沉淀直接跳过并计数，不报错——每周自动沉淀重跑是正常操作，
不该因此失败。

## 其他桶注册表为什么是数据而不是代码

见 `vocab.py` 的模块说明。这里只负责存：`data/intel/companies.json`，`键 → 首次登记时的原名`。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workbench.fileio import write_text, write_text_atomic
from workbench.paths import Paths

from .entry import Entry, EntryError, make_entry_id, make_id, normalize

ENTRIES_NAME = "entries.jsonl"
DEFERRED_NAME = "deferred.jsonl"
REGISTRY_NAME = "companies.json"
CLAIM_CLASSIFICATIONS = ("new", "corroborating", "conflicting", "different_scope")
DEFERRED_PRIORITIES = {"high", "medium", "low"}


@dataclass
class ClaimReview:
    """某条数据主张相对当前库的动态关系；不固化进真源。"""

    index: int
    classification: str
    candidate: dict[str, Any]
    matches: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "classification": self.classification,
            "candidate": self.candidate,
            "matches": self.matches,
        }


@dataclass
class DeferredRecord:
    """尚不能脱离上下文使用、等待补证后人工转正的情报。"""

    origin_run_id: str
    defer_reasons: list[str]
    promotion_requirements: list[str]
    priority: str
    entry: Entry
    status: str = "deferred"
    added: str | None = None

    def __post_init__(self) -> None:
        if self.status != "deferred":
            raise EntryError("待核记录 status 必须是 deferred")
        if not self.origin_run_id.strip():
            raise EntryError("待核记录缺 origin_run_id")
        if self.priority not in DEFERRED_PRIORITIES:
            raise EntryError("待核记录 priority 只能是 high/medium/low")
        for name, values in (
            ("defer_reasons", self.defer_reasons),
            ("promotion_requirements", self.promotion_requirements),
        ):
            if not isinstance(values, list) or not values or not all(
                isinstance(value, str) and value.strip() for value in values
            ):
                raise EntryError(f"待核记录 {name} 必须是非空字符串数组")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "origin_run_id": self.origin_run_id,
            "defer_reasons": self.defer_reasons,
            "promotion_requirements": self.promotion_requirements,
            "priority": self.priority,
            "added": self.added,
            "entry": self.entry.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeferredRecord":
        if not isinstance(data, dict) or not isinstance(data.get("entry"), dict):
            raise EntryError("待核记录必须包含 entry object")
        return cls(
            status=data.get("status", "deferred"),
            origin_run_id=str(data.get("origin_run_id", "")),
            defer_reasons=data.get("defer_reasons", []),
            promotion_requirements=data.get("promotion_requirements", []),
            priority=data.get("priority", "medium"),
            added=data.get("added"),
            entry=Entry.from_dict(data["entry"]),
        )


@dataclass
class DeferOutcome:
    added: list[DeferredRecord]
    skipped: list[DeferredRecord]
    rejected: list[tuple[int, str]]
    claim_reviews: list[ClaimReview] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        counts = {
            "added": len(self.added),
            "skipped": len(self.skipped),
            "rejected": len(self.rejected),
        }
        for classification in CLAIM_CLASSIFICATIONS:
            counts[f"claim_{classification}"] = sum(
                review.classification == classification for review in self.claim_reviews
            )
        return counts


@dataclass
class PromotionOutcome:
    record: DeferredRecord
    add_outcome: AddOutcome
    removed: bool
    already_formal: bool


@dataclass
class AddOutcome:
    """一次追加的结果。dry-run 与真写用同一个形状，方便 diff 前后对照。"""

    added: list[Entry]
    skipped: list[Entry]
    rejected: list[tuple[int, str]]
    new_companies: dict[str, str]
    claim_reviews: list[ClaimReview] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        counts = {
            "added": len(self.added),
            "skipped": len(self.skipped),
            "rejected": len(self.rejected),
            "new_companies": len(self.new_companies),
        }
        for classification in CLAIM_CLASSIFICATIONS:
            counts[f"claim_{classification}"] = sum(
                review.classification == classification for review in self.claim_reviews
            )
        return counts


def _claim_ref(entry: Entry, pool: str) -> dict[str, Any]:
    return {
        "pool": pool,
        "id": entry.id,
        "date": entry.date,
        "title": entry.title,
        "media": entry.media,
        "quote_where": entry.quote_where,
        "claim": entry.claim,
    }


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _values_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_value, right_value = left["value"], right["value"]
    tolerance = max(left.get("tolerance", 0), right.get("tolerance", 0))
    if all(not isinstance(value, bool) and isinstance(value, (int, float)) for value in (left_value, right_value)):
        return abs(left_value - right_value) <= tolerance
    if (
        isinstance(left_value, list) and isinstance(right_value, list)
        and len(left_value) == len(right_value) == 2
        and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in [*left_value, *right_value])
    ):
        return all(abs(a - b) <= tolerance for a, b in zip(left_value, right_value))
    return _canonical(left_value) == _canonical(right_value)


def _review_claim(
    index: int,
    candidate: Entry,
    pool: list[tuple[str, Entry]],
) -> ClaimReview:
    claim = candidate.claim or {}
    related = [
        (source, entry) for source, entry in pool
        if entry.claim
        and entry.claim.get("metric_key") == claim.get("metric_key")
        and entry.claim.get("period") == claim.get("period")
    ]
    if not related:
        return ClaimReview(index, "new", _claim_ref(candidate, "candidate"))

    comparable: list[tuple[str, Entry]] = []
    for source, entry in related:
        other = entry.claim or {}
        same_scope = _canonical(other.get("scope")) == _canonical(claim.get("scope"))
        same_unit = other.get("unit") == claim.get("unit")
        left_basis, right_basis = other.get("basis"), claim.get("basis")
        same_known_basis = bool(left_basis and right_basis and left_basis == right_basis)
        if same_scope and same_unit and same_known_basis:
            comparable.append((source, entry))
    corroborating = [
        (source, entry) for source, entry in comparable
        if _values_equal(entry.claim or {}, claim)
    ]
    conflicting = [
        (source, entry) for source, entry in comparable
        if not _values_equal(entry.claim or {}, claim)
    ]
    if conflicting:
        matches = [*conflicting, *corroborating]
        classification = "conflicting"
    elif corroborating:
        matches = corroborating
        classification = "corroborating"
    else:
        matches = related
        classification = "different_scope"
    return ClaimReview(
        index,
        classification,
        _claim_ref(candidate, "candidate"),
        [_claim_ref(entry, source) for source, entry in matches],
    )


def _probe_id(raw: Entry) -> str | None:
    try:
        return raw.id or (make_entry_id(raw) if raw.date and raw.title else None)
    except Exception:  # invalid claim 交给 normalize 返回可读错误
        return raw.id or (
            make_id(raw.date, raw.url, raw.title) if raw.date and raw.title else None
        )


class Store:
    def __init__(self, base: Paths) -> None:
        self.base = base
        self.root = base.intel
        self.entries_file = self.root / ENTRIES_NAME
        self.deferred_file = self.root / DEFERRED_NAME
        self.registry_file = self.root / REGISTRY_NAME

    def load(self) -> list[Entry]:
        """只读正式库。公司、主题和档案查询不会混入待核项。"""
        if not self.entries_file.is_file():
            return []
        out: list[Entry] = []
        for lineno, line in enumerate(
            self.entries_file.read_text(encoding="utf-8").splitlines(), start=1
        ):
            text = line.strip()
            if not text:
                continue
            try:
                out.append(Entry.from_dict(json.loads(text)))
            except (json.JSONDecodeError, TypeError) as exc:
                raise EntryError(f"{self.entries_file} 第 {lineno} 行解析失败：{exc}") from exc
        return out

    def load_deferred(self) -> list[DeferredRecord]:
        """读取跨批次待核池；坏行同样精确报行号。"""
        if not self.deferred_file.is_file():
            return []
        out: list[DeferredRecord] = []
        for lineno, line in enumerate(
            self.deferred_file.read_text(encoding="utf-8").splitlines(), start=1
        ):
            text = line.strip()
            if not text:
                continue
            try:
                out.append(DeferredRecord.from_dict(json.loads(text)))
            except (json.JSONDecodeError, TypeError, EntryError) as exc:
                raise EntryError(f"{self.deferred_file} 第 {lineno} 行解析失败：{exc}") from exc
        return out

    def ids(self) -> set[str]:
        return {entry.id for entry in self.load() if entry.id}

    def registry(self) -> dict[str, str]:
        if not self.registry_file.is_file():
            return {}
        return json.loads(self.registry_file.read_text(encoding="utf-8"))

    def add(
        self,
        entries: list[Entry],
        *,
        commit: bool,
        exclude_deferred_ids: set[str] | None = None,
    ) -> AddOutcome:
        """校验、去重，并与正式库、待核池及本批主张动态比较。"""
        existing_entries = self.load()
        existing = {entry.id for entry in existing_entries if entry.id}
        excluded = exclude_deferred_ids or set()
        deferred_entries = [
            record.entry for record in self.load_deferred()
            if record.entry.id not in excluded
        ]
        comparison_pool = [
            *(("formal", entry) for entry in existing_entries),
            *(("deferred", entry) for entry in deferred_entries),
        ]
        registry = self.registry()
        added: list[Entry] = []
        skipped: list[Entry] = []
        rejected: list[tuple[int, str]] = []
        new_companies: dict[str, str] = {}
        claim_reviews: list[ClaimReview] = []
        seen_in_batch: set[str] = set()

        for index, raw in enumerate(entries, start=1):
            probe = _probe_id(raw)
            if probe and (probe in existing or probe in seen_in_batch):
                raw.id = probe
                skipped.append(raw)
                seen_in_batch.add(probe)
                continue
            try:
                item, unregistered = normalize(raw, registry=registry)
            except (EntryError, Exception) as exc:  # noqa: BLE001
                rejected.append((index, str(exc)))
                continue
            for name in unregistered:
                from . import vocab

                key = vocab.normalize_other(name)
                if key not in registry and key not in new_companies:
                    new_companies[key] = name
            if item.id in existing or item.id in seen_in_batch:
                skipped.append(item)
                continue
            seen_in_batch.add(item.id)
            if item.claim:
                claim_reviews.append(_review_claim(index, item, comparison_pool))
            comparison_pool.append(("batch", item))
            added.append(item)

        if commit and (added or new_companies):
            self._append(added)
            if new_companies:
                merged = {**registry, **new_companies}
                write_text_atomic(
                    self.registry_file,
                    json.dumps(dict(sorted(merged.items())), ensure_ascii=False, indent=2) + "\n",
                )

        return AddOutcome(added, skipped, rejected, new_companies, claim_reviews)

    def defer(self, records: list[DeferredRecord], *, commit: bool) -> DeferOutcome:
        """把高价值但尚不能独立使用的条目放入待核池。"""
        formal_ids = self.ids()
        current = self.load_deferred()
        deferred_ids = {record.entry.id for record in current if record.entry.id}
        comparison_pool = [
            *(("formal", entry) for entry in self.load()),
            *(("deferred", record.entry) for record in current),
        ]
        registry = self.registry()
        added: list[DeferredRecord] = []
        skipped: list[DeferredRecord] = []
        rejected: list[tuple[int, str]] = []
        claim_reviews: list[ClaimReview] = []
        seen_in_batch: set[str] = set()

        for index, record in enumerate(records, start=1):
            raw = record.entry
            probe = _probe_id(raw)
            if probe and (probe in formal_ids or probe in deferred_ids or probe in seen_in_batch):
                raw.id = probe
                skipped.append(record)
                seen_in_batch.add(probe)
                continue
            try:
                item, _unregistered = normalize(raw, registry=registry)
            except (EntryError, Exception) as exc:  # noqa: BLE001
                rejected.append((index, str(exc)))
                continue
            if item.id in formal_ids or item.id in deferred_ids or item.id in seen_in_batch:
                record.entry = item
                skipped.append(record)
                continue
            record.entry = item
            record.added = record.added or datetime.now(timezone.utc).astimezone().isoformat(
                timespec="seconds"
            )
            seen_in_batch.add(item.id)
            if item.claim:
                claim_reviews.append(_review_claim(index, item, comparison_pool))
            comparison_pool.append(("batch", item))
            added.append(record)

        if commit:
            self._append_deferred(added)
        return DeferOutcome(added, skipped, rejected, claim_reviews)

    def replace(self, entries: list[Entry]) -> None:
        """原子重写真源；Entry 往返会保留可选 claim。"""
        payload = "".join(
            json.dumps(entry.to_dict(), ensure_ascii=False, sort_keys=True) + "\n"
            for entry in entries
        )
        write_text_atomic(self.entries_file, payload)

    def replace_deferred(self, records: list[DeferredRecord]) -> None:
        """原子重写待核池；只由转正流程调用。"""
        payload = "".join(
            json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) + "\n"
            for record in records
        )
        write_text_atomic(self.deferred_file, payload)

    def promote(self, identifier: str, *, commit: bool) -> PromotionOutcome:
        """唯一转正入口；默认预演，确认后先追加正式库再移出待核池。"""
        records = self.load_deferred()
        matches = [
            record for record in records
            if record.entry.id == identifier or identifier in record.entry.title
        ]
        if len(matches) != 1:
            raise EntryError(f"按 {identifier!r} 匹配到 {len(matches)} 条待核记录，需要唯一")
        target = matches[0]
        target_id = target.entry.id or _probe_id(target.entry)
        if not target_id:
            raise EntryError("待核记录没有可计算的稳定 id")

        formal_ids = self.ids()
        already_formal = target_id in formal_ids
        if already_formal:
            outcome = AddOutcome([], [target.entry], [], {}, [])
        else:
            outcome = self.add(
                [Entry.from_dict(target.entry.to_dict())],
                commit=commit,
                exclude_deferred_ids={target_id},
            )

        removed = False
        if commit and (already_formal or outcome.added) and not outcome.rejected:
            self.replace_deferred([
                record for record in records if record.entry.id != target_id
            ])
            removed = True
        return PromotionOutcome(target, outcome, removed, already_formal)

    def _append_deferred(self, records: list[DeferredRecord]) -> None:
        if not records:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True)
            for record in records
        ]
        payload = "\n".join(lines) + "\n"
        if self.deferred_file.is_file():
            with open(self.deferred_file, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
        else:
            write_text(self.deferred_file, payload)

    def _append(self, entries: list[Entry]) -> None:
        if not entries:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(entry.to_dict(), ensure_ascii=False, sort_keys=True) for entry in entries]
        payload = "\n".join(lines) + "\n"
        if self.entries_file.is_file():
            with open(self.entries_file, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
        else:
            write_text(self.entries_file, payload)


def load_entries(base: Paths) -> list[Entry]:
    return Store(base).load()


def entries_path(base: Paths) -> Path:
    return Store(base).entries_file
