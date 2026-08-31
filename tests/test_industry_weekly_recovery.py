"""底稿人工填写失误的容错与兜底。

这些用例钉住的是 2026-08-31 那次真实事故及其成因：

底稿的周度数据有两处——右侧周度区（R/S/T/U/W/X/Y）与左侧「QTD周度」块（B/C/D/E/G/H/I），
同样的六项，使用者两边都手填。于是有两个**每期都可能发生**的失误：

1. 给左侧 QTD 加一周时整行插入 → 右侧周轴中间被punch出一个空行；
2. 只填了左侧，忘了填右侧。

旧实现遇到空行即认为「块到此结束」，于是 9 周 × 6 序列共 54 个值静默消失，
`dataUpdate` 从 2026-08-15 倒退到 2026-06-13，而 diff 门禁报「清空 0」照常写入。
全绿、无告警、下游看板照常生成——最难发现的一类失败。

所以这里既要验「读表能自己兜住」，也要验「万一没兜住，门禁拦得下来」。
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from modules.industry_data import excel, snapshot
from modules.industry_data.paths import DomainPaths
from workbench.paths import Paths

from test_industry_crosscheck import build  # noqa: E402 —— discover 以顶层模块方式加载 tests/


def parse(**kwargs) -> tuple[dict, list[str]]:
    with TemporaryDirectory() as tmp:
        parsed = excel.parse(build(Path(tmp) / "wb.xlsx", **kwargs))
        return parsed["weekly"], parsed["diagnostics"]


class AxisHoleCase(unittest.TestCase):
    """周轴中间的空行必须跳过，而不是当成块尾。"""

    def test_hole_does_not_truncate_axis(self):
        weekly, notes = parse(right_rows=["8/2-8/8", None, "8/9-8/15", "8/16-8/22"])

        self.assertEqual(weekly["weeks"], ["8/2-8/8", "8/9-8/15", "8/16-8/22"])
        self.assertEqual(excel.infer_data_update(weekly["weeks"]), "2026-08-22")
        self.assertTrue(any("空行" in note for note in notes), notes)

    def test_hole_keeps_values_aligned_with_labels(self):
        """空行不能让数值整体错位——错位比截断更难发现。"""
        weekly, _ = parse(
            right_rows=["8/2-8/8", None, "8/9-8/15"],
            hotel=[(0.11, 0.12, 0.13), (0.21, 0.22, 0.23)],
        )

        self.assertEqual(weekly["weeks"], ["8/2-8/8", "8/9-8/15"])
        self.assertEqual(weekly["hotelOccupancy"], [0.11, 0.21])
        self.assertEqual(weekly["hotelRevPAR"], [0.13, 0.23])

    def test_several_holes_all_reported(self):
        weekly, notes = parse(right_rows=["8/2-8/8", None, "8/9-8/15", None, "8/16-8/22"])

        self.assertEqual(len(weekly["weeks"]), 3)
        self.assertTrue(any("空行" in note for note in notes), notes)

    def test_long_blank_run_ends_the_block(self):
        """连续空太多就不是插行带出来的洞了，块到此为止——否则会把无关内容读进来。"""
        weekly, _ = parse(
            right_rows=["8/2-8/8", None, None, None, None, "1/4-1/10"],
        )

        self.assertEqual(weekly["weeks"], ["8/2-8/8"])

    def test_trailing_blank_rows_are_not_holes(self):
        """末周之后的留白是块尾，不该报成洞。"""
        _weekly, notes = parse(right_rows=["8/2-8/8", "8/9-8/15", None, None])

        self.assertFalse([note for note in notes if "空行" in note], notes)

    def test_tail_note_is_not_read_as_a_week(self):
        """底稿末尾那行 `Notes：春节数据为民航局日均（含出境）` 同时含「春节」「日均」，
        注释判断必须排在它们前面。"""
        weekly, _ = parse(
            right_rows=["8/2-8/8", "8/9-8/15"],
            tail_note="Notes：春节数据为民航局日均（含出境）",
        )

        self.assertEqual(weekly["weeks"], ["8/2-8/8", "8/9-8/15"])


class LeftFallbackCase(unittest.TestCase):
    """人只填了左侧时，右侧不能就这么空着。"""

    def test_hotel_falls_back_to_left_not_only_aviation(self):
        """原实现只兜航空，酒店 S/T/U 空着就真空着。"""
        weekly, notes = parse(
            hotel=[(0.11, 0.12, 0.13), (None, None, None), (0.31, 0.32, 0.33)],
            left_hotel=[None, (0.21, 0.22, 0.23), None],
        )

        self.assertEqual(weekly["hotelOccupancy"], [0.11, 0.21, 0.31])
        self.assertEqual(weekly["hotelADR"], [0.12, 0.22, 0.32])
        self.assertTrue(any("兜上" in note for note in notes), notes)

    def test_right_still_wins_when_both_filled(self):
        """左侧是安全网，不是第二个权威。"""
        weekly, _ = parse(
            hotel=[(0.11, 0.12, 0.13)] * 3,
            left_hotel=[(0.99, 0.99, 0.99)] * 3,
        )

        self.assertEqual(weekly["hotelOccupancy"], [0.11, 0.11, 0.11])

    def test_week_missing_on_the_right_is_appended_from_left(self):
        """整周漏填右侧：按左侧的值补进轴末尾，`dataUpdate` 才不会倒退。"""
        weekly, notes = parse(
            right_rows=["8/2-8/8", "8/9-8/15"],
            left_labels=["8/2-8/8", "8/9-8/15", "8/16-8/22"],
            left=[None, None, (0.5, 0.6, 0.7)],
            left_hotel=[None, None, (0.1, 0.2, 0.3)],
        )

        self.assertEqual(weekly["weeks"], ["8/2-8/8", "8/9-8/15", "8/16-8/22"])
        self.assertEqual(weekly["aviationPax"][-1], 0.5)
        self.assertEqual(weekly["hotelOccupancy"][-1], 0.1)
        self.assertEqual(excel.infer_data_update(weekly["weeks"]), "2026-08-22")
        self.assertTrue(any("只在左侧" in note for note in notes), notes)

    def test_earlier_left_only_week_is_reported_not_appended(self):
        """更早的缺口位置在中间，接到末尾会打乱时间顺序——只报，不接。"""
        weekly, notes = parse(
            right_rows=["8/9-8/15", "8/16-8/22"],
            left_labels=["8/2-8/8", "8/9-8/15", "8/16-8/22"],
            left=[(0.5, 0.6, 0.7), None, None],
        )

        self.assertEqual(weekly["weeks"], ["8/9-8/15", "8/16-8/22"])
        self.assertTrue(any("没有" in note and "并入" in note for note in notes), notes)

    def test_empty_left_row_is_not_appended(self):
        """左侧有标签但六项全空，补进来只会凭空造一个空周。"""
        weekly, _ = parse(
            right_rows=["8/2-8/8", "8/9-8/15"],
            left_labels=["8/2-8/8", "8/9-8/15", "8/16-8/22"],
        )

        self.assertEqual(weekly["weeks"], ["8/2-8/8", "8/9-8/15"])

    def test_clean_workbook_says_nothing(self):
        """两边都填好时不该有任何提醒——每期都刷警告等于没有警告。"""
        _weekly, notes = parse(
            right=[(0.5, 0.6, 0.7)] * 3,
            left=[(0.5, 0.6, 0.7)] * 3,
        )

        self.assertEqual(notes, [])


class GateBackstopCase(unittest.TestCase):
    """读表兜不住时，门禁必须拦下来。下一个把轴读短的原因不会是同一个。"""

    @staticmethod
    def diff(old_weeks: list[str], new_weeks: list[str]) -> snapshot.Diff:
        def block(weeks: list[str]) -> dict:
            return {
                "weekly": {"weeks": weeks, "hotelOccupancy": [0.1] * len(weeks)},
                "monthly": {"months": []},
                "quarterly": {},
            }

        return snapshot.compute_diff(block(old_weeks), block(new_weeks))

    def test_vanished_label_counts_as_lost(self):
        """旧门禁只在**新轴的标签**上逐格比，标签本身消失时一格都不命中。"""
        diff = self.diff(["8/2-8/8", "8/9-8/15"], ["8/2-8/8"])

        self.assertEqual(diff.cleared, [])
        self.assertEqual(len(diff.dropped_values), 1)
        self.assertEqual(len(diff.lost), 1)
        self.assertTrue(diff.blocked_reasons)

    def test_growing_axis_is_not_blocked(self):
        diff = self.diff(["8/2-8/8"], ["8/2-8/8", "8/9-8/15"])

        self.assertEqual(diff.lost, [])
        self.assertEqual(diff.blocked_reasons, [])

    def test_data_update_regression_is_blocked(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
            paths = DomainPaths(Paths(root))
            paths.snapshot.parent.mkdir(parents=True, exist_ok=True)
            paths.snapshot.write_text(
                '{"weekly": {"weeks": []}, "monthly": {"months": []}, '
                '"quarterly": {}, "meta": {"dataUpdate": "2026-08-15"}}',
                encoding="utf-8",
            )

            real_build = snapshot.build
            snapshot.build = lambda workbook, previous: {
                "weekly": {"weeks": []},
                "monthly": {"months": []},
                "quarterly": {},
                "meta": {"dataUpdate": "2026-06-13"},
            }
            try:
                result = snapshot.rebuild(paths, root / "fake.xlsx")
            finally:
                snapshot.build = real_build

        self.assertEqual(result.status, "blocked")
        self.assertTrue(any("倒退" in warning for warning in result.warnings), result.warnings)


if __name__ == "__main__":
    unittest.main()
