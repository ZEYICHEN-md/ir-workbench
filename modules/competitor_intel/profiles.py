"""公司档案：JSONL 的人读投影。

## 投影，不是第二份真源

和 `data/canonical/*.json` 同一个纪律（ADR 0001）：档案文件是**从 JSONL 重新生成的**，
手改会在下次生成时被覆盖。所以每份档案顶部都写明这一点——不写的话，半年后一定有人
直接改 markdown 然后发现改动消失，接着开始怀疑整个工具。

只给**建档层**生成（ADR 0002 §2）。索引层与其他桶靠检索，不建档：建档的成本是每期
都要维护，而这两层的定位本来就是「打标签可检索」和「只存不维护」。

## 排版为什么这样

时间倒序，因为读档案的场景是「这家公司最近在干什么」。主角条目进正文，仅被提及的
单独一节列在末尾——两者混排会让「这家公司做了什么」和「别人做了什么牵扯到它」分不清，
而写 Appendix 时这个区别很要紧。
"""

from __future__ import annotations

from pathlib import Path

from workbench.fileio import write_text
from workbench.paths import Paths

from . import vocab
from .entry import KIND_ZH, Entry

BANNER = (
    "> ⚠️ **本文件是投影，不要手改。**内容由 `data/intel/entries.jsonl` 生成，"
    "手改会在下次 `ir intel rebuild` 时被覆盖。要改内容就去改 JSONL 那条记录。"
)


def profiles_dir(base: Paths) -> Path:
    return base.intel / "profiles"


def render(company: str, entries: list[Entry], *, registry: dict[str, str] | None = None) -> str:
    """渲染一家公司的档案。`entries` 已按需要过滤，本函数只管排版。"""
    name = vocab.label(company, registry)
    lead = [e for e in entries if company in e.companies]
    mentioned = [e for e in entries if company not in e.companies]
    lead.sort(key=lambda e: (e.date, e.title), reverse=True)
    mentioned.sort(key=lambda e: (e.date, e.title), reverse=True)

    lines = [f"# {name}（{company}）竞对情报档案", "", BANNER, ""]
    lines.append(
        f"> 条目 {len(entries)} 条（主角 {len(lead)} · 被提及 {len(mentioned)}）"
        + (f"；最近 {lead[0].date}" if lead else "")
    )
    lines.append("")

    if lead:
        lines.append("## 动作与表述（本公司为主角）")
        lines.append("")
        for entry in lead:
            lines.extend(_entry_block(entry))
    else:
        lines.append("## 动作与表述（本公司为主角）")
        lines.append("")
        lines.append("暂无条目。")
        lines.append("")

    if mentioned:
        lines.append("## 被提及（主角是别家，但对本公司有实质信息）")
        lines.append("")
        for entry in mentioned:
            lines.extend(_entry_block(entry, brief=True))

    return "\n".join(lines).rstrip() + "\n"


def _entry_block(entry: Entry, *, brief: bool = False) -> list[str]:
    topics = "、".join(
        vocab.TOPIC_BY_KEY[t].zh for t in entry.topics if t in vocab.TOPIC_BY_KEY
    )
    head = f"### {entry.date} · {entry.title}"
    meta = [f"类型 {KIND_ZH[entry.kind]}", f"主题 {topics}"]
    if entry.media:
        meta.append(f"来源 {entry.media}")
    if entry.sensitivity == "internal":
        meta.append("**内部**")
    lines = [head, "", "> " + " · ".join(meta), ""]
    if entry.kind == "statement" and entry.quote:
        lines.append(f"原话：「{entry.quote}」")
        lines.append("")
        lines.append(f"出处：{entry.quote_where}"
                     + (f"（{entry.speaker}）" if entry.speaker else ""))
        lines.append("")
    if brief:
        body = entry.body.strip().split("\n")[0]
        lines.append(body)
    else:
        lines.append(entry.body.strip())
    lines.append("")
    if entry.url:
        lines.append(f"[原文]({entry.url})")
        lines.append("")
    return lines


def rebuild(base: Paths, entries: list[Entry]) -> list[Path]:
    """重建全部建档层档案。返回写出的文件。

    每次全量重建而不是增量追加：投影只要能从真源一键重放，就永远不用担心它偏了。
    """
    from .query import by_company

    registry = {}
    registry_file = base.intel / "companies.json"
    if registry_file.is_file():
        import json

        registry = json.loads(registry_file.read_text(encoding="utf-8"))

    written: list[Path] = []
    for company in vocab.PROFILED_KEYS:
        rows = by_company(entries, company)
        path = profiles_dir(base) / f"{company}.md"
        write_text(path, render(company, rows, registry=registry))
        written.append(path)
    return written
