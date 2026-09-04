# Update Shareholder List

对用户说 **shareholder list**。Excel 文件名仍是 `Investor List_YYYYMMDD.xlsx`。

不要在旧表上改。CLI 复制 **上一持股季已定稿** 的那本，写出新日期文件。换母版是为了 QoQ 跟谁比，不是为了修格式；百分比 / Index 绿由引擎每行重写。

Sheet 细则：[reference.md](reference.md)。术语：[docs/shareholder-list/CONTEXT.md](../../docs/shareholder-list/CONTEXT.md)。

Agent 代跑 `ir shareholder-list rebuild`，不要把命令贴给用户。不要另写 PowerShell 或 `python -m` 入口。

---

## 给人：怎么更新（正事）

季度/定期更新只有这一条。没新 CIQ、没说要出下一本，就不要跑。

1. 从 Capital IQ 导出两张底表，留在 **Downloads**（不必和上期表放同一文件夹）：
   - `Peer Ownership-Holdings-YYYY-MM-DD-*.xlsx`（要有 Shares 列；**不要** `Peer Ownership-Holdings-Public-*`）
   - `Institution Combined Ownership-Public-*.xlsx`
   - 不要用 `InvestorLists*.xlsx`
2. 跟 agent 说清楚：**「更新 shareholder list，有效日切成今天」**（或指定日，如 2026/11/30）。
3. **关 Excel**（否则写文件会 WinError 32）。
4. Agent 按下面「新切」改常量并跑 `ir shareholder-list rebuild --refresh-market`。
5. 交差文件：`outputs/shareholder-list/{有效日}/Investor List_{有效日 YYYYMMDD}.xlsx`。不要手改格子；不对就改脚本再跑。

**持股季变了**（CIQ 披露季换了，要改 `PRIOR_Q` / `CUR_Q`）：母版改成**上一本已交差定稿**。8/31 之后的下一持股季 = 刚交差的那本。只换有效日、持股还是同一季 → 母版不动。

Yahoo 失败：日期已经改成今天后，保留已有 `modules/shareholder_list/market_caps.json`，跑**不带** `--refresh-market` 的 rebuild，门禁仍要全过。

---

## Agent：先问清要的是哪件事

引擎只有一套。两条路径是刹车，不是两套业务。

| 用户实际要什么 | 你做什么 |
|---|---|
| **出下一本**（有新 CIQ，有效日切成今天/指定日） | **新切**。改第「新切」节常量，`--refresh-market`。**须用户明确说有效日。** |
| 只说「跑一遍 / 重建 / 按 skill 更新」，**没说切日、没有新一期底表** | **锁定重建**：重算当前 `VALID_AS_OF` 那一本。不改日期、不改母版、不加 `--refresh-market`。 |
| 丢了 8/31 文件、要验证脚本、要幂等复现已定稿 | 锁定重建 |

日历过了有效日 **不等于** 用户要出新一期。没说切日就当锁定重建。CLI 打印 `path=locked-rebuild` 时禁止 `--refresh-market`（不要用 `--force-refresh`）。

---

## 新切（用户要出下一本时）

只改 `modules/shareholder_list/build.py` 顶部常量和（若持股季变了）`modules/shareholder_list/discover.py` 的 `PRIOR_TEMPLATE`。文件名由 `VALID_AS_OF` 推导，不要写死输出路径。

- `VALID_AS_OF` = 有效日 `YYYY/MM/DD`（用户要切成今天就写今天）
- `WORKBOOK_AS_OF` = 同一天的英文（`2026/09/01` → `September 1, 2026`），不要斜杠
- `HOLDINGS_AS_OF` 仅当 CIQ 多数披露日变了
- `PRIOR_Q` / `CUR_Q` **和** `PRIOR_TEMPLATE` 仅当 **新持股季**。此时 `PRIOR_TEMPLATE` = 上一本定稿。同持股季只换有效日 → 不要改 `PRIOR_TEMPLATE`。不要指到本期将写出的文件（自己跟自己比）。

然后一条命令（`VALID_AS_OF` 已等于今天之后才允许 `--refresh-market`）：

`ir shareholder-list rebuild --refresh-market`

输入由 CLI 自动找：Downloads 最新 Peer / Combined；母版用 `PRIOR_TEMPLATE`。缺底表就问用户，不要拿 InvestorLists 顶替。

文案权威（CLI 不读）：`modules/shareholder_list/templates/Investor List_26Q1_20260518.xlsx`。

本期 8/31 的 `PRIOR_TEMPLATE` 仍是 6 月：`modules/shareholder_list/templates/Investor List_20260626.xlsx`。

---

## 锁定重建（不是季度更新步骤）

用户没事不要引导去跑这个。只用于复现当前有效日那一本。

`ir shareholder-list rebuild`

不要加 `--refresh-market`。

---

## Full-chain success（新切和锁定重建都要）

缺一即失败。不要只看 spot_check。

1. 进程 **exit code 0**（审计有 findings 即非 0）。
2. JSON `validate.ok` true，`failures` 空。
3. 第二条 JSON：`"n": 0` **且** `"output"` 就是刚写的 `outputs/shareholder-list/{period}/Investor List_{VALID_AS_OF as YYYYMMDD}.xlsx`。
4. `validate.spot_check` vs `VALID_AS_OF`：`g3`、`market_b1`、`combined_1` = `Baidu Holdings, LTD`、`sh_1` = Combined 去掉百度后第一名、`cwi_combined_shares`。
5. 按 [reference.md](reference.md) 过 sheet 清单。audit `output` 路径必须是刚生成的文件。
6. 百分比扫 **每一数据行**：Top 20 F/G/H、SH K/L、地区 holding/%-of-mcap。Combined `% S/O` 保持 `#,##0.00`。

不要打开 Excel 手改。

---

## Presentation（引擎每期重写）

- 隐藏 `SH Prior` 和 `Market`。
- Index：`#E2EEDA` 按本期 `Style=Index` 涂，不要留下上期行绿。
- Top 20 B4/B5 由股数变动生成；清空 B6。箭头相对 0。
- 冻结：SH `D6`，Combined `B4`，地区 `D8`，DATA_ALL `B3`。
- 每行百分比：Top 20 F/G `0.0%` H `0%`；SH K/L `0.0%`；地区 `REGION_PCT_COLS` = `0.00%`。

格式不对改 `build.py`，不要手改 xlsx。

---

## Do not

- 飞书迁引擎；混用 SH 股数% 与地区市值%；用 S&P %S/O 当 F3。
- 用户没说切日还 `--refresh-market` / `--force-refresh`；同持股季刷新时改 `PRIOR_TEMPLATE`。
- 把 `PRIOR_TEMPLATE` 指到本期将写出的文件。
- 把持股日写进 G3；G3 加 TBU。
- Baidu Holdings, LTD 进 SH；用 InvestorLists；按 6 月乱序列贴 Peer。
- 只看五个 spot_check；不核对 audit 的 `output` 路径。
- 只抽查 H36 / K7。门禁扫全表数据行。
- 把 Combined `% S/O` 改成 Excel `%`。
- 另写 `rebuild.ps1` 或 `python -m shareholder_list`。一律 `ir shareholder-list rebuild`。
