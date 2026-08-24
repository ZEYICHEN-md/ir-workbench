# 迁移记录与计划

三个旧项目 → 统一工作台。顺序与理由见 [adr/0003](adr/0003-single-repo-and-module-layout.md)。

## 硬约束

1. **分域搬，不一次全搬。**`database_matain` 每周在用，`peers_rs_update` 季度在用。
2. **每步搬完跑一次真实任务验证**再进下一步。不用 smoke test 代替真实任务。
3. **不在周报或数据更新当周做迁移。**
4. **旧仓冻结后不得回改。**任何「回去改一下旧仓」的动作都是破坏整合。

## 旧仓与去向

| 旧仓 | GitHub | 去向 |
|---|---|---|
| `0703_Travel_Pulse` | `ZEYICHEN-md/Travel_Pulse` | 拆成 `news-digest` / `aviation-monthly` / `hk-market` / `sellside-research`；CLI 内核升为 `workbench/` |
| `database_matain` | `ZEYICHEN-md/database_matain` | 整体 → `industry-data` |
| `peers_rs_update` | `ZEYICHEN-md/ota-peers-appendix` | 整体 → `peers-appendix` |

冻结后三个仓保留在 GitHub 作为历史，不再更新。

## 进度

### ✅ 编排层（2026-08-22）

跨域的工程基建，做在第 1 步之后、其余域迁入之前——先把入口和门禁立住，再往里搬东西。

- [x] **客户端薄壳**：`AGENTS.md`（唯一保证被自动读到的入口）+ `CLAUDE.md` / `.cursor/rules/`
      / `.kiro/steering/` 三个纯指路壳。规则只有一份真源，壳里不复制正文。
- [x] **状态机接入 industry-data**：五步序列（merge → dashboard → insights → feishu → publish）
      写进 `runs/<域>/<周期>/manifest.json`，含输入输出 SHA-256。步骤先种后跑，`status`
      才能报「还差几步」。新增 `ir industry mark` 用于跳过可选步骤。
- [x] **doctor 加各域健康检查**：`modules/<域>/health.py` 暴露 `checks(base)`，doctor 只汇总、
      不懂域内细节。`industry-data` 的实现是**底稿结构校验**（`layout.py`）——16 个指标列的
      表头与分组名、月份行、季度行、QTD 块，逐项核对。14 项测试验证它能抓到列位挪动、
      工作表改名、分组互换等 10 类改动。
- [x] **`ir industry publish`**：dry-run 逐行摆出线上会变什么，五道硬检查（源文件齐全 /
      必须 LF / 发布仓无无关改动 / diff 非整份重写 / 无变化不空提交），确认后才推。
- [x] `--json` 在子命令前后都能写；CLI 输出强制 UTF-8。
- [x] 回归测试 58 项。

未做（第二梯队，移交前要补）：首次安装引导、`ir package` 打包、CI。

### ✅ 第 0 步：骨架 + Control Plane（2026-08-22）

建成并验证可运行：

- `workbench/` —— `paths` / `config` / `doctor` / `status` / `manifest` / `result` / `domains` / `cli`
- 四态结果语义：`success` / `partial` / `blocked` / `failed`，含退出码映射
- 域注册表：八个域的定位、节奏、周期键在 `workbench/domains.py` 定义一次
- manifest 索引 = 域 + 周期键，含输入输出 SHA-256 留痕
- 工作簿显式配置，`config candidates` 只列候选、**不代选**
- `router/ROUTER.md` 意图路由表
- `docs/`：GLOSSARY / CAPABILITIES / MIGRATION / adr 0001–0004

验证：`py -m workbench doctor` → `partial`（模块未迁入、工作簿未指定，符合预期）；`domains`、`status` 正常。

未动任何现有域。

### 🔄 第 1 步：`industry-data`（进行中）

**最紧急**——航空 pipeline 目前写的是 `0703_Travel_Pulse/data_source/` 里那份停在 `0803` 的旧 Excel，而实际维护的是 `database_matain` 里的 `0817`。这条自动化实质上是断的。

- [x] 指标底稿归位：`国内行业数据_0817.xlsx` → `data/workbooks/`，已用 `ir config set industry` 锁定
- [x] 落实 ADR 0001：`merge_b1` 换成全量重建 + diff 门禁；`find_latest_excel`（按文件名猜最新）删除，改读锁定配置；`bootstrap`（从 `data.js` 冷启动）废弃；两个 meta 字段落为模块常量
- [x] **9 个 Node 脚本改写为 Python，去掉 Node 依赖**（ADR 0006）。等价性已用逐字节比对证明
- [x] 搬指标链 → `modules/industry_data/`：`excel.py`（读表）、`snapshot.py`（重建 + 门禁）、`dashboard.py`（看板投影）、`insights.py`（洞察 + Markdown）、`drafts.py`（草稿与确认）、`feishu.py`（多维表投影）、`jsonio.py`（序列化）、`cli.py`
- [x] 搬 `dashboard/travel/` → `dashboard/travel/`
- [x] 搬 `data_source/canonical/` → `data/canonical/`、`data_source/insights/` → `modules/industry_data/insights/`
- [x] 搬 `travel-update-pipeline/SKILL.md` → `modules/industry_data/SKILL.md`（按新命令与 ADR 0001 重写）
- [x] 补回归测试 `tests/test_industry_data.py`（22 项，覆盖投影等价性与 diff 门禁）
- [x] 删 `0703_Travel_Pulse/data_source/` 里的 `国内行业数据_0728/0803.xlsx` 废弃副本
- [x] 旧仓显式停用：`database_matain/MIGRATED.md` + README 顶部横幅 + `.cursor/rules/migrated-do-not-run.mdc`（alwaysApply）
- [x] 验收清单成文：`docs/specs/2026-08-22-industry-data-cutover-runbook.md`
- [ ] **实战验收**（改为下周真实周度数据时做，见上述 runbook）
- [ ] 术语从 `database_matain/CONTEXT.md` 归并；标注该仓 `docs/adr/0002`（canonical 为权威）与 `0004`（Gitee Pages）已失效
- [ ] 验收通过后，删 `database_matain` 里已迁走的部分

### 为什么上线验证推迟到下周（2026-08-22 决定）

人造推送只能验证「同一份数据、新管道产出一致」；真实一周会额外走到**新周次追加、
`dataUpdate` 自动盖章、洞察过期标记、飞书新建行**——这些人造验证覆盖不到。
`MIGRATION.md` 本身就要求「验证必须用真实任务，不能用 smoke test 代替」。

推迟的风险是**双轨运行**：习惯性回旧仓跑会产出分叉，且无机制提示。因此推迟的前置条件是
上面那条「旧仓显式停用」——已完成。

### 第 1 步的本地验证结果（2026-08-22）

| 项 | 结果 |
|---|---|
| 指标快照重建 | ✅ 数据截至 2026-08-08，源 `国内行业数据_0817.xlsx` |
| 与旧快照差异 | 仅 3 处，**全部是旧管道漏掉的真实数据**（见 ADR 0001 后果节），无丢失 |
| `data.js` body | 与原 Node 输出仅差那 3 处数据 + q2 键顺序归一 |
| `insights.js` body | **逐字节完全一致** |
| 洞察 Markdown | 正常生成 |
| 飞书 dry-run | 新建 3 · 填空 3 · 冲突 0 · 无变化跳过 51 |
| 飞书写入门禁 | ✅ 未确认时返回 `blocked`，不写入 |
| 回归测试 | 22 项全过 |
| Node 依赖 | ✅ 已消除 |

**不随本步搬的**（`database_matain` 里但不属于 `industry-data`）：

| 内容 | 去向 |
|---|---|
| `.cursor/skills/expert-call-pipeline/`、`.cursor/agents/expert-call-insights.md`、`scripts/expert_call_pipeline.py`、`scripts/templates/expert_call*` | 第 3.5 步 `expert-calls`（ADR 0005） |
| `docs/briefs/`、`scripts/generate_brief_charts.py`、`scripts/publish_feishu_q3_brief.py` | **归档不迁**——季度展望简报确认为一次性产物（DECISIONS Q27）。归档进 `archive/` 或留在冻结的旧仓即可，脚本废弃。 |

### 🔄 第 2 步：`aviation-monthly`（已迁入，待真实写入验收）

- [x] 管道整体迁入 `modules/aviation_monthly/pipeline.py`（保留原有 dry-run/commit、staging、
      原子安装、独立复算、溯源 manifest —— 这部分质量高，不重写）
- [x] **删掉独立命令行入口**（原 `parser()` / `main()`），唯一入口为 `ir aviation ...`
- [x] **工作簿不再由调用方传路径**，改为从 `ir config` 锁定的两份解析。这正是原来那条
      「pipeline 在写一份没人看的旧表」缺陷的根治
- [x] 三步状态机（dry-run → commit → resync）接入 manifest，周期键 = 年月
- [x] `health.py`：Excel COM 可用性 + Airline Data 五张表齐全，接入 `ir doctor`
- [x] `SKILL.md` 按新入口重写，含硬约束（不能用 openpyxl 保存底稿、合计不许分项相加、
      结构不符须停止、跨年度先建新块）
- [x] 修两个缺陷（见下），补 10 项解析测试
- [x] **dry-run 真实跑通**：2026年7月，34/34 校验通过
- [ ] **真实写入验收**：`--commit` 需用户确认；写入后须接 `ir industry merge`

### 迁移时修掉的两个既有缺陷

**1. 月份行匹配（与 industry-data 同一根因）**

管道用 `clean_text(...) == f"{month}月"` 精确匹配定位月份行，而底稿里 7 月写作
`7月 (preliminary)` → 报 `Cannot locate 2026年7月 monthly row`，**7 月根本写不进去**。

这已经是同一个根因的**第二次**出现（第一次是 `industry-data` 的旧 parser 提前终止）。
因此把规则收敛到 `modules/industry_data/layout.py` 的 `month_number()`，两个域共用一份——
`aviation-monthly` 写的就是那张底稿，必须服从同一契约。

**2. 三大航公告总量行解析（parser-drift）**

原实现只认独立的 `合计` / `总计` 行。实际三家格式不同：

| 航司 | 总量在哪 | 原实现 |
|---|---|---|
| 南航 | 独立 `合计` 行 | ✅ 能取 |
| 东航 | `载运旅客人次（千） 14,267.34 …` —— 指标名行本身 | ❌ parser-drift |
| 国航 | `4、乘客人数(千) 15,690.8 …` —— 同上且带序号前缀 | ❌ parser-drift |

修法：新增 `total_on_anchor_line()`，只取**锚点之后**的第一个数字（绕开 `4、` 序号），
并排除分项行；**优先仍用 `合计` 行**，使南航行为完全不变。

安全性论证：这不是「推算总量」——该行就是公告的官方总量行；且三家的总量都与分项之和
完全相等（东航 12,003.81 + 1,912.45 + 351.08 = 14,267.34），管道原有的勾稽校验
（容差 0.05 千人次）会独立佐证，取错必被拦下。

固定件用的是 2026-08-15 发布的三家真实公告片段。

### ⬜ 第 3 步：`news-digest` + `competitor-intel`

两个一起——沉淀是新闻采集的副产品。要做：情报库 schema 契约、JSONL 真源 + 公司档案投影、周度自动沉淀、回填 5 期历史（`2026年7月第3周` 起）作为验收测试。

同时**明确停用**五部分周报：`report-template.md` 的五部分骨架标废弃，`weekly validate-report` 对 §二 的检查移除。

### ⬜ 第 3.5 步：`expert-calls`

紧跟情报库之后，因为它是第三条采集通道（ADR 0005）。

要做：搬 `expert_call_pipeline.py` + `expert-call-insights.md` + callout 模板 + `config.example.json`；把飞书 doc token 与版块锚点写进 runbook（外部依赖，飞书改版会打断）；洞察写入飞书后追加沉淀进情报库，条目标内部级。

验收：跑一篇真实访谈到飞书，且情报库里出现对应条目。

### ⬜ 第 4 步：`hk-market` / `sellside-research`

港股全套（行情 + 南向 + 成交占比）现在散在 `hk-volume-ratio/` 与 `travel-weekly-report/scripts/` 两处，合并为一个模块。

### ⬜ 第 5 步：`peers-appendix`

放最后，**等下个财报季之前做，不在季中动**。迁移前必须先解决下面三件事。

## `peers-appendix` 迁移前置问题

审计 `peers_rs_update/scripts/earnings_summary/` 37 个脚本后发现：

### 1. 脚本存在两份拷贝，且已大面积分叉 —— 必须先定权威

| | 位置 | 文件数 |
|---|---|---|
| 仓内 | `peers_rs_update/scripts/earnings_summary/` | 37 个 `.py` + tests |
| 本机 skill | `~/.claude/skills/peers-earnings-summary/scripts/` | 25 个 `.py` |

25 个共享文件中 **20 个内容不一致**，仅 5 个相同。skill 副本缺 `accept_docx_gate` / `check_writing_gate` / `ir_snapshot` / `wip_paths` / `writing_structure_gate` / `apply_abnb_section` 等 12 个文件，包含两道 must-pass 门禁。

`scripts/README.md` 声称权威副本是 skill 目录；`docs/EARNINGS_SUMMARY_SKILL.md` 说仓内是镜像。两份文档互相矛盾。

**已裁决（2026-08-22）：仓内那份权威，skill 副本删除、不迁。**

证据——仓内含整代 skill 副本完全没有的内容：

| 标记 | 仓内 | skill 副本 |
|---|---|---|
| `ir_snapshot` | 46 处 | 0 处 |
| `must_cover_in_writing` | 3 处 | 0 处 |
| `audit_model_quarter.py` | 704 行 | 544 行 |

skill 副本整个缺 `check_writing_gate.py` / `ir_snapshot.py` / `writing_structure_gate.py`，而这三个是 2026-08-09 提交「Add writing gate for Q1 structure slots and IR quote grounding」引入的；仓内工作区对 git 干净。skill 副本是 2026-08-17 16:48 从更旧来源批量安装的快照，落后一整代。

迁移时须同步改掉 `scripts/README.md` 里「canonical skill 在 `~/.claude/skills/`」的说法，否则规则与实物再次脱节。

### 2. 三份文档给出三套不同的正式入口

`docs/pipeline/earnings-summary.md` 与 `MODEL_PERFECT_CONTRACT.md` 只给 `run_earnings_pipeline.py`；`scripts/README*.md` 给一堆单步命令；`EARNINGS_SUMMARY_SKILL.md` 给最旧一代 BKNG 链路。

审计结论：正式入口应为 **`run_earnings_pipeline.py`**（主）+ `update_finance_from_model.py`（Writing）+ `render_ir_snapshot_md.py`（材料阶段），其余降级为内部实现或废弃。

### 3. 37 个脚本里 36 个零测试覆盖

只有 `tests/test_chart_label_utils.py`，覆盖 5 个纯函数。四道 must-pass 门禁与全部 `apply_*` 逻辑无回归测试。

→ 泛化重构前必须先补门禁的等价性测试，否则无法验证重构没改变行为。

### 已识别可废弃

`render_expe_finance_texts.py`（自称 LEGACY）、`audit_expe_alignment.py`（写死旧路径，无人调用）、`verify_abnb_26q2_numbers.py` 与 `verify_abnb_26q2_ops_finance.py`（写死 26Q2 数字）、`_cleanup_wip_layout.py`（一次性迁移脚本）。

### 已识别重复能力

- `apply_finance_section`(BKNG) / `apply_expe_finance_section`(EXPE) / `apply_abnb_section`(ABNB)：算法几乎逐行相同，差异是 ANCHORS 表 → 一份实现 + 三份配置
- `export_charts_hires`(原生) vs 两个 clipboard 版：两条技术路线 + 公司特化
- `render_*` 两兄弟：整代已被 `build_expe_writing_brief` + agent 写 texts 取代

### 已识别缺陷（非迁移引入）

- `run_earnings_pipeline.gate_charts_embed` **无条件**调 `export_expe_charts_clipboard.py`，不读 `man["ticker"]`，而该脚本的 `WORD_SLOT_MAP` 是 EXPE 的 image3–8 → 对 ABNB 会贴错图
- ABNB 的 writing 阶段走不通：`extract_model_facts.ROW_MAPS` 无 ABNB，`update_finance_from_model` 直接 `raise SystemExit("Unsupported ticker ABNB")`
- `MODEL_PERFECT_CONTRACT.md` 数据流里的 `build_fill_inputs.py` 全仓不存在
