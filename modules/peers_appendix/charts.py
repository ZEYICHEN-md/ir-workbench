"""Chart update, gate, ticker routing, export, and Word embedding."""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .chart_labels import apply_chart_labels, audit_chart_labels, quarter_num
from .model_common import (
    chart_sheet_name,
    col_letter,
    col_num,
    detect_layout,
)

RANGE_END_RE = re.compile(r":\$([A-Z]+)\$")
EXPE_FINANCE_CHARTS = {
    1: "01_gbv_yoy.png",
    16: "02_gbv_by_business.png",
    2: "03_revenue_yoy.png",
    3: "04_revenue_by_geo.png",
    5: "05_adj_ebitda_margin.png",
    6: "06_opex_pct_rev.png",
}
EXPE_WORD_SLOT_MAP = {
    "media/image3.png": "01_gbv_yoy.png",
    "media/image5.png": "03_revenue_yoy.png",
    "media/image6.png": "04_revenue_by_geo.png",
    "media/image7.png": "05_adj_ebitda_margin.png",
    "media/image8.png": "06_opex_pct_rev.png",
}
ABNB_CHARTS = {
    1: "01_revenue_yoy.png",
    2: "02_gbv_yoy.png",
    3: "03_opex_pct_rev.png",
    4: "04_nights_yoy.png",
    5: "05_take_rate.png",
    6: "06_adj_ebitda_margin.png",
}


@dataclass(frozen=True)
class ChartRoute:
    ticker: str
    exporter: str
    sheet: str
    indices: dict[int, str] | None
    word_slot_map: dict[str, str] | None


def select_chart_route(ticker: str) -> ChartRoute:
    """Pure routing decision used by both export and embed orchestration."""
    normalized = ticker.upper()
    if normalized == "EXPE":
        return ChartRoute(
            normalized,
            "expe_clipboard",
            "EXPE Quarterly Charts",
            EXPE_FINANCE_CHARTS,
            EXPE_WORD_SLOT_MAP,
        )
    if normalized == "ABNB":
        # The authoritative ABNB exporter exists, but no verified Word image-slot
        # mapping exists.  Export is supported; embed requires a human map.
        return ChartRoute(
            normalized,
            "abnb_clipboard",
            "ABNB Quarterly Charts",
            ABNB_CHARTS,
            None,
        )
    return ChartRoute(
        normalized,
        "generic_native",
        f"{normalized} Quarterly Charts",
        None,
        None,
    )


def bump_formula_ends(
    formula: str, target_column: int, lag: int
) -> str | None:
    if not formula:
        return None
    target_letter = col_letter(target_column)
    lower_bound = target_column - lag
    changed = False

    def replace(match: re.Match) -> str:
        nonlocal changed
        column = col_num(match.group(1))
        if lower_bound <= column < target_column:
            changed = True
            return f":${target_letter}$"
        return match.group(0)

    updated = RANGE_END_RE.sub(replace, formula)
    return updated if changed else None


def update_charts(
    model: Path,
    ticker: str,
    quarter: str,
    *,
    out: Path,
    lag: int = 12,
) -> Path:
    """Extend chart series and apply seasonal labels in a sibling workbook."""
    layout = detect_layout(model, ticker)
    if quarter not in layout["quarters"]:
        raise ValueError(f"{ticker} 缺 {quarter}，不能更新图表。")
    if out.resolve() == model.resolve():
        raise ValueError("update_charts 输出必须与输入不同。")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    shutil.copy2(model, out)
    target_column = layout["quarters"][quarter]

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
        worksheet = workbook.Worksheets(chart_sheet_name(ticker))
        for chart_index in range(1, worksheet.ChartObjects().Count + 1):
            chart_object = worksheet.ChartObjects(chart_index)
            if chart_object.Height < 10:
                continue
            chart = chart_object.Chart
            collection = chart.SeriesCollection()
            for series_index in range(1, collection.Count + 1):
                series = collection.Item(series_index)
                try:
                    old_formula = series.Formula
                except Exception:
                    continue
                new_formula = bump_formula_ends(
                    old_formula, target_column, lag
                )
                if new_formula and new_formula != old_formula:
                    series.Formula = new_formula
            try:
                title = chart.ChartTitle.Text
            except Exception:
                title = chart_object.Name
            apply_chart_labels(chart, quarter_num(quarter), title)
        try:
            excel.CalculateFull()
        except Exception:
            pass
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


def finance_chart_indices(ticker: str, count: int) -> set[int]:
    if ticker.upper() == "EXPE":
        return set(EXPE_FINANCE_CHARTS)
    return set(range(1, count + 1))


def check_charts(
    model: Path, ticker: str, quarter: str
) -> list[str]:
    """Must-pass series-end and label-geometry audit."""
    layout = detect_layout(model, ticker)
    if quarter not in layout["quarters"]:
        return [f"{quarter} missing on {ticker}"]
    target_letter = col_letter(layout["quarters"][quarter])
    errors: list[str] = []

    import pythoncom
    import win32com.client as win32

    pythoncom.CoInitialize()
    excel = None
    workbook = None
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        workbook = excel.Workbooks.Open(
            str(model.resolve()), UpdateLinks=0, ReadOnly=True
        )
        worksheet = workbook.Worksheets(chart_sheet_name(ticker))
        count = int(worksheet.ChartObjects().Count)
        for chart_index in sorted(finance_chart_indices(ticker, count)):
            if chart_index > count:
                errors.append(f"chart {chart_index} missing")
                continue
            chart_object = worksheet.ChartObjects(chart_index)
            chart = chart_object.Chart
            try:
                title = chart.ChartTitle.Text
            except Exception:
                title = chart_object.Name
            collection = chart.SeriesCollection()
            for series_index in range(1, collection.Count + 1):
                formula = collection.Item(series_index).Formula
                endings = RANGE_END_RE.findall(formula)
                if endings and endings[-1] != target_letter:
                    errors.append(
                        f"chart {chart_index} series {series_index} ends "
                        f"{endings[-1]} not {target_letter}"
                    )
            require_labels = (
                ticker.upper() == "EXPE"
                and chart_index in {1, 2, 5, 6}
            )
            for error in audit_chart_labels(
                chart,
                quarter_num(quarter),
                title,
                require_labels=require_labels,
            ):
                errors.append(
                    f"chart {chart_index} ({title[:40]}): {error}"
                )
        return errors
    finally:
        try:
            if workbook is not None:
                workbook.Close(False)
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


def _export_clipboard(
    model: Path,
    route: ChartRoute,
    out_dir: Path,
    *,
    scale: int = 2,
) -> list[Path]:
    from PIL import Image, ImageGrab
    import pythoncom
    import win32com.client as win32

    assert route.indices is not None
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    pythoncom.CoInitialize()
    excel = None
    workbook = None
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = True
        excel.DisplayAlerts = False
        excel.ScreenUpdating = True
        workbook = excel.Workbooks.Open(
            str(model.resolve()), UpdateLinks=0, ReadOnly=True
        )
        worksheet = workbook.Worksheets(route.sheet)
        worksheet.Activate()
        time.sleep(0.8)
        count = int(worksheet.ChartObjects().Count)
        for index, filename in route.indices.items():
            if index > count:
                raise ValueError(
                    f"{route.ticker} 图表 {index} 不存在（总数 {count}）。"
                )
            chart_object = worksheet.ChartObjects(index)
            if chart_object.Height < 10:
                chart_object.Height = 240
            destination = out_dir / filename
            destination.unlink(missing_ok=True)
            chart_object.Activate()
            time.sleep(0.25)
            chart_object.CopyPicture(Appearance=1, Format=2)
            time.sleep(0.35)
            image = ImageGrab.grabclipboard()
            if image is None:
                raise ValueError(
                    f"{route.ticker} 图表 {index} 复制后剪贴板为空。"
                )
            if scale > 1:
                image = image.resize(
                    (image.width * scale, image.height * scale),
                    Image.Resampling.LANCZOS,
                )
            image.save(destination, "PNG")
            if destination.stat().st_size < 2000:
                raise ValueError(f"导出的 {destination.name} 小于 2KB。")
            written.append(destination)
        return written
    finally:
        try:
            if workbook is not None:
                workbook.Close(False)
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


def _export_generic_native(
    model: Path,
    route: ChartRoute,
    out_dir: Path,
    *,
    scale: int = 2,
) -> list[Path]:
    from PIL import Image
    import win32com.client as win32

    out_dir.mkdir(parents=True, exist_ok=True)
    excel = win32.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    written: list[Path] = []
    try:
        workbook = excel.Workbooks.Open(
            str(model.resolve()), UpdateLinks=0, ReadOnly=True
        )
        worksheet = workbook.Worksheets(route.sheet)
        worksheet.Activate()
        time.sleep(0.4)
        for index in range(1, worksheet.ChartObjects().Count + 1):
            chart_object = worksheet.ChartObjects(index)
            if chart_object.Height < 10:
                continue
            raw = out_dir / f"_raw_{index}.png"
            destination = out_dir / f"chart_{index:02d}.png"
            raw.unlink(missing_ok=True)
            exported = chart_object.Chart.Export(str(raw), "PNG")
            time.sleep(0.12)
            if not exported or not raw.is_file() or raw.stat().st_size < 2000:
                raw.unlink(missing_ok=True)
                raise ValueError(
                    f"{route.ticker} chart {index} 原生导出失败。"
                )
            if scale > 1:
                with Image.open(raw) as image:
                    resized = image.resize(
                        (image.width * scale, image.height * scale),
                        Image.Resampling.LANCZOS,
                    )
                    resized.save(destination, "PNG")
                raw.unlink()
            else:
                raw.replace(destination)
            written.append(destination)
        workbook.Close(False)
        return written
    finally:
        excel.Quit()


def export_for_ticker(
    model: Path,
    ticker: str,
    out_dir: Path,
    *,
    generated_map: Path | None = None,
) -> tuple[list[Path], ChartRoute]:
    route = select_chart_route(ticker)
    if route.exporter in {"expe_clipboard", "abnb_clipboard"}:
        written = _export_clipboard(model, route, out_dir)
    else:
        written = _export_generic_native(model, route, out_dir)
    if route.word_slot_map is not None and generated_map is not None:
        payload = {
            slot: str((out_dir / filename).resolve())
            for slot, filename in route.word_slot_map.items()
        }
        generated_map.parent.mkdir(parents=True, exist_ok=True)
        generated_map.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return written, route


def load_chart_map(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload:
        raise ValueError(f"chart_map 必须是非空 object：{path}")
    return {str(key): str(value) for key, value in payload.items()}


def embed_charts(
    source_docx: Path,
    mapping: dict[str, str],
    out: Path,
    work: Path,
) -> int:
    """Replace mapped Word media slots without changing document structure."""
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    with ZipFile(source_docx) as archive:
        archive.extractall(work)
    replaced = 0
    for key, image_spec in mapping.items():
        normalized = key.replace("\\", "/")
        if normalized.startswith("word/"):
            destination = work / normalized
        elif normalized.startswith("media/"):
            destination = work / "word" / normalized
        else:
            destination = work / "word" / "media" / Path(normalized).name
        image = Path(image_spec)
        if not image.is_absolute():
            image = source_docx.parent / image
        if not image.is_file():
            raise FileNotFoundError(f"chart_map 找不到图片：{image}")
        if not destination.is_file():
            raise ValueError(
                f"Word 模板没有图位 {destination.relative_to(work)}。"
            )
        shutil.copy2(image, destination)
        replaced += 1
    if replaced != len(mapping):
        raise ValueError(
            f"计划替换 {len(mapping)} 张图，实际替换 {replaced} 张。"
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    with ZipFile(out, "w", ZIP_DEFLATED) as archive:
        for file in work.rglob("*"):
            if file.is_file():
                archive.write(file, file.relative_to(work).as_posix())
    return replaced
