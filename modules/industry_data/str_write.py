"""把中金表算出的酒店数据写进底稿。

## 权威层级（本模块存在的前提）

底稿是唯一指标真源（ADR 0001），但**底稿内部还有一层权威**：

> **人手填的数字最高权威。**周度聚合只是获取数据的一种方式，不是新的权威源。

所以写入规则是**仅填空、绝不覆盖**：空格才写，已有值一律保留，即使与算出来的不同。
历史口径不需要统一——1–6 月的月度值来自 STR 官方月报/券商/一度还有券商预测值，
那都是当时 IR 经理的判断，自动化没有资格改它。

## 四重保护（照搬 aviation_monthly 的做法，那套已在真实写入中验证过）

1. **写入前归档**：当前底稿整份复制进 `data/workbooks/archived/`，文件名带时间戳。
   人能直接双击打开核对，不要求会用 git。
2. **不能用 openpyxl 保存底稿**：它含历史外部链接，openpyxl 保存会重写链接与 XML，
   导致 Excel 打不开。一律走 **Excel COM**。
3. **写完回读**：重新打开核对每一格确实是目标值，并核对不该动的格没被动。
4. **占用检查**：底稿被 Excel 打开时（有 `~$` 锁文件）直接拒绝写入——否则会与人的
   编辑冲突，或者被人保存时覆盖掉。
"""

from __future__ import annotations

import datetime as dt
import shutil
from dataclasses import dataclass
from pathlib import Path

import openpyxl

from workbench.result import Result

from . import layout, str_plan, str_source
from .paths import DOMAIN, DomainPaths

#: 写入的溯源批注模板
COMMENT = "自动写入 · 来源 {source} · tab「{tab}」· {basis} · {stamp}"
COMMENT_AUTHOR = "IR 工作台"


@dataclass
class WriteOutcome:
    address: str
    where: str
    metric: str
    value: float
    verified: float | None


def _lock_file(workbook: Path) -> Path | None:
    candidate = workbook.parent / f"~${workbook.name}"
    return candidate if candidate.exists() else None


def archive(paths: DomainPaths, workbook: Path, tag: str) -> Path:
    """写入前把整份底稿复制进归档目录。返回归档路径。"""
    paths.workbook_archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    target = paths.workbook_archive_dir / f"{workbook.stem}.pre-{tag}-{stamp}{workbook.suffix}"
    shutil.copy2(workbook, target)
    return target


def _write_via_com(workbook: Path, cells: list[tuple[str, float, str]]) -> None:
    """用 Excel COM 写入并全量重算。`cells` 为 (地址, 值, 批注)。"""
    try:
        import pythoncom
        import win32com.client
    except ImportError as error:  # pragma: no cover —— doctor 已预检
        raise RuntimeError(f"需要 pywin32 才能写底稿：{error}") from error

    app = None
    book = None
    pythoncom.CoInitialize()
    try:
        app = win32com.client.DispatchEx("Excel.Application")
        app.Visible = False
        app.DisplayAlerts = False
        app.AskToUpdateLinks = False
        book = app.Workbooks.Open(
            str(workbook.resolve()),
            UpdateLinks=0,
            ReadOnly=False,
            IgnoreReadOnlyRecommended=True,
            AddToMru=False,
        )
        sheet = book.Worksheets(layout.SHEET)
        for address, value, comment in cells:
            target = sheet.Range(address)
            target.Value = value
            # 批注是溯源的一部分：过一个月没人记得这格是自动填的还是手填的
            if target.Comment is not None:
                target.Comment.Delete()
            target.AddComment(comment)
        app.CalculateFullRebuild()
        book.Save()
    except Exception as error:
        raise RuntimeError(f"Excel COM 写入失败：{error}") from error
    finally:
        if book is not None:
            try:
                book.Close(SaveChanges=False)
            except Exception:
                pass
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def _verify(workbook: Path, expected: list[tuple[str, float]], untouched: list[tuple[str, float | None]]
            ) -> tuple[list[tuple[str, float, float | None]], list[str]]:
    """回读核对。返回 (实测值, 问题清单)。"""
    book = openpyxl.load_workbook(workbook, data_only=True)
    problems: list[str] = []
    actual: list[tuple[str, float, float | None]] = []
    try:
        sheet = book[layout.SHEET]
        for address, value in expected:
            got = sheet[address].value
            got = float(got) if isinstance(got, (int, float)) else None
            actual.append((address, value, got))
            if got is None or abs(got - value) > 1e-9:
                problems.append(f"{address} 应为 {value!r}，回读得到 {got!r}")
        for address, before in untouched:
            got = sheet[address].value
            got = float(got) if isinstance(got, (int, float)) else None
            if (before is None) != (got is None) or (
                before is not None and got is not None and abs(got - before) > 1e-9
            ):
                problems.append(f"{address} 本不该被改动：{before!r} → {got!r}")
    finally:
        book.close()
    return actual, problems


def run(paths: DomainPaths, workbook: Path, source: Path, year: int, *, yes: bool = False) -> Result:
    """写入底稿。默认 dry-run；`yes=True` 才真写。**只填空格，不覆盖已有值。**"""
    try:
        cells, notes = str_plan.build(workbook, source, year)
    except str_source.StrSourceError as error:
        return Result(
            status="blocked",
            summary=f"读不出中金表或底稿结构不符：{error}",
            domain=DOMAIN,
            next_steps=["确认中金表 tab 名与列位没改版；改版了先更新 str_source 的契约。"],
        )

    additions = [c for c in cells if c.kind == "新增"]
    conflicts = [c for c in cells if c.kind == "冲突"]

    if not additions:
        return Result(
            status="success",
            summary="没有空格要填，底稿未改动。",
            domain=DOMAIN,
            checks=[
                {"name": "可填空格", "level": "ok", "detail": "0"},
                {
                    "name": "值不一致",
                    "level": "warn" if conflicts else "ok",
                    "detail": f"{len(conflicts)} 处（人手填的值最高权威，不覆盖）",
                },
            ],
            warnings=notes[2:],
        )

    plan_checks = [
        {"name": "中金表", "level": "ok", "detail": source.name},
        {"name": "将填空格", "level": "ok", "detail": f"{len(additions)} 处"},
        {
            "name": "跳过（已有值）",
            "level": "ok",
            "detail": f"{len(conflicts)} 处 —— 人手填的最高权威，不覆盖",
        },
    ]
    plan_checks += [{"name": "待写入", "level": "ok", "detail": c.describe()} for c in additions[:20]]

    if not yes:
        return Result(
            status="partial",
            summary=f"将填 {len(additions)} 处空格，**未写入**。",
            domain=DOMAIN,
            checks=plan_checks,
            warnings=notes[2:],
            next_steps=[
                "核对上面每一格的位置与数值。",
                "确认后回一句「写入」，Agent 才会动底稿。",
                "写入前会把整份底稿归档到 data/workbooks/archived/，可随时取回。",
            ],
            data={"additions": len(additions), "conflicts": len(conflicts)},
        )

    # --- 以下是真写 ---
    lock = _lock_file(workbook)
    if lock:
        return Result(
            status="blocked",
            summary="底稿正在 Excel 里打开，拒绝写入。",
            domain=DOMAIN,
            missing=[f"锁文件：{lock.name}"],
            next_steps=["先在 Excel 里保存并关闭底稿，再让我写入——否则会与你的编辑冲突。"],
        )

    backup = archive(paths, workbook, "str")
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    payload: list[tuple[str, float, str]] = []
    for cell in additions:
        basis = "周度取表内 K/L/M" if cell.where.startswith("周") else "月度按天加权聚合"
        payload.append((
            cell.address,
            cell.new,
            COMMENT.format(source=source.name, tab=str_source.SHEET, basis=basis, stamp=stamp),
        ))

    try:
        _write_via_com(workbook, payload)
    except RuntimeError as error:
        shutil.copy2(backup, workbook)  # 原子性兜底：写坏就整份还原
        return Result(
            status="failed",
            summary=f"写入失败，已从归档还原底稿：{error}",
            domain=DOMAIN,
            checks=[{"name": "已还原", "level": "ok", "detail": backup.name}],
            next_steps=["确认 Excel 可用（ir doctor 会查 pywin32 与 COM），再重试。"],
        )

    actual, problems = _verify(
        workbook,
        [(c.address, c.new) for c in additions],
        [(c.address, c.old) for c in conflicts],
    )

    if problems:
        shutil.copy2(backup, workbook)
        return Result(
            status="failed",
            summary=f"回读核对不通过（{len(problems)} 处），已从归档还原底稿。",
            domain=DOMAIN,
            missing=problems[:10],
            checks=[{"name": "已还原", "level": "ok", "detail": backup.name}],
            next_steps=["把上面的差异贴给维护者——这说明写入路径有问题，不要绕过。"],
        )

    checks = [
        {"name": "写入前归档", "level": "ok", "detail": f"archived/{backup.name}"},
        {"name": "已填空格", "level": "ok", "detail": f"{len(additions)} 处，回读全部一致"},
        {"name": "未覆盖", "level": "ok", "detail": f"{len(conflicts)} 处已有值保持原样"},
    ]
    checks += [
        {"name": "已写入", "level": "ok", "detail": f"{a} = {v * 100:+.2f}%"}
        for a, v, _got in actual[:20]
    ]

    return Result(
        status="success",
        summary=f"已写入底稿 {len(additions)} 处空格，并加了来源批注。",
        domain=DOMAIN,
        checks=checks,
        warnings=notes[2:],
        next_steps=["底稿变了，接着跑 ir industry merge 重建快照。"],
        data={"written": len(additions), "skipped": len(conflicts), "backup": backup.name},
    )
