"""Excel COM mutations for the peers model.

These functions preserve the authoritative ``-o sibling, then promote`` safety
model.  They never open Excel on a destination that the caller must unlink
while the workbook is locked.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from .model_common import (
    INPUT_BLUE_BGR,
    Q_RE,
    XL_CALC_MANUAL,
    XL_PASTE_FORMATS,
    XL_TO_RIGHT,
    col_letter,
    detect_layout,
    format_quarter_label,
    is_year_label,
    next_quarter,
    normalize_quarter,
    prev_quarter_col,
)


def insert_quarter(
    model: Path,
    sheet: str,
    quarter: str | None,
    *,
    dry_run: bool = False,
    out: Path | None = None,
) -> Path:
    """Insert/reuse a quarter column, preserving formulas and sheet label style."""
    layout = detect_layout(model, sheet)
    last_quarter = layout["last_quarter"]
    last_column = layout["last_col"]
    label_row = layout["label_row"]
    raw_target = quarter or next_quarter(last_quarter)
    target = normalize_quarter(raw_target) or raw_target
    if not Q_RE.match(target):
        raise ValueError(f"季度格式不对：{raw_target}")
    if target in layout["quarters"]:
        raise ValueError(
            f"{sheet} 已有 {target}（第 {layout['quarters'][target]} 列）。"
        )

    insert_at = last_column + 1
    reuse_gap = layout["gap_cols"] is not None and layout["gap_cols"] >= 1
    header = format_quarter_label(target, layout.get("label_style", "full"))
    if dry_run:
        return model

    destination = out or model.with_name(f"{model.stem}_{target}{model.suffix}")
    if destination.resolve() == model.resolve():
        raise ValueError("insert_quarter 的输出必须与输入不同，避免 Excel 文件锁死。")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    shutil.copy2(model, destination)

    import pythoncom
    import win32com.client as win32

    pythoncom.CoInitialize()
    excel = None
    workbook = None
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.ScreenUpdating = False
        try:
            excel.Calculation = XL_CALC_MANUAL
        except Exception:
            pass
        workbook = excel.Workbooks.Open(
            str(destination.resolve()), UpdateLinks=0, ReadOnly=False
        )
        worksheet = workbook.Worksheets(sheet)
        if not reuse_gap:
            worksheet.Columns(insert_at).Insert(Shift=XL_TO_RIGHT)
        worksheet.Columns(last_column).Copy(
            Destination=worksheet.Columns(insert_at)
        )
        try:
            excel.CutCopyMode = False
        except Exception:
            pass
        worksheet.Cells(label_row, insert_at).Value = header

        used_last_row = (
            int(worksheet.UsedRange.Rows.Count)
            + int(worksheet.UsedRange.Row)
            - 1
        )
        for row in range(label_row + 1, used_last_row + 1):
            cell = worksheet.Cells(row, insert_at)
            try:
                if cell.HasFormula:
                    continue
            except Exception:
                pass
            if cell.Value not in (None, ""):
                cell.Value = None

        # Always retain a blank spacer before the annual block.
        scan_end = (
            int(worksheet.UsedRange.Column)
            + int(worksheet.UsedRange.Columns.Count)
            + 8
        )
        for column in range(insert_at + 1, scan_end):
            value = worksheet.Cells(label_row, column).Value
            if value is None or not str(value).strip():
                continue
            if is_year_label(value):
                if column == insert_at + 1:
                    worksheet.Columns(column).Insert(Shift=XL_TO_RIGHT)
                break

        workbook.Save()
        workbook.Close(SaveChanges=False)
        workbook = None
        excel.Quit()
        excel = None
        time.sleep(0.5)
        return destination
    finally:
        try:
            if workbook is not None:
                workbook.Close(SaveChanges=False)
        except Exception:
            pass
        try:
            if excel is not None:
                excel.Quit()
        except Exception:
            pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def fill_quarter(
    model: Path,
    facts_path: Path,
    *,
    out: Path,
    dry_run: bool = False,
    allow_formula_overwrite: bool = False,
    force_blue: bool = False,
) -> Path:
    """Write human-approved fill JSON values into the target quarter."""
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    sheet = str(facts["sheet"]).upper()
    quarter = str(facts["quarter"])
    layout = detect_layout(model, sheet)
    if quarter not in layout["quarters"]:
        raise ValueError(
            f"{sheet} 缺 {quarter}；须先插入季度列。"
        )
    column = layout["quarters"][quarter]
    reference_column = prev_quarter_col(layout, quarter)
    font_mode = "force_blue" if force_blue else facts.get(
        "font_mode", "copy_prev_col"
    )
    if font_mode == "copy_prev_col" and reference_column is None:
        font_mode = "force_blue"
    items = [
        item for item in facts.get("inputs", []) if item.get("value") is not None
    ]
    if not items:
        raise ValueError("fill_inputs.json 没有任何非空 inputs。")
    if dry_run:
        return model
    if out.resolve() == model.resolve():
        raise ValueError("fill_quarter 的输出必须与输入不同，避免 Excel 文件锁死。")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    shutil.copy2(model, out)

    import pythoncom
    import win32com.client as win32

    pythoncom.CoInitialize()
    excel = None
    workbook = None
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.ScreenUpdating = False
        workbook = excel.Workbooks.Open(
            str(out.resolve()), UpdateLinks=0, ReadOnly=False
        )
        worksheet = workbook.Worksheets(sheet)
        for item in items:
            row = int(item["row"])
            cell = worksheet.Cells(row, column)
            try:
                if cell.HasFormula and not allow_formula_overwrite:
                    raise ValueError(
                        f"第 {row} 行是公式；fill JSON 不得覆盖公式。"
                    )
            except ValueError:
                raise
            except Exception:
                pass
            cell.Value = item["value"]
            if font_mode == "force_blue":
                cell.Font.Color = INPUT_BLUE_BGR
            elif reference_column is not None:
                reference = worksheet.Cells(row, reference_column)
                reference.Copy()
                cell.PasteSpecial(Paste=XL_PASTE_FORMATS)
                try:
                    excel.CutCopyMode = False
                except Exception:
                    pass
                cell.Value = item["value"]
        workbook.Save()
        workbook.Close(SaveChanges=False)
        workbook = None
        excel.Quit()
        excel = None
        time.sleep(0.5)
        return out
    finally:
        try:
            if workbook is not None:
                workbook.Close(SaveChanges=False)
        except Exception:
            pass
        try:
            if excel is not None:
                excel.Quit()
        except Exception:
            pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def promote_sibling(result: Path, target: Path) -> Path:
    """Atomically-ish promote a closed COM output over the durable work model."""
    if not result.is_file():
        raise FileNotFoundError(result)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".promote")
    if temporary.exists():
        temporary.unlink()
    shutil.copy2(result, temporary)
    temporary.replace(target)
    if result != target:
        result.unlink(missing_ok=True)
    return target
