"""港股市场迁移回归测试。"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from modules.hk_market import market, southbound, volume_ratio
from modules.sellside_research import reader
from workbench.cli import build_parser

import pandas as pd


class TestVolumeRatio(unittest.TestCase):
    def test_regulatory_status_uses_complete_fy_not_recent_trend(self):
        periods = pd.period_range("2025-01", "2026-03", freq="M")
        hk = [40.0] * 12 + [90.0] * 3
        frame = pd.DataFrame(
            {
                "HK_Turnover_HKD": hk,
                "Global_Turnover_HKD": [100.0] * 15,
                "HK_Ratio": hk,
            },
            index=periods,
        )
        summary = volume_ratio.summarize(frame)
        self.assertEqual(summary["FY_label"], "25FY")
        self.assertAlmostEqual(summary["FY"], 40.0)
        self.assertGreater(summary["latest_quarter"], 55.0)
        self.assertIn("距阈值", volume_ratio.regulatory_status(summary))
        self.assertNotIn("已达", volume_ratio.regulatory_status(summary))

    def test_default_window_includes_previous_fy(self):
        self.assertEqual(
            volume_ratio.default_window(pd.Timestamp("2026-09-02").date()),
            ("2025-01-01", "2026-09-03"),
        )

    def test_incomplete_year_cannot_trigger_regulatory_status(self):
        periods = pd.period_range("2025-02", "2026-03", freq="M")
        frame = pd.DataFrame(
            {
                "HK_Turnover_HKD": [90.0] * len(periods),
                "Global_Turnover_HKD": [100.0] * len(periods),
                "HK_Ratio": [90.0] * len(periods),
            },
            index=periods,
        )
        summary = volume_ratio.summarize(frame)
        self.assertIsNone(summary["FY"])
        self.assertIn("不完整", summary["FY_label"])
        self.assertEqual(volume_ratio.regulatory_status(summary), "数据缺失")

    def test_stock_parser_rejects_ambiguous_shape(self):
        with self.assertRaises(ValueError):
            volume_ratio.parse_stocks("携程,09961,TCOM")


class TestMarketPulse(unittest.TestCase):
    def test_week_stats_is_close_to_close_and_sums_each_iso_week(self):
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2026-08-24", "2026-08-28", "2026-08-31", "2026-09-01", "2026-09-02"]
                ),
                "close": [100, 110, 111, 115, 121],
                "amount": [1e8, 2e8, 3e8, 4e8, 5e8],
            }
        )
        result = market.week_stats(frame, "2026-09-02")
        self.assertIsNotNone(result)
        self.assertEqual(result["close_prev"], 110.0)
        self.assertEqual(result["close_this"], 121.0)
        self.assertEqual(result["wow_pct"], 10.0)
        self.assertEqual(result["turnover_this_yi"], 12.0)


class FakeCCASS:
    def query(self, requested: str):
        day = int(requested[-2:])
        rows = {
            9961: {"pct": 9.0 + day / 10, "name": "携程集团", "shares": "1"},
        }
        return requested, rows

    def latest(self):
        return self.query("2026/06/03")


class TestSouthbound(unittest.TestCase):
    def test_month_scan_uses_actual_dates_and_keeps_missing_watchlist(self):
        result = southbound.analyze("2026-06-03", client=FakeCCASS())
        self.assertEqual(result["as_of"], "2026/06/03")
        self.assertEqual(result["trading_days"], ["2026/06/01", "2026/06/02", "2026/06/03"])
        self.assertEqual(result["stocks"]["9961"]["month_change_pp"], 0.2)
        self.assertTrue(result["stocks"]["780"]["missing"])


class TestSellsideReader(unittest.TestCase):
    def test_clean_text_removes_pdf_noise(self):
        self.assertEqual(reader.clean_text("a  \n\n\nb\x00"), "a\n\nb")

    def test_non_pdf_is_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.txt"
            path.write_text("x", encoding="utf-8")
            with self.assertRaises(reader.ResearchError):
                reader.extract(path)


class TestCliRegistration(unittest.TestCase):
    def test_remaining_step_four_commands_are_registered(self):
        parser = build_parser()
        hk = parser.parse_args(["hk-market", "market", "--as-of", "2026-09-02"])
        self.assertEqual(hk.hk_market_command, "market")
        sellside = parser.parse_args(["sellside", "extract", "--file", "report.pdf"])
        self.assertEqual(sellside.sellside_command, "extract")


if __name__ == "__main__":
    unittest.main()
