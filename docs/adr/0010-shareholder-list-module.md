# ADR 0010：机构股东名册作为第九个域迁入工作台

- 日期：2026-09-04
- 状态：已采纳
- 来源：交接包 `update-shareholder-list/payload/`（打包日 2026-09-03）

## 背景

携程 IR 每季用 S&P Capital IQ 两张底表生成完整机构股东名册（约 14 个 sheet）。交接包已有可复现的 Python 生成器、对抗审查和操作手册。用户口头习惯说 **shareholder list**，Excel 文件名仍是 `Investor List_YYYYMMDD.xlsx`。

工作台现有域都不覆盖这件事。不能把引擎塞进飞书，也不能并进 `industry-data`（那是指标底稿权威，ADR 0001）。

交接包 README 是按「通用 skill 仓库」写的（根目录 `src/`、`.cursor/skills/`、`scripts/rebuild.ps1`）。那不是本仓目录约定。迁入以 ADR 0003 为准：代码和 SKILL 在 `modules/<域>/`，Agent 的手是 `ir ...`，交付物在 `outputs/<域>/`。

## 决策

### 1. 独立成第九个域 `shareholder-list`

节奏按季 / 按有效日；周期键用 `data_date`（如 `2026-08-31`）。内部能力，不对外发布。

### 2. 布局与其它域相同

生成器、校验、Yahoo、审计、母版骨架、锁定市值都在 `modules/shareholder_list/`。唯一入口是 `ir shareholder-list rebuild`。不要保留平行的 `src/`、`scripts/rebuild.ps1`、`python -m shareholder_list`。

### 3. 产物走 `outputs/shareholder-list/<有效日>/`

交差文件仍叫 `Investor List_YYYYMMDD.xlsx`，目录按周期键分区，与 `docs/FOLDER.md` 一致。审计 JSON 写在同一目录。生成的 xlsx 不进 git（同 `outputs/peers-model/`）。

### 4. 技能真源在 `modules/shareholder_list/SKILL.md`

`.cursor/skills/update-shareholder-list/` 只放指路薄壳。路由段进 `router/ROUTER.md`。域内术语在 `docs/shareholder-list/CONTEXT.md`。

### 5. 源包 ADR 重新编号，避免覆盖工作台 0001–0004

| 源包 | 工作台 |
|---|---|
| 0001 列序 | [0011](0011-peer-column-order-is-canonical.md) |
| 0002 内嵌上期 | [0012](0012-embed-prior-snapshot.md) |
| 0003 不用飞书生成 | [0013](0013-python-cli-generates-xlsx.md) |
| 0004 Yahoo 市值 | [0014](0014-yahoo-market-caps.md) |

### 6. 底表不进 Git

Capital IQ 导出仍从用户 `%USERPROFILE%\Downloads` 按 mtime 发现。模板骨架在模块 `templates/`。市值锁定在模块 `market_caps.json`。

## 后果

工作台域数为九。业务规则（copy-then-write、锁定重建 vs 新切、不手改 xlsx、不迁飞书）保持交接包原意。目录形状跟 peers-model 一类域对齐，不以交接包 README 当本仓真源。
