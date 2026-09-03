"""模型期间解析、可比列选择与图表期间政策。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

_Q_PATTERNS = [
    re.compile(r"^(?:20)?(\d{2})Q([1-4])$", re.I),
    re.compile(r"^([1-4])Q(\d{2})$", re.I),
]
_H_PATTERNS = [
    re.compile(r"^(?:20)?(\d{2})[- ]?([12])H$", re.I),
    re.compile(r"^(?:20)?(\d{2})H([12])$", re.I),
    re.compile(r"^([12])H[- ]?(?:20)?(\d{2})$", re.I),
]
# 只要干净的年度标签。ABN 的 "FY 2025(BBG EST.)" 不能当成正式 FY 列。
_FY_PATTERNS = [
    re.compile(r"^FY\s*(20\d{2})$", re.I),
    re.compile(r"^(20\d{2})\s*FY$", re.I),
    re.compile(r"^(20\d{2})$"),
]


@dataclass(frozen=True, order=True)
class Period:
    year: int
    kind_order: int
    slot: int
    kind: str

    @property
    def key(self) -> str:
        if self.kind == "quarter":
            return f"{self.year % 100:02d}Q{self.slot}"
        if self.kind == "half":
            return f"{self.year % 100:02d}H{self.slot}"
        return f"FY{self.year}"

    @classmethod
    def parse(cls, value) -> "Period | None":
        if value is None:
            return None
        if isinstance(value, (int, float)) and int(value) == value and 1900 <= int(value) <= 2100:
            return cls(int(value), 2, 0, "year")
        text = str(value).strip().replace("\n", " ")
        if text.endswith(".0") and text[:-2].isdigit():
            text = text[:-2]
        match = _Q_PATTERNS[0].match(text)
        if match:
            return cls(2000 + int(match.group(1)), 0, int(match.group(2)), "quarter")
        match = _Q_PATTERNS[1].match(text)
        if match:
            return cls(2000 + int(match.group(2)), 0, int(match.group(1)), "quarter")
        match = _H_PATTERNS[2].match(text)
        if match:
            return cls(2000 + int(match.group(2)), 1, int(match.group(1)), "half")
        for pattern in _H_PATTERNS[:2]:
            match = pattern.match(text)
            if match:
                return cls(2000 + int(match.group(1)), 1, int(match.group(2)), "half")
        for pattern in _FY_PATTERNS:
            match = pattern.match(text)
            if match:
                return cls(int(match.group(1)), 2, 0, "year")
        return None

    def label_like(self, source) -> str | int:
        text = str(source).strip()
        if self.kind == "quarter":
            if re.match(r"^[1-4]Q\d{2}$", text, re.I):
                return f"{self.slot}Q{self.year % 100:02d}"
            if re.match(r"^20\d{2}Q", text, re.I):
                return f"{self.year}Q{self.slot}"
            return self.key
        if self.kind == "half":
            if "-" in text:
                return f"{self.year}-{self.slot}H"
            if re.match(r"^20\d{2}\s+[12]H", text, re.I):
                return f"{self.year} {self.slot}H"
            if re.match(r"^[12]H", text, re.I):
                return f"{self.slot}H{self.year % 100:02d}"
            return self.key
        if isinstance(source, (int, float)):
            return self.year
        if text.upper().startswith("FY"):
            return f"FY {self.year}"
        if text.upper().endswith("FY") or "FY" in text.upper():
            return f"{self.year} FY"
        return self.year


def scan_periods(ws, header_row: int) -> dict[Period, int]:
    periods: dict[Period, int] = {}
    for col in range(1, (ws.max_column or 1) + 1):
        period = Period.parse(ws.cell(header_row, col).value)
        if period is not None:
            periods[period] = col
    return periods


def previous_quarter(period: Period) -> Period:
    if period.slot == 1:
        return Period(period.year - 1, 0, 4, "quarter")
    return Period(period.year, 0, period.slot - 1, "quarter")


def source_period(target: Period, periods: dict[Period, int], *, require_previous: bool = True) -> Period | None:
    if target.kind == "quarter":
        expected = previous_quarter(target)
    elif target.kind == "half":
        expected = Period(target.year - 1, 1, target.slot, "half")
    else:
        expected = Period(target.year - 1, 2, 0, "year")
    if expected in periods:
        return expected
    if require_previous:
        return None
    candidates = [item for item in periods if item.kind == target.kind and item < target]
    if target.kind == "half":
        candidates = [item for item in candidates if item.slot == target.slot]
    return max(candidates, default=None)


def insertion_column(target: Period, periods: dict[Period, int]) -> int:
    same = [(period, col) for period, col in periods.items() if period.kind == target.kind]
    if not same:
        raise ValueError(f"模板没有 {target.kind} 期间区块")
    return max(col for _, col in same) + 1


def next_other_kind_column(periods: dict[Period, int], after_col: int, kind: str) -> int | None:
    later = [col for period, col in periods.items() if col > after_col and period.kind != kind]
    return min(later) if later else None


def chart_periods(periods: Iterable[Period], target: Period) -> list[Period]:
    """2019 同期起，排除 2020–2022，再接 2023 至目标期间。

    季度：26Q2 → 19Q2/19Q3/19Q4 + 23Q1…26Q2。
    半年/年度：2019 同期 + 2023 至目标年同期。
    """
    available = set(periods)
    if target.kind == "quarter":
        first = [Period(2019, 0, slot, "quarter") for slot in range(target.slot, 5)]
        later = [
            Period(year, 0, slot, "quarter")
            for year in range(2023, target.year + 1)
            for slot in range(1, 5)
            if (year, slot) <= (target.year, target.slot)
        ]
    elif target.kind == "half":
        first = [Period(2019, 1, target.slot, "half")]
        later = [Period(year, 1, target.slot, "half") for year in range(2023, target.year + 1)]
    else:
        first = [Period(2019, 2, 0, "year")]
        later = [Period(year, 2, 0, "year") for year in range(2023, target.year + 1)]
    return [period for period in first + later if period in available]


def label_period(period: Period, target: Period) -> bool:
    if period.year not in {2019, *range(2023, target.year + 1)}:
        return False
    return period.kind == target.kind and (target.kind == "year" or period.slot == target.slot)
