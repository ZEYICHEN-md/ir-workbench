"""news-digest 的运行状态。周期键 = month_week（如 `2026-08-W2`）。

五步，其中**只有第三步是人写的**——工具做召回、查重、校验、导出、沉淀，写字不自动化。
这条边界是刻意的：精选的价值在那两三句 so-what，那是判断，不是搬运。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workbench.manifest import Manifest
from workbench.paths import Paths

DOMAIN = "news-digest"


@dataclass(frozen=True)
class Step:
    key: str
    zh: str
    optional: bool
    gate: str | None
    hint: str
    #: 让这一步往前走所需的一句话。见 aviation_monthly/steps.py 的同名字段说明。
    phrase: str | None = None


#: 每一步都在**自己的产出存在时**完成，不依赖后面的步骤。
#:
#: 第一版把「登记去重台账」并进了 `recall`，于是 `recall` 只有在稿子定稿之后才能完成——
#: 步骤顺序被自己破坏了。后果是跨域汇总把写稿那几天的正常状态报成「有 1 处卡住」
#: （`recall` 停在 `running` 且无门禁）。中途状态被报成故障，人就会开始忽略这一栏。
#: 现在台账登记是独立一步，排在定稿之后。
STEPS: tuple[Step, ...] = (
    Step("recall", "召回候选并查重", False, None, "ir news recall --period …"),
    Step(
        "draft",
        "写稿（人写）",
        False,
        "由人撰写，工具不代写",
        "照 SKILL.md 的骨架写两节，放 outputs/news-digest/<期次>/",
        phrase="稿子写好了",
    ),
    Step("validate", "校验交付物结构", False, None, "ir news validate --period …"),
    Step("export", "导出 HTML / PDF", True, None, "ir news export --period …"),
    Step("log", "登记去重台账", False, None, "ir news log --period … --commit"),
    Step(
        "deposit",
        "沉淀进竞对情报库",
        False,
        "打标是草稿，须核对后入库",
        "ir intel deposit → --commit",
        phrase="沉淀这期新闻",
    ),
    Step(
        "publish",
        "发布到飞书",
        True,
        "对外发布，须用户明确要求",
        "照 modules/news_digest/references/feishu-publish.md 走 lark-cli",
        phrase="发到飞书",
    ),
)

STEP_ORDER = [step.key for step in STEPS]
STEP_BY_KEY = {step.key: step for step in STEPS}


def open_manifest(base: Paths, period: str) -> Manifest:
    manifest = Manifest(base, DOMAIN, period)
    manifest.ensure_steps(STEP_ORDER)
    return manifest


def record(
    base: Paths,
    period: str,
    step: str,
    state: str,
    *,
    note: str | None = None,
    inputs: dict[str, Path] | None = None,
    outputs: dict[str, Path] | None = None,
) -> Manifest:
    manifest = open_manifest(base, period)
    for label, path in (inputs or {}).items():
        manifest.record_input(label, path)
    for label, path in (outputs or {}).items():
        manifest.record_output(label, path)
    manifest.set_step(step, state, note)
    return manifest


def progress(base: Paths, period: str) -> dict:
    manifest = Manifest(base, DOMAIN, period)
    if not manifest.exists:
        return {
            "period": period, "done": 0, "total": len(STEP_ORDER),
            "next": STEP_ORDER[0], "stuck": [], "states": {},
        }
    steps = manifest.load()["steps"]
    done = [k for k, v in steps.items() if v.get("state") in {"done", "skipped"}]
    return {
        "period": period,
        "done": len(done),
        "total": len(STEP_ORDER),
        "next": manifest.next_pending(STEP_ORDER),
        "stuck": [k for k, v in steps.items() if v.get("state") in {"blocked", "failed"}],
        "states": {k: steps.get(k, {}).get("state", "pending") for k in STEP_ORDER},
    }


def render_progress(base: Paths, period: str) -> list[dict]:
    info = progress(base, period)
    states = info["states"]
    level_of = {
        "done": "ok", "skipped": "ok", "running": "warn",
        "pending": "warn", "blocked": "fail", "failed": "fail",
    }
    label_of = {
        "done": "完成", "skipped": "跳过", "running": "进行中",
        "pending": "待办", "blocked": "被拦住", "failed": "失败",
    }
    rows = []
    for step in STEPS:
        state = states.get(step.key, "pending")
        suffix = "（可选）" if step.optional else ""
        detail = label_of.get(state, state)
        if state == "pending" and step.gate:
            detail = f"待办 · 门禁：{step.gate}"
        rows.append(
            {"name": f"{step.zh}{suffix}", "level": level_of.get(state, "warn"), "detail": detail}
        )
    return rows
