"""工作簿锁定与本机发布配置。

原则（ADR 0003 §4）：**工作簿选择必须显式配置，不按文件名猜最新。**

部门当前锁定哪几份 Excel，写在 ``data/workbook-lock.json``，随仓走——clone
下来就能用。``.ir-workbench/config.json`` 只覆盖本机差异（看板发布仓路径、
临时改锁），Git 忽略，避免把某台电脑的绝对路径写进仓库。
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
    "peers_abe": "BKNG / EXPE / ABNB 共用 Model —— peers-model 只输出更新副本",
    "peers_meituan": "美团独立 Model —— peers-model 只输出更新副本",
    "peers_tcel": "同程独立 Model —— peers-model 只输出更新副本",
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

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}

    def load(self) -> dict[str, Any]:
        if self._data is None:
            merged = json.loads(json.dumps(DEFAULTS))
            lock = self._read_json(self.paths.workbook_lock)
            local = self._read_json(self.paths.config_file)
            merged["workbooks"] = {
                **(lock.get("workbooks") or {}),
                **(local.get("workbooks") or {}),
            }
            merged["publish"] = {
                **merged["publish"],
                **(local.get("publish") or {}),
            }
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
        if not Path(stored).is_absolute():
            self._save_lock_key(key, stored)
        return resolved

    def _save_lock_key(self, key: str, stored: str) -> None:
        """仓内路径写入随仓锁定清单，换人 clone 下来还是同一份。"""
        path = self.paths.workbook_lock
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._read_json(path)
        books = dict(payload.get("workbooks") or {})
        books[key] = stored
        payload["workbooks"] = books
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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
        specs = {
            "industry": (self.paths.workbooks, "*国内行业数据*.xls*"),
            "airline": (self.paths.workbooks, "*Airline*Data*.xls*"),
            "peers_abe": (self.paths.models, "peers data comparison*.xls*"),
            "peers_meituan": (self.paths.models, "Meituan*.xls*"),
            "peers_tcel": (self.paths.models, "Tongcheng*Model*.xls*"),
        }
        folder, pattern = specs.get(key, (None, None))
        if folder is None or pattern is None or not folder.is_dir():
            return []
        return sorted(p for p in folder.glob(pattern) if not p.name.startswith("~$"))
