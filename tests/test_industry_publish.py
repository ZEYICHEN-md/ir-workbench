"""发布门禁测试。

发布是对外动作，门禁必须被验证——尤其是「不该发布时确实没发布，而且没把发布仓弄脏」。
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from modules.industry_data import publish
from modules.industry_data.paths import DomainPaths
from workbench.config import Config
from workbench.paths import Paths


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8"
    )


class PublishFixture(unittest.TestCase):
    def setUp(self) -> None:
        # Windows 上 git 的对象文件是只读的，清理会失败——忽略即可，不影响断言
        self._tmp = TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self._tmp.name) / "workbench"
        (root / "workbench").mkdir(parents=True)
        (root / "docs").mkdir()
        (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
        self.base = Paths(root)
        self.paths = DomainPaths(self.base)

        # 工作台侧的四个看板文件（LF）
        self.paths.dashboard_dir.mkdir(parents=True)
        for name in publish.PUBLISH_FILES:
            self._write(self.paths.dashboard_dir / name, [f"// {name}", "line-a", "line-b"])

        # 发布仓：独立 git 仓，先提交一份基线
        self.repo = Path(self._tmp.name) / "publish-repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "T")
        for name in publish.PUBLISH_FILES:
            self._write(self.repo / name, [f"// {name}", "line-a", "line-b"])
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "baseline")

        # Config 每个实例各自缓存，必须复用同一个实例，否则写入会被后一个实例覆盖
        self.config = Config(self.base)
        self.config.load()["publish"]["dashboard_repo"] = str(self.repo)
        self.config.save()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @staticmethod
    def _write(path: Path, lines: list[str], *, crlf: bool = False) -> None:
        newline = "\r\n" if crlf else "\n"
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(newline.join(lines) + newline)

    def _run(self, *, yes: bool = False):
        return publish.run(self.paths, self.base, yes=yes)

    def assertRepoClean(self) -> None:
        self.assertEqual(git(self.repo, "status", "--porcelain").stdout.strip(), "")


class TestPublishGuards(PublishFixture):
    def test_no_change_reports_success_without_commit(self):
        result = self._run()
        self.assertEqual(result.status, "success")
        self.assertIn("无需发布", result.summary)
        self.assertRepoClean()

    def test_dry_run_shows_diff_but_does_not_publish(self):
        self._write(self.paths.dashboard_dir / "data.js", ["// data.js", "line-a", "CHANGED"])
        result = self._run()
        self.assertEqual(result.status, "partial")
        self.assertIn("未发布", result.summary)
        # 关键：dry-run 之后发布仓必须还原干净，不能留下半推状态
        self.assertRepoClean()
        self.assertEqual(len(git(self.repo, "log", "--oneline").stdout.strip().splitlines()), 1)

    def test_confirmed_publish_commits(self):
        self._write(self.paths.dashboard_dir / "data.js", ["// data.js", "line-a", "CHANGED"])
        result = self._run(yes=True)
        # 没有 remote，push 必然失败——但 commit 应已完成，且失败要显式返回
        self.assertEqual(result.status, "failed")
        self.assertIn("push", result.summary)
        log = git(self.repo, "log", "--oneline").stdout.strip().splitlines()
        self.assertEqual(len(log), 2, "确认后应已 commit")

    def test_crlf_source_is_blocked(self):
        self._write(
            self.paths.dashboard_dir / "data.js", ["// data.js", "CHANGED"], crlf=True
        )
        result = self._run(yes=True)
        self.assertEqual(result.status, "blocked")
        self.assertIn("CRLF", result.summary)
        self.assertRepoClean()

    def test_formatting_only_rewrite_is_blocked_and_reverted(self):
        """内容一字未动、每行都多了尾随空白——正是 ADR 0006 要拦的「把真变化埋掉」。"""
        self._write(
            self.paths.dashboard_dir / "data.js",
            ["// data.js   ", "line-a   ", "line-b   "],
        )
        result = self._run(yes=True)
        self.assertEqual(result.status, "blocked")
        self.assertIn("内容没变", result.summary)
        self.assertRepoClean()

    def test_full_content_rewrite_is_allowed_with_warning(self):
        """洞察换一期会重写几乎整个 insights.js——每期都要做的正常操作，不能按占比拦掉。

        原实现只看改动行数占比，于是一次正常的洞察全量刷新（9 条换成 14 条、
        中英正文全新）被判成「整份重写」拒发。守卫的本意是拦格式重写，不是拦内容刷新。
        """
        self._write(
            self.paths.dashboard_dir / "insights.js",
            [f"totally-different-{index}" for index in range(20)],
        )
        result = self._run()

        self.assertEqual(result.status, "partial")
        self.assertTrue(
            any("内容确有变化" in warning for warning in result.warnings), result.warnings
        )
        self.assertRepoClean()

    def test_full_content_rewrite_warning_survives_to_the_push_path(self):
        """提示不能只在 dry-run 出现——真按下发布的那次也要说清这是全量替换。"""
        self._write(
            self.paths.dashboard_dir / "insights.js",
            [f"totally-different-{index}" for index in range(20)],
        )
        result = self._run(yes=True)

        # 没有 remote，push 必然失败；这里只关心 warning 有没有一路带到发布路径
        self.assertTrue(
            any("内容确有变化" in warning for warning in result.warnings), result.warnings
        )

    def test_missing_source_file_is_blocked(self):
        (self.paths.dashboard_dir / "insights.js").unlink()
        result = self._run(yes=True)
        self.assertEqual(result.status, "blocked")
        self.assertIn("不全", result.summary)

    def test_unrelated_dirty_file_in_repo_is_blocked(self):
        (self.repo / "notes.txt").write_text("someone else's work", encoding="utf-8")
        self._write(self.paths.dashboard_dir / "data.js", ["// data.js", "CHANGED"])
        result = self._run(yes=True)
        self.assertEqual(result.status, "blocked")
        self.assertIn("无关的未提交改动", result.summary)

    def test_missing_repo_config_is_blocked(self):
        self.config.load()["publish"]["dashboard_repo"] = None
        self.config.save()
        result = self._run(yes=True)
        self.assertEqual(result.status, "blocked")
        self.assertIn("发布仓", result.summary)

    def test_non_git_path_is_blocked(self):
        plain = Path(self._tmp.name) / "not-a-repo"
        plain.mkdir()
        self.config.load()["publish"]["dashboard_repo"] = str(plain)
        self.config.save()
        result = self._run(yes=True)
        self.assertEqual(result.status, "blocked")
        self.assertIn("git 仓", result.summary)


if __name__ == "__main__":
    unittest.main()
