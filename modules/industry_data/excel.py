"""读指标底稿 Excel 的 2026 块。

布局（勿与旧版混淆）：
  - 周轴：R 列（周标签）
  - 酒店 STR：S / T / U（入住率 / ADR / RevPAR）
  - 航空：W / X / Y = 客运量 / 票价 / 客运航班量（固定列，全年含 Q1）
  - 左侧「QTD周度」G / H / I：仅作航空回退
  - 火车票 Z+：本管道不读

**本模块不再提供「按文件名取最新」**——底稿由 `ir config set industry` 显式锁定
（ADR 0001）。原 `find_latest_excel` / `_excel_version_key` 已随之删除。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import openpyxl

from . import layout

MONTH_LABELS = [f"{i}月" for i in range(1, 13)]

#: 2026 右侧周度航空固定列
RIGHT_AV_PAX_COL = 23
RIGHT_AV_TICKET_COL = 24
RIGHT_AV_FLIGHT_COL = 25

_WEEK_RANGE = re.compile(r"(\d{1,2})/(\d{1,2})\s*-\s*(\d{1,2})/(\d{1,2})")

#: 指标序列名 → 月度/季度所在列
_MONTHLY_COLS: dict[str, int] = {
    "hotelOccupancy": 3,
    "hotelADR": 4,
    "hotelRevPAR": 5,
    "domAviationCAAC": 7,
    "domAviationBig3": 8,
    "railway": 9,
    "intlAviationCAAC": 11,
    "intlAviationBig3": 12,
    "intlCapacity": 13,
}


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace("%", "")
        if not text:
            return None
        try:
            return float(text) / 100.0 if "%" in value else float(text)
        except ValueError:
            return None
    return None


def infer_data_update(weeks: list, year: int = 2026) -> str | None:
    """最新一周的结束日，ISO 格式。跳过「春节 / 日均」。跨年（12→1 月）按 year+1。"""
    for label in reversed(weeks or []):
        text = str(label).strip()
        if "春节" in text or "日均" in text:
            continue
        match = _WEEK_RANGE.search(text)
        if not match:
            continue
        start_m, _start_d, end_m, end_d = (int(x) for x in match.groups())
        end_year = year + 1 if end_m < start_m else year
        return f"{end_year:04d}-{end_m:02d}-{end_d:02d}"
    return None


def norm_week(label: str) -> str:
    """去掉 M/D 的前导零；「春节(日均)」等原样保留。"""
    if not label or "春节" in label or "日均" in label:
        return label.strip() if isinstance(label, str) else label
    text = str(label).strip()

    def strip_part(part: str) -> str:
        if "/" not in part:
            return part
        left, right = part.split("/", 1)
        return f"{int(left)}/{int(right)}"

    if "-" in text:
        left, right = text.split("-", 1)
        return f"{strip_part(left.strip())}-{strip_part(right.strip())}"
    return text


class ExcelLayoutError(RuntimeError):
    """底稿结构与预期不符。按契约应停止，而不是猜测。"""


def _open_2026_block(xlsx_path: Path):
    """打开底稿并定位 2026 块。返回 (sheet, year_row)。"""
    workbook = openpyxl.load_workbook(xlsx_path, data_only=True)
    try:
        sheet = workbook["国内行业数据"]
    except KeyError:
        raise ExcelLayoutError("底稿缺少工作表「国内行业数据」") from None

    for row in range(1, sheet.max_row + 1):
        value = sheet.cell(row, 2).value
        if value and str(value).strip().startswith("2026"):
            return sheet, row
    raise ExcelLayoutError("底稿里找不到 2026 年块（B 列「2026年」）")


def weekly_sides(xlsx_path: Path) -> tuple[dict, dict[str, tuple]]:
    """右侧周度原值 + 左侧「QTD周度」航空原值，**不做回退合并**。

    `parse()` 返回的是合并后的结果，右侧优先会静默盖掉左侧，因此看不出两边是否一致。
    交叉核对必须拿两侧原值，所以单独开这个入口。
    """
    sheet, year_row = _open_2026_block(xlsx_path)
    return _read_right_weekly(sheet, year_row), _parse_weekly_aviation_fallback(sheet, year_row)


def parse(xlsx_path: Path) -> dict:
    """读出与指标快照同形状的字典（weekly / monthly / quarterly / meta）。"""
    sheet, year_row = _open_2026_block(xlsx_path)

    monthly = _parse_monthly(sheet, year_row)
    quarterly = _parse_quarterly(sheet, year_row)
    weekly = _parse_weekly(sheet, year_row)

    return {
        "meta": {"sourceExcel": xlsx_path.name},
        "weekly": weekly,
        "monthly": monthly,
        "quarterly": quarterly,
    }


def _parse_monthly(sheet, year_row: int) -> dict:
    month_start = year_row + 3
    months: list[str] = []
    series: dict[str, list] = {name: [] for name in _MONTHLY_COLS}

    for row in range(month_start, month_start + 12):
        # 月份行标签可能带后缀（如「7月 (preliminary)」）；匹配规则在 layout 里只有一份
        number = layout.month_number(sheet.cell(row, 2).value)
        if number is None:
            break
        months.append(f"{number}月")
        for name, col in _MONTHLY_COLS.items():
            series[name].append(_num(sheet.cell(row, col).value))

    return {"months": months, **series}


def _parse_quarterly(sheet, year_row: int) -> dict:
    month_start = year_row + 3
    quarterly: dict[str, dict] = {}
    for row in range(month_start, month_start + 20):
        label = sheet.cell(row, 2).value
        if not label:
            continue
        text = str(label).strip().upper()
        if not re.match(r"^Q[1-4]$", text):
            continue
        values = {name: _num(sheet.cell(row, col).value) for name, col in _MONTHLY_COLS.items()}
        if any(v is not None for v in values.values()):
            quarterly[text.lower()] = values
    return quarterly


def _read_right_weekly(sheet, year_row: int) -> dict:
    """右侧周度区原值（R 周轴 + S/T/U 酒店 + W/X/Y 航空），未经回退合并。"""
    # 右侧周轴表头：R 列 == "周"
    header_row = None
    for row in range(year_row, year_row + 10):
        value = sheet.cell(row, 18).value
        if value and str(value).strip() == "周":
            header_row = row
            break
    if header_row is None:
        raise ExcelLayoutError("底稿里找不到右侧周度表头（R 列「周」）")

    weeks: list[str] = []
    occupancy: list = []
    adr: list = []
    revpar: list = []
    pax_right: list = []
    ticket_right: list = []
    flight_right: list = []

    for row in range(header_row + 1, header_row + 80):
        label = sheet.cell(row, 18).value
        if label is None or str(label).strip() == "":
            if weeks:
                break
            continue
        text = str(label).strip()
        if text.startswith(("Note", "注", "**")):
            break
        if not re.search(r"\d+/\d+", text) and "春节" not in text and "日均" not in text:
            break
        weeks.append(text)
        occupancy.append(_num(sheet.cell(row, 19).value))
        adr.append(_num(sheet.cell(row, 20).value))
        revpar.append(_num(sheet.cell(row, 21).value))
        pax_right.append(_num(sheet.cell(row, RIGHT_AV_PAX_COL).value))
        ticket_right.append(_num(sheet.cell(row, RIGHT_AV_TICKET_COL).value))
        flight_right.append(_num(sheet.cell(row, RIGHT_AV_FLIGHT_COL).value))

    return {
        "weeks": weeks,
        "hotelOccupancy": occupancy,
        "hotelADR": adr,
        "hotelRevPAR": revpar,
        "aviationPax": pax_right,
        "aviationTicket": ticket_right,
        "aviationFlight": flight_right,
    }


def _parse_weekly(sheet, year_row: int) -> dict:
    right = _read_right_weekly(sheet, year_row)
    weeks = right["weeks"]
    occupancy = right["hotelOccupancy"]
    adr = right["hotelADR"]
    revpar = right["hotelRevPAR"]
    pax_right = right["aviationPax"]
    ticket_right = right["aviationTicket"]
    flight_right = right["aviationFlight"]

    fallback = _parse_weekly_aviation_fallback(sheet, year_row)

    pax: list = []
    ticket: list = []
    flight: list = []
    for index, label in enumerate(weeks):
        key = norm_week(label) if "春节" not in label else label
        left = fallback.get(key) or fallback.get(label)
        for target, right_series, left_index in (
            (pax, pax_right, 0),
            (ticket, ticket_right, 1),
            (flight, flight_right, 2),
        ):
            right_value = right_series[index] if index < len(right_series) else None
            if right_value is not None:
                target.append(right_value)
            elif left:
                target.append(left[left_index])
            else:
                target.append(None)

    return {
        "weeks": weeks,
        "hotelOccupancy": occupancy,
        "hotelADR": adr,
        "hotelRevPAR": revpar,
        "aviationPax": pax,
        "aviationTicket": ticket,
        "aviationFlight": flight,
    }


def _parse_weekly_aviation_fallback(sheet, year_row: int) -> dict[str, tuple]:
    """左侧「QTD周度」G/H/I，仅当右侧对应格为空时回退。"""
    month_start = year_row + 3
    qtd_header = None
    for row in range(month_start, month_start + 40):
        value = sheet.cell(row, 2).value
        if value and "QTD" in str(value):
            qtd_header = row
            break
    if qtd_header is None:
        return {}

    by_week: dict[str, tuple] = {}
    for row in range(qtd_header + 1, qtd_header + 40):
        label = sheet.cell(row, 2).value
        if label is None or str(label).strip() == "":
            if by_week:
                break
            continue
        text = str(label).strip()
        if text.startswith(("Note", "注")):
            break
        if not re.search(r"\d+/\d+", text) and "春节" not in text:
            break
        by_week[norm_week(text)] = (
            _num(sheet.cell(row, 7).value),
            _num(sheet.cell(row, 8).value),
            _num(sheet.cell(row, 9).value),
        )
    return by_week
