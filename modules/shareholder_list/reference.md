# Sheet rules

怎么更新（给人看的步骤）：[SKILL.md](SKILL.md) 第一节。本文件只记各 sheet 写什么。

Authoritative May wording file:

`modules/shareholder_list/templates/Investor List_26Q1_20260518.xlsx`

Skeleton / prior SH (`discover.PRIOR_TEMPLATE`): last published list of the previous holdings quarter. This 8/31 cut:

`modules/shareholder_list/templates/Investor List_20260626.xlsx`

Next holdings quarter: point `PRIOR_TEMPLATE` at that published file under `outputs/shareholder-list/`. Do not keep June as prior. Do not pin to the file this cut will write.

G3 / map D8 / Top 20 B2 / map E16–E18 follow May. Numbers follow this validity snapshot.

**Copy-then-write leftover:** number formats, Index fill, freeze panes, and takeaway text stick to last quarter's **row**. The engine rewrites them every rebuild. `validate` / audit scan every data row. Do not keep a probe list of H36 / K7 / J161.

## Two dates

| 名 | 本期值 | 写在哪 |
|---|---|---|
| 有效日 | 2026/08/31 | SH G3；地图 B3；地区 B3 前半；文件名；`Market!B1` (`valid_as_of`) |
| 持股日 | 2026/06/30 | 地区 B3 `holdings as of`；CIQ Position Date |
| 行情拉取日 | `market_caps.json` `as_of` | `Market!B4` `quotes_fetched` |

G3 句式：`updated as of {有效日}`。无 TBU。不要把持股日写进 G3。

## SH Summary

- F3 = `modules/shareholder_list/market_caps.json` → `tcom_shares_outstanding` (this validity date).
- I/J headers stay `% S/O 25Q2` / `% S/O 25Q3` and stay empty (May).
- H = `IFERROR(F-G, F)` (June).
- K/L = `0.0%` every row. Do not keep June K7 `#,##0` on Vanguard.
- VLOOKUP into Combined uses row-4 indices: D=7, E=10, M=9, N=12, O=14, P=16, Q=17, R=18, S=13.
- SH = Combined minus `Baidu Holdings, LTD` only. `#1` this quarter = `Capital World Investors (U.S.)`.
- Freeze panes `D6` (May). Do not keep June `F265`.
- `SH Prior` and `Market` are hidden.

## Top 20

- B2 = `核心股东持仓情况` (May; no TBU).
- B3 = quarter line + valid date. B4/B5 takeaways are generated from Top 20 / prior-top share changes (≥4% 减持 / 增持). B6 cleared (do not keep last quarter's note).
- Rank Change = 上期排名 − 本期排名（正数=名次上升）。箭头用 3Arrows 相对 0：>0 绿、=0 黄、<0 红。不要用 33%/67% 分位。
- F/G = `0.0%`，H = `0%`。Do not keep June's General format on a row that was `New Entry` last quarter.
- Prior block INDEX/VLOOKUP wrapped in IFERROR. Missing from current SH → H `Exited`.
- Index (`Style=Index`) rows: fill `#E2EEDA` on Top 20 B–H, SH C–S, Combined A–R, region C–D (May).

## 全球投资人地图

- B3 = `updated as of August 31, 2026`.
- D8 = `*小于Total Market Cap, 由于目前可以抓取到的公开披露信息，cover约53%的股东持仓数据`
- E16/E17/E18 = `no ADR holding Equity AUM` / `no Travel holding Equity AUM` / `no TCOM holding`
- C9 = `C8/C7` (holdings value / AUM, not % S/O).

## DATA_ALL / Combined

- Peer column order is canonical (Shares→%S/O→Value→%Port per ticker).
- Combined keep A–R named fields; drop Sustainability Category.
- Combined `% S/O` is CIQ percentage points (`6.67` + `#,##0.00`). Do not rewrite as Excel `%`.
- Fund Style / Region: `IFERROR(VLOOKUP(...),"")`.
- Combined `#1` must be `Baidu Holdings, LTD`.
- Identity: `Capital World Investors (U.S.)` TCOM Shares + 9961 Shares = Shares (Combined). SH D/E/F are formulas.

## Regions

B3: `As of August 31, 2026, AUM > $50bn, holdings as of 2026/06/30`.

Row 5 column numbers must match DATA_ALL headers by name, not 6月 G=7/I=9.

AUM ≥ $50bn, drop Investor Type=`Corporate`, Mapping. APAC = Asia+CN+HK+SG+Oceania. HK mcap = HKD / FX.

Freeze panes `D8` (May). Do not keep June `AK8` / `R28`.
Holding % columns (`J`, `M`, …) rewritten to `0.00%` every name row. Extra names beyond last quarter's last row must not stay `General`.

## 重要投资人 / 普通投资人

Copy from the June skeleton. Do not derive from holdings. Audit compares every cell to the template (`diffs=0`).

## Package

| 组件 | 作用 |
|---|---|
| `ir shareholder-list rebuild` | 唯一入口；一次 `--audit`（审**这次**写的 output） |
| `modules/shareholder_list/build.py` | 生成；季度常量在文件顶部；文件名由 `VALID_AS_OF` 推导 |
| `modules/shareholder_list/validate.py` | 生成后门禁 + `spot_check` |
| `modules/shareholder_list/market.py` | Yahoo crumb |
| `modules/shareholder_list/discover.py` | Downloads 最新底表（Peer 排除 `*-Public-*`） |
| `modules/shareholder_list/adversarial_audit.py` | 逐格对抗审查 |
| `modules/shareholder_list/market_caps.json` | F3、汇率、地区市值 |
| `docs/shareholder-list/CONTEXT.md` / `docs/adr/0010`–`0014` | 术语与决策 |
