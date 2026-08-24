"""aviation-monthly 的健康检查，供 `ir doctor` 调用。"""

from __future__ import annotations

import importlib.util

from workbench.config import Config
from workbench.paths import Paths


def checks(base: Paths) -> list[dict]:
    rows: list[dict] = []

    # 这条管道要靠 Excel COM 重算公式——openpyxl 不能保存指标底稿（会重写外部链接，
    # 导致 Excel 打不开），所以 pywin32 + 本机 Excel 是硬依赖。
    if importlib.util.find_spec("win32com") is None:
        rows.append(
            {
                "name": "Excel COM",
                "level": "fail",
                "detail": "缺 pywin32，无法重算公式",
                "advice": "对 Agent 说「安装工作台依赖」；这条管道离不开本机 Excel。",
            }
        )
    else:
        rows.append({"name": "Excel COM", "level": "ok", "detail": "pywin32 可用"})

    airline = Config(base).workbook("airline")
    if not airline or not airline.is_file():
        # 缺失本身由 doctor 的通用检查报，这里只在存在时做结构校验
        return rows

    rows.extend(_verify_airline_layout(airline))
    return rows


def _verify_airline_layout(workbook) -> list[dict]:
    """核对 Airline Data 的四张表是否都在。

    行映射校验留给管道自己的 `ensure_workbook_contract`——它按年份和表头逐项核，
    比这里重复一遍更准。这里只做「表还在不在」这一层快检。
    """
    required = ("CAAC Data", "Top4 Domestic", "Top4 Intl.+Reg", "Top 4 Total", "Summary")
    try:
        import openpyxl

        wb = openpyxl.load_workbook(workbook, read_only=True)
        try:
            present = set(wb.sheetnames)
        finally:
            wb.close()
    except Exception as error:  # noqa: BLE001
        return [
            {
                "name": "Airline Data 可读",
                "level": "fail",
                "detail": f"{type(error).__name__}: {error}",
                "advice": "确认文件没被 Excel 锁住或损坏。",
            }
        ]

    absent = [name for name in required if name not in present]
    if absent:
        return [
            {
                "name": "Airline Data 工作表",
                "level": "fail",
                "detail": "缺：" + "、".join(absent),
                "advice": "底表结构与契约不符。见 modules/aviation_monthly/references/workbook-contract.md；"
                "结构真的改了要先更新契约与行映射，不要硬跑。",
            }
        ]
    return [{"name": "Airline Data 工作表", "level": "ok", "detail": f"{len(required)} 张齐全"}]
