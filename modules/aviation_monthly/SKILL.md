---
name: aviation-monthly
description: >-
  民航局与三大航月度旅客运输量写入闭环：抓官方公告 → Airline Data 底表 → 重算 →
  指标底稿四个目标格。当用户说更新民航局月度数据、更新三大航月度、X 月航空官方数据
  出了、更新航空月度时使用。只走 dry-run → 确认 → commit。
---

# aviation-monthly

## 这条管道特殊在哪

**它是唯一会写指标底稿的自动化。**ADR 0001 定了 Excel 是唯一真源，人手填（酒店 STR、
周度航空）与自动化写入在同一张表上汇合。所以门禁最严，且写入路径做了四重保护：

1. 先 **dry-run**：抓数、独立复算、与底表现值比对冲突，**不动任何文件**
2. 人确认后 `--commit`
3. 写入走 **staging 副本**，校验通过才装回
4. **原子安装 + 备份**：失败自动回滚，成功才删备份

## 命令

```powershell
ir aviation run --year 2026 --month 7            # dry-run：抓数 + 校验，不写入
ir aviation run --year 2026 --month 7 --commit   # 确认后写入
ir aviation status [--year 2026 --month 7]       # 本月进度
```

**工作簿不用传路径。**一律取 `ir config` 锁定的那两份（`industry` + `airline`）。

> 迁移前正是因为路径靠手传，这条管道一直在写 `0703_Travel_Pulse/data_source/` 里那份
> 停在 `0803` 的旧表，而实际维护的是 `database_matain` 里的 `0817`——**这条自动化实质上
> 是断的，而且没有任何机制会提示。**现在路径由配置单点决定。

## 三步

| # | 步骤 | 门禁 |
|---|---|---|
| 1 | 抓官方数据并校验（不写入） | — |
| 2 | 写入 Airline Data 与指标底稿 | **须用户明确确认** |
| 3 | 重建指标快照并生成看板 | 走 `ir industry merge` → `generate-dashboard` |

第 3 步必须做：底稿变了，快照和看板才会跟上。

## 官方源

| 来源 | 数据 | 原始单位 |
|---|---|---|
| 民航局 | 旅客运输量：合计、国内航线、其中港澳台、国际航线 | 万人 |
| 南航 600029 / 东航 600115 / 国航 601111 | 载客人数：合计、国内、国际、地区 | 千人次 |

CAAC 写入前乘 10 转千人；航司数据不转换。

## 写入指标底稿的四个目标格

在「国内行业数据」表，B 列定位 `{year}年` → 该年块的「月度」表头 → `{month}月` 行，
写入四个同比：

1. 分组「国内航空客运量」下的**民航局**（纯国内 YoY）
2. 同组的**三大航**（国内 Big 3 YoY）
3. 分组「国际航空客运量（含港澳台）」下的**民航局**（国际+地区 YoY）
4. 同组的**三大航**（国际+地区 Big 3 YoY）

只写值、保留原格式；目标格**不加批注**，溯源留在 Airline Data 的输入格批注与 manifest。

## 硬约束（违反就会出事，不是风格问题）

- **指标底稿不能用 openpyxl 保存**：它含历史外部链接，openpyxl 保存会重写链接/XML，
  导致 Excel 打不开。写入一律走 **Excel COM** 在临时副本上操作并全量重算。
- **合计行用公告的「合计」值**，不用分项相加替代（分项可能有 0.01 千人次舍入尾差）。
- **结构不匹配时停止，不要猜。**见 `references/workbook-contract.md`。
- **进入新年度前**，先在四个航空 sheet 与 Summary 建立新年度块、上年分母和月份表头，
  再更新契约里的行映射。脚本会拒绝年份不一致的工作簿。

## 校验阈值

- CAAC：`Total ≈ Domestic+Regional + Pure Intl`，容差 2.1 千人
- 航司：`Total ≈ Domestic + Intl + Regional`，容差 0.05 千人次
- 同比缓存与独立计算差异 ≤ `1e-10`
- 已有目标值与新值差异 > `1e-9` 视为**冲突**（dry-run 会报出来）
- 目标依赖闭包内不得出现 `#REF!/#DIV/0!/#VALUE!/#N/A/#NAME?`
- 全工作簿错误标记数不得高于输入文件

## 溯源

Airline Data 的每个官方输入格加批注：

```
Source: [公告标题], [发布日期/数据期], PDF第N页「表名」表「行名」行, [URL]
```

manifest 写在 `runs/aviation-monthly/<年月>/pipeline.json`，含输入文件 SHA-256、
每个取值的公告出处、独立复算结果与全部校验项。

## Agent 行为清单

- 用户说「更新 X 月航空数据」→ **先 dry-run**，把四个同比数值摆出来让用户核
- 没听到「写入 / 确认」之类明确措辞，不带 `--commit`
- 写入成功后主动提醒接着跑 `ir industry merge`（底稿变了，快照要跟上）
- 官方公告没出或抓不到 → 显式返回 `blocked`，说明缺哪家、等出了再跑；**不要手工推算合计**
- 结构校验不过 → 停下，指向 `references/workbook-contract.md`，不要绕过

## 相关

- `references/workbook-contract.md` —— 行映射与结构契约（改结构必须先改这份）
- `docs/adr/0001-excel-as-metrics-authority.md` —— 为什么底稿是唯一真源
- `modules/industry_data/SKILL.md` —— 写入之后的重建链
