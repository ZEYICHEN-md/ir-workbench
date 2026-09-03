"""当前状态：按域分别报告。

刻意**不**合成一个全局进度条——四种节奏合成一个数字没有意义，
而且会掩盖「某个域已经三个月没跑过」这类真问题。
"""

from __future__ import annotations

from . import domain_state, domains, manifest, pending
from .paths import Paths
from .result import Result

STATE_ZH = {
    "pending": "待办",
    "running": "进行中",
    "done": "完成",
    "blocked": "被拦住",
    "failed": "失败",
    "skipped": "跳过",
}


def run(paths: Paths, domain: str | None = None) -> Result:
    keys = [domain] if domain else list(domains.DOMAINS)
    if domain:
        domains.get(domain)  # 校验域名

    rows: list[dict] = []
    checks: list[dict] = []
    warnings: list[str] = []

    for key in keys:
        definition = domains.get(key)
        runtime = domain_state.probe(paths, definition)
        runtime_ready = runtime.module_present and runtime.cli_loaded and runtime.health_loaded
        periods = manifest.list_periods(paths, key) if runtime.module_present else []
        row: dict = {
            "domain": key,
            "name": definition.zh,
            "facing": definition.facing,
            "cadence": definition.cadence,
            "module_present": runtime.module_present,
            "cli_loaded": runtime.cli_loaded,
            "health_loaded": runtime.health_loaded,
            "runtime_ready": runtime_ready,
            # 兼容旧 JSON 消费方；不再用它推断可运行或已验收。
            "migrated": runtime.module_present,
            "validation_state": definition.validation_state,
            "validation_note": definition.validation_note,
            "periods": len(periods),
            "latest": periods[0] if periods else None,
        }

        if not runtime_ready:
            row["state"] = "运行时未就绪"
            gaps = []
            if not runtime.module_present:
                gaps.append("模块目录缺失")
            if not runtime.cli_loaded:
                gaps.append(runtime.cli_error or "CLI 未加载")
            if not runtime.health_loaded:
                gaps.append(runtime.health_error or "health 未加载")
            checks.append({"name": definition.zh, "level": "fail", "detail": "；".join(gaps)})
        elif not periods:
            if definition.validation_state == "lightweight":
                row["state"] = "轻量能力（按设计不建运行记录）"
            else:
                row["state"] = "就绪，还没跑过"
            level = "warn" if definition.validation_state == "partial" else "ok"
            checks.append(
                {
                    "name": definition.zh,
                    "level": level,
                    "detail": f"{row['state']} · {definition.validation_note}",
                }
            )
        else:
            current = manifest.Manifest(paths, key, periods[0])
            steps = current.load()["steps"]
            done = sum(1 for step in steps.values() if step.get("state") in {"done", "skipped"})
            stuck = [name for name, step in steps.items() if step.get("state") in {"blocked", "failed"}]
            run_state = f"{periods[0]}：{done}/{len(steps)} 步完成" if steps else f"{periods[0]}：已开期"
            row["state"] = run_state
            row["stuck"] = stuck
            if stuck:
                checks.append(
                    {
                        "name": definition.zh,
                        "level": "fail",
                        "detail": f"{periods[0]} 卡在：" + "、".join(stuck),
                    }
                )
                warnings.append(f"{definition.zh} 的 {periods[0]} 有步骤卡住，需要处理。")
            else:
                level = "warn" if definition.validation_state == "partial" else "ok"
                validation = {
                    "validated": "完整验收",
                    "partial": "部分验收",
                    "lightweight": "轻量能力",
                    "unvalidated": "尚未验收",
                }[definition.validation_state]
                checks.append(
                    {
                        "name": definition.zh,
                        "level": level,
                        "detail": f"{run_state} · {validation}：{definition.validation_note}",
                    }
                )
        rows.append(row)

    runtime_gaps = [row["name"] for row in rows if not row["runtime_ready"]]
    partial_validation = [row["name"] for row in rows if row["validation_state"] in {"partial", "unvalidated"}]
    stuck_any = any(row.get("stuck") for row in rows)

    # 「有什么在等我」——放在最前面。
    waiting = pending.collect(paths)
    if waiting:
        checks = pending.as_checks(waiting) + checks

    blocked_waiting = [item for item in waiting if item.kind == "卡住"]
    confirm_waiting = [item for item in waiting if item.kind == "等确认"]
    for item in confirm_waiting:
        if item.phrase:
            warnings.append(f"要继续「{item.step_zh}」，跟我说「{item.phrase}」。")

    if blocked_waiting or stuck_any:
        result_status, summary = "partial", f"有 {len(blocked_waiting)} 处卡住，需要处理。"
    elif confirm_waiting:
        result_status = "partial"
        summary = f"有 {len(confirm_waiting)} 件事在等你说话。"
    elif runtime_gaps:
        result_status = "partial"
        summary = f"{len(rows) - len(runtime_gaps)}/{len(rows)} 个域运行时就绪。"
    elif partial_validation:
        result_status = "partial"
        summary = f"运行时全部就绪；{len(partial_validation)} 个域仍是部分验收。"
    else:
        result_status, summary = "success", f"{len(rows)} 个域运行时就绪且完成既定验收。"

    next_steps = []
    for item in confirm_waiting:
        need = f"说「{item.phrase}」" if item.phrase else (item.gate or "确认")
        next_steps.append(f"{item.domain_zh} · {item.period_label} 的「{item.step_zh}」：{need}")
    if runtime_gaps:
        next_steps.append("修复运行时未就绪域：" + "、".join(runtime_gaps))
    if partial_validation:
        next_steps.append("待完成真实业务验收：" + "、".join(partial_validation))

    return Result(
        status=result_status,
        summary=summary,
        checks=checks,
        warnings=warnings,
        next_steps=next_steps,
        data={
            "domains": rows,
            "waiting": [
                {
                    "domain": item.domain,
                    "period": item.period,
                    "step": item.step,
                    "kind": item.kind,
                    "phrase": item.phrase,
                }
                for item in waiting
            ],
        },
    )
