# ADR 0011：同行持股宽表以 Capital IQ 当前列序为准

- 日期：2026-09-03（源包 0001；工作台编号见 [0010](0010-shareholder-list-module.md)）
- 状态：已采纳

6 月母版 `DATA_ALL` 的列序是当时点选顺序，地区表第 5 行按那套列号写死。新导出按每个代码 Shares → %S/O → Value → %Port 捆列，字段集合相同但列号不同。

决定以新导出列为 canonical：生成时按字段名写 `DATA_ALL`，并重写地区表列号与地图合计引用。不再在 CIQ 里复刻 6 月乱序。
