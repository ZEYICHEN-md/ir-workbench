"""Per-company progress stored in the workbench Manifest.

``Manifest`` is indexed by domain + fiscal quarter.  A quarter contains several
peer companies, so step keys are namespaced as ``TICKER:step``.  This keeps one
workbench-native manifest while preserving an independent company-quarter view.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workbench.manifest import Manifest
from workbench.paths import Paths

DOMAIN = "peers-appendix"


class UnknownStepError(ValueError):
    pass


@dataclass(frozen=True)
class Step:
    key: str
    zh: str
    phase: str
    gate: str | None = None


STEPS: tuple[Step, ...] = (
    Step("materials", "材料与 IR snapshot 齐备", "materials", "人工材料门禁"),
    Step("insert", "插入季度列", "model"),
    Step(
        "fill",
        "用人工 fill JSON 写入 Model",
        "model",
        "人工填写门禁",
    ),
    Step(
        "audit_model_quarter",
        "Model 逐项勾稽",
        "model",
        "must-pass：audit_model_quarter",
    ),
    Step("charts", "延长图表系列并更新标签", "model"),
    Step(
        "check_charts_gate",
        "图表系列与标签门禁",
        "model",
        "must-pass：check_charts_gate",
    ),
    Step("export", "按 ticker 导出图表", "model"),
    Step("brief", "生成机械事实写作 brief", "writing"),
    Step(
        "strategy_decision",
        "确认战略段处理方式",
        "writing",
        "人工战略判断门禁",
    ),
    Step("texts_human", "人工完成 texts JSON", "writing", "人工写作门禁"),
    Step(
        "check_writing_gate",
        "写作完整性与出处门禁",
        "writing",
        "must-pass：check_writing_gate",
    ),
    Step("apply", "按 ticker 写入 Word", "writing"),
    Step("charts_embed", "按 ticker 图位映射嵌图", "writing"),
    Step(
        "accept_docx_gate",
        "Word 成品验收",
        "writing",
        "must-pass：accept_docx_gate",
    ),
)

STEP_ORDER = [step.key for step in STEPS]
STEP_BY_KEY = {step.key: step for step in STEPS}
MODEL_STEPS = [s.key for s in STEPS if s.phase in {"materials", "model"}]
WRITING_STEPS = [s.key for s in STEPS if s.phase == "writing"]
GATE_STEPS = {
    "audit_model_quarter",
    "check_charts_gate",
    "check_writing_gate",
    "accept_docx_gate",
}


def assert_known_steps(names: list[str] | tuple[str, ...]) -> None:
    unknown = [name for name in names if name not in STEP_BY_KEY]
    if unknown:
        raise UnknownStepError(
            "未知 peers 步骤：" + "、".join(unknown)
            + "；允许值：" + "、".join(STEP_ORDER)
        )


def _key(ticker: str, step: str) -> str:
    assert_known_steps([step])
    return f"{ticker.upper()}:{step}"


def open_manifest(base: Paths, ticker: str, period: str) -> Manifest:
    manifest = Manifest(base, DOMAIN, period)
    data = manifest.load()
    ticker = ticker.upper()
    wanted = [_key(ticker, step) for step in STEP_ORDER]
    changed = False
    for key in wanted:
        if key not in data["steps"]:
            data["steps"][key] = {"state": "pending"}
            changed = True
    old_order = list(data.get("order") or [])
    merged_order = [*old_order, *(key for key in wanted if key not in old_order)]
    if merged_order != old_order:
        data["order"] = merged_order
        changed = True
    companies = data.setdefault("companies", {})
    if ticker not in companies:
        companies[ticker] = {"period": period}
        changed = True
    if changed:
        manifest.save()
    return manifest


def record(
    base: Paths,
    ticker: str,
    period: str,
    step: str,
    state: str,
    *,
    note: str | None = None,
    inputs: dict[str, Path] | None = None,
    outputs: dict[str, Path] | None = None,
    result_data: dict | None = None,
) -> Manifest:
    manifest = open_manifest(base, ticker, period)
    prefix = ticker.upper()
    for label, path in (inputs or {}).items():
        manifest.record_input(f"{prefix}:{label}", path)
    for label, path in (outputs or {}).items():
        manifest.record_output(f"{prefix}:{label}", path)
    manifest.set_step(_key(prefix, step), state, note, result_data)
    return manifest


def state(base: Paths, ticker: str, period: str, step: str) -> str:
    manifest = open_manifest(base, ticker, period)
    return manifest.step_state(_key(ticker, step))


def progress(base: Paths, ticker: str, period: str) -> dict:
    manifest = open_manifest(base, ticker, period)
    states = {
        step: manifest.step_state(_key(ticker, step))
        for step in STEP_ORDER
    }
    next_step = next(
        (step for step in STEP_ORDER if states[step] not in {"done", "skipped"}),
        None,
    )
    return {
        "ticker": ticker.upper(),
        "period": period,
        "done": sum(v in {"done", "skipped"} for v in states.values()),
        "total": len(STEP_ORDER),
        "next": next_step,
        "stuck": [k for k, v in states.items() if v in {"blocked", "failed"}],
        "states": states,
    }


def render_progress(base: Paths, ticker: str, period: str) -> list[dict]:
    states = progress(base, ticker, period)["states"]
    levels = {
        "done": "ok",
        "skipped": "ok",
        "blocked": "fail",
        "failed": "fail",
    }
    labels = {
        "done": "完成",
        "skipped": "跳过",
        "running": "进行中",
        "pending": "待办",
        "blocked": "被拦住",
        "failed": "失败",
    }
    rows = []
    for step in STEPS:
        value = states.get(step.key, "pending")
        detail = labels.get(value, value)
        if value == "pending" and step.gate:
            detail = f"待办 · {step.gate}"
        rows.append(
            {
                "name": step.zh,
                "level": levels.get(value, "warn"),
                "detail": detail,
            }
        )
    return rows
