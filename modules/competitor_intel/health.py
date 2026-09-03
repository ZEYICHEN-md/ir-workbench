"""competitor-intel 的健康检查，供 `ir doctor` 调用。

这个域没有外部依赖（没网络、没 Excel、没 COM），所以检查的重点不是「跑不跑得起来」，
而是**库本身有没有悄悄坏掉**：真源能不能解析、投影有没有落后于真源、建档层是不是有
公司长期没条目。

「投影落后于真源」这条特意做成检查项而不是靠人记得跑 rebuild —— 投影是给人读的，
落后的投影比没有投影更坏：它看起来是最新的。
"""

from __future__ import annotations

from workbench.paths import Paths

from . import profiles, vocab
from .entry import EntryError
from .store import Store


def checks(base: Paths) -> list[dict]:
    store = Store(base)
    rows: list[dict] = []

    if not store.entries_file.is_file():
        return [
            {
                "name": "情报库",
                "level": "warn",
                "detail": "还没有任何条目",
                "advice": "对 Agent 说「回填历史情报」即可从往期新闻精选建库。",
            }
        ]

    try:
        entries = store.load()
    except EntryError as error:
        return [
            {
                "name": "情报库真源",
                "level": "fail",
                "detail": str(error),
                "advice": "JSONL 有坏行。上面写了是第几行，去 data/intel/entries.jsonl 修那一行。",
            }
        ]

    rows.append(
        {"name": "情报库真源", "level": "ok", "detail": f"{len(entries)} 条，可解析"}
    )

    if store.deferred_file.is_file():
        try:
            deferred = store.load_deferred()
        except EntryError as error:
            rows.append(
                {
                    "name": "情报库待核池",
                    "level": "fail",
                    "detail": str(error),
                    "advice": "JSONL 有坏行。上面写了是第几行，去 data/intel/deferred.jsonl 修那一行。",
                }
            )
        else:
            rows.append(
                {
                    "name": "情报库待核池",
                    "level": "ok",
                    "detail": f"{len(deferred)} 条待核，可解析",
                }
            )

    # 投影是否落后于真源
    profile_dir = profiles.profiles_dir(base)
    missing = [
        key for key in vocab.PROFILED_KEYS if not (profile_dir / f"{key}.md").is_file()
    ]
    if missing:
        rows.append(
            {
                "name": "公司档案投影",
                "level": "warn",
                "detail": "缺：" + "、".join(missing),
                "advice": "对 Agent 说「重建情报档案」。",
            }
        )
    else:
        newest_entry = store.entries_file.stat().st_mtime
        stale = [
            key for key in vocab.PROFILED_KEYS
            if (profile_dir / f"{key}.md").stat().st_mtime < newest_entry
        ]
        if stale:
            rows.append(
                {
                    "name": "公司档案投影",
                    "level": "warn",
                    "detail": f"{len(stale)} 份比真源旧",
                    "advice": "对 Agent 说「重建情报档案」。落后的投影看起来像最新的，比没有更坏。",
                }
            )
        else:
            rows.append(
                {
                    "name": "公司档案投影",
                    "level": "ok",
                    "detail": f"{len(vocab.PROFILED_KEYS)} 份，均不落后于真源",
                }
            )

    # 建档层覆盖：某家长期没条目，可能是名单该调，也可能是采集漏了这一家
    covered = {key for e in entries for key in e.all_companies}
    empty = [k for k in vocab.PROFILED_KEYS if k not in covered]
    unexpected = [k for k in empty if k not in vocab.SPARSE_EXPECTED]
    expected = [k for k in empty if k in vocab.SPARSE_EXPECTED]
    if unexpected:
        rows.append(
            {
                "name": "建档层覆盖",
                "level": "warn",
                "detail": "无任何条目：" + "、".join(unexpected),
                "advice": "要么是采集漏了这几家，要么是名单该调整（名单变更须走决策，ADR 0002 §2）。",
            }
        )
    if expected:
        # 已裁定这几家条目稀疏属正常。仍然报出来，但不当成待办——
        # 一条永远清不掉的 warn 会让人开始忽略整栏。
        rows.append(
            {
                "name": "建档层覆盖（预期稀疏）",
                "level": "ok",
                "detail": "暂无条目：" + "、".join(expected) + "　—— 已裁定属正常，见 vocab.SPARSE_EXPECTED",
            }
        )
    if not empty:
        rows.append(
            {
                "name": "建档层覆盖",
                "level": "ok",
                "detail": f"{len(vocab.PROFILED_KEYS)} 家均有条目",
            }
        )

    return rows
