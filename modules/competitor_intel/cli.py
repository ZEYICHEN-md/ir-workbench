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

from . import backfill, profiles, query, steps, vocab  # noqa: F401 —— backfill 供 retag 用
from .entry import KIND_ZH, Entry, normalize
from .steps import DOMAIN
from .store import Store

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
            "公司标签是规则匹配（标题里出现＝主角，只在正文出现＝提及），一般可信；"
            "**主题是关键词猜的，务必看一眼**，可直接改草稿里的 topics。",
            "确认后回一句「沉淀这期新闻」，Agent 才会入库。入库读的就是这份草稿，"
            "不会重新解析——你改过的标签不会被冲掉。",
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
        }
    ]
    for index, reason in outcome.rejected[:10]:
        checks.append({"name": f"第 {index} 条", "level": "fail", "detail": reason.split("\n")[0]})

    if not args.commit:
        return Result(
            status="partial",
            summary=f"预演：{len(outcome.added)} 条可入库，**未写入**。",
            domain=DOMAIN,
            checks=checks,
            next_steps=["确认后加 --commit 入库。"],
        )

    written = profiles.rebuild(base, store.load())
    return Result(
        status="partial" if outcome.rejected else "success",
        summary=f"入库 {len(outcome.added)} 条，档案重建 {len(written)} 份。",
        domain=DOMAIN,
        checks=checks,
        data={"counts": outcome.counts},
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


def cmd_status(args, base) -> Result:
    store = Store(base)
    entries = store.load()
    info = query.stats(entries)
    registry = store.registry()
    checks = [
        {"name": "条目总数", "level": "ok", "detail": str(info["total"])},
        {
            "name": "两类条目",
            "level": "ok",
            "detail": "、".join(f"{KIND_ZH[k]} {v}" for k, v in sorted(info["by_kind"].items()))
            or "无",
        },
        {"name": "已覆盖期次", "level": "ok", "detail": "、".join(info["periods"]) or "无"},
        {
            "name": "建档层覆盖",
            "level": "warn" if info["profiled_missing"] else "ok",
            "detail": f"{len(info['profiled_covered'])}/{len(vocab.PROFILED_KEYS)}"
            + ("；缺 " + "、".join(info["profiled_missing"]) if info["profiled_missing"] else ""),
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

    p_add = sub.add_parser("add", help="从 JSON 手工入库（季度通道 / 专家访谈通道）", parents=[common])
    p_add.add_argument("--file", required=True)
    p_add.add_argument("--commit", action="store_true")
    p_add.set_defaults(func=cmd_add)

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
