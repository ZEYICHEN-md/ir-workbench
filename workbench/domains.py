"""七个域的注册表。

这是 ADR 0003 的可执行版本：域的划分、对外/内部定位、节奏与周期键语义
都在这里定义一次，其余代码不得另行硬编码域名。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Facing = Literal["external", "internal"]
ValidationState = Literal["validated", "partial", "lightweight", "unvalidated"]
PeriodKind = Literal[
    "month_week", "data_date", "year_month", "fiscal_quarter", "query_date", "run_id", "none"
]

#: 周期键格式。刻意不统一——一套 period 语义装不下四种节奏（ADR 0003 §3）。
#: **一律 ASCII**：周期键会作为命令行参数和目录名出现，中文在这两处都不安全（ADR 0007）。
#: 给人看的中文标签由 `period_label()` 生成，不作为键。
PERIOD_PATTERNS: dict[str, str] = {
    "month_week": r"^20\d{2}-(0[1-9]|1[0-2])-W[1-5]$",
    "data_date": r"^20\d{2}-\d{2}-\d{2}$",
    "year_month": r"^20\d{4}$",
    "fiscal_quarter": r"^\d{2}Q[1-4]$",
    "query_date": r"^20\d{2}-\d{2}-\d{2}$",
    "run_id": r"^20\d{6}-(?:[01]\d|2[0-3])[0-5]\d[0-5]\d$",
    "none": r"^$",
}

PERIOD_EXAMPLES: dict[str, str] = {
    "month_week": "2026-08-W2",
    "data_date": "2026-08-08",
    "year_month": "202607",
    "fiscal_quarter": "26Q2",
    "query_date": "2026-08-22",
    "run_id": "20260822-143015",
    "none": "（无周期）",
}

_MONTH_WEEK = re.compile(r"^(20\d{2})-(\d{2})-W([1-5])$")
_YEAR_MONTH = re.compile(r"^(20\d{2})(\d{2})$")


def period_label(kind: str, period: str) -> str:
    """周期键 → 给人看的中文标签。键本身永远是 ASCII。"""
    if kind == "month_week":
        match = _MONTH_WEEK.match(period)
        if match:
            year, month, week = match.groups()
            return f"{year}年{int(month)}月第{week}周"
    elif kind == "year_month":
        match = _YEAR_MONTH.match(period)
        if match:
            year, month = match.groups()
            return f"{year}年{int(month)}月"
    elif kind == "data_date":
        return f"数据截至 {period}"
    elif kind == "fiscal_quarter":
        return f"20{period[:2]} {period[2:]}"
    return period


@dataclass(frozen=True)
class Domain:
    key: str
    zh: str
    facing: Facing
    cadence: str
    period_kind: PeriodKind
    summary: str
    #: 迁移来源，供 docs/MIGRATION.md 与 doctor 核对
    origin: str
    #: 真实业务验收状态；与目录存在、CLI/health 能否导入分别报告（ADR 0008）。
    validation_state: ValidationState
    validation_note: str

    @property
    def period_example(self) -> str:
        return PERIOD_EXAMPLES[self.period_kind]

    def validate_period(self, period: str) -> bool:
        return bool(re.match(PERIOD_PATTERNS[self.period_kind], period or ""))

    def label(self, period: str) -> str:
        """给人看的中文标签。用于汇报与交付文件名，**不用作键或目录名**。"""
        return period_label(self.period_kind, period)


DOMAINS: dict[str, Domain] = {
    "news-digest": Domain(
        key="news-digest",
        zh="旅行行业新闻精选",
        facing="external",
        cadence="每周",
        period_kind="month_week",
        summary="唯一对外交付物。写完自动沉淀进竞对情报库。",
        origin="0703_Travel_Pulse/travel-weekly-report（新闻章）",
        validation_state="validated",
        validation_note="已完成一期真实采编、导出、沉淀与授权后发布验收。",
    ),
    "industry-data": Domain(
        key="industry-data",
        zh="国内行业数据与看板",
        facing="internal",
        cadence="每周 / 每月",
        period_kind="data_date",
        summary="指标底稿 Excel → 指标快照 → 看板 / 飞书投影 / 洞察。",
        origin="database_matain",
        validation_state="validated",
        validation_note="已完成真实周度更新、上线与回滚验收。",
    ),
    "aviation-monthly": Domain(
        key="aviation-monthly",
        zh="航空月度数据写入",
        facing="internal",
        cadence="每月",
        period_kind="year_month",
        summary="民航局与三大航月度数据校验后写入指标底稿四个目标格。",
        origin="0703_Travel_Pulse/aviation-monthly-data-pipeline",
        validation_state="validated",
        validation_note="已完成真实月份官方数据写入与下游重建验收。",
    ),
    "hk-market": Domain(
        key="hk-market",
        zh="港股市场数据",
        facing="internal",
        cadence="按需",
        period_kind="query_date",
        summary="行情、南向持股、港美成交额占比（FY 口径）。内部查询，不对外。",
        origin="0703_Travel_Pulse/hk-volume-ratio + travel-weekly-report/scripts",
        validation_state="validated",
        validation_note="三类真实查询均已完成验收。",
    ),
    "competitor-intel": Domain(
        key="competitor-intel",
        zh="竞对情报库",
        facing="internal",
        cadence="每周 / 每季 / 按访谈",
        period_kind="month_week",
        summary="按公司与主题累积 peers 动态。三条采集通道：新闻、财报口径、专家访谈。",
        origin="新建（ADR 0002）",
        validation_state="validated",
        validation_note="周度、季度与专家访谈通道均已有真实数据验收。",
    ),
    "expert-calls": Domain(
        key="expert-calls",
        zh="专家访谈情报与精选",
        facing="internal",
        cadence="按访谈到达",
        period_kind="run_id",
        summary="访谈 PDF → 先生成内部情报草稿供核对入库；独立排序后再由人选择飞书 callout。",
        origin="database_matain/.cursor/skills/expert-call-pipeline",
        validation_state="validated",
        validation_note="真实批次已完成飞书回读；34 条情报已全量分流为 A 类 11 条正式入库、B 类 14 条待核、9 条剔除。",
    ),
    "sellside-research": Domain(
        key="sellside-research",
        zh="卖方研报摘读",
        facing="internal",
        cadence="按需",
        period_kind="none",
        summary="研报 PDF 摘读。轻量能力，不建持久档案（ADR 0004）。",
        origin="0703_Travel_Pulse/inputs 研报处理",
        validation_state="lightweight",
        validation_note="真实研报已验收；按 ADR 0004 有意不建 manifest 或跨期档案。",
    ),
}

EXTERNAL_DOMAINS = [d.key for d in DOMAINS.values() if d.facing == "external"]
INTERNAL_DOMAINS = [d.key for d in DOMAINS.values() if d.facing == "internal"]


def get(key: str) -> Domain:
    try:
        return DOMAINS[key]
    except KeyError:
        known = "、".join(DOMAINS)
        raise KeyError(f"未知域 {key!r}；已知域：{known}") from None
