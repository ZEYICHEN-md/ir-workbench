"""aviation-monthly 的命令。挂在 `ir aviation ...` 下。

与迁移前最大的差别：**工作簿不再由调用方传路径**，一律从 `ir config` 锁定的那两份解析。
迁移前正是因为路径靠手传，这条管道一直在写 `0703_Travel_Pulse/data_source/` 里那份
停在 0803 的旧表——而实际维护的是另一份。
"""

from __future__ import annotations

from pathlib import Path

from workbench.config import Config
from workbench.result import Result

from . import pipeline, steps
from .steps import DOMAIN


def _resolve_workbooks(base) -> tuple[Path | None, Path | None, Result | None]:
    config = Config(base)
    industry = config.workbook("industry")
    airline = config.workbook("airline")
    missing = []
    if not industry or not industry.is_file():
        missing.append("industry（指标底稿 国内行业数据）")
    if not airline or not airline.is_file():
        missing.append("airline（Airline Data 月度底表）")
    if missing:
        return None, None, Result(
            status="blocked",
            summary="工作簿未指定或已失效。",
            domain=DOMAIN,
            missing=missing,
            next_steps=[
                "把工作簿放进 data/workbooks/，让 Agent 跑 `ir config candidates` 列出候选。",
                "**由你**指定用哪一份，系统不按文件名猜（ADR 0001）。",
            ],
        )
    return airline, industry, None


def _summarise_checks(checks: list[dict]) -> list[dict]:
    """把 pipeline 的 checks 折叠成人能扫读的几行，失败项逐条列出。"""
    failed = [c for c in checks if not c.get("ok", True)]
    rows: list[dict] = [
        {
            "name": "校验项",
            "level": "fail" if failed else "ok",
            "detail": f"{len(checks) - len(failed)}/{len(checks)} 通过",
        }
    ]
    for item in failed[:10]:
        rows.append(
            {
                "name": item.get("name", "?"),
                "level": "fail",
                "detail": f"{item.get('detail', '')}（{item.get('kind', '')}）",
            }
        )
    return rows


def cmd_run(args, base) -> Result:
    airline, industry, blocked = _resolve_workbooks(base)
    if blocked:
        return blocked

    period = steps.period_key(args.year, args.month)
    request = pipeline.Request(
        year=args.year,
        month=args.month,
        airline_input=str(airline),
        industry_input=str(industry),
        commit=args.commit,
        # 就地更新那两份被锁定的工作簿：全工作台只有一份底稿（ADR 0001），
        # 派生出带日期的新文件会让人手填与自动化写到不同的表上。
        overwrite=True,
        airline_output=str(airline),
        industry_output=str(industry),
        manifest_output=str(base.runs(DOMAIN, period) / "pipeline.json"),
    )

    checks: list[dict] = []
    try:
        outcome = pipeline.run(request, checks)
    except pipeline.PipelineError as error:
        steps.record(base, period, "commit" if args.commit else "dry-run", "blocked", note=str(error))
        return Result(
            status="blocked",
            summary=f"管道停下了（{error.kind}）：{error}",
            domain=DOMAIN,
            period=period,
            checks=_summarise_checks(checks),
            next_steps=[
                "按 `references/workbook-contract.md` 核对底表结构；契约不符时应停止，而不是猜。",
                "官方公告没出或抓不到时，等出了再跑；不要手工推算合计。",
            ],
        )
    except Exception as error:  # noqa: BLE001 —— 抓取/解析的意外必须显式返回，不能静默
        steps.record(base, period, "commit" if args.commit else "dry-run", "failed", note=str(error))
        return Result(
            status="failed",
            summary=f"管道出错：{type(error).__name__}: {error}",
            domain=DOMAIN,
            period=period,
            checks=_summarise_checks(checks),
        )

    values = outcome.get("independent_results") or {}
    rows = _summarise_checks(checks)
    rows.extend(
        {"name": key, "level": "ok", "detail": f"{value:.4%}" if isinstance(value, float) else str(value)}
        for key, value in sorted(values.items())
    )

    if not args.commit:
        steps.record(
            base,
            period,
            "dry-run",
            "done",
            inputs={"airline": airline, "industry": industry},
        )
        return Result(
            status="partial",
            summary=f"{args.year}年{args.month}月：官方数据已抓齐并校验通过，**未写入**。",
            domain=DOMAIN,
            period=period,
            checks=rows,
            next_steps=[
                "核对上面四个同比数值与官方公告一致。",
                "确认后回一句「写入」，Agent 才会带 --commit 执行。",
                "写入会**就地更新**那两份被锁定的工作簿（带备份，可回退）。",
            ],
            data={"values": values, "manifest": outcome.get("outputs", {}).get("manifest")},
        )

    steps.record(
        base,
        period,
        "commit",
        "done",
        inputs={"airline": airline, "industry": industry},
        outputs={"airline_out": airline, "industry_out": industry},
    )
    validation = outcome.get("validation") or {}
    rows.append(
        {
            "name": "写入后回读",
            "level": "ok" if validation.get("industry_roundtrip") else "fail",
            "detail": "指标底稿目标格回读一致" if validation.get("industry_roundtrip") else "回读不一致",
        }
    )
    return Result(
        status="success",
        summary=f"{args.year}年{args.month}月航空月度数据已写入。",
        domain=DOMAIN,
        period=period,
        checks=rows,
        next_steps=[
            "底稿变了，接着重建指标快照：`ir industry merge` → `generate-dashboard`。",
            "溯源见 runs/aviation-monthly/" + period + "/pipeline.json（含每个输入格的公告出处）。",
        ],
        data={"values": values},
    )


def cmd_status(args, base) -> Result:
    period = steps.period_key(args.year, args.month) if args.year and args.month else None
    if not period:
        periods = sorted(
            (p.name for p in base.runs(DOMAIN).iterdir() if p.is_dir()) if base.runs(DOMAIN).is_dir() else [],
            reverse=True,
        )
        if not periods:
            return Result(
                status="success",
                summary="aviation-monthly：还没跑过任何月份。",
                domain=DOMAIN,
                next_steps=["跑 `ir aviation run --year 2026 --month 7` 开始（默认 dry-run，不写入）。"],
            )
        period = periods[0]

    info = steps.progress(base, period)
    return Result(
        status="partial" if info["next"] else "success",
        summary=f"aviation-monthly：{period[:4]}年{int(period[4:])}月 {info['done']}/{info['total']} 步。",
        domain=DOMAIN,
        period=period,
        checks=steps.render_progress(base, period),
        warnings=["以下步骤卡着：" + "、".join(info["stuck"])] if info["stuck"] else [],
        next_steps=(
            [f"下一步：{steps.STEP_BY_KEY[info['next']].zh} —— {steps.STEP_BY_KEY[info['next']].hint}"]
            if info["next"]
            else ["本月全部步骤已完成。"]
        ),
    )


def register(subparsers, common) -> None:
    parser = subparsers.add_parser("aviation", help="航空月度数据写入指标底稿")
    sub = parser.add_subparsers(dest="aviation_command", required=True)

    p_run = sub.add_parser("run", help="抓官方数据 → 校验 → dry-run；--commit 才写入", parents=[common])
    p_run.add_argument("--year", type=int, required=True)
    p_run.add_argument("--month", type=int, choices=range(1, 13), required=True)
    p_run.add_argument("--commit", action="store_true", help="确认写入（须用户明确要求）")
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", help="本域状态", parents=[common])
    p_status.add_argument("--year", type=int)
    p_status.add_argument("--month", type=int, choices=range(1, 13))
    p_status.set_defaults(func=cmd_status)
