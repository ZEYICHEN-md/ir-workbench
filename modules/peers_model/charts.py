"""Excel Chart SERIES 范围与数据标签策略。"""
from __future__ import annotations

import re

from .periods import Period, chart_periods, label_period

_RANGE_RE = re.compile(
    r"(?:(?:'((?:[^']|'')+)'|([^'!,()]+))!)?\$([A-Z]+)\$(\d+):\$([A-Z]+)\$(\d+)", re.I
)


def _split_series(formula: str) -> list[str]:
    body = formula.strip()
    if not body.upper().startswith("=SERIES(") or not body.endswith(")"):
        return []
    body = body[8:-1]
    parts, start, depth = [], 0, 0
    in_double = in_single = False
    for index, char in enumerate(body):
        if char == '"' and not in_single:
            in_double = not in_double
        elif char == "'" and not in_double:
            in_single = not in_single
        elif not in_double and not in_single:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                parts.append(body[start:index])
                start = index + 1
    parts.append(body[start:])
    return parts if len(parts) == 4 else []


def _sheet_name(match: re.Match, default: str) -> str:
    return (match.group(1) or match.group(2) or default).replace("''", "'").strip()


def _quote_sheet(name: str) -> str:
    return f"'{name.replace(chr(39), chr(39) * 2)}'"


def _runs(columns: list[int]) -> list[tuple[int, int]]:
    if not columns:
        return []
    runs, start, end = [], columns[0], columns[0]
    for col in columns[1:]:
        if col == end + 1:
            end = col
        else:
            runs.append((start, end))
            start = end = col
    runs.append((start, end))
    return runs


def _col_number(letters: str) -> int:
    value = 0
    for char in letters.upper():
        value = value * 26 + ord(char) - 64
    return value


def _col_letter(number: int) -> str:
    out = ""
    while number:
        number, rem = divmod(number - 1, 26)
        out = chr(65 + rem) + out
    return out


def _union_ref(sheet: str, row: int, columns: list[int]) -> str:
    refs = [
        f"{_quote_sheet(sheet)}!${_col_letter(start)}${row}:${_col_letter(end)}${row}"
        for start, end in _runs(columns)
    ]
    return refs[0] if len(refs) == 1 else f"({','.join(refs)})"


def _argument_details(arg: str, default_sheet: str) -> tuple[set[str], set[int], list[int]]:
    matches = list(_RANGE_RE.finditer(arg))
    sheets = {_sheet_name(match, default_sheet) for match in matches}
    rows = {int(match.group(4)) for match in matches} | {int(match.group(6)) for match in matches}
    columns = []
    for match in matches:
        start, end = _col_number(match.group(3)), _col_number(match.group(5))
        low, high = (start, end) if start <= end else (end, start)
        columns.extend(range(low, high + 1))
    return sheets, rows, columns


def _rewrite_arg(arg: str, allowed: set[str], selected: dict[str, list[int]], default_sheet: str) -> str | None:
    if not str(arg).strip():
        return arg
    sheets, rows, _ = _argument_details(arg, default_sheet)
    if len(sheets) != 1 or len(rows) != 1:
        return None
    sheet = next(iter(sheets))
    if sheet not in allowed or not selected.get(sheet):
        return None
    return _union_ref(sheet, next(iter(rows)), selected[sheet])


def rewrite_series_formula(
    formula: str, allowed: set[str], selected: dict[str, list[int]], default_sheet: str
) -> str | None:
    parts = _split_series(formula)
    if not parts:
        return None
    categories = _rewrite_arg(parts[1], allowed, selected, default_sheet)
    values = _rewrite_arg(parts[2], allowed, selected, default_sheet)
    if categories is None or values is None:
        return None
    return f"=SERIES({parts[0]},{categories},{values},{parts[3]})"


def _in_scope(formula: str, allowed: set[str], default_sheet: str) -> bool:
    return any(_sheet_name(match, default_sheet) in allowed for match in _RANGE_RE.finditer(formula))


def series_period_kind(
    formula: str, period_maps: dict[str, dict[Period, int]], default_sheet: str
) -> str | None:
    """当前 SERIES 引用的期间类型。无法判断或混杂时返回 None。"""
    parts = _split_series(formula)
    if not parts:
        return None
    kinds = set()
    for arg in (parts[1], parts[2]):
        if not str(arg).strip():
            continue
        sheets, _, columns = _argument_details(arg, default_sheet)
        if len(sheets) != 1:
            return None
        mapping = period_maps.get(next(iter(sheets)), {})
        inverse = {col: period for period, col in mapping.items()}
        for col in columns:
            period = inverse.get(col)
            if period is not None:
                kinds.add(period.kind)
    if len(kinds) == 1:
        return next(iter(kinds))
    return None


# Excel XlDataLabelsType.xlDataLabelsShowValue；次坐标轴线系列只改
# HasDataLabel 在保存后会被丢掉，必须先 ApplyDataLabels 再删掉非同期点。
_SHOW_VALUE = 2


def _is_filtered(item) -> bool:
    try:
        return bool(item.IsFiltered)
    except Exception:
        return False


def _set_filtered(item, filtered: bool) -> None:
    if not filtered:
        return
    try:
        item.IsFiltered = True
    except Exception:
        pass


def _clear_labels(item) -> None:
    try:
        item.HasDataLabels = False
    except Exception:
        pass
    try:
        for index in range(1, int(item.Points().Count) + 1):
            point = item.Points(index)
            if point.HasDataLabel:
                point.HasDataLabel = False
    except Exception:
        pass


def _style_value_label(label, value) -> None:
    label.ShowValue = True
    label.ShowCategoryName = False
    label.ShowSeriesName = False
    try:
        if isinstance(value, (int, float)) and abs(float(value)) <= 2:
            label.NumberFormat = "0%"
    except Exception:
        pass


def _label_series(item, target: Period) -> tuple[int, list[str]]:
    errors, labeled, parsed = [], 0, 0
    try:
        categories = list(item.XValues) if item.XValues is not None else []
    except Exception:
        categories = []
    if not categories:
        return 0, []
    try:
        values = []
        try:
            values = list(item.Values) if item.Values is not None else []
        except Exception:
            values = []
        applied = False
        try:
            item.ApplyDataLabels(Type=_SHOW_VALUE)
            applied = True
        except Exception:
            _clear_labels(item)
        for point_index, category in enumerate(categories, 1):
            period = Period.parse(category)
            should = period is not None and label_period(period, target)
            if period is not None:
                parsed += 1
            point = item.Points(point_index)
            if should:
                if not applied:
                    point.HasDataLabel = True
                value = values[point_index - 1] if point_index - 1 < len(values) else None
                _style_value_label(point.DataLabel, value)
                if point.HasDataLabel:
                    labeled += 1
                else:
                    errors.append(f"{period.key} 标签未能写上")
            elif applied:
                try:
                    point.DataLabel.Delete()
                except Exception:
                    point.HasDataLabel = False
            else:
                point.HasDataLabel = False
    except Exception as error:  # noqa: BLE001
        errors.append(f"标签写入失败：{error}")
    if parsed == 0:
        errors.append("类别轴无法解析出期间，不能可靠设置同期标签")
    if labeled == 0:
        errors.append("没有生成任何目标同期标签")
    return labeled, errors


def _series_collection(chart):
    try:
        chart.PlotVisibleOnly = False
    except Exception:
        pass
    try:
        collection = chart.FullSeriesCollection()
        if int(collection.Count) > 0:
            return collection
    except Exception:
        pass
    return chart.SeriesCollection()


def _iter_series(wb, sheet_names: tuple[str, ...]):
    for sheet_name in sheet_names:
        ws = wb.Worksheets(sheet_name)
        for chart_index in range(1, int(ws.ChartObjects().Count) + 1):
            collection = _series_collection(ws.ChartObjects(chart_index).Chart)
            for series_index in range(1, int(collection.Count) + 1):
                yield sheet_name, chart_index, series_index, collection.Item(series_index)


def update_chart_sheets(wb, contract, target: Period, period_maps: dict[str, dict[Period, int]]) -> dict:
    live_sheets = {sheet for sheet, mapping in period_maps.items() if target in mapping}
    allowed = contract.writable_sheets & live_sheets
    chart_sheets = contract.charts_for(target.kind)
    selected_periods = {sheet: chart_periods(mapping, target) for sheet, mapping in period_maps.items()}
    selected = {
        sheet: [mapping[period] for period in selected_periods[sheet]]
        for sheet, mapping in period_maps.items()
        if selected_periods[sheet] and sheet in allowed
    }
    rewritten, labeled, ignored, errors = 0, 0, [], []
    pending_labels = []
    if not chart_sheets:
        return {"series_rewritten": 0, "labels_added": 0,
                "series_ignored_out_of_scope": [], "errors": []}
    for sheet_name, chart_index, series_index, item in _iter_series(wb, chart_sheets):
        location = f"{sheet_name} chart {chart_index} series {series_index}"
        try:
            formula = str(item.Formula)
        except Exception as error:  # noqa: BLE001
            errors.append(f"{location}: 无法读取 SERIES：{error}")
            continue
        if not _in_scope(formula, allowed, sheet_name):
            ignored.append(location)
            continue
        kind = series_period_kind(formula, period_maps, sheet_name)
        if kind is not None and kind != target.kind:
            ignored.append(location)
            continue
        new_formula = rewrite_series_formula(formula, allowed, selected, sheet_name)
        if not new_formula:
            errors.append(f"{location}: 引用了授权数据 sheet，但范围结构无法安全改写")
            continue
        filtered = _is_filtered(item)
        try:
            item.Formula = new_formula
        except Exception as error:  # noqa: BLE001
            errors.append(f"{location}: SERIES 写入失败：{error}")
            continue
        _set_filtered(item, filtered)
        rewritten += 1
        parts = _split_series(new_formula)
        if (not filtered) and parts and str(parts[1]).strip():
            pending_labels.append((location, item))
    try:
        wb.Application.CalculateFullRebuild()
    except Exception:
        pass
    for location, item in pending_labels:
        count, label_errors = _label_series(item, target)
        labeled += count
        errors.extend(f"{location}: {error}" for error in label_errors)
    if rewritten == 0:
        errors.append("没有任何引用授权数据 sheet 的图表 series 被更新")
    return {"series_rewritten": rewritten, "labels_added": labeled,
            "series_ignored_out_of_scope": ignored, "errors": errors}


def audit_chart_sheets(wb, contract, target: Period, period_maps: dict[str, dict[Period, int]]) -> dict:
    live_sheets = {sheet for sheet, mapping in period_maps.items() if target in mapping}
    allowed = contract.writable_sheets & live_sheets
    chart_sheets = contract.charts_for(target.kind)
    selected_periods = {sheet: chart_periods(mapping, target) for sheet, mapping in period_maps.items()}
    expected = {
        sheet: [mapping[period] for period in selected_periods[sheet]]
        for sheet, mapping in period_maps.items()
        if selected_periods[sheet] and sheet in allowed
    }
    checked, errors = 0, []
    if not chart_sheets:
        return {"series_checked": 0, "errors": []}
    for sheet_name, chart_index, series_index, item in _iter_series(wb, chart_sheets):
        location = f"{sheet_name} chart {chart_index} series {series_index}"
        formula = str(item.Formula)
        if not _in_scope(formula, allowed, sheet_name):
            continue
        kind = series_period_kind(formula, period_maps, sheet_name)
        if kind is not None and kind != target.kind:
            continue
        parts = _split_series(formula)
        if not parts:
            errors.append(f"{location}: 保存后 SERIES 无法解析")
            continue
        if not str(parts[1]).strip():
            _, _, value_cols = _argument_details(parts[2], sheet_name)
            sheets, _, _ = _argument_details(parts[2], sheet_name)
            data_sheet = next(iter(sheets)) if sheets else None
            if data_sheet and value_cols != expected.get(data_sheet):
                errors.append(f"{location}: 保存后值范围不符合 2019/2023+ 政策")
                continue
            checked += 1
            continue
        category_sheets, _, category_cols = _argument_details(parts[1], sheet_name)
        value_sheets, _, value_cols = _argument_details(parts[2], sheet_name)
        if len(category_sheets) != 1 or category_sheets != value_sheets:
            errors.append(f"{location}: 类别和值引用的数据 sheet 不一致")
            continue
        data_sheet = next(iter(category_sheets))
        if category_cols != expected.get(data_sheet) or value_cols != expected.get(data_sheet):
            errors.append(f"{location}: 保存后范围不符合 2019/2023+ 政策")
            continue
        checked += 1
        if _is_filtered(item):
            continue
        try:
            categories = list(item.XValues)
            for point_index, category in enumerate(categories, 1):
                period = Period.parse(category)
                if period is None:
                    continue
                should_label = label_period(period, target)
                has_label = bool(item.Points(point_index).HasDataLabel)
                if should_label != has_label:
                    errors.append(f"{location}: {period.key} 标签状态不符")
        except Exception as error:  # noqa: BLE001
            errors.append(f"{location}: 保存后标签复核失败：{error}")
    if checked == 0:
        errors.append("保存后没有可核对的授权图表 series")
    return {"series_checked": checked, "errors": errors}
