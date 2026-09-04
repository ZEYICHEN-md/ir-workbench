"""工作簿锁定：随仓清单 + 本机覆盖。"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.config import Config
from workbench.paths import Paths


def _skeleton(root: Path) -> Paths:
    (root / "workbench").mkdir()
    (root / "docs").mkdir()
    (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
    paths = Paths(root)
    paths.ensure_containers()
    return paths


class TestWorkbookLock(unittest.TestCase):
    def test_lock_used_when_no_local_config(self):
        with TemporaryDirectory() as tmp:
            paths = _skeleton(Path(tmp))
            target = paths.models / "peers data comparison_20260807.xlsx"
            target.write_bytes(b"x")
            paths.workbook_lock.write_text(
                json.dumps(
                    {
                        "workbooks": {
                            "peers_abe": "data/models/peers data comparison_20260807.xlsx"
                        }
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(Config(paths).workbook("peers_abe"), target)

    def test_local_overlay_wins(self):
        with TemporaryDirectory() as tmp:
            paths = _skeleton(Path(tmp))
            locked = paths.models / "peers data comparison_20260807.xlsx"
            overlay = paths.models / "peers data comparison_try.xlsx"
            locked.write_bytes(b"lock")
            overlay.write_bytes(b"local")
            paths.workbook_lock.write_text(
                json.dumps(
                    {
                        "workbooks": {
                            "peers_abe": "data/models/peers data comparison_20260807.xlsx"
                        }
                    }
                ),
                encoding="utf-8",
            )
            paths.local.mkdir(parents=True, exist_ok=True)
            paths.config_file.write_text(
                json.dumps(
                    {
                        "workbooks": {
                            "peers_abe": "data/models/peers data comparison_try.xlsx"
                        }
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(Config(paths).workbook("peers_abe"), overlay)

    def test_set_workbook_updates_shared_lock(self):
        with TemporaryDirectory() as tmp:
            paths = _skeleton(Path(tmp))
            target = paths.models / "Meituan Hotel comparison_26Q2.xlsx"
            target.write_bytes(b"m")
            Config(paths).set_workbook("peers_meituan", target)
            lock = json.loads(paths.workbook_lock.read_text(encoding="utf-8"))
            self.assertEqual(
                lock["workbooks"]["peers_meituan"],
                "data/models/Meituan Hotel comparison_26Q2.xlsx",
            )


if __name__ == "__main__":
    unittest.main()
