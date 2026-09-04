"""Locate Capital IQ extracts and the prior Investor List template."""
from __future__ import annotations

from pathlib import Path

DOWNLOADS = Path.home() / "Downloads"
PRIOR_DIR = Path(__file__).resolve().parents[2] / "templates"
PEER_GLOB = "Peer Ownership-Holdings-*.xlsx"
COMBINED_GLOB = "Institution Combined Ownership-Public-*.xlsx"
TEMPLATE_GLOB = "Investor List_*.xlsx"

# Last published shareholder list of the **previous holdings quarter**.
# Copied as skeleton; SH / Combined in this file become SH Prior (QoQ, rank arrows).
# This 8/31 cut: June. Next holdings quarter: point at that cut's published file
# (usually repo `output/Investor List_20260831.xlsx`). Locked rebuild: do not change.
# Never point at the file this VALID_AS_OF will write (self-compare → all QoQ = 0).
PRIOR_TEMPLATE = PRIOR_DIR / "Investor List_20260626.xlsx"


def latest(folder: Path, pattern: str) -> Path | None:
    matches = [p for p in folder.glob(pattern) if p.is_file() and not p.name.startswith("~$")]
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def default_peer() -> Path | None:
    matches = [
        p
        for p in DOWNLOADS.glob(PEER_GLOB)
        if p.is_file() and not p.name.startswith("~$") and "-Public-" not in p.name
    ]
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def default_combined() -> Path | None:
    return latest(DOWNLOADS, COMBINED_GLOB)


def default_template() -> Path | None:
    if PRIOR_TEMPLATE.exists():
        return PRIOR_TEMPLATE
    return latest(PRIOR_DIR, TEMPLATE_GLOB)
