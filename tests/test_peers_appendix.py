"""Regression tests for the migrated peers-appendix core.

All fixtures are synthetic.  Tests never start Excel COM, touch the network, or
require real company PDFs/Word files.
"""

from __future__ import annotations

import argparse
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from modules.peers_appendix import charts, cli, pipeline, steps, writing
from modules.peers_appendix.paths import resolve_view
from workbench.paths import Paths


def make_paths(folder: str) -> Paths:
    root = Path(folder)
    (root / "workbench").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
    paths = Paths(root)
    paths.ensure_containers()
    return paths


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    subparsers = root.add_subparsers(dest="domain", required=True)
    cli.register(subparsers, common)
    return root


class TestParserAndPaths(unittest.TestCase):
    def test_only_peers_public_surface_and_required_commands(self):
        root = parser()
        for command in ("init", "resolve", "model", "writing", "gate", "status"):
            args = root.parse_args(
                ["peers", command]
                + (
                    []
                    if command == "status"
                    else ["--ticker", "EXPE", "--period", "26Q2"]
                )
            )
            self.assertEqual(args.domain, "peers")
            self.assertTrue(callable(args.func))

    def test_period_and_company_paths_follow_workbench_convention(self):
        with TemporaryDirectory() as temp:
            base = make_paths(temp)
            view = resolve_view(base, "expe", "26Q2")
            self.assertEqual(view.ticker, "EXPE")
            self.assertEqual(view.quarter, "2026Q2")
            self.assertEqual(
                view.materials_dir,
                Path(temp) / "inputs" / "peers-appendix" / "EXPE" / "26Q2",
            )
            self.assertEqual(
                view.output_dir,
                Path(temp) / "outputs" / "peers-appendix" / "EXPE" / "26Q2",
            )
            self.assertEqual(
                view.run_dir,
                Path(temp) / "runs" / "peers-appendix" / "26Q2" / "EXPE",
            )

    def test_bad_period_is_rejected(self):
        with TemporaryDirectory() as temp:
            base = make_paths(temp)
            with self.assertRaisesRegex(ValueError, "26Q2"):
                resolve_view(base, "EXPE", "2026Q2")


class TestManifest(unittest.TestCase):
    def test_company_steps_share_quarter_manifest_without_collision(self):
        with TemporaryDirectory() as temp:
            base = make_paths(temp)
            pipeline.initialize(base, "EXPE", "26Q2")
            pipeline.initialize(base, "ABNB", "26Q2")
            manifest_path = (
                Path(temp)
                / "runs"
                / "peers-appendix"
                / "26Q2"
                / "manifest.json"
            )
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(set(payload["companies"]), {"EXPE", "ABNB"})
            self.assertIn("EXPE:audit_model_quarter", payload["steps"])
            self.assertIn("ABNB:audit_model_quarter", payload["steps"])
            self.assertEqual(
                payload["steps"]["EXPE:audit_model_quarter"]["state"],
                "pending",
            )

    def test_init_creates_views_but_not_human_answers(self):
        with TemporaryDirectory() as temp:
            base = make_paths(temp)
            result = pipeline.initialize(base, "EXPE", "26Q2")
            view = resolve_view(base, "EXPE", "26Q2")
            self.assertEqual(result.status, "partial")
            self.assertTrue(view.materials_dir.is_dir())
            self.assertFalse(view.snapshot.exists())
            self.assertFalse(view.fill.exists())
            self.assertFalse(view.strategy_decision.exists())
            self.assertFalse(view.texts.exists())


class TestHardStops(unittest.TestCase):
    def test_authoritative_order_and_must_pass_gates_are_pinned(self):
        self.assertEqual(
            steps.MODEL_STEPS,
            [
                "materials",
                "insert",
                "fill",
                "audit_model_quarter",
                "charts",
                "check_charts_gate",
                "export",
            ],
        )
        self.assertEqual(
            steps.GATE_STEPS,
            {
                "audit_model_quarter",
                "check_charts_gate",
                "check_writing_gate",
                "accept_docx_gate",
            },
        )

    def test_model_stops_at_missing_snapshot_before_com(self):
        with TemporaryDirectory() as temp:
            base = make_paths(temp)
            pipeline.initialize(base, "EXPE", "26Q2")
            result = pipeline.run_model(base, "EXPE", "26Q2")
            self.assertEqual(result.status, "blocked")
            self.assertEqual(result.data["blocked_step"], "materials")
            self.assertEqual(
                steps.state(base, "EXPE", "26Q2", "materials"), "blocked"
            )
            self.assertEqual(
                steps.state(base, "EXPE", "26Q2", "insert"), "pending"
            )

    def test_referenced_material_must_exist(self):
        with TemporaryDirectory() as temp:
            base = make_paths(temp)
            pipeline.initialize(base, "ABNB", "26Q2")
            view = resolve_view(base, "ABNB", "26Q2")
            view.snapshot.write_text(
                json.dumps(
                    {
                        "ticker": "ABNB",
                        "quarter": "2026Q2",
                        "sources": ["shareholder-letter.pdf"],
                        "actuals": {"revenue": {"value": 1, "model_row": 15}},
                    }
                ),
                encoding="utf-8",
            )
            result = pipeline.run_model(base, "ABNB", "26Q2")
            self.assertEqual(result.status, "blocked")
            self.assertIn("shareholder-letter.pdf", result.missing)

    def test_blocked_step_prevents_later_runner(self):
        with TemporaryDirectory() as temp:
            base = make_paths(temp)
            view = resolve_view(base, "EXPE", "26Q2")
            calls: list[str] = []

            def stop(_view):
                calls.append("materials")
                raise pipeline.BlockedStep("materials", "gate failed")

            def should_not_run(_view):
                calls.append("insert")
                return {}

            with patch.dict(
                pipeline.MODEL_RUNNERS,
                {"materials": stop, "insert": should_not_run},
            ):
                result = pipeline._run_selected(
                    view,
                    ["materials", "insert"],
                    pipeline.MODEL_RUNNERS,
                    "model",
                )
            self.assertEqual(result.status, "blocked")
            self.assertEqual(calls, ["materials"])

    def test_unknown_step_is_error_not_skip(self):
        with self.assertRaises(steps.UnknownStepError):
            steps.assert_known_steps(["insert", "mystery_gate"])
        with TemporaryDirectory() as temp:
            base = make_paths(temp)
            view = resolve_view(base, "EXPE", "26Q2")
            with self.assertRaises(steps.UnknownStepError):
                pipeline._run_selected(
                    view,
                    ["mystery_gate"],
                    pipeline.MODEL_RUNNERS,
                    "model",
                )
            self.assertFalse(
                (Path(temp) / "runs" / "peers-appendix").exists(),
                "plan validation must happen before manifest mutation",
            )


class TestTickerRouting(unittest.TestCase):
    def test_chart_export_routes_are_ticker_specific(self):
        expe = charts.select_chart_route("EXPE")
        abnb = charts.select_chart_route("ABNB")
        bkng = charts.select_chart_route("BKNG")
        self.assertEqual(expe.exporter, "expe_clipboard")
        self.assertEqual(abnb.exporter, "abnb_clipboard")
        self.assertEqual(bkng.exporter, "generic_native")
        self.assertNotEqual(expe.indices, abnb.indices)
        self.assertIsNotNone(expe.word_slot_map)
        self.assertIsNone(
            abnb.word_slot_map,
            "ABNB must never inherit the EXPE image3-8 mapping",
        )

    def test_abnb_uses_dedicated_apply(self):
        self.assertEqual(
            writing.select_apply_route("ABNB").name, "abnb_dedicated"
        )
        self.assertEqual(
            writing.select_apply_route("BKNG").name, "bkng_generic"
        )
        with self.assertRaisesRegex(ValueError, "不能假装"):
            writing.select_apply_route("UNKNOWN")


class TestHumanGates(unittest.TestCase):
    def test_fill_json_is_an_explicit_gate(self):
        with TemporaryDirectory() as temp:
            base = make_paths(temp)
            view = resolve_view(base, "EXPE", "26Q2")
            with self.assertRaises(pipeline.BlockedStep) as caught:
                pipeline._load_fill(view)
            self.assertEqual(caught.exception.step, "fill")
            self.assertIn("fill_inputs.json", caught.exception.reason)

    def test_strategy_requires_human_confirmation(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "strategy_decision.json"
            path.write_text(
                json.dumps({"decision": "preserve-template"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "confirmed_by_human"):
                writing.validate_strategy_decision(path)
            path.write_text(
                json.dumps(
                    {
                        "decision": "preserve-template",
                        "confirmed_by_human": True,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                writing.validate_strategy_decision(path)["decision"],
                "preserve-template",
            )

    def test_texts_and_must_cover_are_hard_gates(self):
        brief = {
            "ticker": "EXPE",
            "quarter": "2026Q2",
            "slots": [
                {
                    "id": "ops_lodging_geo",
                    "need_from": ["materials"],
                }
            ],
            "tables": [],
        }
        texts = {
            "ticker": "EXPE",
            "quarter": "2026Q2",
            "paragraphs": [{"id": "ops_lodging_geo", "text": "太短"}],
            "tables": [],
        }
        snapshot = {
            "must_cover_in_writing": [
                {
                    "id": "app_mix",
                    "claim": "App nights 64%",
                    "tokens": ["64%"],
                    "required": True,
                    "scope": "ops_finance",
                }
            ]
        }
        with TemporaryDirectory() as temp:
            errors = writing.check_writing(
                brief,
                texts,
                "2026Q2",
                snapshot,
                Path(temp),
            )
        self.assertTrue(any("too short" in error for error in errors))
        self.assertTrue(any("64%" in error for error in errors))


    def test_abnb_embed_blocks_without_human_chart_map(self):
        with TemporaryDirectory() as temp:
            base = make_paths(temp)
            pipeline.initialize(base, "ABNB", "26Q2")
            view = resolve_view(base, "ABNB", "26Q2")
            view.applied_docx.write_bytes(b"PK\x03\x04")
            with self.assertRaises(pipeline.BlockedStep) as caught:
                pipeline._step_embed(view)
            self.assertEqual(caught.exception.step, "charts_embed")
            self.assertIn("chart_map.json", caught.exception.reason)
            self.assertNotIn("image3", caught.exception.reason)


class TestIsolation(unittest.TestCase):
    def test_python_runtime_has_no_frozen_repo_dependency_or_old_entrypoints(self):
        package = (
            Path(__file__).resolve().parents[1]
            / "modules"
            / "peers_appendix"
        )
        obsolete = {
            "render_expe_finance_texts.py",
            "audit_expe_alignment.py",
            "verify_abnb_26q2_numbers.py",
            "verify_abnb_26q2_ops_finance.py",
            "_cleanup_wip_layout.py",
        }
        self.assertFalse(any((package / name).exists() for name in obsolete))
        for path in package.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("peers_rs_update", text, path.name)
            self.assertNotIn("sys.path.insert", text, path.name)
            if path.name != "cli.py":
                self.assertNotIn("import argparse", text, path.name)
                self.assertNotIn('if __name__ == "__main__"', text, path.name)


if __name__ == "__main__":
    unittest.main()
