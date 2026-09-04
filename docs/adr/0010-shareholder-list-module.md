# ADR 0010：机构股东名册作为第九个域迁入工作台

- 日期：2026-09-04
- 状态：已采纳
- 来源：交接包 `update-shareholder-list/payload/`（打包日 2026-09-03）

## 背景

携程 IR 每季用 S&P Capital IQ 两张底表生成完整机构股东名册（约 14 个 sheet）。交接包已有可复现的 Python 生成器、对抗审查和操作手册。用户口头习惯说 **shareholder list**，Excel 文件名仍是 `Investor List_YYYYMMDD.xlsx`。

工作台现有八个域都不覆盖这件事。不能把引擎塞进飞书，也不能并进 `industry-data`（那是指标底稿权威，ADR 0001）。

## 决策

### 1. 独立成第九个域 `shareholder-list`

节奏按季 / 按有效日；周期键用 `data_date`（如 `2026-08-31`）。内部能力，不对外发布。

### 2. 引擎位置跟交接包契约，不搬进 `modules/`

`python -m shareholder_list` 的 `repo_root()` 认 `src/shareholder_list/build.py` + `scripts/rebuild.ps1`。生成器、校验、Yahoo 抓行情留在 `src/shareholder_list/`；一键脚本留在 `scripts/rebuild.ps1`。`modules/shareholder_list/` 只放 SKILL、工作台 CLI 包装和 health。

工作台 Agent 的手是 `ir shareholder-list rebuild`，与 `rebuild.ps1` 调用同一套 `python -m shareholder_list --audit`。不要再发明第三套入口。

### 3. 产物写在仓库根 `output/`，不改成 `outputs/shareholder-list/`

引擎、审计 JSON、交差文件名都钉在 `output/Investor List_{YYYYMMDD}.xlsx`。改路径会让门禁对不上 audit 的 `output` 字段。这是对 `docs/FOLDER.md` 按域分区的例外，只限本域生成的 xlsx。

### 4. 技能真源在 `modules/shareholder_list/SKILL.md`

与 ADR 0003 一致：`.cursor/skills/update-shareholder-list/` 只放指路薄壳。路由段进 `router/ROUTER.md`。域内术语在 `docs/shareholder-list/CONTEXT.md`（根目录已有工作台 GLOSSARY，不覆盖）。

### 5. 源包 ADR 重新编号，避免覆盖工作台 0001–0004

| 源包 | 工作台 |
|---|---|
| 0001 列序 | [0011](0011-peer-column-order-is-canonical.md) |
| 0002 内嵌上期 | [0012](0012-embed-prior-snapshot.md) |
| 0003 不用飞书生成 | [0013](0013-python-cli-generates-xlsx.md) |
| 0004 Yahoo 市值 | [0014](0014-yahoo-market-caps.md) |

### 6. 底表不进 Git

Capital IQ 导出仍从用户 `%USERPROFILE%\Downloads` 按 mtime 发现。模板骨架进 `templates/`。市值锁定进 `data/market_caps.json`。

## 后果

工作台域数为九。迁入后先用锁定重建验证引擎（不切有效日、不加 `--refresh-market`）。新切仍须用户明确说有效日。
