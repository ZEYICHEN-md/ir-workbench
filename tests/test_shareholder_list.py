"""shareholder-list 迁入后的契约测试。"""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "modules" / "shareholder_list"


class TestEngineLayout(unittest.TestCase):
    def test_prior_dir_is_module_templates(self):
        from modules.shareholder_list.discover import PRIOR_DIR, PRIOR_TEMPLATE

        self.assertEqual(PRIOR_DIR, MODULE / "templates")
        self.assertNotIn("IR_what_I Did", str(PRIOR_DIR))
        self.assertTrue(PRIOR_TEMPLATE.is_file(), PRIOR_TEMPLATE)
        self.assertEqual(PRIOR_TEMPLATE.name, "Investor List_20260626.xlsx")

    def test_wording_template_exists_but_is_not_prior(self):
        from modules.shareholder_list.discover import PRIOR_TEMPLATE

        wording = MODULE / "templates" / "Investor List_26Q1_20260518.xlsx"
        self.assertTrue(wording.is_file())
        self.assertNotEqual(PRIOR_TEMPLATE, wording)

    def test_engine_lives_in_the_module(self):
        self.assertTrue((MODULE / "build.py").is_file())
        self.assertTrue((MODULE / "engine.py").is_file())
        self.assertTrue((MODULE / "adversarial_audit.py").is_file())
        self.assertFalse((ROOT / "src" / "shareholder_list" / "build.py").is_file())
        self.assertFalse((ROOT / "scripts" / "rebuild.ps1").is_file())

    def test_market_caps_live_in_the_module(self):
        payload = (MODULE / "market_caps.json").read_text(encoding="utf-8")
        self.assertIn("tcom_shares_outstanding", payload)
        self.assertIn("2026-08-31", payload)

    def test_default_output_uses_workbench_outputs(self):
        from modules.shareholder_list.engine import default_output

        path = default_output(ROOT)
        self.assertEqual(path.parent, ROOT / "outputs" / "shareholder-list" / "2026-08-31")
        self.assertEqual(path.name, "Investor List_20260831.xlsx")


class TestDomainContract(unittest.TestCase):
    def test_registered_as_ninth_domain(self):
        from workbench.domains import DOMAINS, get

        domain = get("shareholder-list")
        self.assertEqual(domain.zh, "机构股东名册")
        self.assertEqual(domain.period_kind, "data_date")
        self.assertTrue(domain.validate_period("2026-08-31"))
        self.assertFalse(domain.validate_period("2026/08/31"))
        self.assertEqual(len(DOMAINS), 9)

    def test_skill_and_cli_exist(self):
        from workbench.domain_state import probe
        from workbench.domains import get
        from workbench.paths import Paths

        runtime = probe(Paths(ROOT), get("shareholder-list"))
        self.assertTrue(runtime.module_present)
        self.assertTrue(runtime.cli_loaded, runtime.cli_error)
        self.assertTrue(runtime.health_loaded, runtime.health_error)
        self.assertTrue((MODULE / "SKILL.md").is_file())
        self.assertTrue((MODULE / "reference.md").is_file())


class TestRebuildGate(unittest.TestCase):
    def test_missing_extracts_are_blocked(self):
        from modules.shareholder_list.cli import cmd_rebuild
        from workbench.paths import Paths

        args = SimpleNamespace(
            peer=None,
            combined=None,
            template=None,
            output=None,
            refresh_market=False,
            force_refresh=False,
        )
        with (
            patch("modules.shareholder_list.cli.default_peer", return_value=None),
            patch("modules.shareholder_list.cli.default_combined", return_value=None),
        ):
            result = cmd_rebuild(args, Paths(ROOT))
        self.assertEqual(result.status, "blocked")
        self.assertTrue(any("Peer" in item for item in result.missing))

    def test_refresh_on_locked_date_is_blocked(self):
        from datetime import date

        from modules.shareholder_list.build import VALID_AS_OF
        from modules.shareholder_list.cli import cmd_rebuild
        from workbench.paths import Paths

        template = MODULE / "templates" / "Investor List_20260626.xlsx"
        args = SimpleNamespace(
            peer=str(template),
            combined=str(template),
            template=str(template),
            output=None,
            refresh_market=True,
            force_refresh=False,
        )
        locked = tuple(int(part) for part in VALID_AS_OF.replace("-", "/").split("/"))
        if date(*locked) == date.today():
            self.skipTest("VALID_AS_OF is today; locked-refresh gate does not apply")
        result = cmd_rebuild(args, Paths(ROOT))
        self.assertEqual(result.status, "blocked")
        self.assertIn("锁定重建", result.summary)


if __name__ == "__main__":
    unittest.main()
