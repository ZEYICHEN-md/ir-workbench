"""本域的路径。派生自 workbench.paths，不另立一套根目录逻辑。"""

from __future__ import annotations

from pathlib import Path

from workbench.paths import Paths

DOMAIN = "industry-data"


class DomainPaths:
    def __init__(self, base: Paths) -> None:
        self.base = base

    # --- 权威 ---
    @property
    def snapshot(self) -> Path:
        """指标快照（Excel 的机器投影，可全量重建，不接受手改）。"""
        return self.base.canonical / "travel.json"

    @property
    def insights_canonical(self) -> Path:
        """洞察底稿（独立真源，不随指标重建而变）。"""
        return self.base.canonical / "travel-insights.json"

    # --- 投影 ---
    @property
    def dashboard_dir(self) -> Path:
        return self.base.dashboard / "travel"

    @property
    def data_js(self) -> Path:
        return self.dashboard_dir / "data.js"

    @property
    def insights_js(self) -> Path:
        return self.dashboard_dir / "insights.js"

    @property
    def insights_md_dir(self) -> Path:
        return self.base.module(DOMAIN) / "insights"

    @property
    def insights_archive_dir(self) -> Path:
        return self.insights_md_dir / "archive"

    # --- 底稿归档（定义在共享层，两个域都写底稿）---
    @property
    def workbook_archive_dir(self) -> Path:
        return self.base.workbook_archive

    # --- 其他 ---
    @property
    def scratch(self) -> Path:
        return self.base.scratch
