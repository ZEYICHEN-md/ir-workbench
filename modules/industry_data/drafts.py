"""洞察草稿：出草稿（AI 填）→ 人确认中文 → 入库（再译英文）。

硬门禁（ADR：混合确认）：**未经人确认中文，不得写入洞察底稿。**
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from workbench.fileio import write_text
from workbench.result import Result

from . import dashboard, insights as insights_mod
from .jsonio import dumps
from .paths import DOMAIN, DomainPaths

CONSTRAINTS = {
    "tagsOnly": list(insights_mod.TAGS),
    "maxPerTag": insights_mod.MAX_PER_TAG,
    "emptyTagsOk": True,
    "noCrossPeriodNarrative": True,
    "eachItemNeedsRefsAndNumbers": True,
    "proseStyle": "research-brief-short",
    "language": "zh-first; translate en only after zh confirmed",
    "aiJudgesTags": True,
    "humanMustConfirmBeforeCanonicalWrite": True,
}

PROMPT_FOR_AI = "\n".join(
    [
        "根据 dataSlice 仅使用该粒度数据，为每周/月/季写出洞察草稿。",
        "标签只能是 highlight / risk / outlook；每标签最多 2 条；可缺槽。",
        "你负责归类与写句子；每条必须含可核对数字，并填 refs。",
        "显著变化阈值：周度 |同比|≥5%；月度/季度 |同比|≥3%；或季度环比摆动≥5个百分点。",
        "对显著变化可联网检索影响因素：事件/监测窗口必须与指标时间段重叠；仅相邻须写明「此前/背景」；窗口不对齐则省略归因。禁止硬凑、禁止错位时段。",
        "文笔（研报短评）：每条 2～3 句；结构为「数字 →（可选）一句归因 → 一句后续」；归因最多 1 句；展望不重复前面已写数字。",
        "禁止在正文写方法论/meta（如「本表」「本条」「不做归因」「窗口不对齐」）；语气直接肯定，少用公文腔。",
        "标题简短可扫读：亮点/风险用「指标+方向」，展望用「待验证问题」。",
        "先只写 zh；en 留空数组，待人确认中文后再译。",
        "禁止跨粒度叙事（周度稿不要写月度/季度故事）。",
    ]
)


def _slice_period(snapshot: dict, period: str) -> dict:
    if period not in insights_mod.PERIODS:
        raise ValueError(f"未知粒度：{period}")
    return {period: snapshot.get(period)}


def prepare(paths: DomainPaths, period: str | None = None) -> Result:
    if not paths.snapshot.is_file():
        return Result(
            status="blocked",
            summary=f"缺少指标快照：{paths.snapshot}",
            domain=DOMAIN,
            next_steps=["先跑一次数据更新（merge）生成快照。"],
        )
    periods = [period] if period else list(insights_mod.PERIODS)
    snapshot = json.loads(paths.snapshot.read_text(encoding="utf-8"))
    try:
        existing = insights_mod.load(paths)
    except insights_mod.InsightsError:
        existing = None

    paths.scratch.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    name = periods[0] if len(periods) == 1 else "all"
    out_path = paths.scratch / f"insights-draft-{name}-{stamp}.json"

    draft = {
        "status": "draft",
        "constraints": CONSTRAINTS,
        "basedOnTravelJsonUpdatedAt": (snapshot.get("meta") or {}).get("dataUpdate"),
        "periods": {},
        "promptForAi": PROMPT_FOR_AI,
    }
    for item in periods:
        draft["periods"][item] = {
            "dataSlice": _slice_period(snapshot, item),
            "currentConfirmedZh": ((existing or {}).get(item) or {}).get("zh") or [],
            "draftZh": [],
            "draftEn": [],
        }

    write_text(out_path, dumps(draft) + "\n")

    return Result(
        status="success",
        summary="洞察草稿包已生成，等 AI 填 draftZh。",
        domain=DOMAIN,
        checks=[
            {"name": "草稿包", "level": "ok", "detail": str(out_path)},
            {"name": "覆盖粒度", "level": "ok", "detail": "、".join(periods)},
        ],
        next_steps=[
            "按 promptForAi 填 draftZh（每条含可核对数字与 refs）。",
            "**人确认中文之后**才能入库（confirm）；英文在入库时再译。",
        ],
        data={"draft": str(out_path)},
    )


def confirm(paths: DomainPaths, draft_path: Path) -> Result:
    if not draft_path.is_file():
        return Result(status="failed", summary=f"找不到草稿包：{draft_path}", domain=DOMAIN)
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    data = insights_mod.load(paths)
    meta = data.setdefault("meta", {})
    meta.setdefault("stale", {})
    meta.setdefault("confirmedAt", {})
    if draft.get("basedOnTravelJsonUpdatedAt"):
        meta["basedOnTravelJsonUpdatedAt"] = draft["basedOnTravelJsonUpdatedAt"]

    today = _dt.datetime.now(_dt.timezone.utc).date().isoformat()
    updated: list[str] = []
    for period in insights_mod.PERIODS:
        block = (draft.get("periods") or {}).get(period)
        if not block:
            continue
        draft_zh = block.get("draftZh")
        if not isinstance(draft_zh, list) or not draft_zh:
            continue
        target = data.setdefault(period, {"zh": [], "en": []})
        target["zh"] = draft_zh
        draft_en = block.get("draftEn")
        if isinstance(draft_en, list) and draft_en:
            target["en"] = draft_en
        elif "en" not in target:
            target["en"] = []
        meta["stale"][period] = False
        meta["confirmedAt"][period] = today
        updated.append(period)

    if not updated:
        return Result(
            status="blocked",
            summary="草稿包里没有填好的 draftZh，未入库。",
            domain=DOMAIN,
            next_steps=["先把 periods.<粒度>.draftZh 填上再确认。"],
        )

    try:
        insights_mod.validate(data)
    except insights_mod.InsightsError as error:
        return Result(
            status="failed",
            summary=f"洞察校验未通过，未入库：{error}",
            domain=DOMAIN,
            next_steps=["按报错修草稿包（标签、条数、title/body、refs）再确认。"],
        )

    insights_mod.save(paths, data)
    dashboard.write_insights_js(paths, data)
    written = insights_mod.write_markdown(paths, data, archive=True)

    return Result(
        status="success",
        summary="洞察已入库并投影。",
        domain=DOMAIN,
        checks=[
            {"name": "已确认粒度", "level": "ok", "detail": "、".join(updated)},
            {"name": "洞察底稿", "level": "ok", "detail": str(paths.insights_canonical.name)},
            {"name": "投影", "level": "ok", "detail": f"insights.js + {len(written)} 个 Markdown"},
        ],
        data={"periods": updated},
    )
