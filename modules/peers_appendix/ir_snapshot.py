"""IR snapshot validation, model comparison, and human-readable rendering.

The snapshot is written only after a human/agent has read the source material.
This module validates and consumes it; it never fabricates financial values,
guidance, quotes, or writing claims.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().replace(",", "").replace("%", ""))
    except ValueError:
        return None


def _near(left: float | None, right: float | None, tolerance: float) -> bool:
    return (
        left is not None
        and right is not None
        and abs(float(left) - float(right)) <= tolerance
    )


def load_snapshot(
    path: Path,
    *,
    ticker: str | None = None,
    quarter: str | None = None,
) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"ir_snapshot 必须是 JSON object：{path}")
    for key in ("ticker", "quarter", "actuals", "sources"):
        if key not in data:
            raise ValueError(f"ir_snapshot 缺少 {key!r}：{path}")
    if ticker and str(data["ticker"]).upper() != ticker.upper():
        raise ValueError(
            f"ir_snapshot.ticker={data['ticker']}，当前公司是 {ticker}。"
        )
    if quarter and data["quarter"] != quarter:
        raise ValueError(
            f"ir_snapshot.quarter={data['quarter']}，当前季度是 {quarter}。"
        )
    if not isinstance(data["actuals"], dict) or not data["actuals"]:
        raise ValueError("ir_snapshot.actuals 不能为空。")
    if not isinstance(data["sources"], list) or not data["sources"]:
        raise ValueError("ir_snapshot.sources 不能为空。")
    for key, meta in data["actuals"].items():
        if not isinstance(meta, dict) or meta.get("value") is None:
            raise ValueError(f"ir_snapshot.actuals.{key} 缺 value。")
    return data


def resolve_material_path(materials_dir: Path, source: str) -> Path | None:
    direct = materials_dir / source
    stem = Path(source).stem
    candidates = (
        direct,
        materials_dir / Path(source).name,
        materials_dir / f"{stem}.txt",
        materials_dir / f"{stem}.md",
        direct.with_suffix(".txt"),
        direct.with_suffix(".md"),
    )
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file():
            return candidate
    return None


def missing_source_materials(snapshot: dict, materials_dir: Path) -> list[str]:
    return [
        str(source)
        for source in snapshot.get("sources", [])
        if resolve_material_path(materials_dir, str(source)) is None
    ]


def check_fill_vs_snapshot(
    fill: dict,
    snapshot: dict,
    *,
    absolute_tolerance: float = 0.51,
) -> list[dict]:
    findings: list[dict] = []
    by_row = {
        int(item["row"]): item
        for item in fill.get("inputs", [])
        if item.get("value") is not None
    }
    for key, meta in snapshot.get("actuals", {}).items():
        if not isinstance(meta, dict) or meta.get("model_row") is None:
            continue
        row = int(meta["model_row"])
        expected = _num(meta.get("value"))
        item = by_row.get(row)
        got = _num(item.get("value")) if item else None
        ok = _near(expected, got, absolute_tolerance)
        findings.append(
            {
                "severity": "OK" if ok else "FAIL",
                "kind": "ir_snapshot",
                "name": f"fill_vs_snapshot_{key}",
                "row": row,
                "expected": expected,
                "got": got,
            }
        )
    return findings


def check_model_vs_snapshot(
    values: dict[int, object],
    snapshot: dict,
    *,
    absolute_tolerance: float = 0.51,
    yoy_tolerance: float = 0.012,
) -> list[dict]:
    findings: list[dict] = []
    for key, meta in snapshot.get("actuals", {}).items():
        if not isinstance(meta, dict) or meta.get("model_row") is None:
            continue
        row = int(meta["model_row"])
        expected = _num(meta.get("value"))
        got = _num(values.get(row))
        ok = _near(expected, got, absolute_tolerance)
        findings.append(
            {
                "severity": "OK" if ok else "FAIL",
                "kind": "ir_snapshot",
                "name": f"model_vs_snapshot_{key}",
                "row": row,
                "expected": expected,
                "got": got,
            }
        )
        if meta.get("yoy") is not None and meta.get("yoy_model_row") is not None:
            yoy_row = int(meta["yoy_model_row"])
            expected_yoy = _num(meta["yoy"])
            got_yoy = _num(values.get(yoy_row))
            yoy_ok = _near(expected_yoy, got_yoy, yoy_tolerance)
            findings.append(
                {
                    "severity": "OK" if yoy_ok else "FAIL",
                    "kind": "ir_snapshot",
                    "name": f"model_yoy_vs_snapshot_{key}",
                    "row": yoy_row,
                    "expected": expected_yoy,
                    "got": got_yoy,
                }
            )
    return findings


def _automatic_tokens(text: str) -> list[str]:
    tokens = [match.group(0) for match in re.finditer(r"\d+(?:\.\d+)?%?", text)]
    return list(dict.fromkeys(tokens))[:12]


def check_must_cover(
    body: str,
    snapshot: dict,
    *,
    materials_dir: Path,
    scope: str = "ops_finance",
) -> list[dict]:
    """Validate per-quarter writing claims and optional verbatim grounding."""
    findings: list[dict] = []
    for index, raw_item in enumerate(snapshot.get("must_cover_in_writing") or []):
        item = raw_item if isinstance(raw_item, dict) else {"claim": str(raw_item)}
        label = str(
            item.get("id")
            or item.get("claim")
            or item.get("text")
            or f"item_{index}"
        )
        item_scope = str(item.get("scope") or "all")
        if scope == "ops_finance" and item_scope == "strategy":
            continue
        required = bool(item.get("required", True))
        tokens = list(item.get("tokens") or [])
        if not tokens:
            tokens = _automatic_tokens(
                str(item.get("claim") or item.get("text") or "")
            )
        if not tokens:
            findings.append(
                {
                    "severity": "FAIL" if required else "WARN",
                    "kind": "must_cover",
                    "label": label,
                    "note": "缺 tokens[]，无法可靠机检。",
                }
            )
        else:
            missing = [token for token in tokens if str(token) not in body]
            findings.append(
                {
                    "severity": (
                        "OK" if not missing else ("FAIL" if required else "WARN")
                    ),
                    "kind": "must_cover",
                    "label": label,
                    "missing": missing,
                }
            )
        quote = item.get("quote")
        if quote:
            source_path = resolve_material_path(
                materials_dir, str(item.get("source") or "")
            )
            if source_path is None:
                findings.append(
                    {
                        "severity": "FAIL" if required else "WARN",
                        "kind": "must_cover_quote",
                        "label": label,
                        "note": f"找不到 quote 来源 {item.get('source')!r}。",
                    }
                )
            else:
                source_text = re.sub(
                    r"\s+",
                    " ",
                    source_path.read_text(encoding="utf-8", errors="ignore"),
                ).strip()
                normalized_quote = re.sub(r"\s+", " ", str(quote)).strip()
                found = bool(normalized_quote) and normalized_quote in source_text
                findings.append(
                    {
                        "severity": (
                            "OK" if found else ("FAIL" if required else "WARN")
                        ),
                        "kind": "must_cover_quote",
                        "label": label,
                        "source": source_path.name,
                        "note": None if found else "原话未在来源文件中找到。",
                    }
                )
    return findings


def render_markdown(snapshot: dict) -> str:
    lines = [
        f"# {snapshot['ticker']} {snapshot['quarter']} IR Snapshot",
        "",
        "> 由 ir_snapshot.json 机械渲染；数字只改 JSON，不手改本页。",
        "",
        "**Sources:** " + ", ".join(map(str, snapshot.get("sources") or [])),
        "",
        "## Actuals",
        "",
        "| Key | Value | YoY | Model row |",
        "|---|---:|---:|---:|",
    ]
    for key, meta in snapshot["actuals"].items():
        yoy = meta.get("yoy")
        yoy_text = (
            "—"
            if yoy is None
            else f"{float(yoy) * 100:.1f}%".replace(".0%", "%")
        )
        lines.append(
            f"| {key} | {meta.get('value')} | {yoy_text} | "
            f"{meta.get('model_row', '—')} |"
        )
    if snapshot.get("guidance"):
        lines += [
            "",
            "## Guidance",
            "",
            "```json",
            json.dumps(snapshot["guidance"], ensure_ascii=False, indent=2),
            "```",
        ]
    if snapshot.get("must_cover_in_writing"):
        lines += ["", "## Writing must-cover", ""]
        for item in snapshot["must_cover_in_writing"]:
            if isinstance(item, dict):
                lines.append(
                    "- [ ] "
                    + str(item.get("claim") or item.get("text") or item.get("id"))
                )
            else:
                lines.append(f"- [ ] {item}")
    return "\n".join(lines) + "\n"


def write_markdown(snapshot_path: Path, out: Path) -> Path:
    snapshot = load_snapshot(snapshot_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(snapshot), encoding="utf-8", newline="\n")
    return out
