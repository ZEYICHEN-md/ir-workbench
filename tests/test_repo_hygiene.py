"""仓库层面的卫生检查。

这些不是业务逻辑测试，而是把「规则与实物一致」做成可执行的断言——
文档写了约定但没人检查，约定就会慢慢脱节。
"""

from __future__ import annotations

import unittest
from pathlib import Path

from workbench.lifecycle import SKIP_HYGIENE_DIRS

ROOT = Path(__file__).resolve().parents[1]

#: 纳入检查的文本文件后缀
TEXT_SUFFIXES = {".py", ".md", ".json", ".js", ".toml", ".yml", ".yaml", ".mdc", ".gitattributes"}

#: 换行符检查比 ``ir hygiene`` 多跳过交付物目录——里面有生成的 JSON/Markdown。
SKIP_DIRS = set(SKIP_HYGIENE_DIRS) | {"outputs", "output"}


def text_files() -> list[Path]:
    found: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix in TEXT_SUFFIXES or path.name == ".gitattributes":
            found.append(path)
    return found


class TestLineEndingsRepoWide(unittest.TestCase):
    """全仓文本文件一律 LF（ADR 0006）。

    CRLF 会让 git 把整份文件当成改写，把真正的内容变化埋掉——发布前的 diff 核对
    正是靠 diff 干净才成立的。
    """

    def test_no_crlf_in_tracked_text_files(self):
        offenders = [
            str(path.relative_to(ROOT))
            for path in text_files()
            if b"\r\n" in path.read_bytes()
        ]
        self.assertEqual(offenders, [], "以下文件含 CRLF，应为 LF：\n" + "\n".join(offenders))


class TestDocPointers(unittest.TestCase):
    """入口文档里引用的路径必须真的存在。

    坏链在文档里是静默失败：接手人点过去发现没有，就会绕过整套约定自己发挥。
    """

    ENTRY_DOCS = ("AGENTS.md", "CLAUDE.md", "README.md", "router/ROUTER.md")

    #: 从 markdown 里粗略捞出的路径引用（反引号或链接里的相对路径）
    def _referenced_paths(self, text: str) -> set[str]:
        import re

        found: set[str] = set()
        # [文字](相对路径)
        for match in re.finditer(r"\]\(([^)#:]+)\)", text):
            found.add(match.group(1))
        # `路径/带斜杠`
        for match in re.finditer(r"`([A-Za-z0-9_./-]+/[A-Za-z0-9_./-]+)`", text):
            found.add(match.group(1))
        return found

    def test_entry_docs_have_no_broken_paths(self):
        broken: list[str] = []
        for doc in self.ENTRY_DOCS:
            doc_path = ROOT / doc
            self.assertTrue(doc_path.is_file(), f"入口文档缺失：{doc}")
            text = doc_path.read_text(encoding="utf-8")
            for ref in self._referenced_paths(text):
                if ref.startswith(("http", "mailto")):
                    continue
                # 相对于文档所在目录解析；带 ../ 的也能正确落地
                target = (doc_path.parent / ref).resolve()
                if target.exists():
                    continue
                # 允许写成相对仓库根
                if (ROOT / ref).exists():
                    continue
                # 允许 `modules/<域>/SKILL.md` 这类含占位符的示意路径
                if "<" in ref or ref.endswith("/"):
                    continue
                broken.append(f"{doc} → {ref}")
        self.assertEqual(broken, [], "文档里的坏链：\n" + "\n".join(broken))


class TestDomainRegistryMatchesDisk(unittest.TestCase):
    """域注册表与磁盘一致：已迁入的域必须有 SKILL.md。"""

    def test_migrated_domains_have_skill(self):
        from workbench import domains
        from workbench.paths import Paths

        paths = Paths(ROOT)
        missing = [
            key
            for key in domains.DOMAINS
            if paths.module(key).is_dir() and not (paths.module(key) / "SKILL.md").is_file()
        ]
        self.assertEqual(missing, [], f"这些域已迁入但缺 SKILL.md：{missing}")

    def test_module_dir_name_is_slug_of_key(self):
        from workbench import domains
        from workbench.paths import Paths

        paths = Paths(ROOT)
        for key in domains.DOMAINS:
            self.assertEqual(paths.module(key).name, key.replace("-", "_"))

    def test_registered_domains_have_loadable_cli_and_health_contracts(self):
        from workbench import domain_state, domains
        from workbench.paths import Paths

        paths = Paths(ROOT)
        failures = []
        for definition in domains.DOMAINS.values():
            runtime = domain_state.probe(paths, definition)
            if not runtime.module_present or not runtime.cli_loaded or not runtime.health_loaded:
                failures.append(
                    f"{definition.key}: module={runtime.module_present}, "
                    f"cli={runtime.cli_loaded} ({runtime.cli_error}), "
                    f"health={runtime.health_loaded} ({runtime.health_error})"
                )
        self.assertEqual(failures, [], "域运行时契约失败：\n" + "\n".join(failures))


class TestConventionsMatchRegistry(unittest.TestCase):
    """命名与生命周期文档必须覆盖当前注册表，否则 Agent 会按过期例子建错目录。"""

    def test_file_naming_lists_every_domain(self):
        from workbench import domains

        text = (ROOT / "conventions" / "file-naming.md").read_text(encoding="utf-8")
        missing = [key for key in domains.DOMAINS if f"`{key}`" not in text]
        self.assertEqual(missing, [], f"file-naming.md 漏了这些域：{missing}")

    def test_file_naming_uses_ascii_period_examples(self):
        from workbench import domains

        text = (ROOT / "conventions" / "file-naming.md").read_text(encoding="utf-8")
        self.assertNotIn("`2026年8月第2周`", text)
        for key, definition in domains.DOMAINS.items():
            if definition.period_kind == "none":
                continue
            example = definition.period_example.split(" / ", 1)[0].split(" ", 1)[0]
            self.assertIn(example, text, f"{key} 的周期键示例 {example} 应出现在 file-naming.md")

    def test_file_lifecycle_is_indexed(self):
        self.assertTrue((ROOT / "conventions" / "file-lifecycle.md").is_file())
        index = (ROOT / "conventions" / "README.md").read_text(encoding="utf-8")
        folder = (ROOT / "docs" / "FOLDER.md").read_text(encoding="utf-8")
        self.assertIn("file-lifecycle.md", index)
        self.assertIn("file-lifecycle.md", folder)
        self.assertTrue((ROOT / "docs" / "operator" / "README.md").is_file())
        self.assertTrue((ROOT / "docs" / "analyst" / "README.md").is_file())


if __name__ == "__main__":
    unittest.main()
