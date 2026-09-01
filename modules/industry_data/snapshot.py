"""指标快照的全量重建与 diff 门禁（ADR 0001）。

行为与旧的 `merge_b1` **相反**：Excel 单元格为空 = 该数据不存在，重建后快照对应
位置为空。容错不再来自「保留旧值」，而来自下面这道 diff 门禁。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from workbench.fileio import write_text_atomic
from workbench.result import Result

from . import excel
from .jsonio import dumps_canonical
from .normalize import normalize
from .paths import DOMAIN, DomainPaths

#: 底稿里没有、但快照需要的固定口径说明。
#: 刻意放在代码常量而非本机配置——它们描述工作簿的固定口径，不是机器相关设置。
SNAPSHOT_META: dict[str, str] = {
    "dataSource": "STR、民航局、三大航、国铁、航班管家、飞常准",
    "compareBase": "同比2025年（国际航班运力为同比2019年）",
}

#: 出现清空即列出等确认；超过下面任一阈值直接 blocked（疑似结构变化或读错）
CLEAR_BLOCK_COUNT = 10
CLEAR_BLOCK_RATIO = 0.30
#: 比例规则的最小样本量。序列太短时比例没有判别力（1/1 就是 100%），
#: 这种情况只由数量规则管。
CLEAR_RATIO_MIN_SAMPLE = 5

#: 判定「数值变了」的相对容差。
#:
#: 这些值都是同比变化率（小数，如 0.05 = +5%），来自 Excel 的缓存计算值。
#: 底稿被 Excel 重新保存后，缓存值的写法会变——实测同一个数出现过
#: `-0.10400000000000009` 与 `-0.104`、`-0.1267375454145524` 与 `-0.126737545414552`
#: 两种形态（Excel 按 15 位有效数字写出）。按 `!=` 直接比会把这些当成「修改」。
#:
#: 为什么这很危险：runbook 让使用者核对的关键信号正是「修改应为 0」。一次换表
#: 就报十几处假修改，真的那一处混在里面根本分不出来——门禁失去意义。
#: 1e-9 对业务无影响（同比率的第 7 位小数以后没有意义），但足够吸收浮点尾数。
VALUE_REL_TOLERANCE = 1e-9

_PERIOD_LABEL_KEY = {"weekly": "weeks", "monthly": "months"}


def values_differ(old: Any, new: Any) -> bool:
    """两个值是否算「不同」。数值按相对容差比，非数值按相等比。"""
    if isinstance(old, bool) or isinstance(new, bool):
        return old != new
    if isinstance(old, (int, float)) and isinstance(new, (int, float)):
        scale = max(abs(old), abs(new))
        if scale == 0:
            return False
        return abs(old - new) > VALUE_REL_TOLERANCE * scale
    return old != new


@dataclass
class Change:
    where: str
    label: str
    metric: str
    old: Any
    new: Any

    def describe(self) -> str:
        return f"{self.where} · {self.label} · {self.metric}：{self.old} → {self.new}"


@dataclass
class Diff:
    cleared: list[Change] = field(default_factory=list)
    changed: list[Change] = field(default_factory=list)
    added: list[Change] = field(default_factory=list)
    new_labels: list[str] = field(default_factory=list)
    dropped_labels: list[str] = field(default_factory=list)
    #: 时间标签整个从轴上消失而丢掉的已有数值。与 `cleared`（标签还在、格变空）分开记，
    #: 因为二者的排查方向完全不同：前者是轴被截断/改版，后者是有人删了格里的数。
    dropped_values: list[Change] = field(default_factory=list)
    #: 序列名 → (被清空格数, 该序列原有非空格数)
    clear_ratio: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not (self.cleared or self.changed or self.added or self.new_labels or self.dropped_labels)

    @property
    def lost(self) -> list[Change]:
        """所有「原来有、重建后没了」的值。门禁一律按这个口径算。

        旧实现只按 `cleared` 算，而 `cleared` 是在**新轴的标签**上逐格比出来的——
        标签本身从轴上消失时一格都不会命中。实测因此漏过一次 9 周 × 6 序列的丢失，
        报「清空 0」并把快照写了回去。
        """
        return self.cleared + self.dropped_values

    @property
    def changed_periods(self) -> list[str]:
        """本次真正动过的粒度，固定按 weekly → monthly → quarterly 返回。

        洞察只该刷新实际变动的粒度。以前 merge 只给「新增/修改/清空」总数，Agent 不知道
        这些变化落在哪一层，只能把周/月/季全部标旧、全部重写；而同一数据截至日下换修订版
        底稿时，仅靠 `dataUpdate` 也判断不出来。这里直接从逐格 diff 得出唯一答案。
        """
        touched = {
            change.where
            for change in [*self.cleared, *self.changed, *self.added, *self.dropped_values]
        }
        touched.update(item.split(" · ", 1)[0] for item in [*self.new_labels, *self.dropped_labels])
        return [period for period in ("weekly", "monthly", "quarterly") if period in touched]

    @property
    def blocked_reasons(self) -> list[str]:
        reasons = []
        if self.dropped_labels:
            reasons.append(
                f"底稿里少了 {len(self.dropped_labels)} 个时间标签"
                f"（{'、'.join(lab.split(' · ')[-1] for lab in self.dropped_labels[:6])}"
                f"{'…' if len(self.dropped_labels) > 6 else ''}），"
                f"连带丢掉 {len(self.dropped_values)} 个已有数值。"
                "时间轴只应变长；变短基本都是读表被截断或底稿改版"
            )
        if len(self.lost) > CLEAR_BLOCK_COUNT:
            reasons.append(
                f"本次会丢掉 {len(self.lost)} 格数据，超过阈值 {CLEAR_BLOCK_COUNT}"
            )
        for metric, (cleared, total) in sorted(self.clear_ratio.items()):
            if total >= CLEAR_RATIO_MIN_SAMPLE and cleared / total > CLEAR_BLOCK_RATIO:
                reasons.append(
                    f"序列「{metric}」被清空 {cleared}/{total}（{cleared / total:.0%}），"
                    f"超过阈值 {CLEAR_BLOCK_RATIO:.0%}"
                )
        return reasons


def _diff_series_block(where: str, old_block: dict, new_block: dict, label_key: str, diff: Diff) -> None:
    old_labels = list(old_block.get(label_key) or [])
    new_labels = list(new_block.get(label_key) or [])
    diff.new_labels.extend(f"{where} · {lab}" for lab in new_labels if lab not in old_labels)
    gone = [lab for lab in old_labels if lab not in new_labels]
    diff.dropped_labels.extend(f"{where} · {lab}" for lab in gone)

    metrics = sorted(set(old_block) | set(new_block) - {label_key})
    # 消失的标签上原有的每个值都是实际丢失，逐格记下来，否则门禁看不见（见 Diff.lost）
    for label in gone:
        old_index = old_labels.index(label)
        for metric in metrics:
            if metric == label_key:
                continue
            old_values = old_block.get(metric) or []
            old_value = old_values[old_index] if old_index < len(old_values) else None
            if old_value is not None:
                diff.dropped_values.append(Change(where, str(label), metric, old_value, None))

    for metric in metrics:
        if metric == label_key:
            continue
        old_values = old_block.get(metric) or []
        new_values = new_block.get(metric) or []
        cleared_count = 0
        old_non_empty = 0
        for index, label in enumerate(new_labels):
            new_value = new_values[index] if index < len(new_values) else None
            old_value = None
            if label in old_labels:
                old_index = old_labels.index(label)
                if old_index < len(old_values):
                    old_value = old_values[old_index]
            if old_value is not None:
                old_non_empty += 1
            change = Change(where, str(label), metric, old_value, new_value)
            if old_value is not None and new_value is None:
                diff.cleared.append(change)
                cleared_count += 1
            elif old_value is None and new_value is not None:
                diff.added.append(change)
            elif new_value is not None and values_differ(old_value, new_value):
                diff.changed.append(change)
        if cleared_count:
            diff.clear_ratio[f"{where}.{metric}"] = (cleared_count, old_non_empty)


def compute_diff(old: dict, new: dict) -> Diff:
    diff = Diff()
    for period, label_key in _PERIOD_LABEL_KEY.items():
        _diff_series_block(period, old.get(period) or {}, new.get(period) or {}, label_key, diff)

    old_q = old.get("quarterly") or {}
    new_q = new.get("quarterly") or {}
    for quarter in sorted(set(old_q) | set(new_q)):
        if quarter not in old_q:
            diff.new_labels.append(f"quarterly · {quarter}")
        if quarter not in new_q:
            diff.dropped_labels.append(f"quarterly · {quarter}")
        old_row = old_q.get(quarter) or {}
        new_row = new_q.get(quarter) or {}
        for metric in sorted(set(old_row) | set(new_row)):
            old_value = old_row.get(metric)
            new_value = new_row.get(metric)
            change = Change("quarterly", quarter, metric, old_value, new_value)
            if old_value is not None and new_value is None:
                diff.cleared.append(change)
                diff.clear_ratio.setdefault(f"quarterly.{metric}", (0, 0))
                cleared, total = diff.clear_ratio[f"quarterly.{metric}"]
                diff.clear_ratio[f"quarterly.{metric}"] = (cleared + 1, total + 1)
            elif old_value is None and new_value is not None:
                diff.added.append(change)
            elif new_value is not None and values_differ(old_value, new_value):
                diff.changed.append(change)
    return diff


def build(workbook: Path, previous: dict | None) -> dict:
    """从底稿构造完整快照（含 meta 盖章）。不读旧值，只用 meta 里的口径常量。"""
    parsed = excel.parse(workbook)
    meta = dict(SNAPSHOT_META)
    meta["sourceExcel"] = workbook.name
    data_update = excel.infer_data_update((parsed.get("weekly") or {}).get("weeks") or [])
    if data_update:
        meta["dataUpdate"] = data_update
    elif previous:
        meta["dataUpdate"] = (previous.get("meta") or {}).get("dataUpdate", "")
    # 与既有快照的键序一致：dataUpdate 在前
    ordered = {}
    for key in ("dataUpdate", "dataSource", "compareBase", "sourceExcel"):
        if key in meta:
            ordered[key] = meta[key]
    return {
        "weekly": parsed["weekly"],
        "monthly": parsed["monthly"],
        "quarterly": parsed["quarterly"],
        "meta": ordered,
        # 只用于把读表提醒带给 `rebuild`，写快照前会被 pop 掉。
        # 用下划线前缀并单独 pop，是为了让测试里那些 `build = lambda w, p: {...}`
        # 的替身照旧能用——它们不会带这个键，pop 拿到空列表即可。
        "_diagnostics": list(parsed.get("diagnostics") or []),
    }


def _render_changes(changes: list[Change], limit: int = 12) -> list[str]:
    shown = [change.describe() for change in changes[:limit]]
    if len(changes) > limit:
        shown.append(f"…另有 {len(changes) - limit} 处")
    return shown


def rebuild(paths: DomainPaths, workbook: Path, *, confirm_clears: bool = False) -> Result:
    """重建指标快照。出现清空时默认停下等确认。"""
    previous: dict | None = None
    if paths.snapshot.is_file():
        previous = json.loads(paths.snapshot.read_text(encoding="utf-8"))

    try:
        fresh = build(workbook, previous)
    except excel.ExcelLayoutError as error:
        return Result(
            status="blocked",
            summary=f"底稿结构与预期不符：{error}",
            domain=DOMAIN,
            next_steps=[
                "核对底稿是否换了版式或加了新年度块。",
                "结构确实变了的话，先更新读表契约再重跑，不要绕过。",
            ],
        )

    read_notes = list(fresh.pop("_diagnostics", []) or [])

    # 归一到有效精度，消除浮点尾数噪音。
    # 同一个数在「人手动保存 Excel」与「COM 全量重算后保存」下表示不同
    # （`-0.104` 对 `-0.10400000000000009`），会让每次上线的 diff 掺进十几行
    # 无意义变化，把真正的数据变化埋掉。见 normalize.py。
    fresh = normalize(fresh)

    diff = compute_diff(previous or {}, fresh)
    data_update = fresh["meta"].get("dataUpdate", "")

    blocked = diff.blocked_reasons

    # 数据截至日只应往后走。倒退说明读到的周轴比上一版短，或锁错了底稿——
    # 这两种都会让看板整体退回旧日期，而逐格 diff 未必超阈值，所以单独设一道。
    previous_update = ((previous or {}).get("meta") or {}).get("dataUpdate") or ""
    if previous_update and data_update and data_update < previous_update:
        blocked = [
            f"数据截至日倒退：上一版 {previous_update} → 本次 {data_update}。"
            "要么锁的底稿比上一版旧，要么周轴被截断了",
            *blocked,
        ]

    if blocked:
        return Result(
            status="blocked",
            summary="重建被拦下：本次会丢数据，疑似底稿结构变化或读错列。",
            domain=DOMAIN,
            period=data_update or None,
            warnings=[*blocked, *read_notes],
            missing=_render_changes(diff.lost),
            next_steps=[
                "先确认底稿列位没变（周轴 R、酒店 S/T/U、航空 W/X/Y），周轴中间没被插空行。",
                "确实是有意清空的话，让 Agent 带上「确认清空」再跑一次。",
            ],
            data={"cleared": len(diff.cleared), "dropped": len(diff.dropped_values)},
        )

    if diff.lost and not confirm_clears:
        return Result(
            status="partial",
            summary=f"重建会丢掉 {len(diff.lost)} 格数据，未写入，等你确认。",
            domain=DOMAIN,
            period=data_update or None,
            warnings=read_notes,
            checks=[{"name": "将丢失", "level": "warn", "detail": item} for item in _render_changes(diff.lost)],
            next_steps=[
                "这些格在底稿里现在是空的。若是有意撤回，回一句「确认清空」即可写入。",
                "若不该是空的，先去底稿补上再重跑。",
            ],
            data={"cleared": len(diff.cleared), "dropped": len(diff.dropped_values)},
        )

    write_text_atomic(paths.snapshot, dumps_canonical(fresh) + "\n")

    checks = [
        {"name": "数据截至", "level": "ok", "detail": data_update or "（未能推断）"},
        {"name": "底稿", "level": "ok", "detail": workbook.name},
        {
            "name": "变动",
            "level": "ok",
            "detail": (
                f"新增 {len(diff.added)} · 修改 {len(diff.changed)} · "
                f"清空 {len(diff.cleared)} · 标签消失丢值 {len(diff.dropped_values)}"
            ),
        },
    ]
    if diff.new_labels:
        checks.append({"name": "新时间标签", "level": "ok", "detail": "、".join(diff.new_labels[:8])})
    checks.append(
        {
            "name": "实际变动粒度",
            "level": "ok",
            "detail": "、".join(diff.changed_periods) if diff.changed_periods else "无",
        }
    )

    # 正常每周只新增，历史值被改动是要人核对的信号——所以列明细，不只报数量。
    # 只给数量的话，事后无从判断改的是哪一格（快照已被覆盖，无处可查）。
    warnings: list[str] = list(read_notes)
    checks.extend({"name": "底稿填写", "level": "warn", "detail": note} for note in read_notes)
    if diff.changed:
        warnings.append(
            f"有 {len(diff.changed)} 处历史值被改动。正常每周只应新增；"
            "请核对是有意修正还是填错了行。"
        )
        checks.extend(
            {"name": "已修改", "level": "warn", "detail": item}
            for item in _render_changes(diff.changed)
        )

    return Result(
        status="success",
        summary="指标快照已按底稿重建。",
        warnings=warnings,
        domain=DOMAIN,
        period=data_update or None,
        checks=checks,
        # 「下一步是什么」由状态机（steps.py）统一给出，这里不硬编码，避免两处不一致
        data={
            "dataUpdate": data_update,
            "added": len(diff.added),
            "changed": len(diff.changed),
            "cleared": len(diff.cleared),
            "dropped": len(diff.dropped_values),
            "changedPeriods": diff.changed_periods,
        },
    )
