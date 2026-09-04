"""仓库卫生：换行符归一，以及过期临时文件扫描。

换行符：Windows 工具默认写 CRLF，工作台要求全仓 LF（ADR 0006）。
过期文件：规则在 ``conventions/file-lifecycle.md``，由 ``lifecycle`` 执行。
"""

from __future__ import annotations

from pathlib import Path

from . import lifecycle
from .paths import Paths
from .result import Result

TEXT_SUFFIXES = {".py", ".md", ".json", ".js", ".toml", ".yml", ".yaml", ".mdc"}

SKIP_DIRS = set(lifecycle.SKIP_HYGIENE_DIRS)


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


def _lf_result(paths: Paths, *, fix: bool) -> Result:
    offenders = [path for path in text_files(paths.root) if b"\r\n" in path.read_bytes()]
    names = [str(path.relative_to(paths.root)).replace("\\", "/") for path in offenders]

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


def _merge(lf: Result, prune: Result) -> Result:
    """两份卫生结果合成一份。任一需要人处理就报 partial。"""
    rank = {"success": 0, "partial": 1, "blocked": 2, "failed": 3}
    status = lf.status if rank[lf.status] >= rank[prune.status] else prune.status
    summaries = [s for s in (lf.summary, prune.summary) if s]
    data = {}
    if lf.data:
        data["line_endings"] = lf.data
    if prune.data:
        data["prune"] = prune.data
    return Result(
        status=status,
        summary=" ".join(summaries),
        checks=[*lf.checks, *prune.checks],
        missing=[*lf.missing, *prune.missing],
        warnings=[*lf.warnings, *prune.warnings],
        next_steps=[*lf.next_steps, *prune.next_steps],
        data=data,
    )


def run(paths: Paths, *, fix: bool = False, prune: bool = False) -> Result:
    lf = _lf_result(paths, fix=fix)
    if not prune:
        return lf
    return _merge(lf, lifecycle.prune(paths, fix=fix))
