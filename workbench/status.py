"""当前状态：按域分别报告。

刻意**不**合成一个全局进度条——四种节奏合成一个数字没有意义，
而且会掩盖「某个域已经三个月没跑过」这类真问题。
"""

from __future__ import annotations

from . import domains, manifest, pending
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
        migrated = paths.module(key).is_dir()
        periods = manifest.list_periods(paths, key)
        row: dict = {
            "domain": key,
            "name": definition.zh,
            "facing": definition.facing,
            "cadence": definition.cadence,
            "migrated": migrated,
            "periods": len(periods),
            "latest": periods[0] if periods else None,
        }

        if not migrated:
            row["state"] = "未迁入"
            checks.append({"name": definition.zh, "level": "warn", "detail": "尚未迁入工作台"})
        elif not periods:
            row["state"] = "就绪，还没跑过"
            checks.append({"name": definition.zh, "level": "ok", "detail": "就绪，还没跑过"})
        else:
            current = manifest.Manifest(paths, key, periods[0])
            steps = current.load()["steps"]
            done = sum(1 for s in steps.values() if s.get("state") in {"done", "skipped"})
            stuck = [n for n, s in steps.items() if s.get("state") in {"blocked", "failed"}]
            row["state"] = f"{periods[0]}：{done}/{len(steps)} 步完成" if steps else f"{periods[0]}：已开期"
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
                checks.append({"name": definition.zh, "level": "ok", "detail": row["state"]})
        rows.append(row)

    pending_migration = [r["name"] for r in rows if not r["migrated"]]
    stuck_any = any(r.get("stuck") for r in rows)

    # 「有什么在等我」——放在最前面。
    # 门禁把动作停在半路是对的，但停住之后没有出口，动作就会沉进待办里
    # （航空 7 月的写入就这样搁了十几轮）。见 pending.py。
    waiting = pending.collect(paths)
    if waiting:
        checks = pending.as_checks(waiting) + checks

    blocked_waiting = [w for w in waiting if w.kind == "卡住"]
    confirm_waiting = [w for w in waiting if w.kind == "等确认"]
    for item in confirm_waiting:
        if item.phrase:
            warnings.append(f"要继续「{item.step_zh}」，跟我说「{item.phrase}」。")

    if blocked_waiting or stuck_any:
        status, summary = "partial", f"有 {len(blocked_waiting)} 处卡住，需要处理。"
    elif confirm_waiting:
        status = "partial"
        summary = f"有 {len(confirm_waiting)} 件事在等你说话。"
    elif pending_migration:
        status = "partial"
        summary = f"{len(rows) - len(pending_migration)}/{len(rows)} 个域已迁入工作台。"
    else:
        status, summary = "success", f"{len(rows)} 个域全部就位。"

    next_steps = []
    for item in confirm_waiting:
        need = f"说「{item.phrase}」" if item.phrase else (item.gate or "确认")
        next_steps.append(f"{item.domain_zh} · {item.period_label} 的「{item.step_zh}」：{need}")
    if pending_migration:
        next_steps.append("待迁入：" + "、".join(pending_migration) + "（按 docs/MIGRATION.md 的顺序推进）")

    return Result(
        status=status,
        summary=summary,
        checks=checks,
        warnings=warnings,
        next_steps=next_steps,
        data={
            "domains": rows,
            "waiting": [
                {
                    "domain": w.domain,
                    "period": w.period,
                    "step": w.step,
                    "kind": w.kind,
                    "phrase": w.phrase,
                }
                for w in waiting
            ],
        },
    )
