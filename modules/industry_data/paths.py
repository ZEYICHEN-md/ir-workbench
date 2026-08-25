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

    # --- 底稿归档 ---
    @property
    def workbook_archive_dir(self) -> Path:
        """往期与写入前的底稿版本。

        两种东西放这里，都**不删**：
        1. 换新版底稿时的旧版（`国内行业数据_0817.xlsx`）——否则想回头核对上一版就没了；
        2. 每次自动写入前的备份（`国内行业数据_0824.pre-<动作>-<时间戳>.xlsx`）。

        底稿是唯一指标真源（ADR 0001），也就是单点。git 里有版本，但 git 之外也要有
        人能直接双击打开的副本——出事时不该要求接手人会用 git。
        """
        return self.base.workbooks / "archived"

    # --- 其他 ---
    @property
    def scratch(self) -> Path:
        return self.base.scratch
