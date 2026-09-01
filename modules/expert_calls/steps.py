"""Run-id based progress for expert-calls."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workbench.manifest import Manifest
from workbench.paths import Paths

DOMAIN = "expert-calls"


@dataclass(frozen=True)
class Step:
    key: str
    zh: str
    gate: str | None = None
    phrase: str | None = None


STEPS = (
    Step("extract", "抽取访谈 PDF"),
    Step("shortlist", "生成精选候选排序"),
    Step("validate", "校验人工选择结果"),
    Step("render", "渲染 callout XML"),
    Step("publish", "发布到飞书", "写飞书须明确确认", "发布专家访谈精选"),
    Step("intel-draft", "生成情报库草稿"),
)
STEP_ORDER = [step.key for step in STEPS]
STEP_BY_KEY = {step.key: step for step in STEPS}


def open_manifest(base: Paths, run_id: str) -> Manifest:
    manifest = Manifest(base, DOMAIN, run_id)
    manifest.ensure_steps(STEP_ORDER)
    return manifest


def record(
    base: Paths,
    run_id: str,
    step: str,
    state: str,
    *,
    note: str | None = None,
    inputs: dict[str, Path] | None = None,
    outputs: dict[str, Path] | None = None,
    result_data: dict | None = None,
) -> Manifest:
    manifest = open_manifest(base, run_id)
    for label, path in (inputs or {}).items():
        manifest.record_input(label, path)
    for label, path in (outputs or {}).items():
        manifest.record_output(label, path)
    manifest.set_step(step, state, note, result_data)
    return manifest


def progress(base: Paths, run_id: str) -> dict:
    manifest = Manifest(base, DOMAIN, run_id)
    if not manifest.exists:
        return {
            "period": run_id,
            "done": 0,
            "total": len(STEP_ORDER),
            "next": STEP_ORDER[0],
            "stuck": [],
            "states": {},
        }
    entries = manifest.load()["steps"]
    states = {key: entries.get(key, {}).get("state", "pending") for key in STEP_ORDER}
    return {
        "period": run_id,
        "done": sum(state in {"done", "skipped"} for state in states.values()),
        "total": len(STEP_ORDER),
        "next": manifest.next_pending(STEP_ORDER),
        "stuck": [key for key, state in states.items() if state in {"blocked", "failed"}],
        "states": states,
    }


def render_progress(base: Paths, run_id: str) -> list[dict]:
    states = progress(base, run_id)["states"]
    levels = {"done": "ok", "skipped": "ok", "blocked": "fail", "failed": "fail"}
    labels = {
        "done": "完成", "skipped": "跳过", "running": "进行中",
        "pending": "待办", "blocked": "被拦住", "failed": "失败",
    }
    rows = []
    for step in STEPS:
        state = states.get(step.key, "pending")
        detail = labels.get(state, state)
        if state == "pending" and step.gate:
            detail = f"待办 · 门禁：{step.gate}"
        rows.append({"name": step.zh, "level": levels.get(state, "warn"), "detail": detail})
    return rows
