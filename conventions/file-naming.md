# 文件命名约定

## 工作簿（`data/workbooks/`）

```text
国内行业数据_MMDD.xlsx        # 指标底稿
Airline Data_MMDD.xlsx        # 航空月度底表
```

- `MMDD` 是**文件交付日**（这一版表被交进来的日期），**不是数据截至日**。
- 数据截至日只认指标快照的 `meta.dataUpdate`（按最新周结束日自动盖章）。
- 同日多版：`国内行业数据_0817_v2.xlsx`。
- **不要**用 `YYYYMMDD_` 前缀或 `Airline Data_20260723.xlsx` 这类写法——历史上出现过，
  与 `MMDD` 混用会让人以为可以按文件名排序判断新旧。
- 哪一份在用**只看配置**（`ir config show`），不看文件名（ADR 0001）。

判断「哪份最新」时，同时核对三样：文件名日期、文件修改时间、表内已填数据范围。
三者不一致就停下来问人，不要自行选一个。

## 本期原件（`inputs/<域>/<周期>/`）

原文件名保留不动，便于回溯到来源。周期键按域定义（见 `workbench/domains.py`）：

| 域 | 周期键 | 例 |
|---|---|---|
| `news-digest` | 周报期次 | `2026年8月第2周` |
| `industry-data` | 数据截至日 | `2026-08-08` |
| `aviation-monthly` | 年月 | `202607` |
| `peers-appendix` | 财季 | `26Q2` |

## 交付物（`outputs/<域>/<周期>/`）

```text
旅行行业新闻精选-2026年8月第2周.md / .html / .pdf
```

## 设计说明与决策

```text
docs/adr/NNNN-kebab-topic.md          # 难逆决策
docs/specs/YYYY-MM-DD-<主题>-design.md   # 设计说明
docs/specs/YYYY-MM-DD-<主题>-runbook.md  # 操作手册
```

## 一次性产物

一律进 `scratch/`，可随时清空。建议前缀任务日：`20260822_field_list.json`。

**默认可删**——重要结论要沉淀进 `docs/`，不要依赖 `scratch/` 存活。
