"""本域的健康检查，供 `ir doctor` 调用。

约定（各域统一）：暴露 `checks(base) -> list[dict]`，每项含 `name` / `level`
（`ok` / `warn` / `fail`）/ `detail`，可选 `advice`。doctor 负责汇总，不懂域内细节。
"""

from __future__ import annotations

from workbench.config import Config
from workbench.paths import Paths

from . import crosscheck, layout, steps
from .paths import DomainPaths


def checks(base: Paths) -> list[dict]:
    paths = DomainPaths(base)
    rows: list[dict] = []

    workbook = Config(base).workbook("industry")
    if not workbook or not workbook.is_file():
        # 工作簿本身的缺失由 doctor 的通用检查报，这里不重复
        return rows

    structure = layout.verify(workbook)
    rows.extend(structure)

    # 结构不合契约时列号可能已经错位，此时核对内容只会给出误导性的结论
    if not any(row["level"] == "fail" for row in structure):
        rows.extend(crosscheck.checks(workbook))

    period = steps.current_period(paths)
    if period:
        info = steps.progress(base, period)
        if info["stuck"]:
            rows.append(
                {
                    "name": "本期进度",
                    "level": "fail",
                    "detail": f"{period}：卡在 " + "、".join(info["stuck"]),
                    "advice": "跑 `ir industry status` 看具体哪一步、被什么门禁挡着。",
                }
            )
        elif info["next"]:
            rows.append(
                {
                    "name": "本期进度",
                    "level": "warn",
                    "detail": f"{period}：{info['done']}/{info['total']} 步，下一步 {info['next']}",
                }
            )
        else:
            rows.append({"name": "本期进度", "level": "ok", "detail": f"{period}：全部完成或已跳过"})

    return rows
