"""三大航公告解析测试。

固定件是 2026 年 7 月三家公告的真实片段（2026-08-15 发布）。三家格式不同：
  - 南航：有独立「合计」行
  - 东航：总量在指标名行本身
  - 国航：同东航，且带「4、」序号前缀

原实现只认「合计」行，因此东航与国航直接 parser-drift 写不进去。
"""

from __future__ import annotations

import unittest

from modules.aviation_monthly import pipeline as P

# --- 真实公告片段 ---

CSA_PAGE = """
二、旅客运输
载客人数（千人次） 2026年7月 环比 同比 2026年累计 同比
国内 14,573.41 8.12 5.30 90,412.55 2.10
地区 164.03 -2.65 4.73 1,050.31 9.46
国际 1,994.46 5.72 7.05 12,969.69 5.77
合计 16,731.90 7.34 5.46 104,432.55 2.63
"""

CEA_PAGE = """
－地区航线 583.13 9.03% 3,693.64 -0.85%
客运人公里（RPK）
26,985.16 7.13% 164,105.06 4.75%
（百万）
－国内航线 18,033.80 5.91% 106,340.84 1.52%
载运旅客人次（千） 14,267.34 3.98% 87,030.22 0.17%
－国内航线 12,003.81 3.85% 72,401.29 -0.60%
－国际航线 1,912.45 3.75% 12,355.57 4.22%
－地区航线 351.08 10.22% 2,273.36 3.76%
客座率(%) 87.11 2.35pts 86.97 2.17pts
"""

AC_PAGE = """
3、收入货运吨公里(百万)7 473.4 7.0 9.5 2,972.6 4.3
其中: 国内航线 125.0 -7.1 -3.7 915.3 -3.9
4、乘客人数(千) 15,690.8 8.5 31.5 95,389.3 8.0
其中: 国内航线 13,471.8 8.9 34.0 81,071.7 8.0
国际航线 1,814.2 10.2 19.4 11,395.9 8.2
地区航线 404.8 -8.1 10.5 2,921.7 5.1
5、货物及邮件(吨) 127,721.3 0.5 3.9 863,449.5 2.1
"""


class TestParseAirlinePages(unittest.TestCase):
    def test_csa_uses_explicit_total_row(self):
        values, provenance = P.parse_airline_pages("南航", [CSA_PAGE])
        self.assertEqual(values["total"], 16731.90)
        self.assertEqual(values["domestic"], 14573.41)
        self.assertEqual(values["international"], 1994.46)
        self.assertEqual(values["regional"], 164.03)
        self.assertIn("合计", provenance["total"]["row"])

    def test_cea_takes_total_from_metric_line(self):
        values, provenance = P.parse_airline_pages("东航", [CEA_PAGE])
        self.assertEqual(values["total"], 14267.34)
        self.assertEqual(values["domestic"], 12003.81)
        self.assertEqual(values["international"], 1912.45)
        self.assertEqual(values["regional"], 351.08)
        self.assertIn("指标名行", provenance["total"]["row"])

    def test_ac_ignores_enumeration_prefix(self):
        """`4、乘客人数(千) 15,690.8` —— 不能把序号 4 当成总量。"""
        values, _ = P.parse_airline_pages("国航", [AC_PAGE])
        self.assertEqual(values["total"], 15690.8)
        self.assertEqual(values["domestic"], 13471.8)

    def test_all_three_cross_foot(self):
        """总量必须等于分项之和——这是取值正确的独立佐证。"""
        for name, page in (("南航", CSA_PAGE), ("东航", CEA_PAGE), ("国航", AC_PAGE)):
            values, _ = P.parse_airline_pages(name, [page])
            parts = values["domestic"] + values["international"] + values["regional"]
            self.assertAlmostEqual(values["total"], parts, delta=0.05, msg=name)

    def test_missing_anchor_raises_parser_drift(self):
        with self.assertRaises(P.PipelineError) as ctx:
            P.parse_airline_pages("东航", ["完全无关的一页文字"])
        self.assertEqual(ctx.exception.kind, "parser-drift")

    def test_missing_routes_raises_parser_drift(self):
        """只有总量、没有分项时必须报错，不能悄悄放过。"""
        with self.assertRaises(P.PipelineError) as ctx:
            P.parse_airline_pages("东航", ["载运旅客人次（千） 14,267.34 3.98%"])
        self.assertEqual(ctx.exception.kind, "parser-drift")
        self.assertIn("domestic", str(ctx.exception))


class TestTotalOnAnchorLine(unittest.TestCase):
    def test_skips_route_lines(self):
        """分项行即使含锚点也不能当总量。"""
        self.assertIsNone(P.total_on_anchor_line("载运旅客人次", "－国内航线 12,003.81 3.85%"))

    def test_returns_none_without_anchor(self):
        self.assertIsNone(P.total_on_anchor_line("载运旅客人次", "客座率(%) 87.11 2.35pts"))

    def test_returns_none_when_no_number_after_anchor(self):
        self.assertIsNone(P.total_on_anchor_line("乘客人数", "4、乘客人数(千)"))

    def test_takes_first_number_after_anchor_only(self):
        self.assertEqual(P.total_on_anchor_line("乘客人数", "4、乘客人数(千) 15,690.8 8.5"), 15690.8)


if __name__ == "__main__":
    unittest.main()
