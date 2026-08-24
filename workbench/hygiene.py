"""仓库卫生：换行符归一。

为什么需要一条命令而不是靠人记得：编辑器与各类工具在 Windows 上默认写 CRLF，
而工作台要求全仓 LF（ADR 0006）。规则靠人记 = 迟早脱节；做成命令 + 测试断言 = 不会。
"""

from __future__ import annotations

from pathlib import Path

from .paths import Paths
from .result import Result

TEXT_SUFFIXES = {".py", ".md", ".json", ".js", ".toml", ".yml", ".yaml", ".mdc"}

#: 不处理：旧仓（冻结保留原样）、临时产物、构建产物、本机配置
SKIP_DIRS = {
    ".git",
    "__pycache__",
    "scratch",
    "_tmp",
    "dist",
    "build",
    ".venv",
    ".ir-workbench",
    "0703_Travel_Pulse",
    "database_matain",
    "peers_rs_update",
}


def text_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix in TEXT_SUFFIXES or path.name == ".gitattributes":
            found.append(path)
    return found


def run(paths: Paths, *, fix: bool = False) -> Result:
    offenders = [path for path in text_files(paths.root) if b"\r\n" in path.read_bytes()]
    names = [str(path.relative_to(paths.root)) for path in offenders]

    if not offenders:
        return Result(
            status="success",
            summary="全仓文本文件换行符均为 LF。",
            checks=[{"name": "换行符", "level": "ok", "detail": "无 CRLF"}],
        )

    if not fix:
        return Result(
            status="partial",
            summary=f"{len(offenders)} 个文件含 CRLF，未修改。",
            checks=[{"name": name, "level": "warn", "detail": "含 CRLF"} for name in names[:20]],
            next_steps=[
                "跑 `ir hygiene --fix` 归一为 LF。",
                "CRLF 会让 git 把整份文件当成改写，把真正的内容变化埋掉（ADR 0006）。",
            ],
            data={"offenders": names},
        )

    for path in offenders:
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))

    return Result(
        status="success",
        summary=f"已把 {len(offenders)} 个文件归一为 LF。",
        checks=[{"name": name, "level": "ok", "detail": "已归一"} for name in names[:20]],
        data={"fixed": names},
    )
