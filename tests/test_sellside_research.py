"""卖方研报轻量域的合成回归；不含、也不读取任何第三方研报原文。"""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from modules.sellside_research import cli, reader
from workbench.paths import Paths


def make_root(tmp: str) -> Paths:
    root = Path(tmp)
    (root / "workbench").mkdir()
    (root / "docs" / "adr").mkdir(parents=True)
    (root / "docs" / "GLOSSARY.md").write_text("x", encoding="utf-8")
    (root / "router").mkdir()
    (root / "conventions").mkdir()
    paths = Paths(root)
    paths.ensure_containers()
    return paths


def fake_pdf(*page_texts: str | None) -> MagicMock:
    document = MagicMock()
    document.pages = []
    for text in page_texts:
        page = MagicMock()
        page.extract_text.return_value = text
        document.pages.append(page)
    opened = MagicMock()
    opened.__enter__.return_value = document
    opened.__exit__.return_value = False
    return opened


class TestSellsideReader(unittest.TestCase):
    def test_extract_preserves_viewer_page_order_and_markdown_locations(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "synthetic-report.pdf"
            source.write_bytes(b"synthetic")
            with patch.object(reader.pdfplumber, "open", return_value=fake_pdf("Page one 10%", "Page two 20%")):
                payload = reader.extract(source)
            self.assertEqual([page["page"] for page in payload["pages"]], [1, 2])
            self.assertEqual(payload["text_pages"], 2)
            rendered = reader.markdown(payload)
            self.assertIn("## 第 1 页", rendered)
            self.assertIn("## 第 2 页", rendered)

    def test_all_empty_pages_are_blocked_as_scanned_document(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "scanned.pdf"
            source.write_bytes(b"synthetic")
            with patch.object(reader.pdfplumber, "open", return_value=fake_pdf("", None)):
                with self.assertRaisesRegex(reader.ResearchError, "扫描件"):
                    reader.extract(source)

    def test_cli_writes_only_ephemeral_output_and_reports_partial(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            source = paths.inputs("sellside-research") / "synthetic-report.pdf"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"synthetic")
            payload = {
                "source": str(source.resolve()),
                "filename": source.name,
                "page_count": 2,
                "text_pages": 1,
                "chars": 12,
                "pages": [
                    {"page": 1, "text": "Synthetic 10%", "chars": 12},
                    {"page": 2, "text": "", "chars": 0},
                ],
            }
            with patch.object(reader, "extract", return_value=payload):
                result = cli.cmd_extract(SimpleNamespace(file=str(source), output=None), paths)
            self.assertEqual(result.status, "partial")
            self.assertTrue((paths.outputs("sellside-research") / "synthetic-report.pages.md").is_file())
            self.assertEqual(list(paths.runs("sellside-research").glob("*")), [])
            self.assertEqual(list(paths.intel.glob("*")), [])
            self.assertTrue(any("1 页没有可提取文字" in warning for warning in result.warnings))

    def test_non_pdf_is_blocked_without_output(self):
        with TemporaryDirectory() as tmp:
            paths = make_root(tmp)
            source = paths.inputs("sellside-research") / "notes.txt"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("synthetic", encoding="utf-8")
            result = cli.cmd_extract(SimpleNamespace(file=str(source), output=None), paths)
            self.assertEqual(result.status, "blocked")
            self.assertFalse(paths.outputs("sellside-research").exists())


if __name__ == "__main__":
    unittest.main()
