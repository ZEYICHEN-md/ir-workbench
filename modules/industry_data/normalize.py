"""把指标值归一到有效精度，消除浮点尾数噪音。

## 为什么需要

底稿里的同比率是 Excel 公式算出来的缓存值。**同一个数在不同保存路径下会有不同的表示**：

| 保存方式 | `-10.4%` 的表示 |
|---|---|
| 人在 Excel 里手动保存 | `-0.104` |
| Excel COM 全量重算后保存 | `-0.10400000000000009` |

两者数值上只差 `9e-17`，但序列化出来的字符串不同，于是 `data.js` 的 diff 里会出现
十几行「变化」。实测两个方向都遇到过：换一份手动保存的底稿时精度变短（当时 merge
报「修改 14」，全是这类噪音）；航空写入触发 COM 重算后精度又变长。

后果不是显示错误——看板只显示一位小数，这些差异完全看不见——而是**每次上线的 diff
都掺着无意义的行，把真正的数据变化埋在里面**。而「逐行核对 diff」正是发布门禁的核心。

## 为什么 12 位是安全的

同比率的输入本身只有 3–5 位有效数字（如 Occ 68.635、ADR 394.90），算出来的比率
第 10 位以后纯属浮点运算残留。实测归一到 12 位有效数字：

- 快照 272 个浮点数中改动 93 个
- 最大绝对变化 `4.6e-13`（相当于同比率的第 11 位小数）
- **一位小数下显示完全相同**

## 为什么不在读表时做

读表阶段归一会让 `excel.parse()` 的结果与底稿缓存值不再逐位相同，而航空管道的回读
校验依赖逐位比对（容差 `1e-9` 是给独立复算用的，不是给表示差异用的）。所以归一只在
**写快照**这一步做，读表保持原样。
"""

from __future__ import annotations

from typing import Any

#: 保留的有效数字位数。见模块文档：12 位对显示零影响，且能消除全部尾数噪音。
SIGNIFICANT_DIGITS = 12


def normalize_number(value: float) -> float:
    """把一个浮点数归一到有效精度。整数值与 0 原样返回。"""
    if value == 0 or value != value:  # 0 与 NaN 不需要处理
        return value
    return float(f"%.{SIGNIFICANT_DIGITS}g" % value)


def normalize(node: Any) -> Any:
    """递归归一。只动 float，其余类型（含 bool、int、str、None）原样保留。"""
    if isinstance(node, bool):  # bool 是 int 的子类，必须先拦
        return node
    if isinstance(node, float):
        return normalize_number(node)
    if isinstance(node, dict):
        return {key: normalize(value) for key, value in node.items()}
    if isinstance(node, list):
        return [normalize(value) for value in node]
    return node


def count_changes(node: Any) -> int:
    """归一会改动多少个数值。用于报告，不改数据。"""
    if isinstance(node, bool):
        return 0
    if isinstance(node, float):
        return 1 if normalize_number(node) != node else 0
    if isinstance(node, dict):
        return sum(count_changes(value) for value in node.values())
    if isinstance(node, list):
        return sum(count_changes(value) for value in node)
    return 0
