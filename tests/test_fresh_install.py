"""新克隆 / 新解压的工作台必须能直接跑起来。

背景：CI 自建仓起连续 7 次红。修掉依赖清单那次之后仍红，原因换成了
`目录骨架 — 缺 1 个：scratch` —— `scratch/` 被 .gitignore 整体忽略，所以任何
新 clone 都没有它，而 doctor 把它算作必需目录报 fail。

这不只是 CI 的问题：**接手人解压 zip 后首次跑 doctor 会撞上同一件事**，
而给他的提示是「对 Agent 说修复目录结构」——对非技术使用者毫无意义。
现在的规则是：有内容的目录缺了才报 fail，纯容器目录由 doctor 顺手补齐。
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench import doctor
from workbench.paths import Paths


def make_skeleton(root: Path, *, containers: bool = False) -> Paths:
    """造一份「刚 clone 出来」的工作台：有内容的目录都在，容器目录一个都没有。"""
    (root / "workbench").mkdir()
    (root / "docs" / "adr").mkdir(parents=True)
    (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
    (root / "modules").mkdir()
    (root / "router").mkdir()
    (root / "conventions").mkdir()
    paths = Paths(root)
    if containers:
        paths.ensure_containers()
    return paths


class TestContainerDirs(unittest.TestCase):
    def test_fresh_clone_has_no_container_dirs(self):
        with TemporaryDirectory() as tmp:
            paths = make_skeleton(Path(tmp))
            self.assertFalse(
                any(p.is_dir() for p in paths.container_dirs),
                "这个固定件就是要模拟容器目录全缺的状态",
            )

    def test_ensure_creates_all_and_is_idempotent(self):
        with TemporaryDirectory() as tmp:
            paths = make_skeleton(Path(tmp))
            created = paths.ensure_containers()
            self.assertEqual(len(created), len(paths.container_dirs))
            self.assertTrue(all(p.is_dir() for p in paths.container_dirs))
            # 再跑一次不该重复报「新建」
            self.assertEqual(paths.ensure_containers(), [])

    def test_scratch_is_a_container_not_required(self):
        """scratch 被 .gitignore 忽略，绝不能算必需目录。"""
        with TemporaryDirectory() as tmp:
            paths = make_skeleton(Path(tmp))
            self.assertIn(paths.scratch, paths.container_dirs)
            self.assertNotIn(paths.scratch, paths.required_dirs)

    def test_required_dirs_are_all_content_bearing(self):
        """必需目录里不该混进纯容器——否则新安装必然报 fail。"""
        with TemporaryDirectory() as tmp:
            paths = make_skeleton(Path(tmp))
            overlap = set(paths.required_dirs) & set(paths.container_dirs)
            self.assertEqual(overlap, set(), f"这些既算必需又算容器：{overlap}")


class TestDoctorOnFreshClone(unittest.TestCase):
    def test_doctor_does_not_fail_on_missing_containers(self):
        """新 clone 跑 doctor 不该 blocked——它只是还没配工作簿。"""
        with TemporaryDirectory() as tmp:
            paths = make_skeleton(Path(tmp))
            result = doctor.run(paths)
            self.assertNotEqual(result.status, "blocked", f"checks={result.checks}")
            self.assertEqual(result.exit_code, 0)

    def test_doctor_creates_containers_and_says_so(self):
        with TemporaryDirectory() as tmp:
            paths = make_skeleton(Path(tmp))
            result = doctor.run(paths)
            self.assertTrue(all(p.is_dir() for p in paths.container_dirs))
            names = [c["name"] for c in result.checks]
            self.assertIn("容器目录", names)

    def test_doctor_still_fails_on_missing_content_dirs(self):
        """真正缺内容时必须 fail —— 这是「安装不完整」的信号，不能被容器逻辑吞掉。"""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = make_skeleton(root, containers=True)
            (root / "router").rmdir()
            result = doctor.run(paths)
            self.assertEqual(result.status, "blocked")
            self.assertTrue(any("router" in m for m in result.missing))

    def test_missing_content_dir_advice_is_actionable(self):
        """给非技术使用者的下一步必须是他能做的事，不能是「修复目录结构」这种黑话。"""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = make_skeleton(root, containers=True)
            (root / "conventions").rmdir()
            result = doctor.run(paths)
            advice = " ".join(result.next_steps)
            self.assertIn("重新安装", advice)


if __name__ == "__main__":
    unittest.main()
