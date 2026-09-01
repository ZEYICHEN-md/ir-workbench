"""运行 manifest。

索引 = 域 + 周期键（ADR 0003 §3）。manifest 让「进度」脱离对话上下文存活：
换一个会话、换一个人，也能知道上次停在哪、哪些输入参与了结果。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import domains
from .fileio import write_text_atomic
from .paths import Paths

MANIFEST_NAME = "manifest.json"
StepState = str  # pending | running | done | blocked | failed | skipped


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Manifest:
    def __init__(self, paths: Paths, domain: str, period: str) -> None:
        self.domain_def = domains.get(domain)
        if not self.domain_def.validate_period(period):
            raise SystemExit(
                f"{domain} 的周期键格式不对：{period!r}\n"
                f"应形如 {self.domain_def.period_example}"
            )
        self.paths = paths
        self.domain = domain
        self.period = period
        self.file = paths.runs(domain, period) / MANIFEST_NAME
        self._data: dict[str, Any] | None = None

    @property
    def exists(self) -> bool:
        return self.file.is_file()

    def load(self) -> dict[str, Any]:
        if self._data is None:
            if self.exists:
                self._data = json.loads(self.file.read_text(encoding="utf-8"))
            else:
                self._data = {
                    "domain": self.domain,
                    "period": self.period,
                    "created": _now(),
                    "updated": _now(),
                    "steps": {},
                    "inputs": {},
                    "outputs": {},
                    "notes": [],
                }
        return self._data

    def save(self) -> None:
        data = self.load()
        data["updated"] = _now()
        # 走 fileio 保证 UTF-8 + LF：manifest 进 git，CRLF 会让每次更新都显示为全文改写
        write_text_atomic(self.file, json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    # --- 步骤 ---

    def ensure_steps(self, order: list[str]) -> None:
        """把整条步骤序列种进 manifest，未跑的记 pending。

        必须先种再跑：否则 `status` 只能看到「跑过的步骤」，看不到「还差几步」——
        而「还差几步」才是换个会话后接手的人真正需要的信息。
        """
        data = self.load()
        steps = data["steps"]
        changed = data.get("order") != order
        for name in order:
            if name not in steps:
                steps[name] = {"state": "pending"}
                changed = True
        data["order"] = order
        if changed:
            self.save()

    def set_step(
        self,
        name: str,
        state: StepState,
        note: str | None = None,
        result_data: dict[str, Any] | None = None,
    ) -> None:
        steps = self.load()["steps"]
        entry = steps.setdefault(name, {})
        entry["state"] = state
        entry["at"] = _now()
        if note:
            entry["note"] = note
        if result_data is not None:
            # 只记命令明确返回的小型结构化结果（如 merge.changedPeriods），
            # 不把终端文本或大产物塞进 manifest。
            entry["result"] = result_data
        self.save()

    def step_state(self, name: str) -> StepState:
        return self.load()["steps"].get(name, {}).get("state", "pending")

    def next_pending(self, order: list[str]) -> str | None:
        for name in order:
            if self.step_state(name) not in {"done", "skipped"}:
                return name
        return None

    # --- 输入输出留痕（溯源的底层保障）---

    def record_input(self, label: str, path: Path) -> None:
        self.load()["inputs"][label] = {
            "path": str(path),
            "sha256": sha256(path) if path.is_file() else None,
            "at": _now(),
        }
        self.save()

    def record_output(self, label: str, path: Path) -> None:
        self.load()["outputs"][label] = {
            "path": str(path),
            "sha256": sha256(path) if path.is_file() else None,
            "at": _now(),
        }
        self.save()

    def note(self, text: str) -> None:
        self.load()["notes"].append({"at": _now(), "text": text})
        self.save()


def list_periods(paths: Paths, domain: str) -> list[str]:
    """列出某域已有的周期，按目录名倒序（最新在前）。"""
    base = paths.runs(domain)
    if not base.is_dir():
        return []
    return sorted(
        (p.name for p in base.iterdir() if p.is_dir() and (p / MANIFEST_NAME).is_file()),
        reverse=True,
    )


def latest(paths: Paths, domain: str) -> Manifest | None:
    periods = list_periods(paths, domain)
    return Manifest(paths, domain, periods[0]) if periods else None
