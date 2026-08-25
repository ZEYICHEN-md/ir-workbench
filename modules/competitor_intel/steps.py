"""competitor-intel 的运行状态。周期键 = month_week（如 `2026-08-W2`）。

周度通道是新闻精选的副产品，所以只有两步：沉淀（打标入库）与重建投影。
季度通道的表述类条目走 `intel add`，不占周期状态机——它跟财报季而不是跟周次。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workbench.manifest import Manifest
from workbench.paths import Paths

DOMAIN = "competitor-intel"


@dataclass(frozen=True)
class Step:
    key: str
    zh: str
    gate: str | None
    hint: str
    #: 让这一步往前走所需的一句话。见 aviation_monthly/steps.py 的同名字段说明。
    phrase: str | None = None


STEPS: tuple[Step, ...] = (
    Step(
        "deposit",
        "沉淀本期新闻进情报库",
        "打标是草稿，须用户核对后入库",
        "ir intel deposit --period … → --commit",
        phrase="沉淀这期新闻",
    ),
    Step("rebuild", "重建公司档案投影", None, "ir intel rebuild"),
)

STEP_ORDER = [step.key for step in STEPS]
STEP_BY_KEY = {step.key: step for step in STEPS}


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
        return {
            "period": period, "done": 0, "total": len(STEP_ORDER),
            "next": STEP_ORDER[0], "stuck": [], "states": {},
        }
    steps = manifest.load()["steps"]
    done = [k for k, v in steps.items() if v.get("state") in {"done", "skipped"}]
    return {
        "period": period,
        "done": len(done),
        "total": len(STEP_ORDER),
        "next": manifest.next_pending(STEP_ORDER),
        "stuck": [k for k, v in steps.items() if v.get("state") in {"blocked", "failed"}],
        "states": {k: steps.get(k, {}).get("state", "pending") for k in STEP_ORDER},
    }


def render_progress(base: Paths, period: str) -> list[dict]:
    info = progress(base, period)
    states = info["states"]
    level_of = {
        "done": "ok", "skipped": "ok", "running": "warn",
        "pending": "warn", "blocked": "fail", "failed": "fail",
    }
    label_of = {
        "done": "完成", "skipped": "跳过", "running": "进行中",
        "pending": "待办", "blocked": "被拦住", "failed": "失败",
    }
    rows = []
    for step in STEPS:
        state = states.get(step.key, "pending")
        detail = label_of.get(state, state)
        if state == "pending" and step.gate:
            detail = f"待办 · 门禁：{step.gate}"
        rows.append({"name": step.zh, "level": level_of.get(state, "warn"), "detail": detail})
    return rows
