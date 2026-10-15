"""加载一卷题目。YAML 是卷面真源；JSON sidecar 让 CI 不依赖 PyYAML。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import PAPER_IDS, PAPERS_DIR, WORKFLOW_REV


class PaperError(ValueError):
    pass


def _load_mapping(path: Path) -> dict[str, Any]:
    sidecar = path.with_suffix(".json")
    if sidecar.is_file():
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise PaperError(f"{sidecar} 顶层必须是对象")
        return data
    try:
        import yaml  # type: ignore
    except ImportError as error:
        raise PaperError(f"读不了 {path.name}：没有 JSON sidecar，也没有 PyYAML") from error
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PaperError(f"{path} 顶层必须是对象")
    return data


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Paper:
    id: str
    directory: Path
    meta: dict[str, Any]
    env: dict[str, Any]
    task: str
    rubric: str

    @property
    def fixtures(self) -> Path:
        return self.directory / "fixtures"

    @property
    def workflow_rev(self) -> str:
        return self.env.get("workflow_rev") or self.meta.get("workflow_rev") or WORKFLOW_REV

    @property
    def clock(self) -> str:
        return str(self.env.get("clock") or "2026-10-14T10:00:00+08:00")

    @property
    def period(self) -> str:
        return str(self.env.get("period") or "2026-10-W1")

    def fixture(self, relative: str | None) -> Path | None:
        if not relative:
            return None
        path = self.directory / relative
        return path if path.is_file() else None


def list_papers() -> list[str]:
    found = []
    for paper_id in PAPER_IDS:
        directory = PAPERS_DIR / paper_id
        if (directory / "task.md").is_file() and (directory / "rubric.md").is_file():
            found.append(paper_id)
    return found


def load_paper(paper_id: str) -> Paper:
    if paper_id not in PAPER_IDS:
        known = "、".join(PAPER_IDS)
        raise PaperError(f"未知题目 {paper_id!r}；已知：{known}")
    directory = PAPERS_DIR / paper_id
    if not directory.is_dir():
        raise PaperError(f"题目目录不存在：{directory}")
    return Paper(
        id=paper_id,
        directory=directory,
        meta=_load_mapping(directory / "meta.yaml"),
        env=_load_mapping(directory / "env.yaml"),
        task=(directory / "task.md").read_text(encoding="utf-8"),
        rubric=(directory / "rubric.md").read_text(encoding="utf-8"),
    )
