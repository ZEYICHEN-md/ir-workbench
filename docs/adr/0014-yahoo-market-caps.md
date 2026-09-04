# ADR 0014：地区表分母用 Yahoo 市值快照，不用 S&P Value/%S/O 反推

- 日期：2026-09-03（源包 0004；工作台编号见 [0010](0010-shareholder-list-module.md)）
- 状态：已采纳

S&P 的 Value÷%S/O 对部分代码（如 PDD、BKNG）会给出离谱总市值。地区表「% Mkt Cap」沿用旧做法：持仓分子来自 S&P Value，分母用生成日 Yahoo 行情市值；港股保留「港币市值/USD/HKD」。

F3 与地区表分母同一份 `market_caps.json`：有效日有新的 TCOM shares outstanding / 市值 / 汇率就用新的。G3 句式仍是 5 月的 `updated as of {有效日}`，不写 TBU。上期 `% S/O` 仍按上一本的 F3 快照，不拿本期分母去改写历史。
