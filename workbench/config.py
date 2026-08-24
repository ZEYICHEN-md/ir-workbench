"""本机配置。

原则（ADR 0003 §4）：**工作簿选择必须显式配置，不按文件名猜最新。**
配置文件在 .ir-workbench/config.json，Git 忽略——本机配置与共享代码分离，
这样另一台机器上的路径差异不会污染仓库。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import Paths

#: 需要显式指定的工作簿。键 = 逻辑名，值 = 说明
WORKBOOK_KEYS: dict[str, str] = {
    "industry": "国内行业数据 Excel —— 指标底稿，唯一人工编辑面（ADR 0001）",
    "airline": "Airline Data Excel —— 航空月度底表，pipeline 读写",
}

DEFAULTS: dict[str, Any] = {
    "workbooks": {},
    "publish": {
        # 默认不发布任何东西；发布一律要人明确说
        "dashboard_repo": None,
        "feishu_enabled": False,
    },
}


class Config:
    def __init__(self, paths: Paths) -> None:
        self.paths = paths
        self._data: dict[str, Any] | None = None

    @property
    def exists(self) -> bool:
        return self.paths.config_file.is_file()

    def load(self) -> dict[str, Any]:
        if self._data is None:
            if self.exists:
                raw = json.loads(self.paths.config_file.read_text(encoding="utf-8"))
            else:
                raw = {}
            merged = json.loads(json.dumps(DEFAULTS))
            merged.update(raw)
            self._data = merged
        return self._data

    def save(self) -> None:
        self.paths.local.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.load(), ensure_ascii=False, indent=2)
        self.paths.config_file.write_text(payload + "\n", encoding="utf-8")

    # --- 工作簿 ---

    def workbook(self, key: str) -> Path | None:
        """返回已配置的工作簿路径；未配置返回 None（绝不代选）。"""
        if key not in WORKBOOK_KEYS:
            raise KeyError(f"未知工作簿键 {key!r}；已知：{'、'.join(WORKBOOK_KEYS)}")
        value = self.load()["workbooks"].get(key)
        if not value:
            return None
        path = Path(value)
        return path if path.is_absolute() else self.paths.root / path

    def set_workbook(self, key: str, path: Path) -> Path:
        if key not in WORKBOOK_KEYS:
            raise KeyError(f"未知工作簿键 {key!r}；已知：{'、'.join(WORKBOOK_KEYS)}")
        resolved = path if path.is_absolute() else (self.paths.root / path)
        if not resolved.is_file():
            raise SystemExit(f"文件不存在：{resolved}")
        try:
            stored = str(resolved.relative_to(self.paths.root)).replace("\\", "/")
        except ValueError:
            stored = str(resolved)
        self.load()["workbooks"][key] = stored
        self.save()
        return resolved

    # --- 发布 ---

    def publish_repo(self) -> Path | None:
        value = self.load()["publish"].get("dashboard_repo")
        return Path(value) if value else None

    def set_publish_repo(self, path: Path) -> Path:
        resolved = path.expanduser().resolve()
        if not (resolved / ".git").is_dir():
            raise SystemExit(f"不是 git 仓：{resolved}（发布仓是独立 clone，不是工作台子目录）")
        self.load()["publish"]["dashboard_repo"] = str(resolved)
        self.save()
        return resolved

    def candidates(self, key: str) -> list[Path]:
        """列出候选工作簿供**用户**选择。不排序暗示优先级，不代选。"""
        patterns = {"industry": "*国内行业数据*.xls*", "airline": "*Airline*Data*.xls*"}
        pattern = patterns.get(key)
        if not pattern or not self.paths.workbooks.is_dir():
            return []
        return sorted(p for p in self.paths.workbooks.glob(pattern) if not p.name.startswith("~$"))
