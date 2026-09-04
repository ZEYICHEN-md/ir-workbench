# Shareholder List

IR 每季用 S&P Capital IQ 两张底表生成携程机构股东名册。本域是从底表到完整工作簿的生成器，不是 CRM。

## Language

**底表**:
Capital IQ 导出、原样进入工作簿的输入。只有两张：合并持股与同行持股宽表。
_Avoid_: 源数据, raw dump, InvestorLists

**合并持股**:
TCOM + 9961.HK 的 Combined Ownership。机构一行，含分列股数、变动、披露日。
_Avoid_: combined file, 双上市表

**同行持股宽表**:
Peer Ownership / Holdings。持有 20 个代码中任一只的机构，含 Shares / Value / % Port / % S/O。
_Avoid_: DATA_ALL 源, Crossholdings, 宽表导出

**战略股东**:
不进入 IR 机构排名的持有人。当前仅 Baidu Holdings, LTD。
_Avoid_: 大股东, insider, 百度（未写全名时）

**SH Summary**:
合并持股去掉战略股东后的机构排名主表。持股来自合并持股，上期来自内嵌的上期快照。
_Avoid_: 股东汇总, summary tab

**上期快照**:
上一本（上一持股季已定稿）SH Summary 的排名、股数、占比。来源是 `discover.PRIOR_TEMPLATE` 里的 SH，生成时写入本工作簿 `SH Prior`（默认隐藏），禁止桌面外链。锁定重建不要改这份文件。
_Avoid_: [1]SH Summary, 上一本 Excel, 拿本期 output 当母版

**地区大户**:
Equity AUM ≥ $50bn、按国家映射归入 US&CA / EU / APAC / ROW 的资管名单。持仓用宽表 Value，分母用市值快照。
_Avoid_: regional holders, AUM screen

**市值快照**:
生成当日从行情页取得的同行市值与 USD/HKD，写在 `Market` 表（默认隐藏）。
_Avoid_: 7.83, 手写分母

**有效日**:
这份 Investor List 刷新的截止日期。本期是 2026/08/31，写在 SH G3、地图 B3、文件名。
_Avoid_: 持股日, as of 6/30（写在 G3 时）

**持股日**:
CIQ 持仓披露日，本期多为 2026/06/30，写在地区表 B3 的 holdings as of。
_Avoid_: 有效日, 更新日

**邮箱名单**:
重要投资人 / 普通投资人。不从持股衍生，生成时原样复制。
_Avoid_: CRM, 投资人管理

**行粘性格式**:
模板按行号留下的数字格式 / 填充。生成器必须每行重写百分比与 Index 绿，不能沿用上季同一格。
_Avoid_: 只改 H36, 手改 xlsx
