"""交付物结构校验。

## 现在的骨架只有两节

```
# 📬 旅行行业新闻精选 | {年}年{月}月第{周}周
> 发布：…（周二）
> 情报主周：…

## 一、OTA/旅游行业新闻精选
> **本周概览**
> - …
**{图标} {中文标题}**
{一段中文分析}
…

## 二、新闻来源与数据说明
### 新闻来源
| 中文标题 | 英文原标题 | 媒体, 日期, URL |
```

## 五部分周报已停用

旧仓的骨架是五章（新闻 / 行业数据 / 卖方 / 港股 / 来源），最后一期是 `2026年7月第3周`。
之后三期只出新闻精选，说明它事实上早就停了。工作台正式停用它：

- 行业数据 → 看板（datamax.fun），不再抄进周报；
- 港股 → 内部查询（`hk-market`），不对外；
- 卖方 → `sellside-research` 按需摘读。

配套删掉的是旧仓 `report_validate.validate_section_two()` 那 7 条 §二 规则、
`workflow.complete()` 里「一二三四五标题齐全」的契约、以及 `section-two-review` 门禁。
**保留**的是情报主周核对（`validate_intelligence_week`）——它与骨架无关，仍有价值。

所以本模块反过来**主动拦五章格式**：出现 `## 三、` 及以后就报错。不拦的话，
半年后有人照着旧模板写，工具默默接受，对外就发出去了一份含港股与行业数据的稿子。

## 条目数必须等于来源表行数

这不是洁癖。竞对情报库的沉淀靠「正文条目与来源表同序一一对应」来拿日期和 URL
（见 `competitor_intel/backfill.py`）。数不等就配不上，配错了会给一条新闻挂上另一条的
来源和日期——那种错在成稿阶段没人看得出来。

## 关于携程当事方那条纪律

判定标准是语义的（「携程是不是这条新闻的当事方」），旧仓刻意**没有**把它写成代码，
理由是关键词规则会误杀。工作台加了一道**窄检查**：只看条目标题。

因为这个格式下标题就是「谁做了什么」，标题里出现携程，基本就是携程当事方。
代价不对称——误报一次只多一轮对话，漏一次就是对外交付物里出现了携程自己的动作
（AGENTS.md「绝对不做」第 2 条）。所以这一条判 error，不判 warn。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from . import calendar_

_HEADING = re.compile(r"^#\s*.*新闻精选\s*\|\s*(20\d{2})年(\d{1,2})月第([1-5])周", re.M)
_WEEK_LINE = re.compile(
    r"情报主周[：:]\s*(20\d{2})[/.-](\d{1,2})[/.-](\d{1,2})\s*[–\-~]\s*"
    r"(?:(20\d{2})[/.-])?(\d{1,2})[/.-](\d{1,2})"
)
_SECTION_ONE = re.compile(r"^##\s*一、", re.M)
_SECTION_TWO = re.compile(r"^##\s*二、", re.M)
_DEPRECATED_SECTIONS = re.compile(r"^##\s*([三四五])、(.*)$", re.M)
_INLINE_LINK = re.compile(r"\[[^\]]+\]\(https?://[^)]+\)")

#: 标题里出现这些就认为携程是当事方。只在**条目标题**上查，正文提及是允许的
#: （写 so-what 时常要提到对携程的影响）。
TCOM_IN_TITLE = ("携程", "Trip.com", "Ctrip", "TCOM")

#: 2026-08-W4 起强制提供逐条日期审计。历史成稿不补造字段，仍可重放。
_DATE_AUDIT_CUTOFF = date(2026, 8, 24)
_DATE_AUDIT_HEADING = re.compile(r"^###\s*事件日期与归期审计\s*$", re.M)
_AUDIT_COLUMNS = (
    "title", "event_date", "first_disclosure_date", "material_update_date",
    "article_date", "basis", "evidence", "delta",
)
_BASIS_ANCHOR = {
    "事件发生": "event_date",
    "首次披露": "first_disclosure_date",
    "实质跟进": "material_update_date",
    "报告发布": "event_date",
}
_EVIDENCE_LEVELS = {"官方/直接参与方", "主流媒体独立报道", "单一可信媒体", "未证实线索"}
_UNKNOWN_DATE = {"", "—", "-", "未知", "不详"}


def _requires_date_audit(period: str | None) -> bool:
    if not period:
        return False
    try:
        monday, _ = calendar_.intelligence_week(period)
    except calendar_.PeriodError:
        return False
    return monday >= _DATE_AUDIT_CUTOFF


def _parse_audit_date(value: str) -> date | None:
    probe = value.strip()
    if probe in _UNKNOWN_DATE:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(probe, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"日期应为 YYYY/MM/DD、YYYY-MM-DD 或‘未知’，收到 {value!r}")


def _date_audit_rows(text: str) -> list[dict[str, str]]:
    """读取 8 列日期审计表；多列桌面表不会被三列来源表解析器误收。"""
    match = _DATE_AUDIT_HEADING.search(text)
    if not match:
        return []
    tail = text[match.end():]
    next_heading = re.search(r"^###\s+", tail, re.M)
    block = tail[:next_heading.start()] if next_heading else tail
    rows: list[dict[str, str]] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(_AUDIT_COLUMNS):
            continue
        if cells[0] == "中文标题" or all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        rows.append(dict(zip(_AUDIT_COLUMNS, cells)))
    return rows


@dataclass
class Finding:
    level: str      # error | warn | info
    code: str
    message: str


@dataclass
class Review:
    period: str | None
    items: list[tuple[str, str]] = field(default_factory=list)
    source_rows: int = 0
    audit_rows: int = 0
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "warn"]

    @property
    def ok(self) -> bool:
        return not self.errors


def review(text: str, *, expect_period: str | None = None) -> Review:
    """校验一份新闻精选。只读，不改内容。"""
    from modules.competitor_intel import backfill

    out = Review(period=None)
    add = lambda level, code, message: out.findings.append(Finding(level, code, message))  # noqa: E731

    head = _HEADING.search(text)
    if not head:
        add("error", "heading-missing",
            "抬头不对。第一行应是 `# 📬 旅行行业新闻精选 | {年}年{月}月第{周}周`。")
    else:
        out.period = f"{head[1]}-{int(head[2]):02d}-W{head[3]}"
        if expect_period and out.period != expect_period:
            add("error", "period-mismatch",
                f"抬头写的是 {out.period}，但这一期是 {expect_period}。")

    # 五部分骨架已停用
    for match in _DEPRECATED_SECTIONS.finditer(text):
        add("error", "five-part-deprecated",
            f"出现已停用的第「{match[1]}」章（{match[2].strip()}）。五部分周报已停用："
            "行业数据看看板、港股走内部查询、卖方走 sellside-research。"
            "交付物只保留两节。")

    if not _SECTION_ONE.search(text):
        add("error", "section-one-missing", "缺 `## 一、OTA/旅游行业新闻精选`。")
    if not _SECTION_TWO.search(text):
        add("error", "section-two-missing", "缺 `## 二、新闻来源与数据说明`（含新闻来源表）。")

    # 情报主周与日历对账
    week = _WEEK_LINE.search(text)
    if not week:
        add("warn", "week-line-missing", "抬头缺 `> 情报主周：YYYY/MM/DD–MM/DD` 一行。")
    elif out.period:
        try:
            monday, sunday = calendar_.intelligence_week(out.period)
            written = (
                f"{int(week[2]):02d}-{int(week[3]):02d}",
                f"{int(week[5]):02d}-{int(week[6]):02d}",
            )
            actual = (f"{monday:%m-%d}", f"{sunday:%m-%d}")
            if written != actual:
                add("warn", "week-mismatch",
                    f"抬头写的情报主周 {week[2]}/{week[3]}–{week[5]}/{week[6]} 与"
                    f"{out.period} 实际的 {calendar_.week_label(out.period)} 不一致。")
        except calendar_.PeriodError as error:
            add("warn", "period-invalid", str(error))

    # 条目与来源表
    out.items = backfill.body_items(text)
    rows = backfill.source_rows(text)
    out.source_rows = len(rows)

    if not out.items:
        add("error", "no-items", "§一 里没有条目。条目格式是 `**{图标} {中文标题}**` + 空行 + 一段分析。")
    elif len(out.items) != len(rows):
        add("error", "item-source-mismatch",
            f"§一 有 {len(out.items)} 条，来源表有 {len(rows)} 行。两者必须一一对应且同序——"
            "情报库靠这个配对拿日期和 URL，数不等就会给一条新闻挂上另一条的来源。")
    else:
        for (title, _body), row in zip(out.items, rows):
            coverage = backfill.title_coverage(title, row["title_cn"])
            if coverage < backfill.COVERAGE_FLOOR:
                add("warn", "pairing-weak",
                    f"「{title}」与来源行「{row['title_cn']}」重合度 {coverage:.2f}，"
                    "疑似错位，请核对顺序。")

    # 从 W4 起，文章发布日期只负责发现，不能单独充当归期依据。
    audit_rows = _date_audit_rows(text)
    out.audit_rows = len(audit_rows)
    if _requires_date_audit(out.period):
        if not audit_rows:
            add("error", "date-audit-missing",
                "缺 `### 事件日期与归期审计`。从 2026-08-W4 起，每条必须交代事件日、"
                "首次披露日、实质进展日、文章日、归期依据、证据等级和本周信息增量。")
        elif len(audit_rows) != len(out.items):
            add("error", "date-audit-count-mismatch",
                f"正文有 {len(out.items)} 条，日期审计表有 {len(audit_rows)} 行，必须一一对应。")
        else:
            monday, sunday = calendar_.intelligence_week(out.period)
            for (title, _body), audit in zip(out.items, audit_rows):
                coverage = backfill.title_coverage(title, audit["title"])
                if coverage < backfill.COVERAGE_FLOOR:
                    add("warn", "date-audit-pairing-weak",
                        f"「{title}」与日期审计行「{audit['title']}」疑似错位。")

                parsed_dates: dict[str, date | None] = {}
                for field_name in ("event_date", "first_disclosure_date",
                                   "material_update_date", "article_date"):
                    try:
                        parsed_dates[field_name] = _parse_audit_date(audit[field_name])
                    except ValueError as error:
                        add("error", "date-audit-invalid-date", f"「{title}」：{error}")
                        parsed_dates[field_name] = None

                basis = audit["basis"]
                if basis not in _BASIS_ANCHOR:
                    add("error", "date-audit-invalid-basis",
                        f"「{title}」归期依据应为：{'、'.join(_BASIS_ANCHOR)}；收到 {basis!r}。")
                else:
                    anchor = parsed_dates[_BASIS_ANCHOR[basis]]
                    if anchor is None:
                        add("error", "date-audit-anchor-missing",
                            f"「{title}」选择“{basis}”归期，但对应锚点日期为空。")
                    elif not monday <= anchor <= sunday:
                        add("error", "date-audit-anchor-outside-week",
                            f"「{title}」的“{basis}”锚点是 {anchor:%Y/%m/%d}，"
                            f"不在情报主周 {monday:%Y/%m/%d}–{sunday:%m/%d}。"
                            "文章本周发布不能覆盖这个错误。")

                if parsed_dates["article_date"] is None:
                    add("error", "date-audit-article-date-missing",
                        f"「{title}」缺文章发布日期；它虽不决定归期，但必须用于溯源。")

                evidence = audit["evidence"]
                if evidence not in _EVIDENCE_LEVELS:
                    add("error", "date-audit-invalid-evidence",
                        f"「{title}」证据等级不合法：{evidence!r}。")
                elif evidence == "未证实线索":
                    add("error", "date-audit-unverified",
                        f"「{title}」仍是未证实线索，不能独立成条。")
                elif evidence == "单一可信媒体":
                    add("warn", "date-audit-single-source",
                        f"「{title}」只有单一可信媒体支持，正文须明确降低确定性。")

                if not audit["delta"].strip() or audit["delta"].strip() in {"—", "-", "无"}:
                    add("error", "date-audit-delta-missing",
                        f"「{title}」没有写清本周新增了什么信息。")

    for title, body in out.items:
        for needle in TCOM_IN_TITLE:
            if needle.lower() in title.lower():
                add("error", "tcom-as-subject",
                    f"条目标题出现「{needle}」：「{title}」。新闻精选不得写携程自己的动作与表述"
                    "（ADR 0002 §9）。正文里为写 so-what 提到携程是允许的，标题不行。")
                break
        if _INLINE_LINK.search(body):
            add("warn", "inline-link",
                f"「{title}」正文里带了链接。链接统一进来源表，正文不放。")
        if len(body) < 40:
            add("warn", "body-too-short",
                f"「{title}」正文只有 {len(body)} 字，像是没写完。")

    return out


def review_file(path: Path, *, expect_period: str | None = None) -> Review:
    return review(path.read_text(encoding="utf-8"), expect_period=expect_period)


def deliverable_name(period: str) -> str:
    """交付文件名用中文标签——它是给人看的，不穿命令行。"""
    return f"旅行行业新闻精选-{calendar_.label_from_key(period)}.md"
