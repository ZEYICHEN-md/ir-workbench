"""发布日历：期次键、情报主周、发布日。

## 期次定义（沿用旧仓 publication-calendar ADR）

**当月第 N 个周一所在的自然周。周一落在几月就计入几月。**
这条不改——往期成品都按它命名，改了历史就对不上。

## 但键改了：中文 → ASCII

旧仓三处目录（`reports/` `inputs/` `runs/`）都直接用 `2026年8月第2周` 当目录名，
期次也以中文形式在命令行里传。两处在 Windows 上都不安全：PowerShell 默认用 GBK 传参，
中文参数会**静默**变成乱码（ADR 0007）——不报错，只是查不到东西。

所以工作台的键是 `2026-08-W2`（`domains.py` 的 `month_week`），中文标签由
`domains.period_label()` 生成，只用于汇报与交付文件名。交付物文件名仍是中文
（`旅行行业新闻精选-2026年8月第2周.md`），那是给人看的，不穿命令行。
"""

from __future__ import annotations

import calendar as _calendar
import re
from datetime import date, timedelta

#: ASCII 键
KEY_RE = re.compile(r"^(20\d{2})-(0[1-9]|1[0-2])-W([1-5])$")
#: 中文标签（读往期成品、写交付文件名时用）
LABEL_RE = re.compile(r"^(20\d{2})年(\d{1,2})月第([1-5])周$")


class PeriodError(ValueError):
    pass


def _mondays(year: int, month: int) -> list[date]:
    return [
        date(year, month, day)
        for day in range(1, _calendar.monthrange(year, month)[1] + 1)
        if date(year, month, day).weekday() == 0
    ]


def parse_key(period: str) -> tuple[int, int, int]:
    match = KEY_RE.fullmatch((period or "").strip())
    if not match:
        raise PeriodError(f"期次键应形如 2026-08-W2，收到 {period!r}")
    year, month, index = int(match[1]), int(match[2]), int(match[3])
    mondays = _mondays(year, month)
    if index > len(mondays):
        raise PeriodError(
            f"{period} 不存在：{year}年{month}月只有 {len(mondays)} 个周一"
        )
    return year, month, index


def key_from_label(label: str) -> str:
    """`2026年8月第2周` → `2026-08-W2`。用于读往期中文命名的成品。"""
    match = LABEL_RE.fullmatch((label or "").strip())
    if not match:
        raise PeriodError(f"期次标签应形如 2026年8月第2周，收到 {label!r}")
    year, month, index = match.groups()
    return f"{year}-{int(month):02d}-W{index}"


def label_from_key(period: str) -> str:
    year, month, index = parse_key(period)
    return f"{year}年{month}月第{index}周"


def key_from_monday(monday: date) -> str:
    if monday.weekday() != 0:
        raise PeriodError(f"情报主周必须从周一起算，收到 {monday}")
    mondays = _mondays(monday.year, monday.month)
    return f"{monday.year}-{monday.month:02d}-W{mondays.index(monday) + 1}"


def intelligence_week(period: str) -> tuple[date, date]:
    """情报主周的周一与周日。"""
    year, month, index = parse_key(period)
    monday = _mondays(year, month)[index - 1]
    return monday, monday + timedelta(days=6)


def publish_date(period: str) -> date:
    """默认发布日 = 情报主周结束后的周二。"""
    return intelligence_week(period)[1] + timedelta(days=2)


def week_label(period: str) -> str:
    """抬头里那行 `情报主周：2026/08/10–08/16`。"""
    monday, sunday = intelligence_week(period)
    return f"{monday:%Y/%m/%d}–{sunday:%m/%d}"


def current_key(today: date | None = None) -> str:
    """今天所属的期次键。周中随时可算，取本周一。"""
    today = today or date.today()
    return key_from_monday(today - timedelta(days=today.weekday()))


def plan(period: str) -> dict:
    monday, sunday = intelligence_week(period)
    return {
        "period": period,
        "label": label_from_key(period),
        "intelligence_week": {
            "start": monday.isoformat(),
            "end": sunday.isoformat(),
            "label": week_label(period),
        },
        "publish": {"date": publish_date(period).isoformat(), "weekday": "周二"},
        "recall_window": {"since": monday.isoformat(), "until": sunday.isoformat()},
    }
