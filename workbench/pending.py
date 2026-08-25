"""跨域汇总「有什么在等我」。

## 为什么需要这个

门禁把动作停在半路是对的，但**停住之后没人再提起，动作就沉进待办里了**。

真实发生过：航空 7 月的 dry-run 跑完，使用者回了「OK」，门禁正确地判断那不是明确授权，
停在 dry-run。之后十几轮讨论别的事，使用者以为已经写入，Agent 以为使用者知道没写。
两周后线上月度航空四条线还断在 6 月，是使用者偶然问起才发现。

这不是门禁的问题，是**没有出口**的问题。`ir status` 按域分别报，`ir doctor` 报环境，
都没有一处集中回答「现在有什么在等我说话」。业务接手人比原作者更容易踩——
他根本不知道有个动作停在半路。

## 两类要报的东西

| 类别 | 判据 | 为什么这样判 |
|---|---|---|
| **等你说话** | **最新**周期的下一步、且这一步有门禁 | 只报最新期——旧期次的未完成步骤属于历史，一直报会变噪音。除非它 `blocked`/`failed`，那时归入卡住 |
| **卡住** | 其余任何周期里的 `blocked` / `failed` / `running` | 是真问题，多久以前的都要报 |

**一个步骤只会属于一类。**先定「等你说话」那一个，剩下的才进「卡住」。

`running` 落在哪一类要看有没有门禁，这一点踩过：

- 有门禁的 `running`（航空 `commit` 跑完 dry-run 停在那儿）＝**在等人说话**，不是卡住。
  早先把它同时判成两类，结果 `ir status` 顶上报的是「有 1 处卡住」——听起来像出了故障，
  人会去查日志，而实际上只需要他说一句「写入」。
- 无门禁的 `running`（`generate-dashboard` 中途断了）＝真的没收尾，报卡住。

旧期次里有门禁的 `running` 仍然报卡住：航空 7 月没写入、8 月已开期时，7 月那一步
不能因为「不是最新期」就消失——它恰恰是最初那次失误的形状。

## `phrase` 是「让这一步开始推进所需的一句话」

不是「确认某个已生成产物的一句话」。这个区别踩过：洞察那一步的措辞原本写成
「确认这些洞察」，可草稿还没生成，人看到只会莫名其妙——它的正确措辞是「刷新洞察」，
Agent 收到之后会先出草稿，再单独请人确认中文。

## 各域需要提供什么

约定 `modules/<域>/steps.py` 暴露 `STEPS`（含 `key` / `zh` / `gate` / `hint`，
可选 `phrase`）与 `progress(base, period)`。没有 steps 模块的域跳过。
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from . import domains
from .paths import Paths


@dataclass(frozen=True)
class Waiting:
    """一件在等人的事。"""

    domain: str
    domain_zh: str
    period: str
    period_label: str
    step: str
    step_zh: str
    kind: str            # "卡住" | "等确认"
    state: str
    gate: str | None
    phrase: str | None
    hint: str
    note: str | None

    def describe(self) -> str:
        where = f"{self.domain_zh} · {self.period_label}"
        if self.kind == "卡住":
            tail = f"（{self.state}）" + (f"：{self.note}" if self.note else "")
            return f"{where} · {self.step_zh}{tail}"
        need = f"需要你说「{self.phrase}」" if self.phrase else (self.gate or "需要你确认")
        return f"{where} · {self.step_zh} —— {need}"


def _periods(base: Paths, domain: str) -> list[str]:
    """该域跑过的周期，新的在前。"""
    root = base.runs(domain)
    if not root.is_dir():
        return []
    return sorted((p.name for p in root.iterdir() if p.is_dir()), reverse=True)


def _load_steps(domain: str):
    module = f"modules.{domain.replace('-', '_')}.steps"
    try:
        return importlib.import_module(module)
    except ImportError:
        return None


def collect(base: Paths) -> list[Waiting]:
    """扫描全部已迁入域，汇总在等人的事。"""
    out: list[Waiting] = []

    for key in domains.DOMAINS:
        if not base.module(key).is_dir():
            continue
        steps = _load_steps(key)
        if steps is None:
            continue

        zh = domains.get(key).zh
        by_key = getattr(steps, "STEP_BY_KEY", {})
        periods = _periods(base, key)

        for index, period in enumerate(periods):
            try:
                info = steps.progress(base, period)
            except Exception:  # noqa: BLE001 —— 单个域读不出不该让汇总整体失败
                continue

            label = domains.get(key).label(period)
            states = info.get("states") or {}

            # 先认出「等你说话」那一个：最新周期的下一步 + 有门禁。
            # 它若已经 blocked/failed 就不算在等人，让它落到卡住那一栏去。
            awaiting = None
            if index == 0:
                nxt = info.get("next")
                step = by_key.get(nxt) if nxt else None
                if step is not None and getattr(step, "gate", None):
                    if states.get(nxt, "pending") not in {"blocked", "failed"}:
                        awaiting = nxt

            if awaiting:
                step = by_key[awaiting]
                out.append(
                    Waiting(
                        domain=key,
                        domain_zh=zh,
                        period=period,
                        period_label=label,
                        step=awaiting,
                        step_zh=step.zh,
                        kind="等确认",
                        state=states.get(awaiting, "pending"),
                        gate=step.gate,
                        phrase=getattr(step, "phrase", None),
                        hint=getattr(step, "hint", ""),
                        note=None,
                    )
                )

            # 卡住的：全部周期都报，但不重复报上面那一个
            for step_key, state in states.items():
                if state not in {"blocked", "failed", "running"}:
                    continue
                if step_key == awaiting:
                    continue
                step = by_key.get(step_key)
                out.append(
                    Waiting(
                        domain=key,
                        domain_zh=zh,
                        period=period,
                        period_label=label,
                        step=step_key,
                        step_zh=getattr(step, "zh", step_key),
                        kind="卡住",
                        state=state,
                        gate=getattr(step, "gate", None),
                        phrase=getattr(step, "phrase", None),
                        hint=getattr(step, "hint", ""),
                        note=_note(base, key, period, step_key),
                    )
                )

    return out


def _note(base: Paths, domain: str, period: str, step: str) -> str | None:
    from .manifest import Manifest

    try:
        manifest = Manifest(base, domain, period)
        if not manifest.exists:
            return None
        return (manifest.load().get("steps", {}).get(step) or {}).get("note")
    except Exception:  # noqa: BLE001
        return None


#: 两类的显示与严重程度。顺序即优先级——卡住的排最前。
KIND_META = {
    "卡住": ("卡住", "fail", 0),
    "等确认": ("等你确认", "warn", 1),
}


def as_checks(waiting: list[Waiting]) -> list[dict]:
    """渲染成 Result.checks 能用的形状。"""
    rows = []
    for item in sorted(waiting, key=lambda w: (KIND_META[w.kind][2], w.domain, w.period)):
        name, level, _order = KIND_META[item.kind]
        rows.append({"name": name, "level": level, "detail": item.describe()})
    return rows
