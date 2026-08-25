"""浮点归一的测试。

要钉住两件相反的事：
1. 尾数噪音必须被消掉——否则每次上线的 diff 都掺无意义的行，把真变化埋掉；
2. 真实精度不能被削掉——归一不是四舍五入到两位小数，业务值必须完好。
"""

from __future__ import annotations

import unittest

from modules.industry_data.normalize import (
    SIGNIFICANT_DIGITS,
    count_changes,
    normalize,
    normalize_number,
)


class TestNormalizeNumber(unittest.TestCase):
    def test_removes_com_recalc_tail(self):
        """Excel COM 全量重算后的表示（变长）。"""
        for noisy, clean in (
            (-0.10400000000000009, -0.104),
            (-0.06799999999999995, -0.068),
            (-0.15000000000000002, -0.15),
            (0.028999999999999998, 0.029),
            (-0.13999999999999999, -0.14),
        ):
            self.assertEqual(normalize_number(noisy), clean, f"{noisy!r}")

    def test_short_representation_is_already_clean(self):
        """人手动保存后的表示（较短）本身就干净，不该被再动。"""
        for value in (-0.104, -0.068, 0.029, -0.14, -0.03, -0.01):
            self.assertEqual(normalize_number(value), value)

    def test_two_save_paths_converge(self):
        """同一个业务值经两种保存路径后，归一结果必须相同——这才消掉了噪音。"""
        pairs = [
            (-0.104, -0.10400000000000009),
            (0.029, 0.028999999999999998),
            (-0.14, -0.13999999999999999),
        ]
        for manual, recalced in pairs:
            self.assertEqual(normalize_number(manual), normalize_number(recalced))

    def test_meaningful_precision_is_kept(self):
        """12 位有效数字内的值必须原样保留。"""
        for value in (-0.0298973366983238, 0.0566666666666667, -0.00738634184004849):
            self.assertEqual(
                float(f"%.{SIGNIFICANT_DIGITS}g" % value), normalize_number(value)
            )

    def test_change_is_far_below_display_precision(self):
        """看板显示一位小数；归一带来的变化必须远小于此。"""
        for value in (-0.0298973366983238, 0.03588252950065493, -0.10616404685153624):
            after = normalize_number(value)
            self.assertLess(abs(after - value), 1e-11)
            self.assertEqual(f"{value * 100:.1f}%", f"{after * 100:.1f}%")

    def test_zero_and_nan_pass_through(self):
        self.assertEqual(normalize_number(0.0), 0.0)
        self.assertNotEqual(normalize_number(float("nan")), normalize_number(float("nan")))

    def test_sign_is_preserved(self):
        self.assertLess(normalize_number(-0.10400000000000009), 0)
        self.assertGreater(normalize_number(0.028999999999999998), 0)


class TestNormalizeStructure(unittest.TestCase):
    def test_walks_nested_structures(self):
        data = {
            "weekly": {"weeks": ["8/9-8/15"], "hotelADR": [-0.10400000000000009, None]},
            "quarterly": {"q2": {"hotelADR": 0.028999999999999998}},
            "meta": {"dataUpdate": "2026-08-15"},
        }
        out = normalize(data)
        self.assertEqual(out["weekly"]["hotelADR"], [-0.104, None])
        self.assertEqual(out["quarterly"]["q2"]["hotelADR"], 0.029)
        self.assertEqual(out["meta"]["dataUpdate"], "2026-08-15")
        self.assertEqual(out["weekly"]["weeks"], ["8/9-8/15"])

    def test_bool_not_treated_as_number(self):
        """bool 是 int 的子类，必须先拦——否则 True 会被当数值处理。"""
        out = normalize({"stale": {"weekly": True, "monthly": False}})
        self.assertIs(out["stale"]["weekly"], True)
        self.assertIs(out["stale"]["monthly"], False)

    def test_int_untouched(self):
        out = normalize({"count": 33})
        self.assertIsInstance(out["count"], int)
        self.assertEqual(out["count"], 33)

    def test_idempotent(self):
        """归一两次结果必须一样，否则每次 merge 都会产生新 diff。"""
        data = {"a": [-0.10400000000000009, 0.028999999999999998]}
        once = normalize(data)
        self.assertEqual(normalize(once), once)

    def test_count_changes_reports_without_mutating(self):
        data = {"a": [-0.10400000000000009, -0.104, 0.5]}
        self.assertEqual(count_changes(data), 1)
        self.assertEqual(data["a"][0], -0.10400000000000009, "count 不该改数据")


class TestSnapshotUsesNormalize(unittest.TestCase):
    """merge 写快照时必须归一——这是噪音的源头。"""

    def test_rebuild_writes_normalized_values(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from modules.industry_data import snapshot
        from modules.industry_data.paths import DomainPaths
        from workbench.paths import Paths

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workbench").mkdir()
            (root / "docs").mkdir()
            (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
            paths = DomainPaths(Paths(root))
            paths.snapshot.parent.mkdir(parents=True, exist_ok=True)
            paths.snapshot.write_text(json.dumps({"meta": {}}), encoding="utf-8")

            noisy = {
                "weekly": {"weeks": ["8/9-8/15"], "hotelADR": [-0.10400000000000009]},
                "monthly": {"months": [], },
                "quarterly": {},
                "meta": {"dataUpdate": "2026-08-15"},
            }
            real_build = snapshot.build
            snapshot.build = lambda workbook, previous: dict(noisy)
            try:
                result = snapshot.rebuild(paths, root / "fake.xlsx")
            finally:
                snapshot.build = real_build

            self.assertEqual(result.status, "success")
            written = json.loads(paths.snapshot.read_text(encoding="utf-8"))
            self.assertEqual(written["weekly"]["hotelADR"], [-0.104])

    def test_no_spurious_changes_between_save_paths(self):
        """归一之后，两种保存路径的同一份数据不该被 diff 报成「修改」。"""
        from modules.industry_data import snapshot

        manual = normalize({"monthly": {"months": ["1月"], "intlCapacity": [-0.104]}})
        recalced = normalize({"monthly": {"months": ["1月"], "intlCapacity": [-0.10400000000000009]}})
        diff = snapshot.compute_diff(manual, recalced)
        self.assertEqual(diff.changed, [])
        self.assertEqual(diff.added, [])


if __name__ == "__main__":
    unittest.main()
