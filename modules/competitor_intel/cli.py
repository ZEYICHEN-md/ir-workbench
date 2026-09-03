"""competitor-intel 的命令。挂在 `ir intel ...` 下。

## 沉淀为什么是「草稿 → 确认」两段

打标里公司是规则匹配（可靠），主题是关键词猜（不可靠）。让 Agent 直接入库等于把猜的
结果写成事实。所以：

1. `ir intel deposit --from <精选.md>` —— 解析 + 打标，**只写草稿**到 `scratch/`，无副作用；
2. 人核对（可以直接改那份草稿 JSON）；
3. `ir intel deposit --commit` —— **读那份草稿**入库。

第 3 步刻意**不重新解析**原文。重新解析会把人在草稿里改过的标签冲掉，而人不会发现——
他以为自己改了。「确认的就是看过的那一份」这条性质比省一次解析重要得多。
"""

from __future__ import annotations

import json
from pathlib import Path

from workbench.fileio import write_text
from workbench.result import Result

from . import backfill, profiles, query, quarterly, steps, vocab  # noqa: F401 —— backfill 供 retag 用
from .entry import KIND_ZH, Entry, EntryError, normalize
from .steps import DOMAIN
from .store import DeferredRecord, Store

#: 新闻精选成品的文件名前缀。`--dir` 按它 glob。
DIGEST_PREFIX = "旅行行业新闻精选"


def _draft_path(base, period: str) -> Path:
    return base.scratch / f"intel-deposit-{period}.json"


def _load_draft(path: Path) -> tuple[str, list[Entry], list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = [Entry.from_dict(row) for row in data.get("entries", [])]
    return data.get("period", ""), entries, data.get("trace", [])


# --- 沉淀 ---


def cmd_deposit(args, base) -> Result:
    store = Store(base)

    if args.commit:
        return _deposit_commit(args, base, store)

    sources = [Path(p) for p in (args.source or [])]
    if args.dir:
        # 精选文件名是中文（`旅行行业新闻精选-2026年8月第2周.md`）。中文当命令行参数在
        # Windows 上会被 GBK 静默改写（ADR 0007），所以给目录、由这里自己 glob，
        # 不让中文路径穿过命令行。
        root = Path(args.dir)
        if not root.is_dir():
            return Result(
                status="blocked", summary="目录不存在。", domain=DOMAIN, missing=[str(root)]
            )
        sources.extend(sorted(root.rglob(f"{DIGEST_PREFIX}*.md")))
    missing = [str(p) for p in sources if not p.is_file()]
    if not sources or missing:
        return Result(
            status="blocked",
            summary="没有可解析的新闻精选文件。",
            domain=DOMAIN,
            missing=missing or ["--from 至少要给一份新闻精选 Markdown"],
        )

    entries, problems, trace = backfill.parse_many(sources)
    if not entries:
        return Result(
            status="blocked",
            summary="一条都没解析出来。",
            domain=DOMAIN,
            checks=[{"name": "解析", "level": "fail", "detail": p} for p in problems],
            next_steps=["核对精选文件的结构是否还符合 modules/competitor_intel/SKILL.md 里的契约。"],
        )

    period = args.period or (trace[0]["period"] if trace else "")

    # 草稿里放**归一后**的条目，让「草稿 = 将要入库的东西」严格成立。
    # 早先草稿放的是解析结果原样，后果是：一条提到携程的条目在草稿里显示
    # `sensitivity: shareable`，入库时才被规则改成 internal（ADR 0002 §9）。
    # 核对的人看到 shareable 不会知道它会变——那就等于给了他一份假的待确认清单。
    # 归一失败的条目**原样留在草稿里**，不能丢：丢了人就没机会补齐它。
    prepared: list[Entry] = []
    for item in entries:
        try:
            fixed, _unregistered = normalize(Entry.from_dict(item.to_dict()), registry=store.registry())
            prepared.append(fixed)
        except Exception:  # noqa: BLE001 —— 具体原因由下面的 store.add 统一报
            prepared.append(item)

    outcome = store.add([Entry.from_dict(e.to_dict()) for e in prepared], commit=False)

    draft = _draft_path(base, period or "unknown")
    write_text(
        draft,
        json.dumps(
            {
                "period": period,
                "sources": [str(p) for p in sources],
                "entries": [e.to_dict() for e in prepared],
                "trace": trace,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )

    rows = [
        {"name": "解析", "level": "ok", "detail": f"{len(entries)} 条，来自 {len(sources)} 份精选"},
        {
            "name": "入库预演",
            "level": "warn" if outcome.rejected else "ok",
            "detail": f"可入 {len(outcome.added)} · 已存在 {len(outcome.skipped)} · 待处理 {len(outcome.rejected)}",
        },
    ]
    rows.extend(_tagging_rows(trace))
    for index, reason in outcome.rejected[:10]:
        rows.append({"name": f"第 {index} 条", "level": "fail", "detail": reason.split("\n")[0]})
    if outcome.new_companies:
        rows.append(
            {
                "name": "将登记进其他桶",
                "level": "ok",
                "detail": "、".join(sorted(outcome.new_companies)),
            }
        )

    if period:
        steps.record(base, period, "deposit", "running", note=f"草稿 {len(entries)} 条待确认")

    return Result(
        status="partial",
        summary=f"解析出 {len(entries)} 条，草稿已生成，**未入库**。",
        domain=DOMAIN,
        period=period or None,
        checks=rows,
        warnings=problems,
        next_steps=[
            f"核对草稿：{draft}",
            "公司标签是规则匹配（标题里出现＝主角，只在正文出现＝提及），实测可信。",
            "**主题的关键词结果只是起点，Agent 要读完条目在草稿里定稿**，"
            "顺手补上自由标签（tags，不限词表）；人只需扫一眼有没有明显不对。",
            "确认后回一句「沉淀这期新闻」才入库。入库读的就是这份草稿，"
            "不会重新解析——改过的标签不会被冲掉。",
        ],
        data={"draft": str(draft), "period": period, "counts": outcome.counts},
    )


def _deposit_commit(args, base, store: Store) -> Result:
    period = args.period
    if not period:
        drafts = sorted(base.scratch.glob("intel-deposit-*.json"))
        if len(drafts) != 1:
            return Result(
                status="blocked",
                summary="不确定要入库哪一份草稿。",
                domain=DOMAIN,
                missing=[f"scratch 里有 {len(drafts)} 份草稿"],
                next_steps=["用 --period 指定期次，例如 --period 2026-08-W2。"],
            )
        draft = drafts[0]
    else:
        draft = _draft_path(base, period)

    if not draft.is_file():
        return Result(
            status="blocked",
            summary="找不到待入库的草稿。",
            domain=DOMAIN,
            missing=[str(draft)],
            next_steps=[
                "先跑一次不带 --commit 的 deposit 生成草稿并让人核对。"
                "入库只接受核对过的草稿，不接受现场解析。"
            ],
        )

    period, entries, _trace = _load_draft(draft)
    outcome = store.add(entries, commit=True)
    written = profiles.rebuild(base, store.load())

    rows = [
        {"name": "入库", "level": "ok", "detail": f"新增 {len(outcome.added)} 条"},
        {"name": "跳过（已存在）", "level": "ok", "detail": str(len(outcome.skipped))},
        {"name": "公司档案", "level": "ok", "detail": f"重建 {len(written)} 份"},
    ]
    for index, reason in outcome.rejected[:10]:
        rows.append({"name": f"第 {index} 条未入库", "level": "fail", "detail": reason.split("\n")[0]})

    if period:
        steps.record(
            base,
            period,
            "deposit",
            "done" if not outcome.rejected else "running",
            note=f"入库 {len(outcome.added)} 条"
            + (f"，{len(outcome.rejected)} 条待处理" if outcome.rejected else ""),
            inputs={"draft": draft},
            outputs={"entries": store.entries_file},
        )
        steps.record(base, period, "rebuild", "done", outputs={"profiles": profiles.profiles_dir(base)})
        if not outcome.rejected:
            _close_news_digest_step(base, period, len(outcome.added))

    status = "partial" if outcome.rejected else "success"
    return Result(
        status=status,
        summary=f"入库 {len(outcome.added)} 条"
        + (f"，{len(outcome.rejected)} 条被拒需要处理。" if outcome.rejected else "。"),
        domain=DOMAIN,
        period=period or None,
        checks=rows,
        next_steps=(
            ["被拒的条目多半是主题没填或表述类缺原话。修草稿后再跑一次即可，已入库的会自动跳过。"]
            if outcome.rejected
            else ["公司档案在 data/intel/profiles/，可直接读。"]
        ),
        data={"counts": outcome.counts, "profiles": [str(p) for p in written]},
    )


def _close_news_digest_step(base, period: str, count: int) -> None:
    """沉淀完成后，把 news-digest 那一侧的同一步也记完。

    「写完自动沉淀进情报库」在 ADR 0002 里是**一个动作**，但它跨两个域，于是状态各记一份。
    不联动的后果实测到了：情报库这边 2/2 完成、49 条在库，news-digest 那边的
    「沉淀进竞对情报库」仍停在待办，跨域汇总因此报「需要你说『沉淀这期新闻』」——
    而那件事刚刚做完。汇总里出现假待办，整栏就不可信了。

    方向刻意是**由这里去写对方**，而不是让 news-digest 去猜情报库的状态：
    做完这件事的是这条命令，它最清楚。失败不抛——联动不该让主流程挂掉。
    """
    try:
        from modules.news_digest import steps as news_steps

        news_steps.record(
            base, period, "deposit", "done",
            note=f"由 ir intel deposit 完成，入库 {count} 条",
        )
    # 必须连 SystemExit 一起抓：`Manifest.__init__` 用 SystemExit 报「周期键格式不对」，
    # 而 SystemExit 不是 Exception 的子类。只写 `except Exception` 兜不住它——
    # 季度通道的条目（周期键是 `26Q2`）走到这里会把整条入库命令弄崩。测试钉住了这一点。
    except (Exception, SystemExit):  # noqa: BLE001
        pass


def _tagging_rows(trace: list[dict]) -> list[dict]:
    """把打标结果折成人能扫读的行，并把「没标到公司」「主题只靠一个词命中」摆出来。"""
    rows: list[dict] = []
    no_company = [t["title"] for t in trace if not t["companies"] and not t["mentions"]]
    if no_company:
        rows.append(
            {
                "name": "无公司归属",
                "level": "ok",
                "detail": f"{len(no_company)} 条（宏观/政策类正常，schema 允许为空）",
            }
        )
    no_topic = [t["title"] for t in trace if not t["topics"]]
    if no_topic:
        rows.append(
            {
                "name": "主题猜不出",
                "level": "fail",
                "detail": f"{len(no_topic)} 条，需人工在草稿里补：" + "；".join(no_topic[:3]),
            }
        )
    weak = [
        t["title"] for t in trace
        if t["topics"] and all(len(v) <= 1 for v in t.get("topic_hits", {}).values())
    ]
    if weak:
        rows.append(
            {
                "name": "主题只靠单词命中",
                "level": "warn",
                "detail": f"{len(weak)} 条，建议重点核对：" + "；".join(weak[:3]),
            }
        )
    return rows


# --- 手工入库（季度通道 / 专家访谈通道）---

_CLAIM_LABELS = {
    "new": "新增数据",
    "corroborating": "佐证既有数据",
    "conflicting": "数值冲突",
    "different_scope": "疑似口径不同",
}


def _claim_brief(ref: dict) -> str:
    claim = ref.get("claim") or {}
    scope = json.dumps(claim.get("scope", {}), ensure_ascii=False, sort_keys=True)
    source = ref.get("quote_where") or ref.get("media") or "未标位置"
    pool = {"formal": "正式库", "deferred": "待核池", "batch": "本批"}.get(
        ref.get("pool"), ref.get("pool") or "候选"
    )
    return (
        f"[{pool}] {claim.get('metric_key')}={claim.get('value')} {claim.get('unit')} · "
        f"数据期 {claim.get('period')} · scope {scope} · basis {claim.get('basis') or '未说明'}"
        f" · {ref.get('date')} · {source}"
    )


def _claim_checks(outcome) -> list[dict]:
    counts = outcome.counts
    rows = [{
        "name": "数据主张审查",
        "level": "warn" if counts["claim_conflicting"] or counts["claim_different_scope"] else "ok",
        "detail": (
            f"新增 {counts['claim_new']} · 佐证 {counts['claim_corroborating']} · "
            f"冲突 {counts['claim_conflicting']} · 疑似口径不同 {counts['claim_different_scope']}"
        ),
    }]
    for review in outcome.claim_reviews:
        if review.classification not in {"conflicting", "different_scope"}:
            continue
        candidate = _claim_brief(review.candidate)
        existing = "；".join(_claim_brief(match) for match in review.matches[:3])
        rows.append({
            "name": f"第 {review.index} 条 · {_CLAIM_LABELS[review.classification]}",
            "level": "warn",
            "detail": f"新：{candidate}；已有：{existing}",
        })
    return rows


def _quarterly_claim_checks(outcome, exception_indexes: list[int]) -> list[dict]:
    """季度官方披露中，已完整声明scope的地区拆分不是异常。"""
    exceptions = set(exception_indexes)
    explicit_scope = sum(
        review.classification == "different_scope" and review.index not in exceptions
        for review in outcome.claim_reviews
    )
    unresolved = [review for review in outcome.claim_reviews if review.index in exceptions]
    rows = [{
        "name": "数据主张审查",
        "level": "warn" if unresolved else "ok",
        "detail": (
            f"新增 {outcome.counts['claim_new']} · 佐证 {outcome.counts['claim_corroborating']} · "
            f"明确分层口径 {explicit_scope} · 异常待审核 {len(unresolved)}"
        ),
    }]
    for review in unresolved:
        rows.append({
            "name": f"第 {review.index} 条 · {_CLAIM_LABELS[review.classification]}",
            "level": "warn",
            "detail": f"新：{_claim_brief(review.candidate)}；已有："
            + "；".join(_claim_brief(match) for match in review.matches[:3]),
        })
    return rows


def cmd_quarterly(args, base) -> Result:
    """季度材料默认自动沉淀正常项；只有异常项保留人工门禁。"""
    store = Store(base)
    try:
        if args.commit:
            _, outcome = quarterly.commit(base, args.company, args.period, store)
            written = profiles.rebuild(base, store.load())
            return Result(
                status="success",
                summary=f"异常季度条目确认入库 {len(outcome.added)} 条，档案重建 {len(written)} 份。",
                domain=DOMAIN,
                period=args.period,
                checks=[{
                    "name": "同一审核草稿", "level": "ok",
                    "detail": f"新增 {len(outcome.added)} · 已存在 {len(outcome.skipped)}",
                }, *_claim_checks(outcome)],
                data={"counts": outcome.counts},
            )

        missing = []
        if not args.source_pack:
            missing.append("--source-pack 季度材料目录")
        if not args.file:
            missing.append("--file Agent 候选 JSON")
        if missing:
            return Result(
                status="blocked", summary="季度处理缺少输入。", domain=DOMAIN,
                period=args.period, missing=missing,
            )
        plan = quarterly.prepare(
            base, args.company, args.period, Path(args.source_pack), Path(args.file), store,
            auto_commit=not args.dry_run,
        )
    except (quarterly.QuarterlyError, OSError, json.JSONDecodeError) as exc:
        return Result(
            status="blocked",
            summary="季度材料或候选条目未通过校验。",
            domain=DOMAIN,
            period=args.period,
            checks=[{"name": "季度门禁", "level": "fail", "detail": str(exc)}],
        )

    authority_counts = {
        level: sum(row["source_authority"] == level for row in plan.manifest["files"])
        for level in ("P0", "P1", "P2")
    }
    auto_added = len(plan.auto_outcome.added) if plan.auto_outcome else 0
    if plan.auto_outcome:
        written = profiles.rebuild(base, store.load())
        status = "partial" if plan.exception_indexes else "success"
        summary = (
            f"季度正常项自动入库 {auto_added} 条；"
            f"异常待审核 {len(plan.exception_indexes)} 条。"
        )
        next_steps = (
            ["只需核对 review.md 中标为“异常待审核”的条目。"]
            if plan.exception_indexes else []
        )
    else:
        status = "partial"
        summary = (
            f"季度 dry-run：{len(plan.outcome.added)} 条可入，"
            f"其中异常 {len(plan.exception_indexes)} 条；正式库未写入。"
        )
        next_steps = ["去掉 --dry-run 后，正常项将自动入库，异常项仍保留人工门禁。"]

    return Result(
        status=status,
        summary=summary,
        domain=DOMAIN,
        period=args.period,
        checks=[
            {
                "name": "材料 manifest", "level": "ok",
                "detail": (
                    f"{len(plan.manifest['files'])} 个文件 · "
                    f"P0 {authority_counts['P0']} / P1 {authority_counts['P1']} / "
                    f"P2 {authority_counts['P2']}"
                ),
            },
            {
                "name": "候选校验",
                "level": "warn" if plan.exception_indexes else "ok",
                "detail": (
                    f"可入 {len(plan.outcome.added)} · 已存在 {len(plan.outcome.skipped)} · "
                    f"异常 {len(plan.exception_indexes)} · 被拒 {len(plan.outcome.rejected)}"
                ),
            },
            *_quarterly_claim_checks(plan.outcome, plan.exception_indexes),
        ],
        next_steps=next_steps,
        data={
            "manifest": str(plan.manifest_path), "draft": str(plan.draft_path),
            "review": str(plan.review_path), "counts": plan.outcome.counts,
            "auto_added": auto_added, "exception_indexes": plan.exception_indexes,
            "claim_reviews": [review.to_dict() for review in plan.outcome.claim_reviews],
        },
    )


def cmd_add(args, base) -> Result:
    path = Path(args.file)
    if not path.is_file():
        return Result(status="blocked", summary="找不到条目文件。", domain=DOMAIN, missing=[str(path)])
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows_in = payload if isinstance(payload, list) else payload.get("entries", [])
    entries = [Entry.from_dict(row) for row in rows_in]
    store = Store(base)
    outcome = store.add(entries, commit=args.commit)

    checks = [
        {
            "name": "校验",
            "level": "fail" if outcome.rejected else "ok",
            "detail": f"可入 {len(outcome.added)} · 已存在 {len(outcome.skipped)} · 被拒 {len(outcome.rejected)}",
        },
        *_claim_checks(outcome),
    ]
    for index, reason in outcome.rejected[:10]:
        checks.append({"name": f"第 {index} 条", "level": "fail", "detail": reason.split("\n")[0]})

    review_data = [review.to_dict() for review in outcome.claim_reviews]
    has_unresolved = any(
        review.classification in {"conflicting", "different_scope"}
        for review in outcome.claim_reviews
    )
    if not args.commit:
        next_steps = []
        if has_unresolved:
            next_steps.append("先人工核对冲突与疑似口径不同项；系统不会覆盖旧值或自动选一个。")
        next_steps.append("确认后才可加 --commit 追加入库；原有主张不会被覆盖。")
        return Result(
            status="partial",
            summary=f"预演：{len(outcome.added)} 条可入库，**未写入**。",
            domain=DOMAIN,
            checks=checks,
            next_steps=next_steps,
            data={"counts": outcome.counts, "claim_reviews": review_data},
        )

    written = profiles.rebuild(base, store.load())
    return Result(
        status="partial" if outcome.rejected else "success",
        summary=f"入库 {len(outcome.added)} 条，档案重建 {len(written)} 份。",
        domain=DOMAIN,
        checks=checks,
        data={"counts": outcome.counts, "claim_reviews": review_data},
    )


def cmd_defer(args, base) -> Result:
    """把人工选定的 B 类条目放入跨批次待核池；默认无副作用。"""
    path = Path(args.file)
    if not path.is_file():
        return Result(status="blocked", summary="找不到待核条目文件。", domain=DOMAIN, missing=[str(path)])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("records", [])
        if isinstance(payload, dict) and payload.get("source"):
            source_path = Path(payload["source"])
            if not source_path.is_absolute():
                source_path = path.parent / source_path
            source_payload = json.loads(source_path.read_text(encoding="utf-8"))
            source_entries = source_payload.get("entries", [])
            expanded = []
            for row in rows:
                if "entry" in row:
                    expanded.append(row)
                    continue
                index = row.get("entry_index")
                if not isinstance(index, int) or index < 1 or index > len(source_entries):
                    raise EntryError(f"entry_index {index!r} 超出源草稿范围")
                expanded.append({**row, "entry": source_entries[index - 1]})
            rows = expanded
        records = [DeferredRecord.from_dict(row) for row in rows]
    except (OSError, json.JSONDecodeError, TypeError, EntryError) as exc:
        return Result(status="blocked", summary="待核条目文件无法解析。", domain=DOMAIN, missing=[str(exc)])
    if not records:
        return Result(status="blocked", summary="待核条目文件里没有 records。", domain=DOMAIN)

    store = Store(base)
    outcome = store.defer(records, commit=args.commit)
    checks = [
        {
            "name": "校验",
            "level": "fail" if outcome.rejected else "ok",
            "detail": f"可加入 {len(outcome.added)} · 已存在 {len(outcome.skipped)} · 被拒 {len(outcome.rejected)}",
        },
        *_claim_checks(outcome),
    ]
    for index, reason in outcome.rejected[:10]:
        checks.append({"name": f"第 {index} 条", "level": "fail", "detail": reason.split("\n")[0]})

    review_data = [review.to_dict() for review in outcome.claim_reviews]
    if not args.commit:
        return Result(
            status="partial",
            summary=f"预演：{len(outcome.added)} 条可进入待核池，**未写入**。",
            domain=DOMAIN,
            checks=checks,
            next_steps=["人工确认后才可加 --commit；待核项不会进入公司、主题或档案查询。"],
            data={"counts": outcome.counts, "claim_reviews": review_data},
        )
    return Result(
        status="partial" if outcome.rejected else "success",
        summary=f"待核池新增 {len(outcome.added)} 条；正式情报库未改动。",
        domain=DOMAIN,
        checks=checks,
        data={
            "counts": outcome.counts,
            "claim_reviews": review_data,
            "deferred_file": str(store.deferred_file),
        },
    )


def cmd_promote(args, base) -> Result:
    """人工转正唯一入口；先预演，明确确认后才写正式库。"""
    store = Store(base)
    try:
        promotion = store.promote(args.id, commit=args.commit)
    except EntryError as exc:
        return Result(status="blocked", summary="无法唯一定位待核记录。", domain=DOMAIN, missing=[str(exc)])

    record = promotion.record
    outcome = promotion.add_outcome
    checks = [
        {"name": "候选", "level": "ok", "detail": f"{record.entry.title}（{record.entry.id}）"},
        {"name": "暂缓原因", "level": "warn", "detail": "；".join(record.defer_reasons)},
        {"name": "转正条件", "level": "warn", "detail": "；".join(record.promotion_requirements)},
        *_claim_checks(outcome),
    ]
    for index, reason in outcome.rejected[:10]:
        checks.append({"name": f"校验第 {index} 条", "level": "fail", "detail": reason.split("\n")[0]})

    review_data = [review.to_dict() for review in outcome.claim_reviews]
    if not args.commit:
        return Result(
            status="partial",
            summary="转正预演完成，**未写正式库、未移出待核池**。",
            domain=DOMAIN,
            checks=checks,
            next_steps=["核对补证与冲突后，只有人工明确确认才可带 --commit 转正。"],
            data={"claim_reviews": review_data, "entry": record.entry.to_dict()},
        )

    if outcome.rejected or not promotion.removed:
        return Result(
            status="failed",
            summary="转正未完成，待核记录仍保留。",
            domain=DOMAIN,
            checks=checks,
            data={"claim_reviews": review_data},
        )
    written = profiles.rebuild(base, store.load())
    detail = "正式库原已存在，本次清理待核副本" if promotion.already_formal else "追加正式库并移出待核池"
    checks.append({"name": "转正", "level": "ok", "detail": detail})
    return Result(
        status="success",
        summary=f"已转正 1 条，档案重建 {len(written)} 份。",
        domain=DOMAIN,
        checks=checks,
        data={"claim_reviews": review_data, "profiles": [str(path) for path in written]},
    )


# --- 检索 ---


def cmd_company(args, base) -> Result:
    store = Store(base)
    entries = store.load()
    key = vocab.resolve_company(args.company) or vocab.normalize_other(args.company)
    rows = query.by_company(
        entries, key, since=args.since, until=args.until, kind=args.kind,
        include_mentions=not args.lead_only,
    )
    checks = [
        {
            "name": f"{e.date} · {KIND_ZH[e.kind]}",
            "level": "ok",
            "detail": e.title + ("" if key in e.companies else "（仅被提及）"),
        }
        for e in rows[: args.limit]
    ]
    tier = vocab.tier_of(key, store.registry())
    return Result(
        status="success",
        summary=f"{vocab.label(key, store.registry())}（{key}·{vocab.TIER_ZH[tier]}）"
        f"共 {len(rows)} 条。",
        domain=DOMAIN,
        checks=checks or [{"name": "结果", "level": "warn", "detail": "没有匹配条目"}],
        next_steps=(
            [f"建档层公司有人读档案：data/intel/profiles/{key}.md"]
            if tier == "profiled"
            else []
        ),
        data={"company": key, "tier": tier, "entries": [e.to_dict() for e in rows]},
    )


def cmd_topic(args, base) -> Result:
    store = Store(base)
    tiers = ("profiled",) if args.profiled_only else ("profiled", "indexed", "other")
    sliced = query.by_topic(
        store.load(), args.topic, since=args.since, until=args.until, tiers=tiers
    )
    registry = store.registry()
    checks: list[dict] = []
    for company, items in sliced.by_company.items():
        name = (
            query.MACRO_ZH if company == query.MACRO_BUCKET
            else f"{vocab.label(company, registry)}（{company}）"
        )
        checks.append({"name": name, "level": "ok", "detail": f"{len(items)} 条"})
        for entry in items[: args.per_company]:
            checks.append({"name": "　└", "level": "ok", "detail": f"{entry.date} {entry.title}"})
    return Result(
        status="success",
        summary=f"主题「{sliced.topic_zh}」共 {sliced.total} 条，涉及 {len(sliced.by_company)} 个主体。",
        domain=DOMAIN,
        checks=checks or [{"name": "结果", "level": "warn", "detail": "该主题下还没有条目"}],
        data={
            "topic": sliced.topic,
            "by_company": {
                k: [e.to_dict() for e in v] for k, v in sliced.by_company.items()
            },
        },
    )


def cmd_tag(args, base) -> Result:
    store = Store(base)
    entries = store.load()
    if not args.tag:
        counts = query.tag_counts(entries)
        return Result(
            status="success",
            summary=f"共 {len(counts)} 个自由标签。",
            domain=DOMAIN,
            checks=[{"name": k, "level": "ok", "detail": f"{v} 条"} for k, v in list(counts.items())[:60]]
            or [{"name": "标签", "level": "warn", "detail": "还没有条目打过自由标签"}],
            next_steps=["同义词飘了就在这张表上看得出来（如 AEO 与 aeo、减值与计提减值）。"],
            data={"counts": counts},
        )
    rows = query.by_tag(entries, args.tag, since=args.since, until=args.until)
    return Result(
        status="success",
        summary=f"标签「{args.tag}」共 {len(rows)} 条。",
        domain=DOMAIN,
        checks=[
            {"name": e.date, "level": "ok",
             "detail": f"{e.title}（{'、'.join(e.all_companies) or '无公司归属'}）"}
            for e in rows[: args.limit]
        ] or [{"name": "结果", "level": "warn", "detail": "没有匹配条目"}],
        data={"entries": [e.to_dict() for e in rows]},
    )


def cmd_vocab(args, base) -> Result:
    store = Store(base)
    registry = store.registry()
    checks = [
        {"name": f"{c.key}", "level": "ok", "detail": f"{c.zh} · {vocab.TIER_ZH[c.tier]}"}
        for c in vocab.PROFILED + vocab.INDEXED
    ]
    checks.extend(
        {"name": key, "level": "ok", "detail": f"{name} · 其他桶"}
        for key, name in sorted(registry.items())
    )
    checks.extend(
        {"name": t.key, "level": "ok", "detail": f"主题：{t.zh}（{t.scope}）"}
        for t in vocab.TOPICS
    )
    return Result(
        status="success",
        summary=f"受控词表：建档层 {len(vocab.PROFILED)} · 索引层 {len(vocab.INDEXED)} "
        f"· 其他桶 {len(registry)} · 主题 {len(vocab.TOPICS)}。",
        domain=DOMAIN,
        checks=checks,
        next_steps=[
            "建档层与索引层的名单变更须走决策（ADR 0002 §2），不要随手加。",
            "主题词表增删要同时改 vocab.py 与 ADR 0002 §7。",
        ],
    )


def cmd_retag(args, base) -> Result:
    """按当前规则重算已入库条目的主题，先摆差异再改。

    存在的理由：ADR 0002 说打标「自动，事后可改」。抽查 39 条时发现关键词表有几处
    系统性误命中（「独家」命中 Skift 的独家报道标签、「政策」命中企业差旅政策、
    「CEO」命中任何引用 CEO 的稿子），修完表就得能把已入库的标签跟着修。
    """
    store = Store(base)
    entries = store.load()
    if not entries:
        return Result(status="partial", summary="库里还没有条目。", domain=DOMAIN)

    changed: list[tuple[Entry, list[str], list[str]]] = []
    emptied: list[Entry] = []
    updated: list[Entry] = []

    for entry in entries:
        if args.period and entry.period != args.period:
            updated.append(entry)
            continue
        # 只重算周度通道的条目：季度与访谈通道的标签是人手打的，不该被关键词覆盖。
        if entry.channel != "weekly":
            updated.append(entry)
            continue
        # 人核过的标签不再被关键词覆盖。没有这道保护，「事后可改」仍然是空话——
        # 人改完，下一次 retag 就把它算回去了，而且不会有任何提示。
        if entry.topics_reviewed:
            updated.append(entry)
            continue
        topics, _hits = backfill._guess_topics(entry.title, entry.body)
        # 只比集合：顺序变化不是改动，报出来只会让人以为动了很多条
        if set(topics) == set(entry.topics):
            updated.append(entry)
            continue
        if not topics:
            emptied.append(entry)
            updated.append(entry)      # 猜不出就保留原标签，不清空
            continue
        changed.append((entry, entry.topics, topics))
        replaced = Entry.from_dict({**entry.to_dict(), "topics": topics})
        updated.append(replaced)

    rows: list[dict] = []
    for entry, before, after in changed[: args.limit]:
        dropped = [t for t in before if t not in after]
        added = [t for t in after if t not in before]
        detail = entry.title[:30]
        if dropped:
            detail += "　去掉 " + "、".join(dropped)
        if added:
            detail += "　加上 " + "、".join(added)
        rows.append({"name": entry.date, "level": "ok", "detail": detail})
    for entry in emptied[:5]:
        rows.append(
            {"name": "猜不出主题", "level": "warn",
             "detail": f"{entry.title[:30]}（保留原标签 {'、'.join(entry.topics)}，建议人工核）"}
        )

    if not args.commit:
        return Result(
            status="partial",
            summary=f"{len(changed)} 条主题会变，**未写入**。",
            domain=DOMAIN,
            checks=rows or [{"name": "差异", "level": "ok", "detail": "当前规则下没有条目需要改"}],
            next_steps=["确认这些改动后加 --commit 写入。"] if changed else [],
            data={"changed": len(changed), "emptied": len(emptied)},
        )

    store.replace(updated)
    written = profiles.rebuild(base, store.load())
    return Result(
        status="success",
        summary=f"重打 {len(changed)} 条的主题，档案重建 {len(written)} 份。",
        domain=DOMAIN,
        checks=rows,
        data={"changed": len(changed), "emptied": len(emptied)},
    )


def cmd_set_topics(args, base) -> Result:
    """人工改一条的主题，并标为已核（此后 retag 不再动它）。"""
    store = Store(base)
    entries = store.load()
    matched = [e for e in entries if e.id == args.id or args.id in (e.title or "")]
    if len(matched) != 1:
        return Result(
            status="blocked",
            summary=f"按 {args.id!r} 匹配到 {len(matched)} 条，需要唯一。",
            domain=DOMAIN,
            checks=[{"name": e.id or "?", "level": "warn", "detail": e.title} for e in matched[:8]],
            next_steps=["用条目 id，或给一段只匹配一条的标题片段。"],
        )
    target = matched[0]
    topics = [vocab.resolve_topic(t) for t in args.topics]
    before = list(target.topics)

    updated = [
        Entry.from_dict({**e.to_dict(), "topics": topics, "topics_reviewed": True})
        if e.id == target.id else e
        for e in entries
    ]
    if not args.commit:
        return Result(
            status="partial",
            summary=f"「{target.title[:24]}」主题 {before} → {topics}，**未写入**。",
            domain=DOMAIN,
            next_steps=["确认后加 --commit。"],
        )
    store.replace(updated)
    profiles.rebuild(base, store.load())
    return Result(
        status="success",
        summary=f"已改「{target.title[:24]}」的主题并标为已核。",
        domain=DOMAIN,
        checks=[
            {"name": "改前", "level": "ok", "detail": "、".join(before) or "无"},
            {"name": "改后", "level": "ok", "detail": "、".join(topics)},
        ],
    )


def cmd_rebuild(args, base) -> Result:
    store = Store(base)
    entries = store.load()
    written = profiles.rebuild(base, entries)
    return Result(
        status="success",
        summary=f"从 {len(entries)} 条真源重建了 {len(written)} 份公司档案。",
        domain=DOMAIN,
        checks=[{"name": p.stem, "level": "ok", "detail": f"{p.stat().st_size} 字节"} for p in written],
    )


def _unexpected_gaps(info: dict) -> list[str]:
    """建档层里**没被裁定为预期稀疏**的空档。只有这些才算问题。"""
    return [k for k in info["profiled_missing"] if k not in vocab.SPARSE_EXPECTED]


def cmd_status(args, base) -> Result:
    store = Store(base)
    entries = store.load()
    deferred = store.load_deferred()
    info = query.stats(entries)
    info["deferred"] = len(deferred)
    registry = store.registry()
    checks = [
        {"name": "正式条目总数", "level": "ok", "detail": str(info["total"])},
        {"name": "待核池", "level": "warn" if deferred else "ok", "detail": f"{len(deferred)} 条（不进入正式查询）"},
        {
            "name": "两类条目",
            "level": "ok",
            "detail": "、".join(f"{KIND_ZH[k]} {v}" for k, v in sorted(info["by_kind"].items()))
            or "无",
        },
        {"name": "已覆盖期次", "level": "ok", "detail": "、".join(info["periods"]) or "无"},
        {
            "name": "建档层覆盖",
            # 已裁定条目稀疏属正常的那几家不算缺口（vocab.SPARSE_EXPECTED）。
            # 与 health.py 用同一份判据——两处不一致会让人不知道该信哪个。
            "level": "warn" if _unexpected_gaps(info) else "ok",
            "detail": f"{len(info['profiled_covered'])}/{len(vocab.PROFILED_KEYS)}"
            + ("；缺 " + "、".join(info["profiled_missing"]) if info["profiled_missing"] else "")
            + ("（均已裁定属预期稀疏）" if info["profiled_missing"] and not _unexpected_gaps(info) else ""),
        },
        {
            "name": "主题未用到",
            "level": "ok",
            "detail": "、".join(info["topics_unused"]) or "全部用到",
        },
        {"name": "其他桶已登记", "level": "ok", "detail": str(len(registry))},
    ]
    return Result(
        status="success" if info["total"] else "partial",
        summary=f"竞对情报库：{info['total']} 条，{len(info['periods'])} 个期次。"
        if info["total"]
        else "竞对情报库还是空的。",
        domain=DOMAIN,
        checks=checks,
        next_steps=(
            [] if info["total"] else ["对我说「回填历史情报」，我从往期新闻精选建库。"]
        ),
        data=info,
    )


def register(subparsers, common) -> None:
    parser = subparsers.add_parser("intel", help="竞对情报库：沉淀与检索")
    sub = parser.add_subparsers(dest="intel_command", required=True)

    p_dep = sub.add_parser(
        "deposit", help="从新闻精选沉淀条目（先出草稿，确认后 --commit 入库）", parents=[common]
    )
    p_dep.add_argument("--from", dest="source", nargs="*", help="新闻精选 Markdown 路径")
    p_dep.add_argument(
        "--dir",
        help=f"递归找该目录下的 {DIGEST_PREFIX}*.md（避免中文路径穿过命令行，ADR 0007）",
    )
    p_dep.add_argument("--period", help="期次键，如 2026-08-W2")
    p_dep.add_argument("--commit", action="store_true", help="读草稿入库（须用户确认）")
    p_dep.set_defaults(func=cmd_deposit)

    p_add = sub.add_parser("add", help="从 JSON 手工入库（专家访谈 / 兼容入口）", parents=[common])
    p_add.add_argument("--file", required=True)
    p_add.add_argument("--commit", action="store_true")
    p_add.set_defaults(func=cmd_add)

    p_quarterly = sub.add_parser(
        "quarterly", help="季度原件校验：正常项自动入库，异常项单独审核", parents=[common]
    )
    p_quarterly.add_argument("--company", required=True, help="公司 ticker，如 BKNG")
    p_quarterly.add_argument("--period", required=True, help="季度键，如 26Q2")
    p_quarterly.add_argument("--source-pack", help="只读季度原件目录；首次处理必填")
    p_quarterly.add_argument("--file", help="Agent 候选 JSON；首次处理必填")
    p_quarterly.add_argument(
        "--dry-run", action="store_true", help="只生成 manifest/draft/review，不自动入库"
    )
    p_quarterly.add_argument(
        "--commit", action="store_true", help="人工确认异常项后，读取同一 draft 入库"
    )
    p_quarterly.set_defaults(func=cmd_quarterly)

    p_def = sub.add_parser("defer", help="把人工选定的 B 类条目放入跨批次待核池", parents=[common])
    p_def.add_argument("--file", required=True)
    p_def.add_argument("--commit", action="store_true", help="写入待核池（须人工确认）")
    p_def.set_defaults(func=cmd_defer)

    p_pro = sub.add_parser("promote", help="把一条待核情报人工转入正式库", parents=[common])
    p_pro.add_argument("--id", required=True, help="待核条目 id，或唯一标题片段")
    p_pro.add_argument("--commit", action="store_true", help="正式转正（须人工确认）")
    p_pro.set_defaults(func=cmd_promote)

    p_co = sub.add_parser("company", help="按公司纵切检索", parents=[common])
    p_co.add_argument("company")
    p_co.add_argument("--since")
    p_co.add_argument("--until")
    p_co.add_argument("--kind", choices=["action", "statement"])
    p_co.add_argument("--lead-only", action="store_true", help="只看本公司为主角的条目")
    p_co.add_argument("--limit", type=int, default=30)
    p_co.set_defaults(func=cmd_company)

    p_tp = sub.add_parser("topic", help="按主题横切检索（按公司分组）", parents=[common])
    p_tp.add_argument("topic")
    p_tp.add_argument("--since")
    p_tp.add_argument("--until")
    p_tp.add_argument("--profiled-only", action="store_true", help="只看建档层 8 家")
    p_tp.add_argument("--per-company", type=int, default=5)
    p_tp.set_defaults(func=cmd_topic)

    p_tg = sub.add_parser(
        "tag", help="自由标签：不给标签名则列全部词频", parents=[common]
    )
    p_tg.add_argument("tag", nargs="?")
    p_tg.add_argument("--since")
    p_tg.add_argument("--until")
    p_tg.add_argument("--limit", type=int, default=30)
    p_tg.set_defaults(func=cmd_tag)

    p_vc = sub.add_parser("vocab", help="列出受控词表", parents=[common])
    p_vc.set_defaults(func=cmd_vocab)

    p_rt = sub.add_parser(
        "retag", help="按当前规则重算主题（先摆差异，--commit 才写）", parents=[common]
    )
    p_rt.add_argument("--period", help="只重算某一期")
    p_rt.add_argument("--limit", type=int, default=40)
    p_rt.add_argument("--commit", action="store_true")
    p_rt.set_defaults(func=cmd_retag)

    p_sp = sub.add_parser(
        "set-topics", help="人工改一条的主题并标为已核（retag 此后不再动它）", parents=[common]
    )
    p_sp.add_argument("--id", required=True, help="条目 id，或一段只匹配一条的标题片段")
    p_sp.add_argument("--topics", nargs="+", required=True)
    p_sp.add_argument("--commit", action="store_true")
    p_sp.set_defaults(func=cmd_set_topics)

    p_rb = sub.add_parser("rebuild", help="从真源重建公司档案投影", parents=[common])
    p_rb.set_defaults(func=cmd_rebuild)

    p_st = sub.add_parser("status", help="情报库体检", parents=[common])
    p_st.set_defaults(func=cmd_status)
