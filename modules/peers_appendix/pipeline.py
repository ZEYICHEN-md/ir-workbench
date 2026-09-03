"""Phased peers-appendix orchestration with hard-stop gates."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from workbench.result import Result

from . import audit, charts, model_ops, steps, writing
from .ir_snapshot import (
    load_snapshot,
    missing_source_materials,
    write_markdown,
)
from .model_common import detect_layout
from .paths import CompanyQuarterView, resolve_view


@dataclass
class BlockedStep(Exception):
    step: str
    reason: str
    missing: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return self.reason


def initialize(
    base,
    ticker: str,
    period: str,
) -> Result:
    view = resolve_view(base, ticker, period)
    view.ensure_directories()
    manifest = steps.open_manifest(base, view.ticker, view.period)
    manifest.load()["companies"][view.ticker]["paths"] = view.as_dict()
    manifest.save()
    return Result(
        status="partial",
        summary=f"{view.ticker} {view.period} 已建立材料、产出和运行视图；未生成任何业务判断。",
        domain=steps.DOMAIN,
        period=view.period,
        checks=[
            {
                "name": "材料目录",
                "level": "ok",
                "detail": str(view.materials_dir),
            },
            {
                "name": "人工文件",
                "level": "warn",
                "detail": "ir_snapshot / fill_inputs / strategy_decision / texts 均由人完成",
            },
        ],
        next_steps=[
            "把该公司当季 IR/业绩材料、source_model.xlsx 和 template.docx 放进材料目录。",
            "阅读材料后填写 ir_snapshot.json；系统不会自动编数字。",
        ],
        data=view.as_dict(),
    )


def resolved_view(base, ticker: str, period: str) -> Result:
    view = resolve_view(base, ticker, period)
    return Result(
        status="success",
        summary=f"{view.ticker} {view.period} 路径已解析（只读，未创建文件）。",
        domain=steps.DOMAIN,
        period=view.period,
        data=view.as_dict(),
    )


def _require_file(step: str, path: Path, label: str, advice: str) -> None:
    if not path.is_file():
        raise BlockedStep(step, f"缺少 {label}。", [str(path)], [advice])


def _materials_gate(view: CompanyQuarterView) -> dict:
    _require_file(
        "materials",
        view.snapshot,
        "ir_snapshot.json",
        "先读当季 IR/业绩材料，再填写 ir_snapshot.json；不要从旧 Model 反抄。",
    )
    try:
        snapshot = load_snapshot(
            view.snapshot,
            ticker=view.ticker,
            quarter=view.quarter,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise BlockedStep(
            "materials",
            f"ir_snapshot.json 未通过校验：{error}",
            [str(view.snapshot)],
            ["修正 ticker、quarter、sources 和 actuals 后重跑。"],
        ) from error
    missing_sources = missing_source_materials(snapshot, view.materials_dir)
    if missing_sources:
        raise BlockedStep(
            "materials",
            "ir_snapshot 引用的来源材料不在当季材料目录。",
            missing_sources,
            ["放入对应 PDF/TXT/Markdown；门禁必须能回到原材料。"],
        )
    write_markdown(view.snapshot, view.snapshot_markdown)
    input_paths = {"ir_snapshot": view.snapshot}
    for index, source in enumerate(snapshot["sources"], 1):
        # missing_source_materials already proved one compatible path exists.
        from .ir_snapshot import resolve_material_path

        material = resolve_material_path(view.materials_dir, str(source))
        if material is not None:
            input_paths[f"material-{index}"] = material
    steps.record(
        view.base,
        view.ticker,
        view.period,
        "materials",
        "done",
        inputs=input_paths,
        outputs={"ir_snapshot_md": view.snapshot_markdown},
        result_data={"sources": len(snapshot["sources"])},
    )
    return snapshot


def _load_fill(view: CompanyQuarterView) -> dict:
    _require_file(
        "fill",
        view.fill,
        "fill_inputs.json",
        "依据当季 IR snapshot 人工整理 fill JSON；系统不会猜行或补数字。",
    )
    try:
        payload = json.loads(view.fill.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BlockedStep(
            "fill",
            f"fill_inputs.json 无法解析：{error}",
            [str(view.fill)],
        ) from error
    if str(payload.get("sheet", "")).upper() != view.ticker:
        raise BlockedStep(
            "fill",
            f"fill.sheet={payload.get('sheet')!r}，应为 {view.ticker}。",
            [str(view.fill)],
        )
    if payload.get("quarter") != view.quarter:
        raise BlockedStep(
            "fill",
            f"fill.quarter={payload.get('quarter')!r}，应为 {view.quarter}。",
            [str(view.fill)],
        )
    if not isinstance(payload.get("inputs"), list) or not payload["inputs"]:
        raise BlockedStep(
            "fill",
            "fill.inputs 必须是非空列表。",
            [str(view.fill)],
        )
    for index, item in enumerate(payload["inputs"], 1):
        if not isinstance(item, dict) or "row" not in item or "value" not in item:
            raise BlockedStep(
                "fill",
                f"fill.inputs 第 {index} 项缺 row/value。",
                [str(view.fill)],
            )
    return payload


def _seed_model(view: CompanyQuarterView) -> None:
    if view.model.is_file():
        return
    _require_file(
        "insert",
        view.source_model,
        "source_model.xlsx",
        "把本季使用的 peers model 基准明确复制为 source_model.xlsx；系统不按文件名猜最新。",
    )
    view.model.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(view.source_model, view.model)


def _step_insert(view: CompanyQuarterView) -> dict:
    _seed_model(view)
    layout = detect_layout(view.model, view.ticker)
    if view.quarter in layout["quarters"]:
        result = {"already_present": True, "column": layout["quarters"][view.quarter]}
    else:
        sibling = view.run_dir / f"{view.ticker}_{view.period}_insert.xlsx"
        inserted = model_ops.insert_quarter(
            view.model,
            view.ticker,
            view.quarter,
            out=sibling,
        )
        model_ops.promote_sibling(inserted, view.model)
        layout = detect_layout(view.model, view.ticker)
        result = {
            "already_present": False,
            "column": layout["quarters"][view.quarter],
        }
    steps.record(
        view.base,
        view.ticker,
        view.period,
        "insert",
        "done",
        inputs={"source_model": view.source_model}
        if view.source_model.is_file()
        else None,
        outputs={"work_model": view.model},
        result_data=result,
    )
    return result


def _step_fill(view: CompanyQuarterView) -> dict:
    _load_fill(view)
    _require_file(
        "fill",
        view.model,
        "work model",
        "先执行 insert 步骤。",
    )
    sibling = view.run_dir / f"{view.ticker}_{view.period}_filled.xlsx"
    filled = model_ops.fill_quarter(
        view.model,
        view.fill,
        out=sibling,
        allow_formula_overwrite=False,
    )
    model_ops.promote_sibling(filled, view.model)
    steps.record(
        view.base,
        view.ticker,
        view.period,
        "fill",
        "done",
        inputs={"fill_inputs": view.fill},
        outputs={"work_model": view.model},
        result_data={"inputs": len(_load_fill(view)["inputs"])},
    )
    return {"model": str(view.model)}


def _gate_audit(view: CompanyQuarterView) -> dict:
    snapshot = _materials_gate(view)
    _load_fill(view)
    _require_file(
        "audit_model_quarter",
        view.model,
        "work model",
        "先执行完整 Model 阶段的 insert 与 fill。",
    )
    report = audit.run_audit(
        view.model,
        view.ticker,
        view.quarter,
        view.fill,
        snapshot,
    )
    audit.write_report(report, view.audit_report)
    if not report["summary"]["passed"]:
        raise BlockedStep(
            "audit_model_quarter",
            "audit_model_quarter 严格门禁未通过。",
            [
                f"FAIL {report['summary']['fail']}",
                f"WARN {report['summary']['warn']}",
                str(view.audit_report),
            ],
            ["逐项核对 fill、IR snapshot 和 Model 口径；不得绕过后继续 charts。"],
        )
    steps.record(
        view.base,
        view.ticker,
        view.period,
        "audit_model_quarter",
        "done",
        inputs={"work_model": view.model, "fill_inputs": view.fill},
        outputs={"model_audit": view.audit_report},
        result_data=report["summary"],
    )
    return report


def _step_charts(view: CompanyQuarterView) -> dict:
    if steps.state(
        view.base, view.ticker, view.period, "audit_model_quarter"
    ) != "done":
        raise BlockedStep(
            "charts",
            "Model audit 尚未通过，禁止更新图表。",
            next_steps=["先让 audit_model_quarter 达到 strict pass。"],
        )
    sibling = view.run_dir / f"{view.ticker}_{view.period}_charts.xlsx"
    updated = charts.update_charts(
        view.model,
        view.ticker,
        view.quarter,
        out=sibling,
    )
    model_ops.promote_sibling(updated, view.model)
    steps.record(
        view.base,
        view.ticker,
        view.period,
        "charts",
        "done",
        outputs={"work_model": view.model},
    )
    return {"model": str(view.model)}


def _gate_charts(view: CompanyQuarterView) -> dict:
    _require_file(
        "check_charts_gate",
        view.model,
        "work model",
        "先执行 Model 阶段。",
    )
    errors = charts.check_charts(view.model, view.ticker, view.quarter)
    report = {
        "gate": "check_charts_gate",
        "ticker": view.ticker,
        "quarter": view.quarter,
        "passed": not errors,
        "errors": errors,
    }
    view.charts_gate_report.parent.mkdir(parents=True, exist_ok=True)
    view.charts_gate_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if errors:
        raise BlockedStep(
            "check_charts_gate",
            "check_charts_gate 未通过。",
            [*errors[:10], str(view.charts_gate_report)],
            ["修正 series 终点、整数季节标签或重叠后重跑；不得直接 export。"],
        )
    steps.record(
        view.base,
        view.ticker,
        view.period,
        "check_charts_gate",
        "done",
        outputs={"charts_gate": view.charts_gate_report},
    )
    return report


def _step_export(view: CompanyQuarterView) -> dict:
    if steps.state(
        view.base, view.ticker, view.period, "check_charts_gate"
    ) != "done":
        raise BlockedStep(
            "export",
            "图表门禁尚未通过，禁止导出。",
            next_steps=["先通过 check_charts_gate。"],
        )
    written, route = charts.export_for_ticker(
        view.model,
        view.ticker,
        view.chart_dir,
        generated_map=view.generated_chart_map,
    )
    if not written:
        raise BlockedStep(
            "export",
            f"{view.ticker} 没有导出任何图表。",
            next_steps=["检查 Excel 图表 sheet 与 COM 环境。"],
        )
    outputs = {f"chart-{index}": path for index, path in enumerate(written, 1)}
    if view.generated_chart_map.is_file():
        outputs["chart_map"] = view.generated_chart_map
    steps.record(
        view.base,
        view.ticker,
        view.period,
        "export",
        "done",
        outputs=outputs,
        result_data={"route": route.exporter, "count": len(written)},
    )
    return {"route": route.exporter, "charts": [str(path) for path in written]}


MODEL_RUNNERS: dict[str, Callable[[CompanyQuarterView], dict]] = {
    "materials": _materials_gate,
    "insert": _step_insert,
    "fill": _step_fill,
    "audit_model_quarter": _gate_audit,
    "charts": _step_charts,
    "check_charts_gate": _gate_charts,
    "export": _step_export,
}


def _step_brief(view: CompanyQuarterView) -> dict:
    incomplete_gates = [
        gate
        for gate in ("audit_model_quarter", "check_charts_gate")
        if steps.state(view.base, view.ticker, view.period, gate) != "done"
    ]
    if incomplete_gates:
        raise BlockedStep(
            "brief",
            "Model must-pass gates 尚未全部通过，不能生成 writing brief。",
            incomplete_gates,
            next_steps=["先跑完整 Model 阶段或通过 model gates。"],
        )
    snapshot = _materials_gate(view)
    facts = writing.extract_model_facts(
        view.model, view.ticker, view.quarter
    )
    brief = writing.build_writing_brief(facts, snapshot)
    writing.write_brief(brief, view.brief)
    steps.record(
        view.base,
        view.ticker,
        view.period,
        "brief",
        "done",
        inputs={"work_model": view.model, "ir_snapshot": view.snapshot},
        outputs={"writing_brief": view.brief},
        result_data={"slots": len(brief["slots"])},
    )
    return brief


def _step_strategy(view: CompanyQuarterView) -> dict:
    _require_file(
        "strategy_decision",
        view.strategy_decision,
        "strategy_decision.json",
        "由负责人明确选择 preserve-template / mentor-supplied / out-of-scope，并写 confirmed_by_human: true。",
    )
    try:
        decision = writing.validate_strategy_decision(view.strategy_decision)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise BlockedStep(
            "strategy_decision",
            f"战略段门禁未通过：{error}",
            [str(view.strategy_decision)],
        ) from error
    steps.record(
        view.base,
        view.ticker,
        view.period,
        "strategy_decision",
        "done",
        inputs={"strategy_decision": view.strategy_decision},
        result_data={"decision": decision["decision"]},
    )
    return decision


def _step_texts(view: CompanyQuarterView) -> dict:
    _require_file(
        "texts_human",
        view.texts,
        "texts.json",
        "按 writing_brief + 当前季度材料人工写作；系统不会自动套句或补战略判断。",
    )
    try:
        payload = writing.load_texts(view.texts)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise BlockedStep(
            "texts_human",
            f"texts.json 无法使用：{error}",
            [str(view.texts)],
        ) from error
    steps.record(
        view.base,
        view.ticker,
        view.period,
        "texts_human",
        "done",
        inputs={"texts": view.texts},
        result_data={"paragraphs": len(payload["paragraphs"])},
    )
    return payload


def _gate_writing(view: CompanyQuarterView) -> dict:
    _require_file(
        "check_writing_gate",
        view.brief,
        "writing_brief.json",
        "先执行 writing 的 brief 步骤。",
    )
    snapshot = _materials_gate(view)
    _step_strategy(view)
    texts = _step_texts(view)
    brief = json.loads(view.brief.read_text(encoding="utf-8"))
    errors = writing.check_writing(
        brief,
        texts,
        view.quarter,
        snapshot,
        view.materials_dir,
    )
    report = {
        "gate": "check_writing_gate",
        "ticker": view.ticker,
        "quarter": view.quarter,
        "passed": not errors,
        "errors": errors,
        "scope": "ops_finance",
    }
    view.writing_gate_report.parent.mkdir(parents=True, exist_ok=True)
    view.writing_gate_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if errors:
        raise BlockedStep(
            "check_writing_gate",
            "check_writing_gate 未通过。",
            [*errors[:12], str(view.writing_gate_report)],
            ["补齐 brief 槽位、当季 must-cover 与原话出处后重跑；不得 apply。"],
        )
    steps.record(
        view.base,
        view.ticker,
        view.period,
        "check_writing_gate",
        "done",
        outputs={"writing_gate": view.writing_gate_report},
    )
    return report


def _step_apply(view: CompanyQuarterView) -> dict:
    if steps.state(
        view.base, view.ticker, view.period, "check_writing_gate"
    ) != "done":
        raise BlockedStep(
            "apply",
            "写作门禁尚未通过，禁止写入 Word。",
            next_steps=["先通过 check_writing_gate。"],
        )
    _require_file(
        "apply",
        view.template,
        "template.docx",
        "放入该公司上季 Word 模板；不可拿其他 ticker 模板代替。",
    )
    result = writing.apply_for_ticker(
        view.ticker,
        view.template,
        view.texts,
        view.applied_docx,
        view.run_dir / "docx_apply_work",
    )
    steps.record(
        view.base,
        view.ticker,
        view.period,
        "apply",
        "done",
        inputs={"template": view.template, "texts": view.texts},
        outputs={"applied_docx": view.applied_docx},
        result_data={"route": result["route"], "matched": result["matched"]},
    )
    return result


def _step_embed(view: CompanyQuarterView) -> dict:
    _require_file(
        "charts_embed",
        view.applied_docx,
        "已写文本的 Word",
        "先执行 apply。",
    )
    if not view.chart_map.is_file():
        route = charts.select_chart_route(view.ticker)
        if route.ticker == "ABNB":
            detail = (
                "ABNB 使用专用图表导出，但旧仓没有经过验证的 Word 图位映射；"
                "请人工核对上季 Word 的 media 槽位后提供 chart_map.json。"
            )
        else:
            detail = (
                f"{view.ticker} 使用 {route.exporter} 导出；"
                "请提供该公司模板对应的 chart_map.json。"
            )
        raise BlockedStep(
            "charts_embed",
            detail,
            [str(view.input_chart_map)],
            ["map 的 key 是 media/imageN.png，value 是本季导出的 PNG 路径。"],
        )
    try:
        mapping = charts.load_chart_map(view.chart_map)
        mapping = {
            key: str(
                Path(value)
                if Path(value).is_absolute()
                else (view.base.root / value).resolve()
            )
            for key, value in mapping.items()
        }
        replaced = charts.embed_charts(
            view.applied_docx,
            mapping,
            view.docx,
            view.run_dir / "chart_embed_work",
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise BlockedStep(
            "charts_embed",
            f"图表嵌入失败：{error}",
            [str(view.chart_map)],
        ) from error
    steps.record(
        view.base,
        view.ticker,
        view.period,
        "charts_embed",
        "done",
        inputs={"chart_map": view.chart_map},
        outputs={"docx": view.docx},
        result_data={
            "route": charts.select_chart_route(view.ticker).exporter,
            "replaced": replaced,
        },
    )
    return {"replaced": replaced, "docx": str(view.docx)}


def _gate_docx(view: CompanyQuarterView) -> dict:
    _require_file(
        "accept_docx_gate",
        view.docx,
        "嵌图后的 Word",
        "先执行 writing apply 与 charts_embed。",
    )
    _require_file(
        "accept_docx_gate",
        view.chart_map,
        "chart_map.json",
        "验收必须知道本次实际替换了哪些图位。",
    )
    _require_file(
        "accept_docx_gate",
        view.template,
        "template.docx",
        "验收需要与本公司的上季模板比较。",
    )
    _require_file(
        "accept_docx_gate",
        view.texts,
        "texts.json",
        "验收需要对本次人工 texts 做 re-apply smoke。",
    )
    mapping = charts.load_chart_map(view.chart_map)
    errors = writing.accept_docx(
        view.ticker,
        view.docx,
        view.template,
        view.texts,
        view.quarter,
        mapping,
    )
    report = {
        "gate": "accept_docx_gate",
        "ticker": view.ticker,
        "quarter": view.quarter,
        "passed": not errors,
        "errors": errors,
    }
    view.docx_gate_report.parent.mkdir(parents=True, exist_ok=True)
    view.docx_gate_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if errors:
        raise BlockedStep(
            "accept_docx_gate",
            "accept_docx_gate 未通过。",
            [*errors[:12], str(view.docx_gate_report)],
            ["修正季度文字、未匹配槽位或图位后重跑；不得宣称 Word 完成。"],
        )
    steps.record(
        view.base,
        view.ticker,
        view.period,
        "accept_docx_gate",
        "done",
        outputs={"docx_gate": view.docx_gate_report, "docx": view.docx},
    )
    return report


WRITING_RUNNERS: dict[str, Callable[[CompanyQuarterView], dict]] = {
    "brief": _step_brief,
    "strategy_decision": _step_strategy,
    "texts_human": _step_texts,
    "check_writing_gate": _gate_writing,
    "apply": _step_apply,
    "charts_embed": _step_embed,
    "accept_docx_gate": _gate_docx,
}


def _run_selected(
    view: CompanyQuarterView,
    selected: list[str],
    runners: dict[str, Callable[[CompanyQuarterView], dict]],
    phase: str,
) -> Result:
    # Validate the entire plan before touching files.  The frozen orchestrator
    # silently skipped unknown names; that is unsafe for must-pass gates.
    steps.assert_known_steps(selected)
    invalid = [name for name in selected if name not in runners]
    if invalid:
        raise steps.UnknownStepError(
            f"{phase} 阶段不包含步骤：" + "、".join(invalid)
        )
    completed: list[str] = []
    outputs: dict[str, object] = {}
    for name in selected:
        steps.record(
            view.base,
            view.ticker,
            view.period,
            name,
            "running",
        )
        try:
            outputs[name] = runners[name](view)
        except BlockedStep as error:
            if error.step != name:
                steps.record(
                    view.base,
                    view.ticker,
                    view.period,
                    name,
                    "blocked",
                    note=f"前置门禁 {error.step}：{error.reason}",
                )
            steps.record(
                view.base,
                view.ticker,
                view.period,
                error.step,
                "blocked",
                note=error.reason,
            )
            return Result(
                status="blocked",
                summary=f"{view.ticker} {view.period} 在 {error.step} 硬停止：{error.reason}",
                domain=steps.DOMAIN,
                period=view.period,
                missing=error.missing,
                next_steps=error.next_steps,
                data={"completed_this_run": completed, "blocked_step": error.step},
            )
        except Exception as error:  # noqa: BLE001 — return a durable failed state
            steps.record(
                view.base,
                view.ticker,
                view.period,
                name,
                "failed",
                note=f"{type(error).__name__}: {error}",
            )
            return Result(
                status="failed",
                summary=(
                    f"{view.ticker} {view.period} 的 {name} 失败："
                    f"{type(error).__name__}: {error}"
                ),
                domain=steps.DOMAIN,
                period=view.period,
                data={"completed_this_run": completed, "failed_step": name},
            )
        completed.append(name)
    return Result(
        status="success",
        summary=f"{view.ticker} {view.period} {phase} 阶段通过。",
        domain=steps.DOMAIN,
        period=view.period,
        checks=[
            {"name": name, "level": "ok", "detail": "完成"}
            for name in completed
        ],
        data={"completed_this_run": completed, "outputs": outputs},
    )


def run_model(base, ticker: str, period: str) -> Result:
    view = resolve_view(base, ticker, period)
    view.ensure_directories()
    return _run_selected(
        view,
        steps.MODEL_STEPS,
        MODEL_RUNNERS,
        "model",
    )


def run_writing(base, ticker: str, period: str) -> Result:
    view = resolve_view(base, ticker, period)
    view.ensure_directories()
    return _run_selected(
        view,
        steps.WRITING_STEPS,
        WRITING_RUNNERS,
        "writing",
    )


def run_gates(
    base,
    ticker: str,
    period: str,
    *,
    phase: str,
    step: str | None = None,
) -> Result:
    view = resolve_view(base, ticker, period)
    if step is not None:
        selected = [step]
    elif phase == "model":
        selected = ["audit_model_quarter", "check_charts_gate"]
    elif phase == "writing":
        selected = ["check_writing_gate", "accept_docx_gate"]
    elif phase == "all":
        selected = [
            "audit_model_quarter",
            "check_charts_gate",
            "check_writing_gate",
            "accept_docx_gate",
        ]
    else:
        raise ValueError(f"未知 gate phase：{phase}")
    steps.assert_known_steps(selected)
    non_gates = [name for name in selected if name not in steps.GATE_STEPS]
    if non_gates:
        raise steps.UnknownStepError(
            "gate 命令只接受 must-pass 步骤：" + "、".join(steps.GATE_STEPS)
        )
    runners = {**MODEL_RUNNERS, **WRITING_RUNNERS}
    return _run_selected(view, selected, runners, f"{phase} gates")
