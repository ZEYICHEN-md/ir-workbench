"""洞察底稿：读写、校验、过期标记，以及 Markdown 投影。

洞察底稿是**独立真源**，不随指标快照重建而变动（ADR 0001）。
维度固定三槽：亮点 / 风险 / 展望，每槽最多 2 条，可缺槽。
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from workbench.fileio import write_text, write_text_atomic

from .jsonio import dumps_canonical
from .paths import DomainPaths

PERIODS = ("weekly", "monthly", "quarterly")
TAGS = ("highlight", "risk", "outlook")
MAX_PER_TAG = 2

TAG_LABELS = {
    "zh": {"highlight": "亮点", "risk": "风险", "outlook": "展望"},
    "en": {"highlight": "Highlight", "risk": "Risk", "outlook": "Outlook"},
}
PERIOD_LABELS = {
    "zh": {"weekly": "周度", "monthly": "月度", "quarterly": "季度"},
    "en": {"weekly": "Weekly", "monthly": "Monthly", "quarterly": "Quarterly"},
}

_NUM_SPAN = re.compile(r'<span class="num-highlight">([^<]*)</span>')
_ANY_TAG = re.compile(r"<[^>]+>")


class InsightsError(RuntimeError):
    pass


def load(paths: DomainPaths) -> dict:
    if not paths.insights_canonical.is_file():
        raise InsightsError(f"缺少洞察底稿：{paths.insights_canonical}")
    return json.loads(paths.insights_canonical.read_text(encoding="utf-8"))


def save(paths: DomainPaths, data: dict) -> None:
    write_text_atomic(paths.insights_canonical, dumps_canonical(data) + "\n")


def validate(data: dict) -> None:
    for period in PERIODS:
        block = data.get(period)
        if not block:
            continue
        for lang in ("zh", "en"):
            _validate_items(block.get(lang) or [], period, lang)


def _validate_items(items: list, period: str, lang: str) -> None:
    counts = {tag: 0 for tag in TAGS}
    for item in items:
        tag = item.get("tag")
        if tag not in TAGS:
            raise InsightsError(f"{period}.{lang}：标签不合法 {tag!r}（只能是 {'/'.join(TAGS)}）")
        counts[tag] += 1
        if counts[tag] > MAX_PER_TAG:
            raise InsightsError(f"{period}.{lang}：标签 {tag} 超过 {MAX_PER_TAG} 条")
        if not item.get("title") or not item.get("body"):
            raise InsightsError(f"{period}.{lang}：缺 title 或 body")
        refs = item.get("refs")
        if not isinstance(refs, list) or not refs:
            raise InsightsError(f"{period}.{lang}：每条洞察都要有 refs[]（可核对的指标与数字）")


def mark_all_stale(data: dict) -> dict:
    meta = data.setdefault("meta", {})
    stale = meta.setdefault("stale", {})
    for period in PERIODS:
        stale[period] = True
    return data


def mark_stale_if_outdated(paths: DomainPaths) -> list[str]:
    """洞察依据的数据日期落后于快照时，标记全部粒度过期。返回**新**标记的粒度。

    为什么要自动做：SKILL 承诺「指标快照更新后，若对应粒度洞察未重新确认，会被标为
    可能过期」，但此前 `mark_all_stale` 只有手动命令会调用——merge 完全不碰它。
    实测后果是洞察 `basedOnTravelJsonUpdatedAt` 停在 2026-08-08、快照已到 2026-08-15，
    而 `stale` 三项全是 `False`，看板会拿上一周的洞察配这一周的图表且不作任何提示。

    判据用「洞察依据日期 vs 快照日期」而不是「本次 diff 是否为空」：空跑一次也不该把
    真实的落后状态抹掉，而洞察若已基于最新数据确认，空跑也不会被误标。
    """
    current = snapshot_data_update(paths)
    if not current or not paths.insights_canonical.is_file():
        return []

    data = load(paths)
    meta = data.setdefault("meta", {})
    if (meta.get("basedOnTravelJsonUpdatedAt") or "") == current:
        return []

    stale = meta.setdefault("stale", {})
    newly = [period for period in PERIODS if not stale.get(period)]
    if not newly:
        return []

    mark_all_stale(data)
    save(paths, data)
    return newly


def snapshot_data_update(paths: DomainPaths) -> str | None:
    if not paths.snapshot.is_file():
        return None
    snapshot = json.loads(paths.snapshot.read_text(encoding="utf-8"))
    return (snapshot.get("meta") or {}).get("dataUpdate") or None


# --- Markdown 投影 ---


def html_body_to_md(body: str | None) -> str:
    text = _NUM_SPAN.sub(r"**\1**", str(body or ""))
    return _ANY_TAG.sub("", text).strip()


def archive_key(data: dict) -> str:
    meta = data.get("meta") or {}
    confirmed = (meta.get("confirmedAt") or {}).get("weekly")
    return meta.get("basedOnTravelJsonUpdatedAt") or confirmed or _dt.date.today().isoformat()


def _stale_summary(data: dict) -> str:
    stale = (data.get("meta") or {}).get("stale") or {}
    return ", ".join(period for period in PERIODS if stale.get(period))


def render_markdown(data: dict, lang: str) -> str:
    labels = TAG_LABELS.get(lang, TAG_LABELS["zh"])
    period_labels = PERIOD_LABELS.get(lang, PERIOD_LABELS["zh"])
    meta = data.get("meta") or {}
    stale_parts = _stale_summary(data)
    title = "Travel industry dashboard insights" if lang == "en" else "旅游行业数据看板 · 洞察"
    based_on = meta.get("basedOnTravelJsonUpdatedAt") or ""
    confirmed = meta.get("confirmedAt") or {}

    lines: list[str] = [
        "---",
        f"title: {title}",
        f"lang: {lang}",
        f"basedOnTravelJsonUpdatedAt: {based_on}",
        "confirmedAt:",
        *[f"  {period}: {confirmed.get(period) or ''}" for period in PERIODS],
        f"stale: {stale_parts or 'none'}",
        "source: data/canonical/travel-insights.json",
        "---",
        "",
        f"# {title}",
        "",
    ]

    if lang == "zh":
        lines.append(
            f"> 数据截至 **{based_on or '—'}**；由 `travel-insights.json` 投影生成，供简报/飞书等复用。"
        )
        lines.append(f"> ⚠️ 可能过期粒度：{stale_parts}" if stale_parts else "")
    else:
        lines.append(
            f"> Data as of **{based_on or '—'}**; projected from `travel-insights.json` "
            "for reuse in briefs and docs."
        )
        lines.append(f"> ⚠️ Possibly stale: {stale_parts}" if stale_parts else "")
    lines.append("")

    for period in PERIODS:
        items = (data.get(period) or {}).get(lang) or []
        if not items:
            continue
        lines.extend([f"## {period_labels[period]}", ""])
        by_tag: dict[str, list] = {tag: [] for tag in TAGS}
        for item in items:
            if item.get("tag") in by_tag:
                by_tag[item["tag"]].append(item)
        for tag in TAGS:
            group = by_tag[tag]
            if not group:
                continue
            lines.extend([f"### {labels[tag]}", ""])
            for item in group:
                lines.extend([f"#### {item['title']}", "", html_body_to_md(item.get("body")), ""])
                refs = item.get("refs") or []
                if refs:
                    joined = "；".join(refs) if lang == "zh" else "; ".join(refs)
                    lines.append(f"*引用：{joined}*" if lang == "zh" else f"*Refs: {joined}*")
                    lines.append("")

    deduped: list[str] = []
    for index, line in enumerate(lines):
        if line == "" and index > 0 and lines[index - 1] == "":
            continue
        deduped.append(line)
    return "\n".join(deduped).strip() + "\n"


def write_markdown(paths: DomainPaths, data: dict, *, archive: bool = False) -> list[Path]:
    written: list[Path] = []
    for lang in ("zh", "en"):
        content = render_markdown(data, lang)
        written.append(write_text(paths.insights_md_dir / f"travel-insights-{lang}.md", content))
        if archive:
            archive_dir = paths.insights_archive_dir / archive_key(data)
            written.append(write_text(archive_dir / f"travel-insights-{lang}.md", content))
    return written
