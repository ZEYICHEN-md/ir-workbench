# ADR 0013：用 Python CLI 生成 Excel 母版，不把引擎迁飞书

- 日期：2026-09-03（源包 0003；工作台编号见 [0010](0010-shareholder-list-module.md)）
- 状态：已采纳

持股机器是 5000×99 的公式立方；飞书 CLI 适合看板和邮箱，不适合整表覆盖粘贴。CapIQ 导出是 xlsx，openpyxl 复制 6 月母版骨架后替换底表并衍生其余 sheet，是可复现、可校验的路径。
