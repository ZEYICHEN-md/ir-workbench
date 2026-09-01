"""Offline health checks for expert-calls."""

from __future__ import annotations

import importlib.util
import shutil

from workbench.paths import Paths


def checks(base: Paths) -> list[dict]:
    del base
    pdf_ok = importlib.util.find_spec("pdfplumber") is not None
    lark_ok = shutil.which("lark-cli") is not None or shutil.which("lark-cli.cmd") is not None
    return [
        {
            "name": "PDF 文本抽取",
            "level": "ok" if pdf_ok else "fail",
            "detail": "pdfplumber 可用" if pdf_ok else "缺 pdfplumber",
            **({"advice": "安装工作台依赖 pdfplumber。"} if not pdf_ok else {}),
        },
        {
            "name": "飞书 CLI",
            "level": "ok" if lark_ok else "warn",
            "detail": "lark-cli 可用" if lark_ok else "未找到 lark-cli；抽取和渲染仍可用",
            **({"advice": "发布前安装并授权 lark-cli。"} if not lark_ok else {}),
        },
    ]
