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
    str_plan,
    str_write,
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
    state = steps.step_state(result.status, result.data)
    steps.record(base, period, step, state, note=note, result_data=result.data or None, **paths_kw)
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
    paths = DomainPaths(base)
    result = snapshot.rebuild(paths, workbook, confirm_clears=args.confirm_clears)

    changed_periods = list(result.data.get("changedPeriods") or [])
    if result.status == "success" and changed_periods:
        # 只把**实际变动**的粒度标旧。显式传 diff 结果很重要：同一个 dataUpdate 下换修订版
        # 底稿时日期没有变化，仅靠日期会漏掉；只新增周度时又不该把月/季一起打旧。
        try:
            newly_stale = insights_mod.mark_stale_if_outdated(paths, changed_periods)
        except insights_mod.InsightsError:
            newly_stale = []  # 洞察底稿不存在不该拖垮 merge
        if newly_stale:
            result.warnings.append("实际变动粒度的洞察已标旧：" + "、".join(newly_stale))
            result.checks.append(
                {"name": "洞察", "level": "warn", "detail": "已标旧：" + "、".join(newly_stale)}
            )

        # 更新数据后**自动**把对应粒度的草稿包备好。Agent 接下来直接填中文并展示给人，
        # 不再多问一句「要不要刷新洞察」。人只在看完中文后决定「写入并上线」。
        draft_result = drafts.prepare(paths, periods=changed_periods)
        draft_path = draft_result.data.get("draft")
        if draft_path:
            result.data["insightsDraft"] = draft_path
            result.checks.append(
                {
                    "name": "洞察草稿",
                    "level": "ok",
                    "detail": f"已按实际变动生成（{'、'.join(changed_periods)}）",
                }
            )

    logged = _log(base, "merge", result, inputs={"workbook": workbook})

    if logged.status == "success" and changed_periods and logged.period:
        # 同一个数据截至日下换修订版时，manifest 可能还保留着上一轮的 done；必须重置下游。
        manifest = steps.open_manifest(base, logged.period)
        reason = "指标有新变化：" + "、".join(changed_periods)
        for step in ("dashboard", "insights", "publish"):
            manifest.set_step(step, "pending", reason)
        # 飞书多维表已半弃用：默认不做、不再每期追问；用户哪天明确要同步再单独打开。
        manifest.set_step("feishu", "skipped", "飞书多维表暂不使用；需要时再单独同步")

        logged.next_steps = [
            "生成本地看板投影（不发布）。",
            f"按草稿包只写实际变动的 {'、'.join(changed_periods)} 洞察，并直接展示中文给用户审查。",
            "不要问『要不要刷新洞察』；用户看完后只问一次：是否写入洞察并上线。",
        ]
    elif logged.status == "success" and not changed_periods:
        logged.checks.append({"name": "洞察草稿", "level": "ok", "detail": "指标无变化，无需刷新"})

    return logged


def cmd_generate_dashboard(args, base) -> Result:
    paths = DomainPaths(base)
    result = dashboard.generate(paths)
    outputs = {"data_js": paths.data_js}
    if paths.insights_js.is_file():
        outputs["insights_js"] = paths.insights_js
    return _log(base, "dashboard", result, outputs=outputs)


def cmd_insights_draft(args, base) -> Result:
    # 默认只出最近一次 merge 实际变动的粒度；显式 --all 才全量。
    # 出草稿不算完成——洞察这一步的完成判据是「人确认后入库」。
    paths = DomainPaths(base)
    if args.period:
        return drafts.prepare(paths, args.period)
    if args.all:
        return drafts.prepare(paths)

    period = steps.current_period(paths)
    selected = steps.changed_periods(base, period)
    if not selected:
        return Result(
            status="success",
            summary="最近一次 merge 没有指标变化，不需要刷新洞察。",
            domain=DOMAIN,
            period=period,
            next_steps=["若确实要全量重写，显式使用 insights draft --all。"],
            data={"periods": []},
        )
    return drafts.prepare(paths, periods=selected)


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


def cmd_str_plan(args, base) -> Result:
    """只读：中金表 → 酒店周度与月度 → 与底稿对照。不写任何文件。"""
    workbook, blocked = _resolve_workbook(base)
    if blocked:
        return blocked
    source = Path(args.source)
    if not source.is_file():
        return Result(
            status="blocked",
            summary=f"找不到中金表：{source}",
            domain=DOMAIN,
            next_steps=["把中金旅游周度数据表放进 inputs/industry-data/<数据截至日>/ 再指定路径。"],
        )
    result = str_plan.run(workbook, source, args.year)

    # 原件不进 git（体积大、第三方材料），所以来源信息必须落在 manifest 里，
    # 否则「这个月的数是从哪份表算的」将无从回溯。
    # 只登记输入，**不动步骤状态**——str-plan 是只读的，不代表哪一步做完了。
    period = steps.current_period(DomainPaths(base))
    if period:
        steps.open_manifest(base, period).record_input("str_source", source)
        result.period = period
    return result


def cmd_str_apply(args, base) -> Result:
    """把中金表算出的酒店数据填进底稿空格。默认 dry-run，`--yes` 才写。"""
    workbook, blocked = _resolve_workbook(base)
    if blocked:
        return blocked
    source = Path(args.source)
    if not source.is_file():
        return Result(
            status="blocked",
            summary=f"找不到中金表：{source}",
            domain=DOMAIN,
            next_steps=["把中金表放进 inputs/industry-data/<数据截至日>/ 再指定路径。"],
        )

    paths = DomainPaths(base)
    result = str_write.run(paths, workbook, source, args.year, yes=args.yes)

    # 原件不进 git，来源与哈希必须落在 manifest 里才能回溯
    period = steps.current_period(paths)
    if period:
        manifest = steps.open_manifest(base, period)
        manifest.record_input("str_source", source)
        if result.status == "success" and result.data.get("written"):
            manifest.record_input("workbook", workbook)
        result.period = period
    return result


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

    p_str = add("str-plan", help="从中金周报算酒店周度与月度，对照底稿出清单（只读）")
    p_str.add_argument("source", help="中金旅游周度数据表路径")
    p_str.add_argument("--year", type=int, default=2026, help="底稿年度块，默认 2026")
    p_str.set_defaults(func=cmd_str_plan)

    p_str_apply = add("str-apply", help="把中金表算出的酒店数据填进底稿空格（须明确确认）")
    p_str_apply.add_argument("source", help="中金旅游周度数据表路径")
    p_str_apply.add_argument("--year", type=int, default=2026)
    p_str_apply.add_argument("--yes", action="store_true", help="确认写入底稿")
    p_str_apply.set_defaults(func=cmd_str_apply)

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

    p_draft = insights_sub.add_parser(
        "draft",
        help="按最近一次 merge 的实际变动粒度出草稿（默认）；可显式单粒度或全量",
        parents=[common],
    )
    draft_scope = p_draft.add_mutually_exclusive_group()
    draft_scope.add_argument("--period", choices=list(insights_mod.PERIODS), help="只出指定粒度")
    draft_scope.add_argument("--all", action="store_true", help="忽略 diff，周/月/季全量出草稿")
    p_draft.set_defaults(func=cmd_insights_draft)

    p_confirm = insights_sub.add_parser("confirm", help="人确认中文后入库", parents=[common])
    p_confirm.add_argument("draft", help="草稿包 JSON 路径")
    p_confirm.set_defaults(func=cmd_insights_confirm)

    p_stale = insights_sub.add_parser("mark-stale", help="标记全部粒度洞察可能过期", parents=[common])
    p_stale.set_defaults(func=cmd_insights_stale)
