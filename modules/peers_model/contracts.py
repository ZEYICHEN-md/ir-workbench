"""声明式工作簿合同。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from workbench.config import Config

HERE = Path(__file__).resolve().parent
ALIASES = {"MT": "MEITUAN", "3690": "MEITUAN", "TCEL": "TCEL", "0780": "TCEL"}


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class Contract:
    company: str
    workbook_key: str
    sheets: tuple[dict, ...]
    chart_sheets_by_kind: dict[str, tuple[str, ...]]

    @property
    def writable_sheets(self) -> set[str]:
        return {str(item["name"]) for item in self.sheets}

    @property
    def chart_sheets(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(
            sheet for sheets in self.chart_sheets_by_kind.values() for sheet in sheets
        ))

    def charts_for(self, period_kind: str) -> tuple[str, ...]:
        return self.chart_sheets_by_kind.get(period_kind, ())


def normalize_company(company: str) -> str:
    key = company.strip().upper()
    return ALIASES.get(key, key)


def load(company: str) -> Contract:
    company = normalize_company(company)
    path = HERE / "contracts" / f"{company.lower()}.json"
    if not path.is_file():
        known = ", ".join(p.stem.upper() for p in (HERE / "contracts").glob("*.json"))
        raise ContractError(f"不支持 {company}；已知公司：{known}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    chart_raw = raw.get("chart_sheets", {})
    if isinstance(chart_raw, list):
        chart_raw = {kind: chart_raw for kind in ("quarter", "half", "year")}
    return Contract(
        company=raw["company"], workbook_key=raw["workbook_key"],
        sheets=tuple(raw["sheets"]),
        chart_sheets_by_kind={
            str(kind): tuple(str(sheet) for sheet in sheets)
            for kind, sheets in chart_raw.items()
        },
    )


def workbook(contract: Contract, config: Config) -> Path:
    path = config.workbook(contract.workbook_key)
    if path is None:
        raise ContractError(f"尚未配置 {contract.workbook_key} 工作簿")
    if not path.is_file():
        raise ContractError(f"配置的工作簿不存在：{path}")
    return path
