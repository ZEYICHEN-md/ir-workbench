"""新闻去重台账：跨期去重的确定性一层。

## 为什么不能只靠 URL

同一件事常有多个 URL（转载、不同媒体、跟进报道）。所以在 URL 之外再加两道确定性防线：

1. **URL 规范化**：剥掉 `utm_*`/`fbclid` 等追踪参数、去 `www.`、去末尾斜杠、小写化。
2. **事件指纹 + 标题相似度**：标题归一为词集后比相似度；并可显式登记事件指纹
   （`主体|事件核心`，如 `netease|hkex-migration`），跨不同措辞与不同 URL 命中。

## 脚本只给候选，不下判断

「这算不算同一件事的实质跟进」是语义判断，交给人与 Agent。台账只负责给出**高度疑似
重复**的候选，附命中原因。这条边界是刻意的：自动剔除会漏掉真正的跟进报道
（例「延续上期：Booking B2B 由 Agoda CEO 兼任」——那条是该写的）。

## 与情报库的分工

| | 台账 | 情报库 |
|---|---|---|
| 问题 | 这条**是不是上期写过了** | 这条**说了什么、归谁** |
| 判重方式 | 相似度（模糊，给人看） | 确定性 id（精确，保幂等） |
| 时机 | 选稿前 | 定稿后 |

两者都用「去重」这个词，但不是一回事，也不能互相替代。用相似度做幂等会把改写过标题的
同一条入两次；用确定性 id 做选稿查重会漏掉换了 URL 的同一件事。

## 台账文件

`modules/news_digest/news-log.jsonl`，一行一条，人可读、可 git diff。
字段：`period` `date` `title` `url` `url_norm` `event_key` `source`。

> 迁移说明：旧仓字段名是 `week`，值是中文期次（`2026年7月第1周`）。工作台改用 `period`
> + ASCII 键（`2026-07-W1`）。读取时**两种都认**，写入一律新格式——旧记录不改写，
> 让 git 历史里那 31 条保持原样可核对。
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from workbench.fileio import write_text_atomic

from . import calendar_

LEDGER_NAME = "news-log.jsonl"

_TRACK = re.compile(r"^(utm_|fbclid|gclid|mc_|ref$|ref_|spm|from$)", re.I)
_STOP = {
    "the", "a", "an", "to", "of", "in", "on", "for", "and", "is", "are", "with",
    "its", "as", "at", "by", "it", "s", "amid", "over", "into", "but", "now",
}

#: 默认标题相似度阈值。0.72 是旧仓用了几期的经验值，不动。
DEFAULT_SIM = 0.72
#: 默认只与最近几期比对。更早的重复基本不再是问题，全量比会制造噪音。
DEFAULT_WEEKS = 3


class LedgerError(ValueError):
    pass


def ledger_path(base) -> Path:
    """台账放模块目录内，与 `industry-data` 的 insights 同一个先例：
    它是本域的持久内容，不是跨域共享数据。"""
    return base.module("news-digest") / LEDGER_NAME


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    url = url.strip()
    match = re.match(r"(?i)^(https?://)?([^/?#]+)([^?#]*)(\?[^#]*)?", url)
    if not match:
        return url.lower().rstrip("/")
    host = match.group(2).lower()
    if host.startswith("www."):
        host = host[4:]
    path = (match.group(3) or "").rstrip("/")
    query = match.group(4) or ""
    kept = []
    if query.startswith("?"):
        for pair in query[1:].split("&"):
            key = pair.split("=", 1)[0]
            if key and not _TRACK.match(key):
                kept.append(pair)
    tail = ("?" + "&".join(kept)) if kept else ""
    return f"{host}{path}{tail}"


def title_tokens(title: str | None) -> list[str]:
    words = re.findall(r"[a-z0-9\u4e00-\u9fff]+", (title or "").lower())
    return [w for w in words if w not in _STOP and len(w) > 1]


def title_similarity(left: str, right: str) -> float:
    a, b = " ".join(title_tokens(left)), " ".join(title_tokens(right))
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def row_period(row: dict) -> str:
    """兼容旧字段：`period`（新，ASCII）优先，回退 `week`（旧，中文）。"""
    if row.get("period"):
        return row["period"]
    legacy = row.get("week") or ""
    try:
        return calendar_.key_from_label(legacy)
    except calendar_.PeriodError:
        return legacy


def load(base) -> list[dict]:
    path = ledger_path(base)
    if not path.is_file():
        return []
    rows = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LedgerError(f"台账第 {lineno} 行损坏：{exc.msg}") from exc
        if not isinstance(row, dict):
            raise LedgerError(f"台账第 {lineno} 行必须是对象")
        rows.append(row)
    return rows


def recent(rows: list[dict], weeks: int | None) -> list[dict]:
    """按真实期次取最近 N 期（不是按行数估算——每期条数不固定）。

    **按期次键排序取最新，不按文件里的出现顺序。**旧实现取的是文件末尾 N 期，
    这依赖「文件顺序 == 时间顺序」。补录历史（比如补上漏登记的 `2026-07-W3`）会追加到
    文件末尾，于是那一期被当成最新的，真正的最近三期反而被挤出比对范围——查重静默失效。

    能改成排序是 ASCII 键带来的：`2026-07-W3` < `2026-08-W1` 字典序即时间序。
    旧仓的中文键做不到（`2026年7月第3周` 与 `2026年10月第1周` 会排反），
    这大概就是当初只能用文件顺序的原因。
    """
    if not weeks or weeks <= 0:
        return rows
    keys = {row_period(r) for r in rows if row_period(r)}
    keep = set(sorted(keys)[-weeks:])
    return [r for r in rows if row_period(r) in keep]


@dataclass
class Hit:
    reason: str
    period: str
    date: str
    title: str
    url: str


def find_duplicates(candidate: dict, rows: list[dict], sim: float) -> list[Hit]:
    url_norm = normalize_url(candidate.get("url", ""))
    event_key = (candidate.get("event_key") or "").strip().lower()
    hits: list[Hit] = []
    for row in rows:
        reason = None
        if url_norm and url_norm == row.get("url_norm"):
            reason = "URL 规范化后相同"
        elif event_key and event_key == (row.get("event_key") or "").lower():
            reason = f"事件指纹相同（{event_key}）"
        else:
            score = title_similarity(candidate.get("title", ""), row.get("title", ""))
            if score >= sim:
                reason = f"标题相似度 {score:.2f}"
        if reason:
            hits.append(
                Hit(reason, row_period(row), row.get("date", ""), row.get("title", ""),
                    row.get("url", ""))
            )
    return hits


def check(base, candidates: list[dict], *, weeks: int = DEFAULT_WEEKS,
          sim: float = DEFAULT_SIM) -> list[dict]:
    rows = recent(load(base), weeks)
    out = []
    for item in candidates:
        hits = find_duplicates(item, rows, sim)
        out.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "duplicate": bool(hits),
                "matches": [h.__dict__ for h in hits],
            }
        )
    return out


@dataclass
class AddOutcome:
    written: list[dict]
    blocked: list[tuple[dict, list[Hit]]]
    no_url: list[str]


def add(
    base,
    period: str,
    items: list[dict],
    *,
    weeks: int = DEFAULT_WEEKS,
    sim: float = DEFAULT_SIM,
    force: bool = False,
    reason: str = "",
    backfill: bool = False,
    commit: bool = True,
) -> AddOutcome:
    """登记本期收录的新闻。**写入前自动查重，命中即拒**，除非 `force` + 非空 `reason`。

    拒绝而不是警告：登记是「以后据此判重」的动作，登进去一条重复的，下一期就查不出来了。

    `backfill=True` 补录历史期次时跳过查重，理由是**查重方向反了**：判重问的是
    「这条是不是重复了**更早**写过的东西」，而补录的期次比台账里已有的都早。
    实测补录 `2026-07-W3` 时 10 条里 7 条被判重复，命中的全是它**后面**几期的跟进报道
    （例：07-W3 的「欧盟处罚 Google」命中 07-W4 的「Google 垂直搜索公平性仍受关注」）——
    那是正确的相似关系，但拿来阻止补录是错的用法。

    补录的行标 `backfilled: true`，与 `forced_reason` 分开：强行收录一条重复稿
    和补录一段缺失历史是两件事，混用一个字段以后就分不清了。
    """
    calendar_.parse_key(period)
    if force and not reason.strip():
        raise LedgerError("force 收录必须同时给出非空理由——理由会随条目写入台账。")

    rows = recent(load(base), weeks)
    no_url = [i.get("title", "") for i in items if not (i.get("url") or "").strip()]

    blocked: list[tuple[dict, list[Hit]]] = []
    if not force and not backfill:
        for item in items:
            hits = find_duplicates(item, rows, sim)
            if hits:
                blocked.append((item, hits))
    if blocked:
        return AddOutcome([], blocked, no_url)

    prepared = []
    for item in items:
        row = {
            "period": period,
            "date": item.get("date", ""),
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "url_norm": normalize_url(item.get("url", "")),
            "event_key": (item.get("event_key") or "").strip().lower(),
            "source": item.get("source", ""),
        }
        if force:
            row["forced_reason"] = reason.strip()
        if backfill:
            row["backfilled"] = True
        prepared.append(row)

    if commit and prepared:
        _append(base, prepared)
    return AddOutcome(prepared, [], no_url)


def _append(base, rows: list[dict]) -> None:
    path = ledger_path(base)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    payload = existing + "".join(
        json.dumps(row, ensure_ascii=False) + "\n" for row in rows
    )
    # 整份原子重写而不是追加：台账是判重依据，写坏一半比没写更糟。
    write_text_atomic(path, payload)


def periods(base) -> list[str]:
    order: list[str] = []
    for row in load(base):
        key = row_period(row)
        if key and key not in order:
            order.append(key)
    return order
