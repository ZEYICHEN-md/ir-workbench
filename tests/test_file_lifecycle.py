"""文件生命周期与过期清理。"""

from __future__ import annotations

import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.lifecycle import FROZEN_LOCAL_DIRS, PruneItem, apply, prune, scan
from workbench.paths import Paths


def _touch(path: Path, *, age_days: int, now: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    mtime = now - age_days * 86400
    path.stat()  # ensure exists
    import os

    os.utime(path, (mtime, mtime))


class TestPruneBuckets(unittest.TestCase):
    def test_old_scratch_is_auto_and_fresh_scratch_is_kept(self):
        now = time.time()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = Paths(root)
            paths.ensure_containers()
            _touch(root / "scratch" / "old.json", age_days=20, now=now)
            _touch(root / "scratch" / "fresh.json", age_days=2, now=now)
            _touch(root / "scratch" / ".gitkeep", age_days=40, now=now)
            items = scan(paths, now=now)
            autos = {item.relative: item for item in items if item.auto}
            self.assertIn("scratch/old.json", autos)
            self.assertNotIn("scratch/fresh.json", autos)
            self.assertNotIn("scratch/.gitkeep", autos)

    def test_root_output_and_tmp_are_always_expired(self):
        now = time.time()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = Paths(root)
            _touch(root / "output" / "adversarial_audit.json", age_days=0, now=now)
            _touch(root / "_tmp" / "dump.txt", age_days=0, now=now)
            autos = {item.relative for item in scan(paths, now=now) if item.auto}
            self.assertIn("output/adversarial_audit.json", autos)
            self.assertIn("_tmp/dump.txt", autos)

    def test_old_inputs_are_report_only(self):
        now = time.time()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = Paths(root)
            paths.ensure_containers()
            _touch(root / "inputs" / "news-digest" / "2026-01-W1" / "clip.pdf", age_days=100, now=now)
            items = {item.relative: item for item in scan(paths, now=now)}
            self.assertIn("inputs/news-digest/2026-01-W1/clip.pdf", items)
            self.assertFalse(items["inputs/news-digest/2026-01-W1/clip.pdf"].auto)

    def test_fix_deletes_auto_only_and_keeps_scratch_container(self):
        now = time.time()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = Paths(root)
            paths.ensure_containers()
            _touch(root / "scratch" / "old.json", age_days=20, now=now)
            _touch(root / "output" / "leftover.json", age_days=0, now=now)
            _touch(root / "inputs" / "clip.pdf", age_days=120, now=now)
            result = prune(paths, fix=True, now=now)
            self.assertFalse((root / "scratch" / "old.json").exists())
            self.assertFalse((root / "output").exists())
            self.assertTrue((root / "scratch").is_dir())
            self.assertTrue((root / "inputs" / "clip.pdf").exists())
            self.assertEqual(result.status, "partial")
            self.assertIn("inputs/clip.pdf", result.data["report_only"])

    def test_apply_refuses_paths_outside_root(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "wb"
            root.mkdir()
            outsider = Path(tmp) / "secret.txt"
            outsider.write_text("no", encoding="utf-8")
            paths = Paths(root)
            deleted = apply(
                paths,
                [
                    PruneItem(
                        relative="../secret.txt",
                        size=2,
                        age_days=0,
                        bucket="output",
                        auto=True,
                    )
                ],
            )
            self.assertEqual(deleted, [])
            self.assertTrue(outsider.exists())

    def test_dry_run_does_not_delete(self):
        now = time.time()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = Paths(root)
            paths.ensure_containers()
            target = root / "scratch" / "old.json"
            _touch(target, age_days=20, now=now)
            result = prune(paths, fix=False, now=now)
            self.assertEqual(result.status, "partial")
            self.assertTrue(target.exists())
            self.assertIn("确认删除", " ".join(result.next_steps))


class TestFrozenDirs(unittest.TestCase):
    def test_frozen_dirs_are_gitignored(self):
        text = Path(__file__).resolve().parents[1].joinpath(".gitignore").read_text(encoding="utf-8")
        for name in FROZEN_LOCAL_DIRS:
            self.assertIn(f"{name}/", text, f"{name} 必须被 gitignore，否则会变成第二套入口")

    def test_peer_model_candidates_come_from_data_models(self):
        from workbench.config import Config

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = Paths(root)
            paths.ensure_containers()
            target = paths.models / "peers data comparison_20260807.xlsx"
            target.write_bytes(b"fake")
            leftover = root / "peers_rs_update" / "deliverables" / "models"
            leftover.mkdir(parents=True)
            (leftover / "peers data comparison_old.xlsx").write_bytes(b"old")
            found = {p.name for p in Config(paths).candidates("peers_abe")}
            self.assertEqual(found, {"peers data comparison_20260807.xlsx"})

    def test_hygiene_skips_frozen_dirs(self):
        from workbench.hygiene import SKIP_DIRS

        for name in FROZEN_LOCAL_DIRS:
            self.assertIn(name, SKIP_DIRS)


if __name__ == "__main__":
    unittest.main()
