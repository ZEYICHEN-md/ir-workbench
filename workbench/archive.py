"""写入前归档底稿。

两条自动化写入路径共用这一份实现：
- `aviation-monthly`：民航局与三大航月度数据 → 四个航空格
- `industry-data`：中金周报 → 酒店周度与月度格

规则由使用者定：**任何自动写入之前，先保留一份编辑前的原版**，方便人工核对和兜底。
归档只增不删——想省空间也不该删，它是底稿这个单点的唯一非 git 备份。
"""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

from .paths import Paths


def archive_workbook(base: Paths, workbook: Path, tag: str) -> Path:
    """把整份工作簿复制进归档目录。返回归档路径。

    命名 `<原名>.pre-<tag>-<时间戳><后缀>`，例如
    `国内行业数据_0824.pre-aviation-20260825T161200.xlsx`。
    `tag` 说明是哪条写入路径动的手，出事时能直接看出该找谁。
    """
    target_dir = base.workbook_archive
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    target = target_dir / f"{workbook.stem}.pre-{tag}-{stamp}{workbook.suffix}"
    shutil.copy2(workbook, target)
    return target


def lock_file(workbook: Path) -> Path | None:
    """工作簿是否被 Excel 打开着（`~$` 锁文件）。

    打开时写入会与人的编辑冲突，或者被人保存时覆盖掉——必须拒写而不是硬来。
    """
    candidate = workbook.parent / f"~${workbook.name}"
    return candidate if candidate.exists() else None
