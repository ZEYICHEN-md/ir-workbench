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


#: `os.replace` 撞 Windows 文件锁时重试几次。
#: 实测过：跑测试时一次 `PermissionError: [WinError 5]`，来自 Defender / 索引器短暂
#: 持有临时文件的句柄。这不是逻辑错误，隔一下就好。
#: 值得加重试而不是当偶发忽略——manifest 每记一步都走这个函数，真实运行同样会撞，
#: 而撞上的后果是那一步的进度没写下去、状态与实际脱节。
_REPLACE_RETRIES = 5
_REPLACE_BACKOFF = 0.05


def write_text_atomic(path: Path, content: str) -> Path:
    """先写临时文件再替换。用于不能写坏的权威文件。"""
    import time

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    for attempt in range(_REPLACE_RETRIES):
        try:
            tmp.replace(path)
            return path
        except PermissionError:
            if attempt == _REPLACE_RETRIES - 1:
                raise
            time.sleep(_REPLACE_BACKOFF * (attempt + 1))
    return path
