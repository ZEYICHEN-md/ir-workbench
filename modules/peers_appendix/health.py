"""Health checks for the peers-appendix core."""

from __future__ import annotations

import importlib.util

from workbench import manifest as manifest_mod
from workbench.paths import Paths

from .steps import DOMAIN


def checks(base: Paths) -> list[dict]:
    rows: list[dict] = []
    for module, label, advice in (
        ("openpyxl", "Excel 结构读取", "安装工作台主依赖 openpyxl。"),
        ("win32com", "Excel COM", "安装 pywin32，并确认本机有桌面版 Excel。"),
        ("PIL", "图表 PNG", "安装 Pillow；图表导出与缩放需要它。"),
        ("lxml", "Word XML", "安装 lxml；Word apply/accept gate 需要它。"),
    ):
        available = importlib.util.find_spec(module) is not None
        rows.append(
            {
                "name": label,
                "level": "ok" if available else "fail",
                "detail": f"{module} 可用" if available else f"缺 {module}",
                "advice": None if available else advice,
            }
        )
    latest = manifest_mod.latest(base, DOMAIN)
    if latest is None:
        rows.append(
            {
                "name": "Peers 运行记录",
                "level": "ok",
                "detail": "尚未初始化季度（不算故障）",
            }
        )
    else:
        companies = sorted((latest.load().get("companies") or {}).keys())
        rows.append(
            {
                "name": "Peers 运行记录",
                "level": "ok",
                "detail": f"{latest.period} · {len(companies)} 家",
            }
        )
    return rows
