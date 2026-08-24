"""看板投影：指标快照 → data.js，洞察底稿 → insights.js。

投影是单向的：看板文件永远不回写权威。
"""

from __future__ import annotations

import json

from workbench.fileio import write_text
from workbench.result import Result

from . import insights as insights_mod
from . import steps
from .jsonio import dumps
from .paths import DOMAIN, DomainPaths

DATA_HEADER = """// ============================================================
// 旅游行业数据看板 - 由指标快照生成，请勿手改
// 权威：指标底稿 data/workbooks/（Excel）
// 快照：data/canonical/travel.json
// 重新生成：ir industry generate-dashboard
// 所有数值均为"同比变化率"（小数形式，如 0.05 = +5%）
// ============================================================

const DATA = """

INSIGHTS_HEADER = """// ============================================================
// 旅游看板洞察投影 — 请勿手改
// 权威：data/canonical/travel-insights.json
// 重新生成：ir industry generate-dashboard
// ============================================================

const INSIGHTS = """


def write_data_js(paths: DomainPaths) -> None:
    if not paths.snapshot.is_file():
        raise FileNotFoundError(f"缺少指标快照：{paths.snapshot}")
    data = json.loads(paths.snapshot.read_text(encoding="utf-8"))
    write_text(paths.data_js, DATA_HEADER + dumps(data) + ";\n")


def write_insights_js(paths: DomainPaths, data: dict) -> None:
    insights_mod.validate(data)
    write_text(paths.insights_js, INSIGHTS_HEADER + dumps(data) + ";\n")


def generate(paths: DomainPaths) -> Result:
    checks: list[dict] = []
    warnings: list[str] = []

    write_data_js(paths)
    checks.append({"name": "看板数据", "level": "ok", "detail": str(paths.data_js.name)})

    if paths.insights_canonical.is_file():
        data = insights_mod.load(paths)
        write_insights_js(paths, data)
        checks.append({"name": "看板洞察", "level": "ok", "detail": str(paths.insights_js.name)})
        written = insights_mod.write_markdown(paths, data)
        checks.append(
            {"name": "洞察 Markdown", "level": "ok", "detail": f"{len(written)} 个文件"}
        )
        stale = [p for p in insights_mod.PERIODS if ((data.get("meta") or {}).get("stale") or {}).get(p)]
        if stale:
            warnings.append(
                "以下粒度的洞察可能已过期（指标更新后未重新确认）：" + "、".join(stale)
            )
        complete = True
    else:
        warnings.append("没有洞察底稿，只生成了看板数据。")
        complete = False

    return Result(
        status="partial" if warnings else "success",
        summary="看板投影已生成。",
        domain=DOMAIN,
        checks=checks,
        warnings=warnings,
        # 洞察过期只是提醒，四个投影文件都已写出——这一步算做完了。
        # 缺洞察底稿则是真没做完（insights.js 没生成），不能标完成。见 steps.step_state()
        data={steps.COMPLETE_KEY: complete},
        # 「下一步是什么」由状态机（steps.py）统一给出
    )
