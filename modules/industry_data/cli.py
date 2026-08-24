"""industry-data 的命令。挂在 `ir industry ...` 下。

Agent 的手，不是人的入口。人的入口是 router/ROUTER.md。
"""

from __future__ import annotations

import json
from pathlib import Path

from workbench.config import Config
from workbench.result import Result

from . import (
    dashboard,
    drafts,
    feishu,
    insights as insights_mod,
    publish,
    snapshot,
    steps,
)
from .paths import DOMAIN, DomainPaths


def _resolve_workbook(base) -> tuple[Path | None, Result | None]:
    config = Config(base)
    workbook = config.workbook("industry")
    if workbook and workbook.is_file():
        return workbook, None
    candidates = config.candidates("industry")
    return None, Result(
        status="blocked",
        summary="指标底稿未指定，或配置指向的文件不存在。",
        domain=DOMAIN,
        checks=[{"name": "候选", "level": "warn", "detail": c.name} for c in candidates],
        next_steps=[
            "请**你**指定用哪一份底稿——系统不按文件名猜最新（ADR 0001）。",
            "指定后 Agent 会执行 `ir config set industry <路径>` 锁定。",
        ],
    )


def _log(base, step: str, result: Result, *, note: str | None = None, **paths_kw) -> Result:
    """把结果记进 manifest，并把「下一步是哪一步」补进 Result。

    只在能确定本期（快照已生成）时记录——周期键就是数据截至日。
    """
    period = steps.current_period(DomainPaths(base))
    if not period:
        return result
    state = {"success": "done", "partial": "running", "blocked": "blocked", "failed": "failed"}[
        result.status
    ]
    steps.record(base, period, step, state, note=note, **paths_kw)
    result.period = period
    info = steps.progress(base, period)
    if info["stuck"]:
        result.warnings.append("以下步骤卡着：" + "、".join(info["stuck"]))
    nxt = info.get("next")
    if result.status in {"success", "partial"} and nxt and nxt != step:
        following = steps.STEP_BY_KEY[nxt]
        suffix = "（可选）" if following.optional else ""
        result.next_steps.append(f"下一步：{following.zh}{suffix} —— {following.hint}")
    return result


def cmd_merge(args, base) -> Result:
    workbook, blocked = _resolve_workbook(base)
    if blocked:
        return blocked
    result = snapshot.rebuild(DomainPaths(base), workbook, confirm_clears=args.confirm_clears)
    return _log(base, "merge", result, inputs={"workbook": workbook})


def cmd_generate_dashboard(args, base) -> Result:
    paths = DomainPaths(base)
    result = dashboard.generate(paths)
    outputs = {"data_js": paths.data_js}
    if paths.insights_js.is_file():
        outputs["insights_js"] = paths.insights_js
    return _log(base, "dashboard", result, outputs=outputs)


def cmd_insights_draft(args, base) -> Result:
    # 出草稿不算完成——洞察这一步的完成判据是「人确认后入库」
    return drafts.prepare(DomainPaths(base), args.period)


def cmd_insights_confirm(args, base) -> Result:
    paths = DomainPaths(base)
    result = drafts.confirm(paths, Path(args.draft))
    return _log(base, "insights", result, outputs={"insights_canonical": paths.insights_canonical})


def cmd_mark(args, base) -> Result:
    """手动标记某一步——主要用于跳过可选步骤（如用户说「不要上线」）。"""
    paths = DomainPaths(base)
    period = steps.current_period(paths)
    if not period:
        return Result(
            status="blocked",
            summary="还没有本期（指标快照未生成），无法标记步骤。",
            domain=DOMAIN,
            next_steps=["先跑 merge。"],
        )
    step = steps.STEP_BY_KEY[args.step]
    if args.state == "skipped" and not step.optional and not args.note:
        return Result(
            status="blocked",
            summary=f"「{step.zh}」不是可选步骤，跳过必须说明原因。",
            domain=DOMAIN,
            next_steps=["带上 --note 说明为什么跳过，理由会写进 manifest。"],
        )
    steps.record(base, period, args.step, args.state, note=args.note)
    return Result(
        status="success",
        summary=f"已把「{step.zh}」标记为 {args.state}。",
        domain=DOMAIN,
        period=period,
        checks=steps.render_progress(base, period),
    )


def cmd_insights_stale(args, base) -> Result:
    paths = DomainPaths(base)
    data = insights_mod.load(paths)
    insights_mod.mark_all_stale(data)
    updated = insights_mod.snapshot_data_update(paths)
    if updated:
        data.setdefault("meta", {})["basedOnTravelJsonUpdatedAt"] = updated
    insights_mod.save(paths, data)
    dashboard.write_insights_js(paths, data)
    return Result(
        status="success",
        summary="已把全部粒度的洞察标为可能过期（不自动重写）。",
        domain=DOMAIN,
        checks=[{"name": "基于数据截至", "level": "ok", "detail": updated or "（未知）"}],
        next_steps=["要刷新洞察就走草稿流程；人确认中文后才入库。"],
    )


def cmd_feishu_plan(args, base) -> Result:
    paths = DomainPaths(base)
    if not paths.snapshot.is_file():
        return Result(
            status="blocked",
            summary=f"缺少指标快照：{paths.snapshot}",
            domain=DOMAIN,
            next_steps=["先跑一次数据更新（merge）。"],
        )
    data = json.loads(paths.snapshot.read_text(encoding="utf-8"))
    plan = feishu.build_plan(data)
    plan_path = feishu.write_plan(plan)
    conflicts = plan.get("conflicts") or []
    return Result(
        status="partial" if conflicts else "success",
        summary="飞书待写入清单已生成（dry-run，未写入）。",
        domain=DOMAIN,
        checks=[
            {"name": "新建", "level": "ok", "detail": str(len(plan.get("create") or []))},
            {"name": "填空", "level": "ok", "detail": str(len(plan.get("fill_empty") or []))},
            {"name": "冲突（飞书已有值 ≠ 快照）", "level": "warn" if conflicts else "ok", "detail": str(len(conflicts))},
            {"name": "无变化跳过", "level": "ok", "detail": str(len(plan.get("skip_unchanged") or []))},
        ],
        warnings=["存在冲突行；默认**不覆盖**，需要覆盖须另行明确。"] if conflicts else [],
        next_steps=[
            f"看一下 {plan_path}。",
            "确认后由 Agent 执行写入；**没听到你明确说「写入」不会动飞书。**",
        ],
        data={"plan": str(plan_path)},
    )


def cmd_feishu_apply(args, base) -> Result:
    plan_path = DomainPaths(base).scratch / "feishu_travel_plan.json"
    if not plan_path.is_file():
        return Result(
            status="blocked",
            summary="没有待写入清单。",
            domain=DOMAIN,
            next_steps=["先跑 feishu plan 生成 dry-run 清单。"],
        )
    if not args.yes:
        return Result(
            status="blocked",
            summary="飞书写入需要明确确认，未执行。",
            domain=DOMAIN,
            next_steps=["用户明确说「写入」后，Agent 才带 --yes 执行。"],
        )
    feishu.apply_plan(plan_path, yes=True, overwrite_conflicts=args.overwrite_conflicts)
    result = Result(
        status="success",
        summary="飞书投影已写入。",
        domain=DOMAIN,
        checks=[
            {
                "name": "冲突覆盖",
                "level": "warn" if args.overwrite_conflicts else "ok",
                "detail": "已覆盖" if args.overwrite_conflicts else "未覆盖（默认仅新建 + 填空）",
            }
        ],
    )
    note = "含冲突覆盖" if args.overwrite_conflicts else None
    return _log(base, "feishu", result, note=note, inputs={"plan": plan_path})


def cmd_publish(args, base) -> Result:
    result = publish.run(DomainPaths(base), base, yes=args.yes)
    if result.status == "success" and "无需发布" not in result.summary:
        return _log(base, "publish", result)
    return result


def cmd_status(args, base) -> Result:
    paths = DomainPaths(base)
    checks: list[dict] = []
    warnings: list[str] = []
    period = steps.current_period(paths)

    config_workbook = Config(base).workbook("industry")
    checks.append(
        {
            "name": "指标底稿",
            "level": "ok" if config_workbook and config_workbook.is_file() else "fail",
            "detail": config_workbook.name if config_workbook else "未指定",
        }
    )

    if paths.snapshot.is_file():
        meta = (json.loads(paths.snapshot.read_text(encoding="utf-8")).get("meta") or {})
        checks.append(
            {
                "name": "指标快照",
                "level": "ok",
                "detail": f"数据截至 {meta.get('dataUpdate', '?')} · 源 {meta.get('sourceExcel', '?')}",
            }
        )
    else:
        checks.append({"name": "指标快照", "level": "warn", "detail": "还没生成"})

    if paths.insights_canonical.is_file():
        data = json.loads(paths.insights_canonical.read_text(encoding="utf-8"))
        stale = [p for p in insights_mod.PERIODS if ((data.get("meta") or {}).get("stale") or {}).get(p)]
        checks.append(
            {
                "name": "洞察底稿",
                "level": "warn" if stale else "ok",
                "detail": ("可能过期：" + "、".join(stale)) if stale else "全部为最新确认",
            }
        )
        if stale:
            warnings.append("指标更新后这些粒度的洞察未重新确认：" + "、".join(stale))
    else:
        checks.append({"name": "洞察底稿", "level": "warn", "detail": "不存在"})

    for label, path in (("看板数据", paths.data_js), ("看板洞察", paths.insights_js)):
        checks.append(
            {"name": label, "level": "ok" if path.is_file() else "warn", "detail": path.name if path.is_file() else "未生成"}
        )

    info = steps.progress(base, period)
    next_steps: list[str] = []
    incomplete = False
    if period:
        incomplete = info["next"] is not None
        checks.append(
            {
                "name": f"—— 本期进度（{period}）",
                "level": "warn" if incomplete else "ok",
                "detail": f"{info['done']}/{info['total']} 步",
            }
        )
        checks.extend(steps.render_progress(base, period))
        if info["stuck"]:
            warnings.append("以下步骤卡着：" + "、".join(info["stuck"]))
        nxt = info.get("next")
        if nxt:
            following = steps.STEP_BY_KEY[nxt]
            suffix = "（可选）" if following.optional else ""
            next_steps.append(f"下一步：{following.zh}{suffix} —— {following.hint}")
        else:
            next_steps.append("本期全部步骤已完成或已跳过。")
    else:
        warnings.append("还没有本期——指标快照未生成，先跑 merge。")

    if warnings:
        status = "partial"
        summary = "industry-data：有需要处理的事项。"
    elif incomplete:
        status = "partial"
        summary = f"industry-data：本期（{period}）还有步骤没走完。"
    else:
        status = "success"
        summary = f"industry-data：本期（{period}）全部步骤已完成或已跳过。" if period else "industry-data 就绪。"

    return Result(
        status=status,
        summary=summary,
        domain=DOMAIN,
        period=period,
        checks=checks,
        warnings=warnings,
        next_steps=next_steps,
    )


def register(subparsers, common) -> None:
    """挂载本域命令。`common` 提供 --json 等共享开关，使其在子命令前后都能写。"""
    parser = subparsers.add_parser("industry", help="国内行业数据与看板")
    sub = parser.add_subparsers(dest="industry_command", required=True)

    def add(name: str, **kwargs):
        return sub.add_parser(name, parents=[common], **kwargs)

    p_merge = add("merge", help="按底稿全量重建指标快照（含 diff 门禁）")
    p_merge.add_argument(
        "--confirm-clears",
        action="store_true",
        help="确认清空：底稿里为空的格允许写成空（ADR 0001）",
    )
    p_merge.set_defaults(func=cmd_merge)

    p_dash = add("generate-dashboard", help="生成看板投影 data.js / insights.js")
    p_dash.set_defaults(func=cmd_generate_dashboard)

    p_publish = add("publish", help="上线 datamax.fun（对外发布，须明确确认）")
    p_publish.add_argument("--yes", action="store_true", help="确认发布：提交并推送")
    p_publish.set_defaults(func=cmd_publish)

    p_status = add("status", help="本域状态与本期进度")
    p_status.set_defaults(func=cmd_status)

    p_mark = add("mark", help="手动标记步骤（主要用于跳过可选步骤）")
    p_mark.add_argument("step", choices=steps.STEP_ORDER)
    p_mark.add_argument(
        "state",
        choices=["pending", "running", "done", "skipped", "blocked", "failed"],
    )
    p_mark.add_argument("--note", help="原因；跳过非可选步骤时必填")
    p_mark.set_defaults(func=cmd_mark)

    p_feishu = sub.add_parser("feishu", help="飞书多维表投影（默认仅新建 + 填空）")
    feishu_sub = p_feishu.add_subparsers(dest="feishu_command", required=True)
    p_plan = feishu_sub.add_parser("plan", help="出待写入清单与冲突清单（dry-run）", parents=[common])
    p_plan.set_defaults(func=cmd_feishu_plan)
    p_apply = feishu_sub.add_parser("apply", help="写入（须明确确认）", parents=[common])
    p_apply.add_argument("--yes", action="store_true", help="确认写入")
    p_apply.add_argument(
        "--overwrite-conflicts",
        action="store_true",
        help="连飞书已有的不同值也按快照覆盖（默认不覆盖）",
    )
    p_apply.set_defaults(func=cmd_feishu_apply)

    p_insights = sub.add_parser("insights", help="洞察草稿与入库")
    insights_sub = p_insights.add_subparsers(dest="insights_command", required=True)

    p_draft = insights_sub.add_parser("draft", help="出草稿包给 AI 填", parents=[common])
    p_draft.add_argument("--period", choices=list(insights_mod.PERIODS))
    p_draft.set_defaults(func=cmd_insights_draft)

    p_confirm = insights_sub.add_parser("confirm", help="人确认中文后入库", parents=[common])
    p_confirm.add_argument("draft", help="草稿包 JSON 路径")
    p_confirm.set_defaults(func=cmd_insights_confirm)

    p_stale = insights_sub.add_parser("mark-stale", help="标记全部粒度洞察可能过期", parents=[common])
    p_stale.set_defaults(func=cmd_insights_stale)
