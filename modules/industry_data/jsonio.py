"""与 Node `JSON.stringify(data, null, 2)` 字节一致的 JSON 序列化。

存在的唯一理由：这批脚本原本是 Node 实现，改写为 Python 后要能拿现有的
`dashboard/travel/data.js` / `insights.js` **逐字节比对**来证明等价。
一旦迁移验证完成，本模块仍保留——看板文件的差异噪音越小越好。
"""

from __future__ import annotations

import json
import math
from typing import Any


def _fmt_number(value: float | int) -> str:
    """按 JS Number → String 的规则输出。

    差异点只有一处：Python 对整数值的 float（如 ``0.0``）输出 ``0.0``，
    JS 输出 ``0``。这里统一按 JS 处理。
    """
    if isinstance(value, bool):  # bool 是 int 的子类，必须先拦
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if math.isnan(value) or math.isinf(value):
        return "null"  # JS JSON.stringify 把 NaN/Infinity 写成 null
    if value == int(value) and abs(value) < 1e16:
        return str(int(value))
    return repr(value)


def dumps(data: Any, indent: int = 2) -> str:
    """等价于 ``JSON.stringify(data, null, indent)``。"""

    def render(node: Any, level: int) -> str:
        pad = " " * (indent * level)
        inner_pad = " " * (indent * (level + 1))
        if node is None:
            return "null"
        if isinstance(node, bool):
            return "true" if node else "false"
        if isinstance(node, (int, float)):
            return _fmt_number(node)
        if isinstance(node, str):
            return json.dumps(node, ensure_ascii=False)
        if isinstance(node, list):
            if not node:
                return "[]"
            items = [f"{inner_pad}{render(v, level + 1)}" for v in node]
            return "[\n" + ",\n".join(items) + "\n" + pad + "]"
        if isinstance(node, dict):
            if not node:
                return "{}"
            items = [
                f"{inner_pad}{json.dumps(str(k), ensure_ascii=False)}: {render(v, level + 1)}"
                for k, v in node.items()
            ]
            return "{\n" + ",\n".join(items) + "\n" + pad + "}"
        raise TypeError(f"不支持的类型：{type(node).__name__}")

    return render(data, 0)


def dumps_canonical(data: Any, indent: int = 2) -> str:
    """权威文件（指标快照 / 洞察底稿）的序列化。

    与看板投影用的 `dumps` 不同：权威文件原本由 Python 写出，保留 Python 的
    数字写法（如 ``0.0`` 不会被压成 ``0``），迁移前后字节一致。
    看板投影原本由 Node 写出，因此那边必须用 `dumps`。
    """
    return json.dumps(data, ensure_ascii=False, indent=indent)
