"""Public ``ir peers ...`` parser surface."""

from __future__ import annotations

from workbench import manifest as manifest_mod
from workbench.result import Result

from . import pipeline, steps


def cmd_init(args, base) -> Result:
    return pipeline.initialize(base, args.ticker, args.period)


def cmd_resolve(args, base) -> Result:
    return pipeline.resolved_view(base, args.ticker, args.period)


def cmd_model(args, base) -> Result:
    return pipeline.run_model(base, args.ticker, args.period)


def cmd_writing(args, base) -> Result:
    return pipeline.run_writing(base, args.ticker, args.period)


def cmd_gate(args, base) -> Result:
    return pipeline.run_gates(
        base,
        args.ticker,
        args.period,
        phase=args.phase,
        step=args.step,
    )


def cmd_status(args, base) -> Result:
    period = args.period
    if period is None:
        latest = manifest_mod.latest(base, steps.DOMAIN)
        if latest is None:
            return Result(
                status="partial",
                summary="peers-appendix 尚未初始化任何季度。",
                domain=steps.DOMAIN,
                next_steps=["用 `ir peers init --ticker EXPE --period 26Q2` 建立一期视图。"],
            )
        period = latest.period

    manifest = manifest_mod.Manifest(base, steps.DOMAIN, period)
    if not manifest.exists:
        return Result(
            status="partial",
            summary=f"peers-appendix {period} 尚未初始化。",
            domain=steps.DOMAIN,
            period=period,
        )
    data = manifest.load()
    companies = sorted((data.get("companies") or {}).keys())
    if args.ticker:
        ticker = args.ticker.upper()
        if ticker not in companies:
            return Result(
                status="partial",
                summary=f"{ticker} {period} 尚未初始化。",
                domain=steps.DOMAIN,
                period=period,
                next_steps=[f"先初始化 {ticker} {period}。"],
            )
        info = steps.progress(base, ticker, period)
        return Result(
            status=(
                "success"
                if info["done"] == info["total"] and not info["stuck"]
                else "partial"
            ),
            summary=f"{ticker} {period}：{info['done']}/{info['total']} 步完成。",
            domain=steps.DOMAIN,
            period=period,
            checks=steps.render_progress(base, ticker, period),
            warnings=(
                ["卡住：" + "、".join(info["stuck"])]
                if info["stuck"]
                else []
            ),
            data=info,
        )

    checks = []
    complete = True
    for ticker in companies:
        info = steps.progress(base, ticker, period)
        company_done = info["done"] == info["total"] and not info["stuck"]
        complete = complete and company_done
        checks.append(
            {
                "name": ticker,
                "level": "ok" if company_done else (
                    "fail" if info["stuck"] else "warn"
                ),
                "detail": f"{info['done']}/{info['total']} 步"
                + (
                    f" · 卡住 {','.join(info['stuck'])}"
                    if info["stuck"]
                    else ""
                ),
            }
        )
    return Result(
        status="success" if complete and companies else "partial",
        summary=f"peers-appendix {period}：{len(companies)} 家公司。",
        domain=steps.DOMAIN,
        period=period,
        checks=checks,
        data={"companies": companies},
    )


def _add_company_period(parser, *, period_required: bool = True) -> None:
    parser.add_argument("--ticker", required=True, help="公司 ticker，如 EXPE / ABNB / BKNG")
    parser.add_argument(
        "--period",
        required=period_required,
        help="财季键 YYQn，如 26Q2",
    )


def register(subparsers, common) -> None:
    parser = subparsers.add_parser(
        "peers",
        help="Peers 当季材料 → Model → 写作与 Appendix",
    )
    sub = parser.add_subparsers(dest="peers_command", required=True)

    init = sub.add_parser(
        "init",
        help="初始化公司×财季材料/产出/运行视图",
        parents=[common],
    )
    _add_company_period(init)
    init.set_defaults(func=cmd_init)

    resolve = sub.add_parser(
        "resolve",
        help="只读解析公司×财季的全部约定路径",
        parents=[common],
    )
    _add_company_period(resolve)
    resolve.set_defaults(func=cmd_resolve)

    model = sub.add_parser(
        "model",
        help="insert → 人工 fill → audit → charts → gate → ticker 导出",
        parents=[common],
    )
    _add_company_period(model)
    model.set_defaults(func=cmd_model)

    writing_cmd = sub.add_parser(
        "writing",
        help="brief → 人工 strategy/texts → gate → ticker apply/embed → accept",
        parents=[common],
    )
    _add_company_period(writing_cmd)
    writing_cmd.set_defaults(func=cmd_writing)

    gate = sub.add_parser(
        "gate",
        help="只复查 must-pass gates，不执行写入步骤",
        parents=[common],
    )
    _add_company_period(gate)
    gate.add_argument(
        "--phase",
        choices=("model", "writing", "all"),
        default="all",
    )
    gate.add_argument(
        "--step",
        choices=tuple(sorted(steps.GATE_STEPS)),
        help="只检查一道 must-pass gate",
    )
    gate.set_defaults(func=cmd_gate)

    status = sub.add_parser(
        "status",
        help="查看季度或单家公司的持久状态",
        parents=[common],
    )
    status.add_argument("--ticker")
    status.add_argument("--period", help="默认取最近一期")
    status.set_defaults(func=cmd_status)
