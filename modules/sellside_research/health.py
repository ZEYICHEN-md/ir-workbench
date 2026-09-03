"""sellside-research 健康检查。"""

from __future__ import annotations

import importlib.util

from workbench.paths import Paths


def checks(_base: Paths) -> list[dict]:
    available = importlib.util.find_spec("pdfplumber") is not None
    return [
        {
            "name": "PDF 按页抽取",
            "level": "ok" if available else "fail",
            "detail": "pdfplumber 可用" if available else "缺 pdfplumber",
            **({"advice": "对 Agent 说「安装工作台依赖」。"} if not available else {}),
        },
        {
            "name": "持久化边界",
            "level": "ok",
            "detail": "不建索引、不进竞对情报库、不产生跨期 manifest",
        },
    ]
