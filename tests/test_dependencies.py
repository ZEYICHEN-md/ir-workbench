"""依赖声明与运行时自检必须一致。

背景：CI 曾连续 6 次全红而无人知晓。原因是为了省安装时间，CI 用 `pip install --no-deps`
再手动补几个包——于是依赖清单有了两份，手动那份漏了 `pdfplumber`，而航空管道要用它读
民航局 PDF。本地装过所以本地全绿，CI 没装所以一直红。

这套测试把两处钉在一起：`pyproject.toml` 的 `dependencies`（安装清单）与
`doctor.REQUIRED_DEPS`（运行时自检）必须互相覆盖。以后加依赖忘了同步，测试会先报。
"""

from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

from workbench import doctor

ROOT = Path(__file__).resolve().parents[1]

#: 发布名 → import 名。只有不一致的才列。
IMPORT_NAME = {
    "beautifulsoup4": "bs4",
    "python-docx": "docx",
    "pywin32": "win32com",
}

#: 不参与 doctor 自检的包及原因。
SELF_CHECKED_ELSEWHERE = {
    # pywin32 由 aviation_monthly/health.py 单独查（要连 Excel COM 一起验，
    # 光 import 成功不代表 COM 可用）
    "pywin32",
}


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _names(specs: list[str]) -> set[str]:
    """从依赖串里取发布名：`requests==2.34.2` → `requests`。"""
    out = set()
    for spec in specs:
        name = re.split(r"[<>=!~;\[]", spec, maxsplit=1)[0].strip()
        if name:
            out.add(name)
    return out


class TestDeclaredDependencies(unittest.TestCase):
    def setUp(self) -> None:
        self.project = _pyproject()["project"]
        self.declared = _names(self.project["dependencies"])

    def test_every_declared_dep_is_self_checked(self):
        """装了什么就该查什么——否则缺包只会在真跑时炸。"""
        for name in sorted(self.declared - SELF_CHECKED_ELSEWHERE):
            module = IMPORT_NAME.get(name, name)
            self.assertIn(
                module,
                doctor.REQUIRED_DEPS,
                f"pyproject 声明了 {name}，但 doctor.REQUIRED_DEPS 里没有 {module}",
            )

    def test_every_required_dep_is_declared(self):
        """doctor 要求什么，安装清单里就该有——否则新机器装完仍跑不起来。"""
        declared_modules = {IMPORT_NAME.get(n, n) for n in self.declared}
        for module in sorted(doctor.REQUIRED_DEPS):
            self.assertIn(
                module,
                declared_modules,
                f"doctor 要求 {module}，但 pyproject 的 dependencies 里没有对应包",
            )

    def test_pending_deps_are_not_in_main_dependencies(self):
        """未迁入域的包不该进主依赖——那会让安装变重，进而诱使 CI 走 --no-deps。"""
        pending = _names(_pyproject()["project"]["optional-dependencies"]["pending"])
        overlap = pending & self.declared
        self.assertEqual(overlap, set(), f"这些包同时在 dependencies 与 pending 里：{overlap}")

    def test_pending_deps_are_not_required_by_doctor(self):
        """未迁入域缺包是正常的，doctor 不该报 fail。"""
        pending = _names(_pyproject()["project"]["optional-dependencies"]["pending"])
        for name in pending:
            module = IMPORT_NAME.get(name, name)
            self.assertNotIn(
                module,
                doctor.REQUIRED_DEPS,
                f"{module} 属未迁入域，不该出现在 REQUIRED_DEPS（会让 doctor 误报 fail）",
            )

    def test_all_deps_are_pinned(self):
        """依赖必须钉版本：接手人几个月后装出来的必须与现在一致。"""
        for spec in self.project["dependencies"]:
            base = spec.split(";", 1)[0].strip()
            self.assertRegex(
                base,
                r"==\d",
                f"{spec} 没有钉死版本（应为 `包==版本`）",
            )


class TestDoctorDependencySeverity(unittest.TestCase):
    """必需依赖缺失要 fail，未迁域依赖缺失只提示——两者不能混。"""

    def test_required_and_pending_do_not_overlap(self):
        overlap = set(doctor.REQUIRED_DEPS) & set(doctor.PENDING_DEPS)
        self.assertEqual(overlap, set(), f"同一个包不能既必需又待迁：{overlap}")

    def test_required_deps_have_explanations(self):
        """每条都要说清缺了影响什么，否则接手人看到包名也不知道要不要管。"""
        for module, why in doctor.REQUIRED_DEPS.items():
            self.assertTrue(why.strip(), f"{module} 缺少说明")


if __name__ == "__main__":
    unittest.main()
