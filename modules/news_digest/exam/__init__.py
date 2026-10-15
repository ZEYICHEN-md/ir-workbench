"""新闻精选自动考卷。评测入口，不是第十个域，也不是同事面向的 skill。"""

from __future__ import annotations

from pathlib import Path

WORKFLOW_REV = "news-digest@2026-10-14"
PAPER_IDS = (
    "nd-trunk-pending-publish",
    "nd-gate-tcom-wiki",
    "nd-human-sowhat",
    "nd-resilience-blocked",
)

PACKAGE_DIR = Path(__file__).resolve().parent
PAPERS_DIR = PACKAGE_DIR / "papers"
