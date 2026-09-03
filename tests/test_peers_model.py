"""Peers Model 期间解析、图表改写与合同。"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from modules.peers_model.charts import rewrite_series_formula, series_period_kind
from modules.peers_model.contracts import load
from modules.peers_model.periods import (
    Period,
    chart_periods,
    label_period,
    previous_quarter,
    source_period,
)

ROOT = Path(__file__).resolve().parents[1]


class TestPeriodParse(unittest.TestCase):
    def test_quarter_styles(self):
        self.assertEqual(Period.parse("26Q2").key, "26Q2")
        self.assertEqual(Period.parse("2026Q2").key, "26Q2")
        self.assertEqual(Period.parse("2Q26").key, "26Q2")
        self.assertEqual(Period.parse("3Q24").key, "24Q3")

    def test_half_styles(self):
        self.assertEqual(Period.parse("2017 1H").key, "17H1")
        self.assertEqual(Period.parse("2017-1H").key, "17H1")
        self.assertEqual(Period.parse("17H2").key, "17H2")
        self.assertEqual(Period.parse("1H26").key, "26H1")

    def test_year_styles_reject_estimates(self):
        self.assertEqual(Period.parse(2025).key, "FY2025")
        self.assertEqual(Period.parse("FY 2025").key, "FY2025")
        self.assertEqual(Period.parse("2023FY").key, "FY2023")
        self.assertIsNone(Period.parse("FY 2025(BBG EST.)"))
        self.assertIsNone(Period.parse("2024E"))

    def test_label_like_preserves_sheet_style(self):
        self.assertEqual(Period.parse("26Q3").label_like("2026Q2"), "2026Q3")
        self.assertEqual(Period.parse("26Q3").label_like("2Q26"), "3Q26")
        self.assertEqual(Period.parse("FY2026").label_like(2025), 2026)


class TestPeriodPolicy(unittest.TestCase):
    def test_previous_quarter_wraps_year(self):
        self.assertEqual(previous_quarter(Period.parse("26Q1")).key, "25Q4")
        self.assertEqual(previous_quarter(Period.parse("26Q2")).key, "26Q1")

    def test_source_period_requires_adjacent_quarter(self):
        periods = {Period.parse("26Q1"): 10, Period.parse("25Q4"): 9}
        self.assertEqual(source_period(Period.parse("26Q2"), periods).key, "26Q1")
        self.assertIsNone(source_period(Period.parse("26Q3"), periods))
        fallback = source_period(Period.parse("26Q3"), periods, require_previous=False)
        self.assertEqual(fallback.key, "26Q1")

    def test_chart_periods_skip_pandemic_years(self):
        available = [
            Period.parse(f"{yy}Q{q}")
            for yy in ("19", "20", "21", "22", "23", "24", "25", "26")
            for q in range(1, 5)
            if not (yy == "26" and q > 2)
        ]
        keys = [item.key for item in chart_periods(available, Period.parse("26Q2"))]
        self.assertEqual(keys[0], "19Q2")
        self.assertNotIn("19Q1", keys)
        self.assertNotIn("20Q2", keys)
        self.assertNotIn("21Q1", keys)
        self.assertNotIn("22Q4", keys)
        self.assertIn("23Q1", keys)
        self.assertEqual(keys[-1], "26Q2")

    def test_labels_only_same_season(self):
        target = Period.parse("26Q3")
        self.assertTrue(label_period(Period.parse("19Q3"), target))
        self.assertTrue(label_period(Period.parse("23Q3"), target))
        self.assertTrue(label_period(Period.parse("26Q3"), target))
        self.assertFalse(label_period(Period.parse("26Q2"), target))
        self.assertFalse(label_period(Period.parse("20Q3"), target))
        self.assertFalse(label_period(Period.parse("22Q3"), target))

    def test_half_and_year_chart_windows(self):
        halves = [Period.parse(f"{yy}H1") for yy in ("19", "20", "23", "24", "25", "26")]
        self.assertEqual(
            [item.key for item in chart_periods(halves, Period.parse("26H1"))],
            ["19H1", "23H1", "24H1", "25H1", "26H1"],
        )
        years = [Period.parse(f"FY{year}") for year in range(2019, 2027)]
        self.assertEqual(
            [item.key for item in chart_periods(years, Period.parse("FY2026"))],
            ["FY2019", "FY2023", "FY2024", "FY2025", "FY2026"],
        )


class TestChartRewrite(unittest.TestCase):
    def test_contiguous_range_becomes_union_skipping_gap(self):
        selected = {"EXPE": [34, 35, 36, 37, 50, 51, 52]}
        formula = "=SERIES(EXPE!$A$5,EXPE!$AH$3:$BW$3,EXPE!$AH$5:$BW$5,1)"
        new = rewrite_series_formula(formula, {"EXPE"}, selected, "EXPE Quarterly Charts")
        self.assertIn("EXPE'!$AH$3:$AK$3", new)
        self.assertIn("EXPE'!$AX$3:$AZ$3", new)
        self.assertNotIn("$BW$", new)

    def test_existing_union_is_rewritten(self):
        selected = {"Key Financial Data": [10, 11, 12, 13, 26, 27]}
        formula = (
            "=SERIES('Key Financial Data'!$A$5,"
            "('Key Financial Data'!$J$3:$M$3,'Key Financial Data'!$Z$3:$AM$3),"
            "('Key Financial Data'!$J$5:$M$5,'Key Financial Data'!$Z$5:$AM$5),1)"
        )
        new = rewrite_series_formula(formula, {"Key Financial Data"}, selected, "charts")
        self.assertIn("$J$3:$M$3", new)
        self.assertIn("$Z$3:$AA$3", new)
        self.assertNotIn("$AM$", new)

    def test_empty_categories_keep_empty_and_rewrite_values(self):
        selected = {"Tongchengelong": [26, 27, 52]}
        formula = '=SERIES("交易额同比",,Tongchengelong!$Z$77:$AZ$77,2)'
        new = rewrite_series_formula(formula, {"Tongchengelong"}, selected, "TCEL charts")
        self.assertTrue(new.startswith('=SERIES("交易额同比",,'))
        self.assertIn("$Z$77:$AA$77", new)

    def test_series_name_with_comma_still_splits(self):
        from modules.peers_model.charts import _split_series
        formula = (
            '=SERIES("Instore,Hotels and Travel YoY growth",'
            "'Segment Reporting'!$AT$3:$AX$3,'Segment Reporting'!$AT$71:$AX$71,5)"
        )
        parts = _split_series(formula)
        self.assertEqual(len(parts), 4)
        self.assertIn("Instore,Hotels", parts[0])
        self.assertIn("$AT$3:$AX$3", parts[1])

    def test_series_kind_from_period_map(self):
        mapping = {Period.parse("26Q1"): 74, Period.parse("26Q2"): 75, Period.parse("FY2025"): 86}
        formula = "=SERIES(EXPE!$A$5,EXPE!$AT$3:$BW$3,EXPE!$AT$5:$BW$5,1)"
        self.assertEqual(series_period_kind(formula, {"EXPE": mapping}, "EXPE"), "quarter")


class TestContracts(unittest.TestCase):
    def test_known_companies_and_tcel_allowlist(self):
        tcel = load("TCEL")
        self.assertEqual([item["name"] for item in tcel.sheets], ["Tongchengelong", "Sheet6"])
        self.assertEqual(tcel.charts_for("quarter"), ("TCEL charts",))
        self.assertEqual(tcel.charts_for("half"), ())
        self.assertNotIn("Comp", tcel.writable_sheets)

    def test_abe_companies_share_workbook_but_not_sheets(self):
        bkng, expe, abnb = load("BKNG"), load("EXPE"), load("ABNB")
        self.assertEqual(bkng.workbook_key, expe.workbook_key)
        self.assertEqual(bkng.writable_sheets, {"BKNG"})
        self.assertEqual(expe.writable_sheets, {"EXPE"})
        self.assertEqual(abnb.writable_sheets, {"ABNB"})
        self.assertEqual(bkng.charts_for("year"), ())

    def test_meituan_quarter_skips_old_segment_block(self):
        mt = load("MEITUAN")
        quarter_sheets = [item["name"] for item in mt.sheets if "quarter" in item["kinds"]]
        self.assertEqual(quarter_sheets, ["Key Financial Data", "New Segment Reporting"])
        half_sheets = [item["name"] for item in mt.sheets if "half" in item["kinds"]]
        self.assertIn("Segment Reporting", half_sheets)

    def test_contract_json_is_valid(self):
        folder = ROOT / "modules" / "peers_model" / "contracts"
        for path in folder.glob("*.json"):
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("company", raw)
            self.assertIn("sheets", raw)


if __name__ == "__main__":
    unittest.main()
