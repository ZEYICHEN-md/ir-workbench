"""industry-data 的运行状态。

为什么需要：一条链如果只是「一串命令」，进度就只活在对话里——换个会话、换个人，
就不知道跑到哪、哪一步被门禁挡着。manifest 让进度脱离对话存活。

周期键 = **数据截至日**（`meta.dataUpdate`），由底稿最新一周的结束日推出，
所以只有 `merge` 跑完才知道本期是哪一期。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from workbench.manifest import Manifest
from workbench.paths import Paths

from .paths import DOMAIN, DomainPaths


@dataclass(frozen=True)
class Step:
    key: str
    zh: str
    optional: bool
    gate: str | None
    hint: str
    #: 让这一步**往前走**所需的一句话。见 aviation_monthly/steps.py 里的同名字段说明：
    #: 只写「须明确确认」不够，人看完仍不知道该说什么，动作就会沉在待办里。
    #:
    #: 注意它是**从当前状态往前走**的措辞，不是「确认某个已生成产物」的措辞。
    #: `insights` 曾写成「确认这些洞察」——可草稿还没生成，人看到只会莫名其妙。
    #: 两段式的步骤（draft→confirm、plan→apply）这里填第一段：汇总看到它们时
    #: 基本都停在没开始的状态，第二段的确认在那一段自己的输出里再提。
    phrase: str | None = None


STEPS: tuple[Step, ...] = (
    Step("merge", "重建指标快照", False, "出现清空时须确认", "ir industry merge", phrase="确认清空"),
    Step("dashboard", "生成看板投影", False, None, "ir industry generate-dashboard"),
    Step(
        "insights",
        "刷新洞察",
        True,
        "草稿自动生成；须用户确认中文后入库",
        "merge 自动选层出草稿 → Agent 展示中文 → confirm",
        phrase="确认洞察并写入",
    ),
    Step(
        "feishu",
        "飞书多维表投影",
        True,
        "须用户明确说「写入」",
        "ir industry feishu plan → apply --yes",
        phrase="同步飞书",
    ),
    Step(
        "publish",
        "上线 datamax.fun",
        True,
        "对外发布，须用户明确要求",
        "见 docs/specs/…-cutover-runbook.md",
        phrase="上线",
    ),
)

STEP_ORDER = [step.key for step in STEPS]
STEP_BY_KEY = {step.key: step for step in STEPS}


#: 命令可在 `Result.data` 里放这个键，声明「本步的产出是否完整」。
#: 只在 `partial` 时被用到——见 `step_state()`。
COMPLETE_KEY = "step_complete"


def step_state(status: str, data: dict | None = None) -> str:
    """结果状态 → 步骤状态。

    直白的映射只有一处不成立：**`partial` 有两种含义。**

    - 「做完了，但有提醒」——`generate-dashboard` 三个文件都写出了，只是洞察可能过期；
    - 「没做完，等人处理」——`merge` 遇到清空未确认时根本没写入。

    早先一律映射成 `running`，后果是第一种会永久停在「进行中」：进度少算一步，
    状态机还一直提示回头重做已经做完的那一步（实测 publish 成功后被提示去
    `generate-dashboard`）。所以由最清楚语义的那个命令用 `data["step_complete"]`
    自己声明，状态机不去猜。
    """
    if status == "partial" and (data or {}).get(COMPLETE_KEY):
        return "done"
    return {"success": "done", "partial": "running", "blocked": "blocked", "failed": "failed"}[status]


def current_period(paths: DomainPaths) -> str | None:
    """本期 = 指标快照的数据截至日。快照还没生成就没有「本期」。"""
    if not paths.snapshot.is_file():
        return None
    meta = json.loads(paths.snapshot.read_text(encoding="utf-8")).get("meta") or {}
    return meta.get("dataUpdate") or None


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
    result_data: dict | None = None,
    inputs: dict[str, Path] | None = None,
    outputs: dict[str, Path] | None = None,
) -> Manifest:
    manifest = open_manifest(base, period)
    for label, path in (inputs or {}).items():
        manifest.record_input(label, path)
    for label, path in (outputs or {}).items():
        manifest.record_output(label, path)
    manifest.set_step(step, state, note, result_data=result_data)
    return manifest


def changed_periods(base: Paths, period: str | None) -> list[str]:
    """读取本期最近一次 merge 的实际变动粒度。

    存在 manifest 里而不是依赖对话上下文，所以换会话后 `insights draft` 仍只生成该写的层。
    旧 manifest 没有结构化结果时返回空；调用方可以显式 `--all` 做兼容兜底。
    """
    if not period:
        return []
    manifest = Manifest(base, DOMAIN, period)
    if not manifest.exists:
        return []
    result = ((manifest.load().get("steps") or {}).get("merge") or {}).get("result") or {}
    selected = list(result.get("changedPeriods") or [])
    return [item for item in ("weekly", "monthly", "quarterly") if item in selected]


def progress(base: Paths, period: str | None) -> dict:
    """给 status 用的进度摘要。"""
    if not period:
        return {"period": None, "done": 0, "total": len(STEP_ORDER), "next": None, "stuck": []}
    manifest = Manifest(base, DOMAIN, period)
    if not manifest.exists:
        return {"period": period, "done": 0, "total": len(STEP_ORDER), "next": STEP_ORDER[0], "stuck": []}
    steps = manifest.load()["steps"]
    done = [k for k, v in steps.items() if v.get("state") in {"done", "skipped"}]
    stuck = [k for k, v in steps.items() if v.get("state") in {"blocked", "failed"}]
    return {
        "period": period,
        "done": len(done),
        "total": len(STEP_ORDER),
        "next": manifest.next_pending(STEP_ORDER),
        "stuck": stuck,
        "states": {k: steps.get(k, {}).get("state", "pending") for k in STEP_ORDER},
    }


def render_progress(base: Paths, period: str | None) -> list[dict]:
    """把进度渲染成 Result.checks 能用的形状。"""
    info = progress(base, period)
    states = info.get("states") or {}
    level_of = {
        "done": "ok",
        "skipped": "ok",
        "running": "warn",
        "pending": "warn",
        "blocked": "fail",
        "failed": "fail",
    }
    label_of = {
        "done": "完成",
        "skipped": "跳过",
        "running": "进行中",
        "pending": "待办",
        "blocked": "被拦住",
        "failed": "失败",
    }
    rows: list[dict] = []
    for step in STEPS:
        state = states.get(step.key, "pending")
        suffix = "（可选）" if step.optional else ""
        detail = label_of.get(state, state)
        if state == "pending" and step.gate:
            detail = f"待办 · 门禁：{step.gate}"
        rows.append(
            {
                "name": f"{step.zh}{suffix}",
                "level": level_of.get(state, "warn"),
                "detail": detail,
            }
        )
    return rows
