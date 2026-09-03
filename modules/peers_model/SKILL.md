# Peers Model 自动更新

本模块只处理 Excel Model 与 Charts 的机械维护，不恢复 Word Appendix 或业绩总结写作。
旧 `peers_rs_update` 和 `peers_model_scripts` 只作只读参考，运行入口只有 `ir peers-model`。

## 用户怎么开口

- “这是 BKNG 26Q3 财报，更新 Model”
- “用这份美团半年报更新 26H1 Model”
- “同程年报出了，更新 FY2026”

一次只更新**一家公司**。ABE 三家共用一本 Excel，但 BKNG / EXPE / ABNB 的 sheet 结构不同，互不改写。

## 固定流程

1. `inspect` 只读核对配置、sheet 和期间结构。
2. `prepare` 用 pdfplumber 按查看器页码抽取正文和表格，并从上一可比期间生成逐行 facts 模板。
3. Agent 回到原 PDF 填 facts。每个 disclosed 值必须保留文件、SHA-256、页码、表/行、原话、原始数值文本、单位和换算系数。
4. `plan` 不写 Excel。它重新打开原 PDF（与第一遍不同的抽取参数），逐项核对原话与数值；同格冲突、缺页或证据变化一律 blocked。
5. 把写入单元格、格式来源和图表范围摆给用户。用户说「确认写入模型副本」后才写入。
6. `apply --confirmed` 复制权威 Model 到 `outputs/peers-model/`，只修改副本；Excel COM 写入、全量重算、关闭后重开回读、再用第三套 PDF 抽取参数复核。原始 Model 永不覆盖。

## 期间规则

- 季度：`26Q3`。新增列继承上一季度同行格式和公式。
- 半年度：`26H1`。只有模板已有半年区块才更新，格式源取上一年同期。
- 年度：`FY2026`。只有模板已有年度区块才更新，格式源取上一年度。
- 某 sheet 缺少可比期间或该类模板时明确跳过；不能凭空造一套布局。
- 季报只动季度列；半年报 / 年报按模板实际存在的半年、年度区块更新。不要把季度图的 SERIES 改成年度列。

## 公司合同

| 公司 | 工作簿 | 写入 sheet | 说明 |
|---|---|---|---|
| BKNG / EXPE / ABNB | ABE 共用一本 | 各自的数据 sheet + `{TICKER} Quarterly Charts` | 只改这一家 |
| 美团 | 独立 Model | `Key Financial Data`、`New Segment Reporting`（季）；半年/年另含 `Segment Reporting` | `H` 等历史表不写 |
| 同程 | 独立 Model | **只要前两个 sheet**：`Tongchengelong`、`Sheet6`；图：`TCEL charts` | 其余 sheet 禁写。Sheet6 没有可比季度就跳过 |

## Charts

季度图从 2019 **对应季度**开始，排除 2020–2022，再接 2023Q1 至目标季度。比如 26Q3：
`19Q3:19Q4 + 23Q1:26Q3`，只给 19Q3、23Q3、24Q3、25Q3、26Q3 打标签。
半年和年度使用同样的“2019 同期 + 2023 至目标年同期”规则。
只改合同指定 chart sheet、且只改引用授权数据 sheet、期间类型与本次更新一致的 series。
空类别轴的 series 只改值范围，不造类别。

## Agent 填 facts

- 只填硬编码数字。公式行（含蓝色 YoY 公式）由 Excel 从上一列平移，不要手填、不要写 `=BW5` 这种列字母。填了也会被丢掉，避免盖掉公式。
- `role: disclosed` 必须能在 PDF 里对上。`echo` 是公司名或期间标签，系统可自动改。
- 模型单位与 PDF 单位不同时写清 `conversion_factor`（例如 PDF 12% → 模型 0.12，factor=0.01；PDF 百万 → 模型千，factor=1000）。
- 取不到就删掉该行，留空；不许编数。

## 命令

```powershell
ir peers-model inspect --company BKNG
ir peers-model prepare --company BKNG --period 26Q3 --pdf path\to\earnings.pdf
ir peers-model plan --company BKNG --period 26Q3 --facts outputs\...\facts.json
ir peers-model apply --company BKNG --period 26Q3 --facts outputs\...\facts.json --confirmed
```

holdout 自测（删掉已有期间再写回，不覆盖权威文件）：

```powershell
ir peers-model selftest --company ALL --period 26Q2
```
