"""统一的运行结果语义。

四种状态是工作台的核心契约：任何操作都必须明确落在其中之一，
不允许「跑完了但不知道算不算成功」。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

Status = Literal["success", "partial", "blocked", "failed"]

#: 状态 → 进程退出码。partial 也算可继续，故为 0。
EXIT_CODES: dict[str, int] = {
    "success": 0,
    "partial": 0,
    "blocked": 2,
    "failed": 1,
}

STATUS_ZH: dict[str, str] = {
    "success": "完成",
    "partial": "部分完成",
    "blocked": "被拦住，需要人处理",
    "failed": "失败",
}


@dataclass
class Result:
    """一次操作的结果。

    ``missing`` 与 ``next_steps`` 是刻意必填的设计：不确定性必须被显式表达，
    不能包装成确定答案（见 docs/GLOSSARY.md 与 finally_we_know 第 9 条）。
    """

    status: Status
    summary: str
    domain: str | None = None
    period: str | None = None
    checks: list[dict[str, Any]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.status]

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"status": self.status, "summary": self.summary}
        if self.domain:
            out["domain"] = self.domain
        if self.period:
            out["period"] = self.period
        for key in ("checks", "missing", "warnings", "next_steps", "data"):
            value = getattr(self, key)
            if value:
                out[key] = value
        return out

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def render(self) -> str:
        """人读输出。给 Agent 转述给同事用，不出现路径以外的技术细节。"""
        lines = [f"[{STATUS_ZH[self.status]}] {self.summary}"]
        for check in self.checks:
            mark = {"ok": "  ✓", "warn": "  !", "fail": "  ✗"}.get(check.get("level", "ok"), "  ·")
            detail = check.get("detail")
            lines.append(f"{mark} {check['name']}" + (f" — {detail}" if detail else ""))
        if self.missing:
            lines.append("缺少：")
            lines.extend(f"  - {item}" for item in self.missing)
        if self.warnings:
            lines.append("提醒：")
            lines.extend(f"  - {item}" for item in self.warnings)
        if self.next_steps:
            lines.append("下一步：")
            lines.extend(f"  {i}. {step}" for i, step in enumerate(self.next_steps, 1))
        return "\n".join(lines)
