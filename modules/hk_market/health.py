"""hk-market 健康检查。"""

from __future__ import annotations

import importlib.util

from workbench.paths import Paths

DEPENDENCIES = {
    "pandas": "月度聚合与周度行情",
    "akshare": "港股指数与港股成交额",
    "yfinance": "美股成交额及港股回退源",
}


def checks(_base: Paths) -> list[dict]:
    missing = [
        f"{name}（{purpose}）"
        for name, purpose in DEPENDENCIES.items()
        if importlib.util.find_spec(name) is None
    ]
    return [
        {
            "name": "行情依赖",
            "level": "fail" if missing else "ok",
            "detail": "缺：" + "、".join(missing) if missing else "齐全",
            **({"advice": "对 Agent 说「安装工作台依赖」。"} if missing else {}),
        },
        {
            "name": "监管口径",
            "level": "ok",
            "detail": "55% 状态只按最近完整财年 FY；L12M/季度仅作趋势",
        },
    ]
