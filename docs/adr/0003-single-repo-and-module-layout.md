# ADR 0003 — 单一内部仓、模块划分、周期键按域定义

> **增补（2026-08-22）**：模块数由七增至八——`expert-calls` 见 [ADR 0005](0005-expert-calls-module.md)。
> 同时确认季度行业展望简报为一次性产物，不设模块（见 `docs/DECISIONS.md` Q27）。
>
> **增补（2026-09-03）**：`peers-appendix` 退役，模块数回到七。Appendix / 业绩总结由人写，
> 季度检索走 `competitor-intel`。旧仓冻结，工作台不保留该域代码或 CLI。见 `docs/DECISIONS.md`。

- 状态：**Accepted**（2026-08-22）
- 日期：2026-08-22

## 背景

三个域原本是三个独立 GitHub 仓（`Travel_Pulse` / `database_matain` / `ota-peers-appendix`），各有各的约定、成熟度和 Agent 配置面。已确认的整合前提：

- 指标底稿 Excel 只能有一份（ADR 0001），现在两个仓各存一份且版本不一致
- 竞对情报库横跨新闻精选（周）与 Appendix（季），不属于任一单仓（ADR 0002）
- 一个 Control Plane、一套 config、一份 zip 交付、一条更新通道

## 决策

### 1. 仓拓扑

| 仓 | 内容 | 可见性 |
|---|---|---|
| **内部工作仓** | 全部三个域 + 共享数据层 + 情报库 + Control Plane | 私有 |
| **公开作品集仓** | 代码与框架，由 export 生成，不含任何数据材料 | 公开 |
| **看板发布仓** | 看板四文件（`travel-dashboard` → datamax.fun） | 现状不变 |
| 三个旧仓 | 冻结在 GitHub 作为历史，不再更新 | 现状不变 |

公开仓**由导出脚本生成，不是 git 镜像**。镜像会带上包含敏感材料的历史，过滤历史比重新导出风险高。

### 2. 八个模块

| 模块 | 面向 | 节奏 | 来源 |
|---|---|---|---|
| `news-digest` | **对外交付** | 周 | Travel_Pulse `travel-weekly-report` 新闻章 |
| `industry-data` | 内部 | 周 / 月 | database_matain（指标 / 看板 / 洞察部分） |
| `aviation-monthly` | 内部 | 月 | Travel_Pulse `aviation-monthly-data-pipeline` |
| `hk-market` | 内部查询 | 按需 | Travel_Pulse `hk-volume-ratio` + `hk_market_pulse.py` + `ccass_southbound.py` |
| `competitor-intel` | 内部 | 周 / 季 / 按访谈 | 新建，见 ADR 0002 |
| `expert-calls` | 内部 | 按访谈到达 | database_matain `.cursor/skills/expert-call-pipeline`，见 ADR 0005 |
| ~~`peers-appendix`~~ | 内部 | 季 | **2026-09-03 退役**，见文首增补 |
| `sellside-research` | 内部查询 | 按需 | Travel_Pulse `inputs/` 研报处理，轻量化 |

对外交付物只有 `news-digest` 一个。其余七个是内部能力。

**不设模块的旧能力**：季度行业展望简报（`database_matain/docs/briefs/` + `generate_brief_charts.py` + `publish_feishu_q3_brief.py`）确认为一次性产物，归档不迁。

### 3. 周期键按域定义

一套 period 语义装不下四种节奏，不强行统一。**键一律 ASCII**（ADR 0007 修订）：

| 模块 | 周期键 | 例 | 中文标签 |
|---|---|---|---|
| `news-digest` | 月内周次 | `2026-08-W2` | 2026年8月第2周 |
| `industry-data` | 数据截至日 | `2026-08-08` | 数据截至 2026-08-08 |
| `aviation-monthly` | 年月 | `202607` | 2026年7月 |
| `competitor-intel` | 月内周次（周度）+ 财季（季度） | `2026-08-W2` / `26Q3` | — |
| ~~`peers-appendix`~~ | 财季 | `26Q2` | 2026-09-03 退役 |
| `hk-market` | 查询日 | `2026-08-22` | — |
| `sellside-research` | 无 | — | — |

> **2026-08-22 修订**：原设计 `news-digest` 与 `competitor-intel` 用中文键 `2026年8月第2周`。
> 因周期键同时是命令行参数与目录名，而 Windows/PowerShell 会静默损坏中文参数，改为 ASCII 键
> 加中文标签分离。详见 [ADR 0007](0007-ascii-period-keys-and-utf8-io.md)。

manifest 索引 = **域 + 周期键**。`status` 按域分别报告，不合成一个全局进度条。

### 4. 分层职责

- **Control Plane**（`workbench/`）：config、doctor、status、manifest、退出码语义（`success` / `partial` / `blocked` / `failed`）。跨域共用。
- **顶层路由**（`router/ROUTER.md`）：人的唯一入口，意图 → 域分派。
- **模块**（`modules/<域>/`）：各域的 SKILL.md、scripts、references。
- **共享数据层**（`data/`）：指标底稿、指标快照、洞察底稿、情报库。**跨域共用，不在模块内。**

### 5. Agent 配置面

规则与流程只有一份真源（`router/`、`modules/*/SKILL.md`、`conventions/`）。`.cursor/` / `.kiro/` / `.claude/` 只放**指路薄壳**，不复制正文。

现存 `Travel_Pulse/.agents/skills` 与 `.claude/skills` 的 28 个目录镜像双份一并收敛为薄壳。

## 后果

**好的：**
- Excel 只有一份，航空 pipeline 与指标同步指向同一个文件（现在 pipeline 写的是一份没人看的旧表）。
- 情报库有了归属，周度沉淀与季度消费在同一个仓内。
- 一次 doctor 覆盖全部域；一份 zip 交付全部能力。

**要接受的：**
- `database_matain` 每周在用、`peers_rs_update` 季度在用，迁移必须分域进行，不能一次全搬，也不能在周报或数据更新当周做。
- 公开仓需要一个导出脚本并保持与内部仓同步，是新增的维护项。
- 旧仓冻结后，任何「回去改一下旧仓」的动作都是破坏整合，需明令禁止。

## 相关

- `docs/GLOSSARY.md`、`docs/CAPABILITIES.md`、`docs/FOLDER.md`
- ADR 0001（指标底稿权威）、ADR 0002（竞对情报库）
