"""peers-model 运行状态。周期键 = TICKER-26Q2 / TICKER-26H1 / TICKER-FY2026。"""
from __future__ import annotations

from dataclasses import dataclass

from workbench.manifest import Manifest
from workbench.paths import Paths

DOMAIN = "peers-model"


@dataclass(frozen=True)
class Step:
    key: str
    zh: str
    gate: str | None
    hint: str
    phrase: str | None = None


STEPS: tuple[Step, ...] = (
    Step("extract", "抽取 PDF 并生成 facts 模板", None, "ir peers-model prepare"),
    Step("facts", "按 PDF 填写结构化 facts", None, "填写 outputs/.../facts.template.json"),
    Step("verify", "独立重读 PDF 核对证据", None, "ir peers-model plan"),
    Step("plan", "生成零写入计划", None, "ir peers-model plan"),
    Step(
        "apply",
        "写入 Model 副本",
        "须用户明确确认",
        "ir peers-model apply --confirmed",
        phrase="确认写入模型副本",
    ),
    Step("readback", "关闭重开回读单元格", None, "apply 内自动完成"),
    Step("charts", "按 2019/2023+ 政策更新并审计图表", None, "apply 内自动完成"),
)

STEP_ORDER = [step.key for step in STEPS]
STEP_BY_KEY = {step.key: step for step in STEPS}


def open_manifest(base: Paths, period: str) -> Manifest:
    manifest = Manifest(base, DOMAIN, period)
    manifest.ensure_steps(STEP_ORDER)
    return manifest


def progress(base: Paths, period: str) -> dict:
    manifest = Manifest(base, DOMAIN, period)
    if not manifest.exists:
        return {
            "period": period, "done": 0, "total": len(STEP_ORDER),
            "next": STEP_ORDER[0], "stuck": [], "states": {},
        }
    states = manifest.load()["steps"]
    done = [key for key, value in states.items() if value.get("state") in {"done", "skipped"}]
    order = [key for key in STEP_ORDER if key in states]
    nxt = next((key for key in order if states[key].get("state") not in {"done", "skipped"}), None)
    stuck = [
        key for key, value in states.items()
        if value.get("state") in {"blocked", "failed"}
    ]
    return {
        "period": period, "done": len(done), "total": len(STEP_ORDER),
        "next": nxt, "stuck": stuck, "states": {key: value.get("state") for key, value in states.items()},
    }
