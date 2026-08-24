"""统一的文本写出。

**所有生成文件一律用 LF 换行。**

背景：Python 的 `Path.write_text` 在 Windows 上默认把 `\\n` 翻成 `\\r\\n`，而这些文件
历史上由 Node 写出（LF）。若不统一，每次生成都会产生「全部行都变了」的 diff 噪音，
把真正的内容变化埋掉。`travel.json` 之前是 CRLF，纯属 Python 默认行为的意外，不是约定。

配套：仓库根 `.gitattributes` 固定 `eol=lf`，避免 Windows 检出时又被换回来。
"""

from __future__ import annotations

from pathlib import Path


def write_text(path: Path, content: str, *, mkdir: bool = True) -> Path:
    """以 UTF-8 + LF 写出文本。"""
    if mkdir:
        path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return path


def write_text_atomic(path: Path, content: str) -> Path:
    """先写临时文件再替换。用于不能写坏的权威文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    tmp.replace(path)
    return path
