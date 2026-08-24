"""aviation-monthly 的运行状态。周期键 = 年月（如 `202607`）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workbench.manifest import Manifest
from workbench.paths import Paths

DOMAIN = "aviation-monthly"


@dataclass(frozen=True)
class Step:
    key: str
    zh: str
    gate: str | None
    hint: str


STEPS: tuple[Step, ...] = (
    Step("dry-run", "抓官方数据并校验（不写入）", None, "ir aviation run --year 2026 --month 7"),
    Step("commit", "写入 Airline Data 与指标底稿", "须用户明确确认", "ir aviation run … --commit"),
    Step("resync", "重建指标快照并生成看板", None, "ir industry merge → generate-dashboard"),
)

STEP_ORDER = [step.key for step in STEPS]
STEP_BY_KEY = {step.key: step for step in STEPS}


def period_key(year: int, month: int) -> str:
    return f"{year}{month:02d}"


def open_manifest(base: Paths, period: str) -> Manifest:
    manifest = Manifest(base, DOMAIN, period)
    manifest.ensure_steps(STEP_ORDER)
    return manifest


def record(
    base: Paths,
    period: str,
    step: str,
    state: str,
    *,
    note: str | None = None,
    inputs: dict[str, Path] | None = None,
    outputs: dict[str, Path] | None = None,
) -> Manifest:
    manifest = open_manifest(base, period)
    for label, path in (inputs or {}).items():
        manifest.record_input(label, path)
    for label, path in (outputs or {}).items():
        manifest.record_output(label, path)
    manifest.set_step(step, state, note)
    return manifest


def progress(base: Paths, period: str) -> dict:
    manifest = Manifest(base, DOMAIN, period)
    if not manifest.exists:
        return {"period": period, "done": 0, "total": len(STEP_ORDER), "next": STEP_ORDER[0], "stuck": [], "states": {}}
    states = manifest.load()["steps"]
    done = [k for k, v in states.items() if v.get("state") in {"done", "skipped"}]
    return {
        "period": period,
        "done": len(done),
        "total": len(STEP_ORDER),
        "next": manifest.next_pending(STEP_ORDER),
        "stuck": [k for k, v in states.items() if v.get("state") in {"blocked", "failed"}],
        "states": {k: states.get(k, {}).get("state", "pending") for k in STEP_ORDER},
    }


def render_progress(base: Paths, period: str) -> list[dict]:
    info = progress(base, period)
    states = info["states"]
    level_of = {"done": "ok", "skipped": "ok", "running": "warn", "pending": "warn", "blocked": "fail", "failed": "fail"}
    label_of = {
        "done": "完成",
        "skipped": "跳过",
        "running": "进行中",
        "pending": "待办",
        "blocked": "被拦住",
        "failed": "失败",
    }
    rows = []
    for step in STEPS:
        state = states.get(step.key, "pending")
        detail = label_of.get(state, state)
        if state == "pending" and step.gate:
            detail = f"待办 · 门禁：{step.gate}"
        rows.append({"name": step.zh, "level": level_of.get(state, "warn"), "detail": detail})
    return rows
