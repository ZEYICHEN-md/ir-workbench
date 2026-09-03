"""Seasonal integer chart labels and their must-pass geometry audit.

Ported from the authoritative chart-label helper.  Labels are limited to the
same calendar quarter, integer percentages, and are nudged away from sibling
labels and the x-axis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

XL_CENTER, XL_ABOVE, XL_BELOW, XL_LEFT, XL_RIGHT = -4108, 0, 1, -4131, -4152
DECIMAL_PCT_RE = re.compile(r"\d+\.\d+\s*%")


def quarter_num(quarter: str) -> int:
    return int(quarter[-1])


def category_matches_quarter(category, number: int) -> bool:
    text = str(category).upper().replace(" ", "")
    return f"Q{number}" in text


def fmt_pct(value) -> str | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if abs(number) > 2:
        return None
    return f"{int(round(number * 100))}%"


def is_integer_pct_text(text: str) -> bool:
    return not text or DECIMAL_PCT_RE.search(str(text)) is None


@dataclass
class LabelBox:
    series: int
    point: int
    text: str
    left: float
    top: float
    width: float
    height: float
    category: str = ""

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height


def boxes_overlap(left: LabelBox, right: LabelBox, pad: float = 2.0) -> bool:
    return not (
        left.right + pad <= right.left
        or right.right + pad <= left.left
        or left.bottom + pad <= right.top
        or right.bottom + pad <= left.top
    )


def _clear_labels(series) -> None:
    try:
        series.HasDataLabels = False
    except Exception:
        pass
    try:
        count = series.Points().Count
    except Exception:
        return
    for index in range(1, count + 1):
        try:
            series.Points(index).HasDataLabel = False
        except Exception:
            pass


def _style_label(
    data_label,
    text: str,
    *,
    size: int = 9,
    position: int = XL_ABOVE,
) -> None:
    data_label.ShowSeriesName = False
    data_label.ShowCategoryName = False
    data_label.ShowValue = True
    data_label.NumberFormat = "0%"
    try:
        data_label.Position = position
    except Exception:
        pass
    data_label.Font.Size = size
    data_label.Font.Bold = True
    data_label.Font.Color = 0x000000
    try:
        data_label.Text = text
    except Exception:
        pass
    try:
        data_label.Format.Fill.Visible = True
        data_label.Format.Fill.Solid()
        data_label.Format.Fill.ForeColor.RGB = 0xFFFFFF
    except Exception:
        pass


def collect_label_boxes(chart) -> list[LabelBox]:
    boxes: list[LabelBox] = []
    collection = chart.SeriesCollection()
    for series_index in range(1, collection.Count + 1):
        series = collection.Item(series_index)
        try:
            categories = list(series.XValues)
            count = series.Points().Count
        except Exception:
            continue
        for point_index in range(1, count + 1):
            try:
                point = series.Points(point_index)
                if not point.HasDataLabel:
                    continue
                label = point.DataLabel
                boxes.append(
                    LabelBox(
                        series=series_index,
                        point=point_index,
                        text=str(label.Text or "").strip(),
                        left=float(label.Left),
                        top=float(label.Top),
                        width=float(label.Width),
                        height=float(label.Height),
                        category=(
                            str(categories[point_index - 1]).strip()
                            if point_index <= len(categories)
                            else ""
                        ),
                    )
                )
            except Exception:
                continue
    return boxes


def _plot_bottom(chart) -> float | None:
    try:
        return float(chart.PlotArea.Top) + float(chart.PlotArea.Height)
    except Exception:
        return None


def resolve_label_overlaps(
    chart, *, max_passes: int = 8, min_gap: float = 3.0
) -> int:
    moves = 0
    series_collection = chart.SeriesCollection()
    bottom = _plot_bottom(chart)
    for _ in range(max_passes):
        boxes = collect_label_boxes(chart)
        changed = False
        if bottom is not None:
            for box in boxes:
                if box.bottom > bottom - 4:
                    try:
                        label = series_collection.Item(box.series).Points(
                            box.point
                        ).DataLabel
                        label.Top = label.Top - (box.bottom - (bottom - 6)) - 4
                        moves += 1
                        changed = True
                    except Exception:
                        pass
        boxes = collect_label_boxes(chart)
        for left_index in range(len(boxes)):
            for right_index in range(left_index + 1, len(boxes)):
                left, right = boxes[left_index], boxes[right_index]
                if not boxes_overlap(left, right, pad=min_gap):
                    continue
                lower, upper = (
                    (left, right) if left.top >= right.top else (right, left)
                )
                gap = max(min_gap + 2, upper.bottom + min_gap - lower.top)
                try:
                    label = series_collection.Item(lower.series).Points(
                        lower.point
                    ).DataLabel
                    label.Top -= gap
                    moves += 1
                    changed = True
                except Exception:
                    pass
        if not changed:
            break
    return moves


def _seasonal_labels(
    series,
    q_number: int,
    *,
    center: bool = False,
    size: int = 9,
) -> list[str]:
    _clear_labels(series)
    try:
        categories = list(series.XValues)
        values = list(series.Values)
    except Exception:
        return []
    hits = [
        index
        for index, category in enumerate(categories, 1)
        if category_matches_quarter(category, q_number)
    ]
    output = []
    for index in hits:
        text = fmt_pct(values[index - 1] if index <= len(values) else None)
        if text is None:
            continue
        point = series.Points(index)
        point.HasDataLabel = True
        _style_label(
            point.DataLabel,
            text,
            size=size,
            position=XL_CENTER if center else XL_ABOVE,
        )
        if index == hits[-1]:
            try:
                point.DataLabel.Left -= 18
                point.DataLabel.Top -= 14
            except Exception:
                pass
        output.append(f"{categories[index - 1]}={text}")
    return output


def _last_nonempty(series) -> tuple[int, object] | None:
    try:
        values = list(series.Values)
        count = series.Points().Count
    except Exception:
        return None
    index = count
    for probe in range(len(values), 0, -1):
        if values[probe - 1] not in (None, ""):
            index = probe
            break
    return index, values[index - 1]


def _opex_prefix(name: str) -> str:
    lowered = name.lower()
    for keys, prefix in (
        (("cost of", "cos"), "COS "),
        (("p&d", "product", "technology", "tech"), "P&D "),
        (("s&m", "marketing", "selling"), "S&M "),
        (("g&a", "admin", "general"), "G&A "),
        (("operations and support",), "Ops "),
    ):
        if any(key in lowered for key in keys):
            return prefix
    return ""


def apply_chart_labels(chart, q_number: int, chart_title: str = "") -> list[str]:
    title = (chart_title or "").lower()
    collection = chart.SeriesCollection()
    for index in range(1, collection.Count + 1):
        _clear_labels(collection.Item(index))
    log: list[str] = []

    if "take rate" in title:
        if collection.Count >= 1:
            log += [
                f"s1:{item}"
                for item in _seasonal_labels(collection.Item(1), q_number)
            ]
        if collection.Count >= 2:
            second = collection.Item(2)
            last = _last_nonempty(second)
            if last:
                index, value = last
                text = fmt_pct(value)
                if text:
                    point = second.Points(index)
                    point.HasDataLabel = True
                    _style_label(
                        point.DataLabel,
                        f"TTM {text}",
                        size=8,
                        position=XL_BELOW,
                    )
                    try:
                        point.DataLabel.Left += 14
                        point.DataLabel.Top += 10
                    except Exception:
                        pass
                    log.append(f"s2:TTM {text}")
        moves = resolve_label_overlaps(
            chart, max_passes=10, min_gap=4.0
        )
        if moves:
            log.append(f"overlap_nudge:{moves}")
        return log

    if "opex" in title or "operating expense" in title:
        placed = []
        for index in range(1, collection.Count + 1):
            series = collection.Item(index)
            last = _last_nonempty(series)
            if not last:
                continue
            point_index, value = last
            text = fmt_pct(value)
            if not text:
                continue
            try:
                name = series.Name or ""
            except Exception:
                name = ""
            shown = f"{_opex_prefix(name)}{text}"
            point = series.Points(point_index)
            point.HasDataLabel = True
            position = XL_RIGHT if float(value) >= 0.20 else XL_LEFT
            _style_label(point.DataLabel, shown, size=8, position=position)
            placed.append((float(value), point.DataLabel))
            log.append(f"s{index}:{shown}")
        for rank, (value, label) in enumerate(
            sorted(placed, key=lambda item: -item[0])
        ):
            try:
                label.Top -= 12 + rank * 8
                label.Left += 12 if value >= 0.20 else -12
            except Exception:
                pass
        moves = resolve_label_overlaps(
            chart, max_passes=12, min_gap=5.0
        )
        if moves:
            log.append(f"overlap_nudge:{moves}")
        return log

    for index in range(1, collection.Count + 1):
        series = collection.Item(index)
        try:
            name = (series.Name or "").lower()
        except Exception:
            name = ""
        if (
            "yoy" in name
            or "growth" in name
            or "同比" in name
            or ("margin" in name and "margin" in title)
        ):
            log += [
                f"s{index}:{item}"
                for item in _seasonal_labels(series, q_number)
            ]
        elif (
            "%" in name
            and any(key in name for key in ("agency", "merchant"))
            and any(key in title for key in ("business", "业务", "by busines"))
        ):
            log += [
                f"s{index}:{item}"
                for item in _seasonal_labels(
                    series, q_number, center=True, size=10
                )
            ]
    moves = resolve_label_overlaps(chart)
    if moves:
        log.append(f"overlap_nudge:{moves}")
    return log


def audit_chart_labels(
    chart,
    q_number: int,
    chart_title: str = "",
    *,
    require_labels: bool = False,
) -> list[str]:
    title = (chart_title or "").lower()
    boxes = collect_label_boxes(chart)
    if require_labels and not boxes:
        return [f"no data labels on {chart_title!r}"]
    errors: list[str] = []
    for box in boxes:
        if not is_integer_pct_text(box.text):
            errors.append(f"non-integer pct label {box.text!r}")
        exempt = (
            "opex" in title
            or "operating expense" in title
            or ("take rate" in title and box.text.upper().startswith("TTM"))
        )
        if (
            not exempt
            and box.category
            and re.search(r"Q[1-4]", box.category.upper())
            and not category_matches_quarter(box.category, q_number)
        ):
            errors.append(
                f"off-season label {box.text!r} on {box.category!r}"
            )
    bottom = _plot_bottom(chart)
    if bottom is not None:
        for box in boxes:
            if box.bottom > bottom - 2:
                errors.append(f"label overlaps plot bottom {box.text!r}")
    for left in range(len(boxes)):
        for right in range(left + 1, len(boxes)):
            if boxes_overlap(boxes[left], boxes[right], pad=2.0):
                errors.append(
                    f"label overlap {boxes[left].text!r} vs "
                    f"{boxes[right].text!r}"
                )
    return errors
