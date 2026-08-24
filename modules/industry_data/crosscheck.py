"""周度数据的人工填写核对，供 `ir doctor` 调用。

与 `layout.py` 分工：`layout` 核对**结构**（列位有没有挪），本模块核对**内容**
（这一周的数填全了没、两边填的一致不一致）。两者都在跑 merge 之前就该发现问题。

### 为什么要交叉核对左右两侧

底稿里周度航空有两处：右侧 W/X/Y 与左侧「QTD周度」G/H/I。`excel.py` 的规则是
**右侧优先，右侧为空才回退左侧**。使用者两边都手填，于是出现一个静默失败面——
右侧填错行、左侧填对了，看板上出现的是右侧那个错值，左侧的正确值不起任何作用，
**而且不会报错**。这正是 ADR 0001 要消掉的那类「技术上合法、业务上全错」。

既然两边都填，这份重复劳动就可以当成双录来用：不一致时报出来，等于免费复核。
"""

from __future__ import annotations

from pathlib import Path

from . import excel

#: 右侧列 → (左侧同指标列字母, 指标中文名)
AVIATION_PAIRS: tuple[tuple[str, str, str, str], ...] = (
    ("aviationPax", "W", "G", "客运量"),
    ("aviationTicket", "X", "H", "票价"),
    ("aviationFlight", "Y", "I", "客运航班量"),
)

#: 左侧 G/H/I 在回退元组里的下标，与 AVIATION_PAIRS 同序
_LEFT_INDEX = {"aviationPax": 0, "aviationTicket": 1, "aviationFlight": 2}

#: 每周应填齐的六项（右侧）
WEEKLY_REQUIRED: tuple[tuple[str, str, str], ...] = (
    ("hotelOccupancy", "S", "酒店入住率"),
    ("hotelADR", "T", "酒店ADR"),
    ("hotelRevPAR", "U", "酒店RevPAR"),
    ("aviationPax", "W", "航空客运量"),
    ("aviationTicket", "X", "航空票价"),
    ("aviationFlight", "Y", "航空客运航班量"),
)

#: 两侧数值差异容差。手填两边应当完全相同，留一点余量只为避开浮点噪音。
TOLERANCE = 1e-9

#: 只核对最近这么多周。更早的周次是历史，两侧口径可能本来就有出入，
#: 每次 doctor 都翻旧账会把本周真正的问题淹掉。
RECENT_WEEKS = 8


def _fmt(value: float | None) -> str:
    return "空" if value is None else f"{value:.4%}"


def checks(workbook: Path) -> list[dict]:
    """返回 checks 列表（`ok` / `warn` / `fail`）。读不出就交给 layout 去报，这里静默跳过。"""
    try:
        right, left = excel.weekly_sides(workbook)
    except Exception:  # noqa: BLE001 —— 结构问题由 layout.verify 负责报，不在这里重复
        return []

    weeks: list[str] = right["weeks"]
    if not weeks:
        return []

    rows = [_check_latest_week(right, weeks)]
    rows.extend(_check_two_sides(right, left, weeks))
    return rows


def _check_latest_week(right: dict, weeks: list[str]) -> dict:
    """最新一周的六项应填齐——酒店与航空每周都更新，缺格通常是漏填而非没有数据。"""
    index = len(weeks) - 1
    label = weeks[index]
    missing = [
        f"{letter} 列{name}"
        for field, letter, name in WEEKLY_REQUIRED
        if right[field][index] is None
    ]

    if not missing:
        return {"name": "最新周填写", "level": "ok", "detail": f"{label}：六项齐全"}
    return {
        "name": "最新周填写",
        "level": "warn",
        "detail": f"{label} 缺 {len(missing)} 项：" + "、".join(missing),
        "advice": "酒店与航空每周都更新，缺格通常是漏填。"
        "确实还没有数据就先留空——空格会如实反映为缺失，补上后重跑 merge 即可。",
    }


def _check_two_sides(right: dict, left: dict[str, tuple], weeks: list[str]) -> list[dict]:
    """同一周标签下，右侧 W/X/Y 与左侧 QTD G/H/I 都非空时应当相等。"""
    if not left:
        return [
            {
                "name": "航空左右核对",
                "level": "ok",
                "detail": "左侧 QTD 无数据，仅用右侧 W/X/Y",
            }
        ]

    recent = weeks[-RECENT_WEEKS:]
    mismatches: list[str] = []
    compared = 0
    unmatched: list[str] = []

    for label in recent:
        key = label if "春节" in label else excel.norm_week(label)
        values = left.get(key) or left.get(label)
        index = weeks.index(label)
        if values is None:
            # 只有右侧缺格、真的要靠回退时，配不上才会造成缺数；
            # 右侧填满时左侧有没有这一周都不影响结果，报出来只是噪音。
            if any(right[field][index] is None for field, *_ in AVIATION_PAIRS):
                unmatched.append(label)
            continue
        for field, right_letter, left_letter, name in AVIATION_PAIRS:
            right_value = right[field][index]
            left_value = values[_LEFT_INDEX[field]]
            if right_value is None or left_value is None:
                continue
            compared += 1
            if abs(right_value - left_value) > TOLERANCE:
                mismatches.append(
                    f"{label} {name}：{right_letter}={_fmt(right_value)} 对 "
                    f"{left_letter}={_fmt(left_value)}"
                )

    rows: list[dict] = []
    if mismatches:
        rows.append(
            {
                "name": "航空左右核对",
                "level": "warn",
                "detail": f"最近 {len(recent)} 周有 {len(mismatches)} 处不一致："
                + "；".join(mismatches),
                "advice": "**看板取的是右侧 W/X/Y**，左侧不一致也不会生效。"
                "先确认哪边是对的：右侧错了就改右侧再重跑 merge；"
                "两侧口径本就不同则说明左侧不该再手填。",
            }
        )
    else:
        rows.append(
            {
                "name": "航空左右核对",
                "level": "ok",
                "detail": f"最近 {len(recent)} 周核对 {compared} 处，两侧一致"
                if compared
                else f"最近 {len(recent)} 周无两侧同时有值的格，无可核对",
            }
        )

    if unmatched:
        rows.append(
            {
                "name": "周标签配对",
                "level": "warn",
                "detail": "这些周右侧航空有缺格，左侧 QTD 里又配不上：" + "、".join(unmatched),
                "advice": "回退是按周标签配对的，两边写法必须一致（如 `8/16-8/22`）。"
                "配不上又缺格，这一周的航空就会变空——补右侧，或把左侧标签写法改成一致。",
            }
        )
    return rows
