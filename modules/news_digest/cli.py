"""news-digest 的命令。挂在 `ir news ...` 下。

交付物落在 `outputs/news-digest/<期次键>/旅行行业新闻精选-<中文标签>.md`：
**目录名用 ASCII 键，文件名用中文标签**。目录会被当参数传、被 glob，中文在那两处不安全
（ADR 0007）；文件名是交付给人的，中文才对。
"""

from __future__ import annotations

import json
from pathlib import Path

from workbench.fileio import write_text
from workbench.result import Result

from . import calendar_, digest, ledger, recall, steps
from .steps import DOMAIN


def _resolve_period(args) -> str:
    return args.period or calendar_.current_key()


def deliverable(base, period: str) -> Path:
    return base.outputs(DOMAIN, period) / digest.deliverable_name(period)


# --- 计划 ---


def cmd_plan(args, base) -> Result:
    period = _resolve_period(args)
    try:
        info = calendar_.plan(period)
    except calendar_.PeriodError as error:
        return Result(status="blocked", summary=str(error), domain=DOMAIN)
    target = deliverable(base, period)
    return Result(
        status="success",
        summary=f"{info['label']}：情报主周 {info['intelligence_week']['label']}，"
        f"建议 {info['publish']['date']}（周二）发。",
        domain=DOMAIN,
        period=period,
        checks=[
            {"name": "情报主周", "level": "ok", "detail": info["intelligence_week"]["label"]},
            {"name": "召回窗口", "level": "ok",
             "detail": f"{info['recall_window']['since']} 至 {info['recall_window']['until']}"},
            {"name": "交付文件", "level": "ok" if target.is_file() else "warn",
             "detail": str(target) + ("" if target.is_file() else "（还没写）")},
        ],
        data=info,
    )


# --- 召回 ---


def cmd_recall(args, base) -> Result:
    period = _resolve_period(args)
    try:
        monday, sunday = calendar_.intelligence_week(period)
    except calendar_.PeriodError as error:
        return Result(status="blocked", summary=str(error), domain=DOMAIN)

    rows, problems = recall.gather(
        since=args.since or monday.isoformat(),
        sources=args.source or None,
        scoped_only=args.scoped_only,
    )
    scoped = sum(1 for r in rows if r["in_scope"])
    target = base.scratch / f"news-recall-{period}.json"
    write_text(target, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")

    checks = [
        {"name": "枚举", "level": "ok" if rows else "fail",
         "detail": f"{len(rows)} 条，其中类目相关 {scoped} 条"},
    ]
    for source, (label, _url) in recall.FEEDS.items():
        got = sum(1 for r in rows if r["source"] == label)
        broken = any(label in p for p in problems)
        checks.append(
            {"name": label, "level": "fail" if broken else "ok",
             "detail": "抓取失败" if broken else f"{got} 条"}
        )
    checks.extend(
        {"name": f"补充检索 {index}", "level": "ok",
         "detail": f"[{q['engine']}] {q['label']}：{q['query']}"
         + (f"　⚠️ {q['note']}" if q.get("note") else "")}
        for index, q in enumerate(recall.SUPPLEMENT_QUERIES, 1)
    )

    # 召回**在候选产出时就算完成**：登记台账是定稿之后的独立一步。
    # 早先把两件事并在这一步，`recall` 就要等定稿才能完成，写稿那几天会被报成「卡住」。
    steps.record(base, period, "recall", "done" if rows else "failed",
                 note=f"枚举 {len(rows)} 条", outputs={"candidates": target})

    return Result(
        status="partial" if rows else "failed",
        summary=f"{calendar_.label_from_key(period)}：枚举到 {len(rows)} 条候选"
        f"（类目相关 {scoped} 条）。",
        domain=DOMAIN,
        period=period,
        checks=checks,
        warnings=problems + [
            "枚举只是候选主干。上面那 5 条补充检索**要我用 exa / tavily 各跑一遍**"
            "再与枚举对账——单靠检索会被当周最大声量话题挤占，实测稳定漏报。"
        ],
        next_steps=[
            f"候选清单在 {target}。",
            "选稿前先查重：`ir news check`（跨期去重台账）。",
        ],
        data={"candidates": str(target), "count": len(rows), "in_scope": scoped},
    )


# --- 去重台账 ---


def _read_items(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        data = data.get("items") or data.get("entries") or []
    if not isinstance(data, list):
        raise ledger.LedgerError("条目文件顶层必须是数组")
    return data


def cmd_check(args, base) -> Result:
    items = _read_items(args.file)
    results = ledger.check(base, items, weeks=args.weeks, sim=args.sim)
    dupes = [r for r in results if r["duplicate"]]
    checks = []
    for row in dupes:
        checks.append({"name": "疑似重复", "level": "warn", "detail": row["title"]})
        for match in row["matches"][:3]:
            checks.append(
                {"name": "　└", "level": "warn",
                 "detail": f"{match['reason']} | {match['period']} · {match['title']}"}
            )
    return Result(
        status="partial" if dupes else "success",
        summary=f"查了 {len(results)} 条，{len(dupes)} 条与最近 {args.weeks} 期疑似重复。",
        domain=DOMAIN,
        checks=checks or [{"name": "查重", "level": "ok", "detail": "没有疑似重复"}],
        next_steps=(
            ["台账只给候选，不下判断。逐条看：纯重复就剔掉；实质跟进可以收，"
             "写成「延续上期：…」并在登记时说明理由。"]
            if dupes else []
        ),
        data={"results": results},
    )


def cmd_log(args, base) -> Result:
    period = _resolve_period(args)
    items = _read_items(args.file)
    try:
        outcome = ledger.add(
            base, period, items, weeks=args.weeks, sim=args.sim,
            force=args.force, reason=args.reason, commit=args.commit,
        )
    except ledger.LedgerError as error:
        return Result(status="blocked", summary=str(error), domain=DOMAIN, period=period)

    if outcome.blocked:
        checks = []
        for item, hits in outcome.blocked:
            checks.append({"name": "拒绝登记", "level": "fail", "detail": item.get("title", "")})
            for hit in hits[:3]:
                checks.append({"name": "　└", "level": "fail",
                               "detail": f"{hit.reason} | {hit.period} · {hit.title}"})
        return Result(
            status="blocked",
            summary=f"{len(outcome.blocked)} 条与最近 {args.weeks} 期疑似重复，已拒绝写入。",
            domain=DOMAIN,
            period=period,
            checks=checks,
            next_steps=[
                "纯重复的剔掉。",
                "确实是实质跟进就加 --force 并给 --reason 说明；理由会随条目写进台账，"
                "以后能查为什么当时收了。",
            ],
        )

    warnings = [f"URL 为空，该条的 URL 层去重会失效：{t}" for t in outcome.no_url]
    if not args.commit:
        return Result(
            status="partial",
            summary=f"预演：{len(outcome.written)} 条可登记，**未写入**。",
            domain=DOMAIN,
            period=period,
            warnings=warnings,
            next_steps=["确认后加 --commit 写台账。"],
        )
    steps.record(base, period, "log", "done", note=f"台账登记 {len(outcome.written)} 条",
                 outputs={"ledger": ledger.ledger_path(base)})
    return Result(
        status="success",
        summary=f"已登记 {len(outcome.written)} 条到去重台账。",
        domain=DOMAIN,
        period=period,
        warnings=warnings,
        data={"written": len(outcome.written)},
    )


# --- 校验与导出 ---


def cmd_validate(args, base) -> Result:
    period = _resolve_period(args)
    path = Path(args.file) if args.file else deliverable(base, period)
    if not path.is_file():
        return Result(
            status="blocked",
            summary="找不到交付物。",
            domain=DOMAIN,
            period=period,
            missing=[str(path)],
            next_steps=[f"稿子写好放到 {path}（目录用期次键，文件名用中文标签）。"],
        )

    # 能拿到一份可校验的稿子，就说明写稿那一步已经做完了。
    # 不这样标的话「写稿（人写）」会永远停在待办——没有命令能标记它完成。
    steps.record(base, period, "draft", "done", inputs={"digest": path})

    result = digest.review_file(path, expect_period=period if not args.file else None)
    checks = [
        {"name": "条目", "level": "ok", "detail": f"{len(result.items)} 条"},
        {"name": "来源表", "level": "ok", "detail": f"{result.source_rows} 行"},
    ]
    checks.extend(
        {"name": f.code, "level": {"error": "fail", "warn": "warn"}.get(f.level, "ok"),
         "detail": f.message}
        for f in result.findings
    )
    state = "success" if result.ok and not result.warnings else ("blocked" if not result.ok else "partial")
    steps.record(base, period, "validate", "done" if result.ok else "blocked",
                 note=f"{len(result.errors)} 处硬错误", inputs={"digest": path})
    return Result(
        status=state,
        summary=(f"结构校验通过（{len(result.items)} 条）。" if result.ok
                 else f"有 {len(result.errors)} 处必须改。"),
        domain=DOMAIN,
        period=period,
        checks=checks,
        next_steps=(
            ["改完再跑一次。硬错误没清掉不要导出，也不要沉淀——"
             "条目与来源表配不上会让情报库给新闻挂错来源。"]
            if not result.ok else
            [f"导出：`ir news export --period {period}`",
             "沉淀进情报库：`ir intel deposit --dir outputs/news-digest`"]
        ),
        data={"findings": [f.__dict__ for f in result.findings]},
    )


def cmd_export(args, base) -> Result:
    period = _resolve_period(args)
    path = Path(args.file) if args.file else deliverable(base, period)
    if not path.is_file():
        return Result(status="blocked", summary="找不到交付物。", domain=DOMAIN,
                      period=period, missing=[str(path)])

    review = digest.review_file(path)
    if not review.ok:
        return Result(
            status="blocked",
            summary=f"结构还有 {len(review.errors)} 处硬错误，先别导出。",
            domain=DOMAIN,
            period=period,
            checks=[{"name": f.code, "level": "fail", "detail": f.message} for f in review.errors],
            next_steps=[f"先跑 `ir news validate --period {period}` 看清单。"],
        )

    from . import export as exporter

    html = exporter.export_html(path)
    outputs = {"html": html}
    warnings: list[str] = []
    if args.pdf:
        try:
            outputs["pdf"] = exporter.export_pdf(html)
        except Exception as error:  # noqa: BLE001 —— PDF 失败不该毁掉已产出的 HTML
            warnings.append(
                f"PDF 导出失败（{type(error).__name__}: {error}）。HTML 已生成。"
                "多数情况是没跑过 `playwright install chromium`——装包不等于装浏览器。"
            )

    steps.record(base, period, "export", "done" if "pdf" in outputs or not args.pdf else "running",
                 outputs={k: v for k, v in outputs.items()})
    return Result(
        status="partial" if warnings else "success",
        summary=f"已导出 {'HTML + PDF' if 'pdf' in outputs else 'HTML'}。",
        domain=DOMAIN,
        period=period,
        checks=[{"name": k.upper(), "level": "ok", "detail": str(v)} for k, v in outputs.items()],
        warnings=warnings,
        data={k: str(v) for k, v in outputs.items()},
    )


def cmd_skip(args, base) -> Result:
    """记下某一期**故意不出**，把剩余步骤标为跳过。

    为什么要有这个：不记的话那一期会永远挂在「等你说话 · 写稿」上。跨域汇总的意义
    正是把停住的动作摆出来，所以它里面绝不能有假的——一条假的会让人开始忽略整栏。

    另一种做法是删掉 `runs/news-digest/<期次>/`，但那会连「我们当时决定不出」这个
    事实一起删掉。半年后看 outputs 里缺一期，没人知道是漏了还是有意的。

    必须给理由，且理由写进 manifest。"""
    period = _resolve_period(args)
    if not (args.reason or "").strip():
        return Result(
            status="blocked",
            summary="跳过一期必须说明理由。",
            domain=DOMAIN,
            period=period,
            next_steps=["加 --reason，理由会写进 manifest，以后能查为什么这期没出。"],
        )
    info = steps.progress(base, period)
    states = info.get("states") or {}
    remaining = [
        key for key in steps.STEP_ORDER
        if states.get(key, "pending") not in {"done", "skipped"}
    ]
    if not remaining:
        return Result(status="success", summary=f"{calendar_.label_from_key(period)} 没有待跳过的步骤。",
                      domain=DOMAIN, period=period)
    if not args.commit:
        return Result(
            status="partial",
            summary=f"会把 {len(remaining)} 步标为跳过，**未写入**。",
            domain=DOMAIN,
            period=period,
            checks=[{"name": steps.STEP_BY_KEY[k].zh, "level": "ok", "detail": "→ 跳过"}
                    for k in remaining],
            next_steps=["确认后加 --commit。"],
        )
    for key in remaining:
        steps.record(base, period, key, "skipped", note=f"本期不出：{args.reason.strip()}")
    return Result(
        status="success",
        summary=f"{calendar_.label_from_key(period)} 已记为本期不出。",
        domain=DOMAIN,
        period=period,
        checks=[{"name": "理由", "level": "ok", "detail": args.reason.strip()},
                {"name": "标为跳过", "level": "ok", "detail": "、".join(remaining)}],
    )


def cmd_status(args, base) -> Result:
    period = args.period
    if not period:
        root = base.runs(DOMAIN)
        periods = sorted((p.name for p in root.iterdir() if p.is_dir()), reverse=True) if root.is_dir() else []
        period = periods[0] if periods else calendar_.current_key()
    info = steps.progress(base, period)
    nxt = steps.STEP_BY_KEY.get(info["next"]) if info["next"] else None
    return Result(
        status="partial" if info["next"] else "success",
        summary=f"news-digest：{calendar_.label_from_key(period)} "
        f"{info['done']}/{info['total']} 步。",
        domain=DOMAIN,
        period=period,
        checks=steps.render_progress(base, period),
        next_steps=[f"下一步：{nxt.zh} —— {nxt.hint}"] if nxt else ["本期全部步骤已完成。"],
    )


def register(subparsers, common) -> None:
    parser = subparsers.add_parser("news", help="旅行行业新闻精选（对外交付物）")
    sub = parser.add_subparsers(dest="news_command", required=True)

    p = sub.add_parser("plan", help="本期日历、召回窗口、交付文件名", parents=[common])
    p.add_argument("--period", help="期次键，如 2026-08-W2；不给取本周")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("recall", help="RSS 枚举候选 + 打印补充检索清单", parents=[common])
    p.add_argument("--period")
    p.add_argument("--since", help="覆盖起始日 YYYY-MM-DD")
    p.add_argument("--source", nargs="*", choices=sorted(recall.FEEDS), help="只抓这些源")
    p.add_argument("--scoped-only", action="store_true", help="只留类目相关条目")
    p.set_defaults(func=cmd_recall)

    p = sub.add_parser("check", help="选稿前跨期查重", parents=[common])
    p.add_argument("--file", required=True, help="候选 JSON")
    p.add_argument("--weeks", type=int, default=ledger.DEFAULT_WEEKS)
    p.add_argument("--sim", type=float, default=ledger.DEFAULT_SIM)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("log", help="定稿后登记进去重台账", parents=[common])
    p.add_argument("--period")
    p.add_argument("--file", required=True, help="已收录条目 JSON")
    p.add_argument("--weeks", type=int, default=ledger.DEFAULT_WEEKS)
    p.add_argument("--sim", type=float, default=ledger.DEFAULT_SIM)
    p.add_argument("--commit", action="store_true", help="实际写入（默认预演）")
    p.add_argument("--force", action="store_true", help="疑似重复仍收录（须配 --reason）")
    p.add_argument("--reason", default="", help="force 收录的理由，随条目入台账")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("validate", help="校验交付物结构", parents=[common])
    p.add_argument("--period")
    p.add_argument("--file", help="直接指定 .md 路径")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("export", help="导出 HTML（--pdf 另出 PDF）", parents=[common])
    p.add_argument("--period")
    p.add_argument("--file")
    p.add_argument("--pdf", action="store_true")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("skip", help="记下某一期故意不出（须给理由）", parents=[common])
    p.add_argument("--period")
    p.add_argument("--reason", default="", help="为什么这期不出，写进 manifest")
    p.add_argument("--commit", action="store_true")
    p.set_defaults(func=cmd_skip)

    p = sub.add_parser("status", help="本域状态", parents=[common])
    p.add_argument("--period")
    p.set_defaults(func=cmd_status)
