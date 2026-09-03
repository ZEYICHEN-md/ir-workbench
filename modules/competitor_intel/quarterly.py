"""季度官方材料/电话会进入公司情报库的两阶段门面。

旧 ``peers_rs_update`` 只作为只读原件库；本模块扫描、校验并在 ``scratch``
生成同一份可审核草稿。正式写入仍唯一委托给 :class:`Store`。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workbench.fileio import write_text_atomic

from .entry import Entry
from .store import AddOutcome, Store


class QuarterlyError(ValueError):
    """季度材料包或候选条目不满足可核对契约。"""


@dataclass
class QuarterlyPlan:
    manifest_path: Path
    draft_path: Path
    review_path: Path
    manifest: dict[str, Any]
    entries: list[Entry]
    outcome: AddOutcome
    exception_indexes: list[int]
    auto_outcome: AddOutcome | None = None


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _classify(path: Path) -> tuple[str, str]:
    name = path.name.lower()
    if "10-q" in name or "8-k" in name:
        return "regulatory-filing", "P0"
    if path.suffix.lower() == ".txt":
        return "derived", "P2"
    if "sentiment" in name:
        return "derived", "P2"
    if "broker" in name or "t_e" in name or "transcript" in name:
        return "third-party-transcript", "P1"
    if any(token in name for token in (
        "earnings release", "earnings-release", "prepared remarks", "presentation",
        "shareholder-letter",
    )):
        return "company-ir", "P0"
    return "derived", "P2"


def artifact_paths(base, company: str, period: str) -> tuple[Path, Path, Path]:
    target = base.scratch / "intel-quarterly" / company.upper() / period
    return target / "source-manifest.json", target / "draft.json", target / "review.md"


def scan_source_pack(base, company: str, period: str, source_pack: Path) -> dict[str, Any]:
    pack = source_pack.resolve()
    root = base.root.resolve()
    if not pack.is_dir():
        raise QuarterlyError(f"季度材料目录不存在：{source_pack}")
    try:
        pack.relative_to(root)
    except ValueError as exc:
        raise QuarterlyError("季度材料目录必须位于当前工作区内") from exc
    if pack.name.upper() != period.upper() or pack.parent.name.upper() != company.upper():
        raise QuarterlyError(
            f"材料目录应以 <公司>/<期次> 结尾；收到 {pack.parent.name}/{pack.name}"
        )

    files: list[dict[str, Any]] = []
    for path in sorted(item for item in pack.rglob("*") if item.is_file()):
        source_type, authority = _classify(path)
        files.append({
            "path": path.relative_to(root).as_posix(),
            "pack_path": path.relative_to(pack).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "source_type": source_type,
            "source_authority": authority,
        })
    if not files:
        raise QuarterlyError("季度材料目录为空")

    signature = json.dumps(
        [{"path": row["path"], "sha256": row["sha256"]} for row in files],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "schema_version": 1,
        "company": company.upper(),
        "period": period,
        "source_pack": pack.relative_to(root).as_posix(),
        "generated_at": _now(),
        "source_pack_digest": hashlib.sha256(signature.encode("utf-8")).hexdigest(),
        "files": files,
    }


def _load_rows(candidate_file: Path) -> list[dict[str, Any]]:
    if not candidate_file.is_file():
        raise QuarterlyError(f"找不到季度候选文件：{candidate_file}")
    try:
        payload = json.loads(candidate_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QuarterlyError(f"季度候选文件无法解析：{exc}") from exc
    if isinstance(payload, list):
        rows = payload
    else:
        defaults = payload.get("defaults", {})
        sources = payload.get("sources", {})
        raw_rows = payload.get("entries", [])
        if not isinstance(defaults, dict) or not isinstance(sources, dict):
            raise QuarterlyError("季度候选 defaults/sources 必须是 object")
        rows = []
        for index, raw in enumerate(raw_rows, start=1):
            if not isinstance(raw, dict):
                raise QuarterlyError(f"季度候选第 {index} 条必须是 object")
            source_key = raw.get("source")
            if source_key and source_key not in sources:
                raise QuarterlyError(f"季度候选第 {index} 条 source={source_key!r} 未定义")
            source = sources.get(source_key, {}) if source_key else {}
            if source_key and not isinstance(source, dict):
                raise QuarterlyError(f"季度候选第 {index} 条 source={source_key!r} 不是 object")
            rows.append({**defaults, **source, **{k: v for k, v in raw.items() if k != "source"}})
    if not isinstance(rows, list) or not rows:
        raise QuarterlyError("季度候选文件没有 entries")
    if not all(isinstance(row, dict) for row in rows):
        raise QuarterlyError("季度候选 entries 必须全部是 object")
    return rows


def _validate_references(
    base, company: str, period: str, entries: list[Entry], manifest: dict[str, Any]
) -> None:
    indexed = {row["path"]: row for row in manifest["files"]}
    problems: list[str] = []
    for index, entry in enumerate(entries, start=1):
        if entry.channel != "quarterly":
            problems.append(f"第 {index} 条 channel 必须是 quarterly")
        if (entry.period or "").upper() != period.upper():
            problems.append(f"第 {index} 条 period 必须是 {period}")
        if company.upper() not in [name.upper() for name in entry.companies]:
            problems.append(f"第 {index} 条 companies 必须包含 {company.upper()}")
        source_path = (entry.source_path or "").replace("\\", "/")
        source = indexed.get(source_path)
        if not source:
            problems.append(f"第 {index} 条 source_path 不在本次材料 manifest：{source_path}")
            continue

        if Path(source_path).suffix.lower() != ".pdf":
            problems.append(f"第 {index} 条须指向可按页核对的 PDF 原件")
        if entry.source_type != source["source_type"]:
            problems.append(
                f"第 {index} 条 source_type={entry.source_type}，manifest={source['source_type']}"
            )
        if entry.source_authority != source["source_authority"]:
            problems.append(
                f"第 {index} 条 source_authority={entry.source_authority}，"
                f"manifest={source['source_authority']}"
            )
        if Path(source_path).name not in (entry.quote_where or ""):
            problems.append(f"第 {index} 条 quote_where 必须写出原件文件名")
        if not re.search(r"第\s*\d+\s*页", entry.quote_where or ""):
            problems.append(f"第 {index} 条 quote_where 必须精确到 PDF 页码")
    if problems:
        raise QuarterlyError("季度候选来源校验未通过：\n- " + "\n- ".join(problems))


def _exception_indexes(entries: list[Entry], outcome: AddOutcome) -> list[int]:
    """只把真正需要判断的项送人工；正常公司披露默认可直接入库。"""
    flagged = {
        review.index for review in outcome.claim_reviews
        if review.classification == "conflicting"
    }
    for review in outcome.claim_reviews:
        if review.classification != "different_scope":
            continue
        claim = review.candidate.get("claim") or {}
        scope = claim.get("scope") or {}
        has_unknown = any(str(value).strip().lower() == "unknown" for value in scope.values())
        if not claim.get("basis") or not scope or has_unknown:
            flagged.add(review.index)
    for index, entry in enumerate(entries, start=1):
        if entry.review_flags:
            flagged.add(index)
        if entry.claim and entry.claim.get("confidence") == "low":
            flagged.add(index)
        quote = entry.quote or ""
        if "[indiscernible]" in quote.lower() or "[inaudible]" in quote.lower():
            flagged.add(index)
    return sorted(flagged)


def _render_review(
    company: str,
    period: str,
    manifest: dict[str, Any],
    entries: list[Entry],
    outcome: AddOutcome,
    exception_indexes: list[int],
    auto_outcome: AddOutcome | None = None,
) -> str:
    if auto_outcome is None:
        headline = "> dry-run：正式库未写入。正常项正式运行时自动入库，只有异常项需人工确认。"
    elif exception_indexes:
        headline = "> 正常项已自动入库；下列标为“异常待审核”的条目尚未写入。"
    else:
        headline = "> 来源、口径与冲突校验均通过，本批正常项已自动写入正式库。"
    lines = [
        f"# {company} {period} · 季度情报处理记录", "", headline, "",
        "## 材料包", "",
        f"- 文件数：{len(manifest['files'])}",
        f"- SHA-256 包摘要：`{manifest['source_pack_digest']}`",
        f"- P0 / P1 / P2：{sum(r['source_authority'] == 'P0' for r in manifest['files'])} / "
        f"{sum(r['source_authority'] == 'P1' for r in manifest['files'])} / "
        f"{sum(r['source_authority'] == 'P2' for r in manifest['files'])}",
        "", "## 本批条目", "",
    ]
    reviews = {review.index: review for review in outcome.claim_reviews}
    added_ids = {entry.id for entry in (auto_outcome.added if auto_outcome else [])}
    for index, entry in enumerate(entries, start=1):
        if index in exception_indexes:
            disposition = "异常待审核"
        elif auto_outcome is None:
            disposition = "校验通过，正式运行时自动入库"
        elif entry.id in added_ids:
            disposition = "已自动入库"
        else:
            disposition = "正式库已存在，未重复写入"
        lines.extend([
            f"### {index}. {entry.title}", "", f"- 处理：{disposition}",
            f"- 结论：{entry.body}", f"- 原话：{entry.quote}",
            f"- 出处：{entry.quote_where}",
            f"- 来源级别：{entry.source_authority} · {entry.source_type}",
            f"- 主题：{', '.join(entry.topics)}",
        ])
        if entry.review_flags:
            lines.append(f"- 异常原因：{'；'.join(entry.review_flags)}")
        if entry.claim:
            review = reviews.get(index)
            classification = review.classification if review else "未审查"
            lines.extend([
                f"- 数据主张：`{entry.claim['metric_key']}` = {entry.claim['value']} "
                f"{entry.claim['unit']}（{entry.claim['period']}）",
                f"- 冲突审查：{classification}",
            ])
            if review and review.matches:
                lines.append(f"- 可比历史项：{len(review.matches)} 条（详见 draft.json）")
        lines.append("")
    lines.extend([
        "## 处理汇总", "", f"- 可入：{len(outcome.added)}",
        f"- 已存在：{len(outcome.skipped)}", f"- 异常待审核：{len(exception_indexes)}",
        f"- 被拒：{len(outcome.rejected)}", "",
    ])
    return "\n".join(lines)


def prepare(
    base,
    company: str,
    period: str,
    source_pack: Path,
    candidate_file: Path,
    store: Store,
    *,
    auto_commit: bool = False,
) -> QuarterlyPlan:
    company = company.upper()
    manifest = scan_source_pack(base, company, period, source_pack)
    entries = [Entry.from_dict(row) for row in _load_rows(candidate_file)]
    _validate_references(base, company, period, entries, manifest)
    outcome = store.add(entries, commit=False)
    if outcome.rejected:
        details = "; ".join(f"第 {i} 条 {reason}" for i, reason in outcome.rejected)
        raise QuarterlyError(f"季度候选未通过 Entry 校验：{details}")
    exception_indexes = _exception_indexes(entries, outcome)

    manifest_path, draft_path, review_path = artifact_paths(base, company, period)
    draft = {
        "schema_version": 2,
        "company": company,
        "period": period,
        "source_pack": manifest["source_pack"],
        "source_pack_digest": manifest["source_pack_digest"],
        "manifest_path": manifest_path.relative_to(base.root).as_posix(),
        "candidate_file": candidate_file.resolve().relative_to(base.root.resolve()).as_posix(),
        "generated_at": _now(),
        "committed": False,
        "exception_indexes": exception_indexes,
        "preview_counts": outcome.counts,
        "claim_reviews": [review.to_dict() for review in outcome.claim_reviews],
        "entries": [entry.to_dict() for entry in entries],
    }
    write_text_atomic(
        manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    write_text_atomic(
        draft_path, json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )

    auto_outcome = None
    if auto_commit:
        frozen = json.loads(draft_path.read_text(encoding="utf-8"))
        safe_entries = [
            Entry.from_dict(row) for index, row in enumerate(frozen["entries"], start=1)
            if index not in exception_indexes
        ]
        auto_outcome = store.add(safe_entries, commit=True)
        if auto_outcome.rejected:
            raise QuarterlyError("正常季度条目自动入库时出现拒收，请检查正式库状态")
        draft["auto_committed"] = True
        draft["last_auto_run_at"] = _now()
        draft["last_auto_run_counts"] = auto_outcome.counts
        formal_by_id = {entry.id: entry for entry in store.load() if entry.id}
        safe_ids = [entry.id for entry in safe_entries if entry.id in formal_by_id]
        added_times = [
            formal_by_id[identifier].added for identifier in safe_ids
            if formal_by_id[identifier].added
        ]
        draft["auto_committed_at"] = min(added_times) if added_times else _now()
        draft["auto_committed_entry_ids"] = safe_ids
        draft["auto_committed_entry_count"] = len(safe_ids)
        draft["committed"] = not exception_indexes
        write_text_atomic(
            draft_path, json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )

    write_text_atomic(
        review_path,
        _render_review(
            company, period, manifest, entries, outcome, exception_indexes, auto_outcome
        ),
    )
    return QuarterlyPlan(
        manifest_path, draft_path, review_path, manifest, entries, outcome,
        exception_indexes, auto_outcome,
    )


def commit(base, company: str, period: str, store: Store) -> tuple[dict[str, Any], AddOutcome]:
    company = company.upper()
    manifest_path, draft_path, _ = artifact_paths(base, company, period)
    if not draft_path.is_file() or not manifest_path.is_file():
        raise QuarterlyError("找不到已审核季度草稿；必须先完成 dry-run")
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    if draft.get("company") != company or draft.get("period") != period:
        raise QuarterlyError("季度草稿的公司或期次与本次提交不一致")
    source_pack = base.root / draft["source_pack"]
    current_manifest = scan_source_pack(base, company, period, source_pack)
    if current_manifest["source_pack_digest"] != draft.get("source_pack_digest"):
        raise QuarterlyError("季度原件在审核后发生变化；请重新 dry-run 并审核")

    entries = [Entry.from_dict(row) for row in draft.get("entries", [])]
    _validate_references(base, company, period, entries, current_manifest)
    exception_indexes = {
        int(index) for index in draft.get("exception_indexes") or []
    }
    if draft.get("auto_committed"):
        selected = [
            entry for index, entry in enumerate(entries, start=1)
            if index in exception_indexes
        ]
    else:
        selected = entries
    if not selected:
        empty = AddOutcome([], [], [], {}, [])
        draft["committed"] = True
        draft["committed_at"] = _now()
        draft["commit_counts"] = empty.counts
        write_text_atomic(
            draft_path, json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
        return draft, empty
    preview = store.add([Entry.from_dict(row.to_dict()) for row in selected], commit=False)
    if preview.rejected:
        raise QuarterlyError("已审核草稿现在无法通过校验；未写入正式库")
    outcome = store.add(selected, commit=True)
    if outcome.rejected:
        raise QuarterlyError("季度草稿提交出现拒收，请检查正式库状态")
    draft["committed"] = True
    draft["committed_at"] = _now()
    draft["commit_counts"] = outcome.counts
    write_text_atomic(
        draft_path, json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return draft, outcome
