# 迁移记录与计划

三个旧项目 → 统一工作台。顺序与理由见 [adr/0003](adr/0003-single-repo-and-module-layout.md)。

## 硬约束

1. **分域搬，不一次全搬。**`database_matain` 每周在用，`peers_rs_update` 季度在用。
2. **每步搬完跑一次真实任务验证**再进下一步。不用 smoke test 代替真实任务。
3. **不在周报或数据更新当周做迁移。**
4. **旧仓冻结后不得回改。**任何「回去改一下旧仓」的动作都是破坏整合。

## 旧仓与去向

## 仓库现状（2026-08-24）

| 仓 | 地址 | 可见性 | 说明 |
|---|---|---|---|
| 内部工作仓 | `ZEYICHEN-md/ir-workbench` | **私有** | 工作台本体，含指标底稿与运行记录 |
| 看板发布仓 | `ZEYICHEN-md/travel-dashboard` | 公开 | → EdgeOne → https://datamax.fun |
| 公开作品集仓 | 未建 | — | 须由导出脚本生成，见下方警告 |

> ⚠️ **内部仓永远不能改成公开。**指标底稿 Excel 已纳入 git 追踪，历史里永久存在；
> 删掉文件也取不出历史。公开作品集仓必须**另起空仓 + 导出脚本**生成，不能 fork、
> 不能镜像、不能改可见性。
>
> ⚠️ **仓在个人账号下，交接时须转移。**否则原作者离职后部门拿不到工作台。

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

### ✅ 第 1 步：`industry-data`（2026-08-24 完成，含真实上线验收）

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
- [x] **实战验收（2026-08-24 完成）**：真实周度数据 `2026-08-15` 走完 merge → dashboard →
      publish，线上 datamax.fun 核对通过。详见下方「实战验收结果」
- [x] 术语从 `database_matain/CONTEXT.md` 归并；标注该仓 `docs/adr/0002`（canonical 为权威）
      与 `0004`（Gitee Pages）已失效，并在 `CONTEXT.md` 顶部列出「已失效 / 已归并 / 未迁」导航
- [x] 删 `database_matain` 里已迁走的部分（45 个文件），保留 `docs/`、`CONTEXT.md`、git 历史
      与未迁的 Expert Call 链

### 实战验收结果（2026-08-24）

用真实的 `国内行业数据_0824.xlsx`（新增 `8/9-8/15` 一周）走完整条链。

| 核对项 | 结果 |
|---|---|
| 数据截至日自动盖章 | `2026-08-15`（按最新周结束日） |
| 变动 | 新增 6（本周六项）· 修改 0 · 清空 0 |
| 线上 datamax.fun | 新周次、月度到 7 月、Q2 三项齐全、9 图表正常、中英切换正常 |
| 发布仓 | `1d9eae6`，已同步 origin |
| 回归测试 | 105 项全过 |

**切换带来的三处线上变化**（runbook 预告过，全部到位）：月度酒店 RevPAR 7 月由空变 -5.0%；
季度 Q2 补上入住率 -0.83% 与 ADR +2.9%；一批浮点尾数归一。这些都是旧管道漏读的真实数据。

### 验收中发现并修掉的三处缺陷

真实跑才暴露的，本地 smoke test 碰不到 —— 这印证了「验证必须用真实任务」这条硬约束。

**1. diff 门禁把浮点尾数当成「修改」。**换一份被 Excel 重新保存过的底稿后，merge 报「修改 14」，
逐格核对发现全是 `-0.10400000000000009` 对 `-0.104` 这类差异（Excel 按 15 位有效数字写缓存值）。
危险在于 runbook 让人盯的信号正是「修改应为 0」——假修改会把真修改淹掉。改为相对容差 `1e-9`，
并让「修改」栏列出明细（此前只报数量，快照被覆盖后无从查证改了哪一格）。

**2. 洞察过期标记在迁移中丢了 —— 这是行为回退，不是继承缺陷。**
旧实现 `sync_travel.py` 在 merge 后**自动**调用 `mark_insights_stale.js`（旧 `scripts/README.md`
写明「merge-excel 会自动调用」），改写时漏掉了这一步。实测后果：洞察 `basedOn` 停在 `2026-08-08`、
快照已到 `08-15`，而过期标记三项全 `false`，看板会拿上一周的洞察配这一周的图表且无提示。
现在 `merge` 比对日期后自动打标。

> **教训**：跨运行时改写的等价性验证做了「看板输出逐字节比对」，但那只能证明**产出内容**一致，
> 证明不了**行为链**一致（哪一步自动触发哪一步）。逐字节比对有盲区，需要另外核对调用关系。

**3. `partial` 被一律当成「没做完」。**`generate-dashboard` 四个投影文件都写出了，只因带洞察过期
提醒返回 `partial`，步骤就被记成 `running`，导致进度少算一步、且 publish 成功后状态机还提示回头
去生成看板。现在由命令用 `data["step_complete"]` 自己声明产出是否完整（`steps.step_state()`）。

### 顺带新增的两道人工填写核对

使用者每周更新酒店与航空，且**左右两侧都手填**（右侧 W/X/Y 与左侧 QTD G/H/I）。而读表规则是
右侧优先、右侧为空才回退左侧——右侧填错行时左侧的正确值不生效，也不报错。于是把这份重复劳动
当双录用：`modules/industry_data/crosscheck.py` 核对两侧一致性，并检查最新周六项是否填齐。

第一版对「左右配对不上」一律告警，实测在 `6/21-6/27` 上误报（右侧三项齐全，左侧没有那一周，
对结果无影响）——改为只在右侧有缺格、真的要靠回退时才报，避免每周固定噪音让人开始忽略提醒。

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

### 🔄 第 3 步：`news-digest` + `competitor-intel`（2026-08-25 迁入，待真实一期验收）

两个一起——沉淀是新闻采集的副产品。

**competitor-intel（新建，ADR 0002 落地）**

- [x] JSONL 真源 + 建档层公司档案投影；两类条目（动作 / 表述）
- [x] 受控词表：建档层 8 家 + 索引层 8 家（代码，改动须走决策）+ 其他桶种子（加一家不用走决策）
- [x] 主题 10 个，键为 ASCII slug；未登记主题一律拒绝
- [x] 两种切法：按公司纵切（含「仅被提及」）、按主题横切（按公司分组，建档层排前）
- [x] TCOM 采集不设限、发布设限；沾到即标内部级；`for_digest_supply()` 一律排除
- [x] **回填 4 期历史 39 条**，幂等已验（重跑 +0 / 跳过 39）
- [x] 38 项测试；`ir doctor` 查真源可解析 + 投影是否落后于真源

**news-digest（从 `0703_Travel_Pulse` 迁入）**

- [x] 期次键改 ASCII（`2026-08-W2`），中文标签只用于汇报与交付文件名
- [x] 召回层合并两个脚本（Skift + 36氪 RSS）；补充检索清单只打印不执行
- [x] 去重台账迁入并补全：31 条 → **51 条 / 7 期**
- [x] 交付物结构校验取代旧的 §二 校验；主动拦五部分骨架
- [x] 导出器**照搬不重写**，逐字节比对证明新旧输出一致
- [x] 删掉独立命令行入口，唯一入口 `ir news ...`
- [x] 四期真实成品全部通过校验，零假警告；两个 RSS 源实测可达
- [x] 32 项测试
- [ ] **真实一期验收**：下一期从 `plan` 走到 `deposit`

**明确停用的五部分周报**

- [x] `report-template.md` 的五部分骨架作废，往期成品只作归档
- [x] 旧 `report_validate.validate_section_two()` 那 7 条 §二 规则不迁
- [x] 旧 `workflow.complete()` 的「一二三四五标题齐全」契约与 `section-two-review` 门禁不迁
- [x] 反过来**主动拦**：`ir news validate` 见到 `## 三、` 及以后即报硬错误
- [x] 保留情报主周核对（旧 `validate_intelligence_week`）——它与骨架无关，仍有价值

### 第 3 步的两处漏迁（使用者指出后补上，2026-08-25）

使用者反馈「旧仓说一句『更新新一周的新闻精选』就全流程跑完，包括编辑飞书云文档」。核对后确认两处真漏了：

**1. 飞书发布 runbook 整份没迁。**
`0703_Travel_Pulse/conventions/news-digest-feishu-archive.md`（157 行）没搬，而 SKILL 里
「发布到飞书」那一步写的是「见 SKILL.md 的发布一节」——**那一节不存在**。
状态机留了一步，既没实现也没流程。这类悬空引用比缺功能更坏：它看起来是有的。
已整份搬入 `modules/news_digest/references/feishu-publish.md`，只改路径，
两份文档相反的写语义与「附件定位」那段踩坑记录一字未动。

**2. 端到端剧本没迁，只搬了命令清单。**
旧仓 `travel-pulse-weekly/SKILL.md` 是一份**编排剧本**：使用者说一句话，Agent 一路跑完到飞书。
迁移后变成 7 个独立的 `ir news` 子命令，能力齐全但没有那份「按这个顺序一路做完」的指令，
体验从「说一句」退回「逐条下指令」。已在 `modules/news_digest/SKILL.md` 补回，
明确只在两处停下（入库前核对打标、发布前等授权）。

> **教训**：迁移的验收标准过去只看「能力在不在」。这两处都属于**能力在、流程不在**——
> 脚本都搬了、命令都能跑，但把它们串起来的那份编排知识留在旧仓。
> 逐字节比对证明不了这个，跑一遍单个命令也证明不了，只有真按「使用者说一句话」演一遍才暴露。

**不迁的旧脚本**：`extract_news_digest.py`（依赖五章周报，且近三期精选本就是直接写的）、
`fetch_airline_inputs.py`（写入早已停用）、`read_industry_data.py` / `read_airline_data.py`
（归 `industry-data`）、`ccass_southbound.py` / `hk_market_pulse.py`（归 `hk-market`，第 4 步）。

### 第 3 步迁移中发现的问题

**1. ADR 0002 写「回填 5 期」，实际只有 4 期精选成品。**
`2026年7月第3周` 起的成品是 4 份（`旅行行业新闻精选-*.md`）。第 5 期（`2026年7月第2周`）
与更早的 `6月第4周` 只有五部分周报，且三份的 §一 结构互不相同（`6月第4周` 用
`### 英文标题`、`7月第2周` 的来源表在 §四、`7月第3周` 在 §五），而 `7月第3周` 的周报 §一
只有 7 条、它的精选有 10 条。**结论：只回填 4 期精选。**为已停用格式的 2 期低质量数据写三套
解析器不值得，且这些数据本身口径不齐。这条差异记在这里而不是悄悄按 4 期做。

**2. 台账漏登记两期，跨期去重对那两周是瞎的。**
旧台账 31 条覆盖 `06-W4 / 07-W1 / 07-W2 / 07-W4 / 08-W2`，缺 `07-W3` 与 `08-W1`——
这两期有成品、也进了情报库，但从没登记。已从情报库条目补录 20 条，现为 51 条 / 7 期。

**3. 台账的「最近 N 期」原本按文件顺序取，补录会把它搞坏。**
补录的期次追加到文件末尾，于是被当成最新的，真正的最近三期被挤出比对范围——查重静默失效。
改为按期次键排序取最新。**这个修法是 ASCII 键换来的**：旧的中文键字典序会把
`2026年10月第1周` 排在 `2026年7月第3周` 前面，所以当初只能依赖文件顺序。

**4. 补录历史时查重方向是反的。**
判重问的是「这条是不是重复了**更早**写过的东西」，而补录的期次比台账已有的都早。
实测补 `07-W3` 时 10 条里 7 条被判重复，命中的全是它**后面**几期的跟进报道
（例：07-W3 的「欧盟处罚 Google」命中 07-W4 的「Google 垂直搜索公平性仍受关注」）——
相似关系判对了，但拿来阻止补录是错的用法。新增 `backfill` 模式跳过查重，行标
`backfilled: true`，与 `forced_reason` 分开：强收一条重复稿和补一段缺失历史是两件事。

**5. 回填实测抓到情报库两个缺陷**（详见 ADR 0002 相关提交）：
`TRIP` 是 Tripadvisor 的合法键，却被自己的防歧义规则拒掉（比对没区分大小写）；
配对可信度用 `SequenceMatcher.ratio()` 把 4 条正确配对判成疑似错位——来源表标题是正文标题
的**刻意缩写**，按两串总长归一必然偏低，须改成「短串被覆盖了多少」。

**6. 建档层 8 家里 MEITUAN / TCEL / FLIGGY 回填后 0 条。**
4 期精选里确实没有这三家的条目。这与选稿边界一致（中文侧只收「携程非当事方」的境内事件，
可收范围本来就窄），是覆盖事实不是 bug。`ir doctor` 会持续报这一项，直到中文侧采集补上。

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
