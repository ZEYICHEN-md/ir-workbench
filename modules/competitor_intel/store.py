"""JSONL 真源 + 其他桶注册表。

## 为什么是 JSONL 而不是一个大 JSON 数组

沿用工作台已验证的「真源 + 投影」（ADR 0002 §10）。JSONL 的三个好处都是这里真需要的：

- **可追加**：每周沉淀是往后加，不该重写整份文件；
- **diff 干净**：新增 9 条就是 +9 行，一眼看得出这周加了什么。大 JSON 数组重排序会让
  diff 变成整份重写——这个坑在 `industry-data` 上已经付过一次代价（浮点尾数那次）；
- **坏一行不毁全库**：解析失败只丢那一行，且能指出是第几行。

## 幂等

追加按 `id` 去重。同一条重复沉淀直接跳过并计数，不报错——每周自动沉淀重跑是正常操作，
不该因此失败。

## 其他桶注册表为什么是数据而不是代码

见 `vocab.py` 的模块说明。这里只负责存：`data/intel/companies.json`，`键 → 首次登记时的原名`。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from workbench.fileio import write_text, write_text_atomic
from workbench.paths import Paths

from .entry import Entry, EntryError, make_id, normalize

ENTRIES_NAME = "entries.jsonl"
REGISTRY_NAME = "companies.json"


@dataclass
class AddOutcome:
    """一次追加的结果。dry-run 与真写用同一个形状，方便 diff 前后对照。"""

    added: list[Entry]
    skipped: list[Entry]          # id 已存在
    rejected: list[tuple[int, str]]   # (序号, 原因)
    new_companies: dict[str, str]     # 本次要登记进其他桶的

    @property
    def counts(self) -> dict[str, int]:
        return {
            "added": len(self.added),
            "skipped": len(self.skipped),
            "rejected": len(self.rejected),
            "new_companies": len(self.new_companies),
        }


class Store:
    def __init__(self, base: Paths) -> None:
        self.base = base
        self.root = base.intel
        self.entries_file = self.root / ENTRIES_NAME
        self.registry_file = self.root / REGISTRY_NAME

    # --- 读 ---

    def load(self) -> list[Entry]:
        """读全部条目。坏行**报到行号**再抛——库越大越需要知道是哪一行。"""
        if not self.entries_file.is_file():
            return []
        out: list[Entry] = []
        for lineno, line in enumerate(
            self.entries_file.read_text(encoding="utf-8").splitlines(), start=1
        ):
            text = line.strip()
            if not text:
                continue
            try:
                out.append(Entry.from_dict(json.loads(text)))
            except (json.JSONDecodeError, TypeError) as exc:
                raise EntryError(
                    f"{self.entries_file} 第 {lineno} 行解析失败：{exc}"
                ) from exc
        return out

    def ids(self) -> set[str]:
        return {e.id for e in self.load() if e.id}

    def registry(self) -> dict[str, str]:
        if not self.registry_file.is_file():
            return {}
        return json.loads(self.registry_file.read_text(encoding="utf-8"))

    # --- 写 ---

    def add(self, entries: list[Entry], *, commit: bool) -> AddOutcome:
        """校验 + 去重 + （可选）落盘。

        `commit=False` 时**完全无副作用**——包括不登记新公司。dry-run 必须能反复跑。
        """
        existing = self.ids()
        registry = self.registry()
        added: list[Entry] = []
        skipped: list[Entry] = []
        rejected: list[tuple[int, str]] = []
        new_companies: dict[str, str] = {}
        seen_in_batch: set[str] = set()

        for index, raw in enumerate(entries, start=1):
            # **先查在不在库里，再校验。**顺序反了会让已入库的条目被报成「待处理」：
            # 重新沉淀同一期时，草稿是重新解析的、主题又是猜的，猜不出就抛错，
            # 于是一条早已在库且标签都核过的条目看起来像还有活要干。
            probe = raw.id or (
                make_id(raw.date, raw.url, raw.title)
                if raw.date and raw.title else None
            )
            if probe and (probe in existing or probe in seen_in_batch):
                raw.id = probe
                skipped.append(raw)
                seen_in_batch.add(probe)
                continue
            try:
                item, unregistered = normalize(raw, registry=registry)
            except (EntryError, Exception) as exc:  # noqa: BLE001 —— 词表错误也要落到这里
                rejected.append((index, str(exc)))
                continue
            for name in unregistered:
                from . import vocab

                key = vocab.normalize_other(name)
                if key not in registry and key not in new_companies:
                    new_companies[key] = name
            if item.id in existing or item.id in seen_in_batch:
                skipped.append(item)
                continue
            seen_in_batch.add(item.id)
            added.append(item)

        if commit and (added or new_companies):
            self._append(added)
            if new_companies:
                merged = {**registry, **new_companies}
                write_text_atomic(
                    self.registry_file,
                    json.dumps(dict(sorted(merged.items())), ensure_ascii=False, indent=2) + "\n",
                )

        return AddOutcome(added, skipped, rejected, new_companies)

    def replace(self, entries: list[Entry]) -> None:
        """整份重写。

        ADR 0002 说打标「自动，事后可改」，但一开始只有追加没有改——那条「可改」是空话。
        改标签必须能重写，所以有这个方法。

        原子重写而不是就地改行：真源写坏一半比没写更糟。id 不变，所以重写后
        `add()` 的幂等仍然成立。
        """
        payload = "".join(
            json.dumps(e.to_dict(), ensure_ascii=False, sort_keys=True) + "\n" for e in entries
        )
        write_text_atomic(self.entries_file, payload)

    def _append(self, entries: list[Entry]) -> None:
        if not entries:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps(e.to_dict(), ensure_ascii=False, sort_keys=True) for e in entries
        ]
        payload = "\n".join(lines) + "\n"
        if self.entries_file.is_file():
            # 追加也必须写 LF：这份文件进 git，CRLF 会让每周新增显示成全文改写。
            with open(self.entries_file, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
        else:
            write_text(self.entries_file, payload)


def load_entries(base: Paths) -> list[Entry]:
    return Store(base).load()


def entries_path(base: Paths) -> Path:
    return Store(base).entries_file
