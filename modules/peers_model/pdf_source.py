"""PDF 两遍独立抽取与事实证据验证。"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pdfplumber

SKIP_ROLES = {"echo", "derived", "replay"}


class EvidenceError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _table_blob(tables) -> str:
    parts = []
    for table in tables or []:
        for row in table:
            for cell in row:
                if cell not in (None, ""):
                    parts.append(str(cell))
    return " ".join(parts)


def _page_blob(page, *, variant: str) -> str:
    if variant == "layout":
        text = page.extract_text(x_tolerance=2, y_tolerance=3, layout=True) or ""
    else:
        text = page.extract_text() or ""
    return text + "\n" + _table_blob(page.extract_tables() or [])


def extract_first_pass(path: Path) -> dict:
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise EvidenceError(f"PDF 不存在或格式不对：{path}")
    pages = []
    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            tables = page.extract_tables() or []
            pages.append({"page": index, "text": text, "tables": tables})
    if not any((page["text"] or "").strip() or page["tables"] for page in pages):
        raise EvidenceError(f"{path.name} 没有可提取文字，可能是扫描件")
    return {
        "file": str(path.resolve()), "sha256": sha256(path),
        "page_count": len(pages), "pages": pages,
    }


def write_extract(payload: dict, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", str(text)).replace(",", "").lower()


def _as_number(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _numbers_in_text(text: str) -> list[float]:
    cleaned = str(text).replace(",", "").replace("−", "-").replace("–", "-").replace("%", "")
    values = []
    for token in re.findall(r"\(?-?\d+(?:\.\d+)?\)?", cleaned):
        negative = token.startswith("(") and token.endswith(")")
        raw = token.strip("()")
        try:
            value = float(raw)
        except ValueError:
            continue
        values.append(-abs(value) if negative else value)
    return values


def _near(left: float, right: float) -> bool:
    return abs(left - right) <= max(1e-6, abs(right) * 1e-6)


def verify_facts(facts: dict, *, variant: str = "layout") -> list[dict]:
    """重新打开原 PDF 验证每个结构化值；从不读取第一遍 extract JSON。"""
    findings = []
    seen: dict[tuple[str, int], object] = {}
    for index, fact in enumerate(facts.get("facts", []), 1):
        role = str(fact.get("role") or "disclosed").strip().lower()
        sheet, row = str(fact.get("sheet", "")), int(fact.get("row", 0) or 0)
        value = fact.get("value")
        model_unit = str(fact.get("unit", "")).strip()
        model_number = _as_number(value)
        if role in SKIP_ROLES:
            if not sheet or row <= 0 or value in (None, ""):
                findings.append({"ok": False, "fact": index, "error": f"{role} 行仍需 sheet/row/value"})
                continue
            findings.append({"ok": True, "fact": index, "sheet": sheet, "row": row, "skipped": role})
            continue
        if not sheet or row <= 0 or model_number is None or not model_unit:
            findings.append({"ok": False, "fact": index,
                             "error": "缺 sheet/row/数值 value/model unit"})
            continue
        key = (sheet, row)
        if key in seen and seen[key] != value:
            findings.append({"ok": False, "fact": index,
                             "error": f"同一单元格数值冲突：{seen[key]} vs {value}"})
            continue
        seen[key] = value

        source = fact.get("source") or {}
        path = Path(source.get("file", ""))
        page_number = int(source.get("page", 0) or 0)
        quote = str(source.get("quote", "")).strip()
        value_text = str(source.get("value_text", "")).strip()
        source_unit = str(source.get("unit", "")).strip()
        source_number = _as_number(source.get("numeric_value"))
        factor = _as_number(source.get("conversion_factor"))
        required = (
            ("file", path.is_file()), ("sha256", bool(source.get("sha256"))),
            ("page", page_number > 0), ("table/section", bool(str(source.get("table", "")).strip())),
            ("row/paragraph", bool(str(source.get("row", "")).strip())),
            ("quote", bool(quote)), ("value_text", bool(value_text)),
            ("source numeric_value", source_number is not None),
            ("source unit", bool(source_unit)), ("conversion_factor", factor is not None),
        )
        missing = [name for name, present in required if not present]
        if missing:
            findings.append({"ok": False, "fact": index,
                             "error": "证据缺字段：" + ", ".join(missing)})
            continue

        actual_hash = sha256(path)
        if str(source["sha256"]).lower() != actual_hash:
            findings.append({"ok": False, "fact": index, "error": "PDF SHA-256 已变化或填错"})
            continue
        if not _near(model_number, source_number * factor):
            findings.append({"ok": False, "fact": index,
                             "error": (f"单位换算不成立：{source_number} {source_unit} × {factor} "
                                       f"≠ {model_number} {model_unit}")})
            continue
        if not any(_near(source_number, token) for token in _numbers_in_text(value_text)):
            findings.append({"ok": False, "fact": index,
                             "error": "value_text 中找不到 source numeric_value"})
            continue

        try:
            with pdfplumber.open(path) as pdf:
                if page_number > len(pdf.pages):
                    raise EvidenceError(f"页码 {page_number} 超出 PDF 页数")
                fresh = _page_blob(pdf.pages[page_number - 1], variant=variant)
        except Exception as error:  # noqa: BLE001
            findings.append({"ok": False, "fact": index, "error": f"独立抽取失败：{error}"})
            continue

        page_norm, quote_norm, value_norm = _norm(fresh), _norm(quote), _norm(value_text)
        ok = bool(quote_norm and value_norm and value_norm in quote_norm and (
            quote_norm in page_norm or value_norm in page_norm
        ))
        findings.append({
            "ok": ok, "fact": index, "sheet": sheet, "row": row, "variant": variant,
            "model": {"value": value, "unit": model_unit},
            "source": {"file": str(path), "sha256": actual_hash, "page": page_number,
                       "table": source.get("table"), "source_row": source.get("row"),
                       "numeric_value": source_number, "unit": source_unit,
                       "conversion_factor": factor},
            **({"error": "独立抽取页面中找不到原话或数值文本"} if not ok else {}),
        })
    return findings


def load_facts(path: Path) -> dict:
    if not path.is_file():
        raise EvidenceError(f"facts 文件不存在：{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("facts"), list):
        raise EvidenceError("facts JSON 缺少 facts 数组")
    return payload
