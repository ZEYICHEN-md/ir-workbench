# 迁移记录与计划

三个旧项目 → 统一工作台。顺序与理由见 [adr/0003](adr/0003-single-repo-and-module-layout.md)。

## 硬约束

1. **分域搬，不一次全搬。**`database_matain` 每周在用，`peers_rs_update` 季度在用。
2. **每步搬完跑一次真实任务验证**再进下一步。不用 smoke test 代替真实任务。
3. **不在周报或数据更新当周做迁移。**
4. **旧仓冻结后不得回改。**任何「回去改一下旧仓」的动作都是破坏整合。

## 旧仓与去向

## 仓库现状（2026-09-01）

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
| `peers_rs_update` | `ZEYICHEN-md/ota-peers-appendix` | **不迁入**。2026-09-03 裁定退役：Appendix / 业绩总结由人写，季度检索走情报库；旧仓冻结保留 |

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

- [x] **Windows CI**：`.github/workflows/tests.yml` 在 push / PR / 手动触发时安装完整依赖，跑全量 unittest、doctor、域注册表和 LF hygiene。

未做（第二梯队）：`ir package` 打包、公开作品集导出。同事开箱手册已有 `docs/HANDOVER.md`。

### ✅ 第 0 步：骨架 + Control Plane（2026-08-22）

建成并验证可运行：

- `workbench/` —— `paths` / `config` / `doctor` / `status` / `manifest` / `result` / `domains` / `cli`
- 四态结果语义：`success` / `partial` / `blocked` / `failed`，含退出码映射
- 域注册表：最初规划八个域；`peers-appendix` 退役后由 `peers-model` 补回第八个域；`shareholder-list` 为第九个域（ADR 0010）。定位、节奏、周期键与验收状态在 `workbench/domains.py` 定义一次
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
| `.cursor/skills/expert-call-pipeline/`、`.cursor/agents/expert-call-insights.md`、`scripts/expert_call_pipeline.py`、`scripts/templates/expert_call*` | 已迁入 `modules/expert_calls/`（第 3.5 步，ADR 0005） |
| `docs/briefs/`、`scripts/generate_brief_charts.py`、`scripts/publish_feishu_q3_brief.py` | **归档不迁**——季度展望简报确认为一次性产物（DECISIONS Q27）。归档进 `archive/` 或留在冻结的旧仓即可，脚本废弃。 |

### ✅ 第 2 步：`aviation-monthly`（2026-08 完成真实写入验收）

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
- [x] **真实写入验收**：2026 年 7 月数据已正式写入两份权威 Excel，随后重建行业快照与看板；`runs/aviation-monthly/202607/pipeline.json` 45/45 校验通过，16 个官方输入均可逐格溯源

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

### ✅ 第 3 步：`news-digest` + `competitor-intel`（2026-08-W4 完成真实一期验收）

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
- [x] 去重台账迁入并补全：迁移时 31 条 → 51 条 / 7 期；W4 验收后为 **68 条 / 9 期**
- [x] 交付物结构校验取代旧的 §二 校验；主动拦五部分骨架
- [x] 导出器**照搬不重写**，逐字节比对证明新旧输出一致
- [x] 删掉独立命令行入口，唯一入口 `ir news ...`
- [x] 四期真实成品全部通过校验，零假警告；两个 RSS 源实测可达
- [x] 32 项测试
- [x] **真实一期验收**：`2026-08-W4` 从日期审计、validate、export、log、情报库沉淀到飞书发布全链完成；新闻 manifest 7/7、情报库 2/2

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

### 第 3 步的对抗性复审（2026-08-25，使用者要求）

上面两处补完后又做了一轮对抗性审查，对照旧仓 28 份知识层文件。**又查出 5 处严重漏迁**，
形态比前两处更隐蔽：**新仓有一句概括，旧仓有一整套判据**——读新仓不会觉得缺什么。

| 漏项 | 原在哪 | 已补到 | 漏了会怎样 |
|---|---|---|---|
| **源质量门槛**（可信源清单 + 判定原则 + 4 条排除特征；非旗舰源命中必须落到可信源） | 旧 `ADR-004` + `data-sources.md` | `modules/news_digest/references/source-quality.md` | SKILL 要求每期跑补充检索，必然捞回内容农场与「TOP10」榜单稿，无门槛就直接落进**唯一对外交付物** |
| **B 类「旅行中断/外部冲击」整类采集** | `data-sources.md`（反例：2026/06 欧洲热浪致铁路胀轨停运） | `references/retrieval.md` + `recall.py` 新增 4 条 B 类查询与中断类目词 | 整类静默漏掉且无提示。情报库里已有「台风红霞致香港机场 350 航班取消」，证明该收，而召回层根本不去找 |
| **中文侧检索参数级禁令**（描述式只喂 exa；tavily 必须短词且不锁域名；`topic` 只接受 `general`） | 旧 `ADR-002` 对照实验表 | `references/retrieval.md`（含整张实验表） | **本次会话现场重犯**：我用中文描述式喂 tavily 查 8/17–8/23，返回 2023–2025 的稿子 |
| **飞常准 / 航班管家 周度手动取数** | `manual-acquisition.md` | `modules/industry_data/references/manual-sources.md` | 底稿右侧 W/X/Y 与国际运力列每周靠人从微信抄，SKILL 只说列在哪不说数从哪来 → 每周固定动作断掉 |
| **lark-cli Windows 编码与传参坑**（`@file` 必须 UTF-8 **无 BOM**；`--content` 不支持 @file；`--params` 不能写进 URL query；审批与授权两层且先后有序） | 旧 `.kiro/steering/feishu-cli-usage.md` | `conventions/lark-cli-windows.md` | news-digest 最后一步就是写飞书，这些坑一个不避就卡在 invalid JSON 与中文乱码 |

另补了中等项：选稿三步与定稿自检清单、图标语义、概览写法与禁用大帽子、语气要求、
「延续上期」立成规则 → `modules/news_digest/references/editorial-standards.md`。

并裁定了一处**规则冲突**：旧仓「非发布周用第三方测算值顶上、不留空窗」与工作台
「抓不到就 blocked、不推算」直接相反，而两边都没写对方已废。裁定旧规则停用
（理由见 `modules/industry_data/references/manual-sources.md`）——那条服务的是五部分周报
§二「每周必须有个数」的需求，那一节已经没了；往底稿塞测算值会让所有下游当实测值用。

> **教训升级**：验收标准从「能力在不在」再往前推一格——**每条能力都要能指出支撑它的
> 判断规范落在哪个文件的哪一节**。
>
> 还有一条元教训：`conventions/README.md` 的待迁表里曾写「lark-cli 约定属全局规范，
> 工作台不再抄一份」——**这个判断是没核对就下的**，全局那份只有策略、零踩坑。
> 「已被 X 覆盖」这种记法本身会变成新的漏迁来源，因为它让后来的人不再去查。
> 该表已加硬要求：写「已覆盖」必须指出是哪份文件的哪一节，并真的看过。

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
这两期有成品、也进了情报库，但从没登记。已从情报库条目补录 20 条，迁移当时达到 51 条 / 7 期；
完成 W4 真实验收后，当前为 **68 条 / 9 期**。

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

**6. 迁移回填时建档层 8 家里 MEITUAN / TCEL / FLIGGY 为 0 条。**

这是迁移时点的覆盖事实；2026-08-W4 后 TCEL 与 FLIGGY 已有周度条目。2026-09-02 已把
美团 26Q2 财报与电话会按季度通道入库。名单不动；若连续多期有公开动作仍无周度条目，才判采集漏项。

### ✅ 第 3.5 步：`expert-calls`（2026-09-03 完成真实双分支验收）

紧跟情报库之后，因为它是第三条采集通道（ADR 0005）。已完成：

- [x] 新模块 `modules/expert_calls/`、统一入口 `ir expert-calls`、`YYYYMMDD-HHMMSS` run id 与六步状态机
- [x] `pdfplumber` 按页抽取；空文本/扫描件 hard block；真实 PDF/TXT 加入 Git 忽略边界
- [x] 人工选择前生成候选排序：逐篇概述、关键数据、行业事实/洞察、专家来源与职能、局限与六维评分，代码计算 A/B/C 档；大型跨国平台相关业务高管优先；区域性来源降低专家背书，但直接覆盖 Trip.com 国际扩张重点中国或亚太市场时最高可保留 B 档；单体酒店和非重点区域小公司仍受 C 档上限；排序不代替人决定
- [x] **候选排序真实只读验证**：2026-09-01 并行读取 `test_expert_calls/` 的 7 篇真实访谈；加入大型跨国平台高管偏好，并将公司规模、战略市场相关性和相对公开口径的信息增量拆分后，复跑为 A 1 / B 4 / C 2。MakeMyTrip 来源因直接覆盖亚太重点市场由 C 恢复为 B；Expedia B2B 来源虽权威，但核心内容与 26Q2 财报及电话会大体重复，`information_gain` 从 5 降至 2，由 A 降为 B。已生成更新后人读报告；全部保持待决定，未渲染 callout、未调用飞书；这不等于真实发布验收
- [x] manifest 代码门禁：直接 IR 信息增量、至少 4 个锚定数字、每段数字、每个数字原话与页码/位置；B2B 不单独构成收录理由
- [x] 2026-09-01 用 `lark-cli --as user` 回读目标 Wiki **revision 1680**，确认三个现有摘要的唯一版式：灰边框 + 📌 + blockquote + 裸 URL；旧浅蓝背景与 bookmark 模板作废
- [x] 专家访谈与公司情报库解耦：本地解析后先从所有访谈生成情报草稿，不受飞书 `include` 影响；所有条目强制 `internal` 并保留专家原话与位置，人工确认后走既有 `intel add` 入库
- [x] 飞书发布成为独立展示分支；默认 dry-run，按精确标题/PDF 链接判重，逐条写后回读并用新 block id 串行插入；发布成功不生成或提交情报草稿
- [x] 合成固定件回归测试，不使用真实访谈材料、不访问飞书
- [x] **真实业务验收（飞书分支）**：`20260901-190000` 已写入飞书 3 条并回读，manifest 记录 3 个 block id
- [x] **真实业务验收（情报分支）**：同批 34 条草稿已全量分流；A 类 11 条全部进入正式库，B 类 14 条全部进入 `deferred.jsonl`，9 条剔除保留完整批准清单。三组互斥且逐 ID 对账无缺口，详见 `docs/specs/2026-09-03-expert-calls-acceptance-audit.md`

两条真实分支均完成既定范围验收，`expert-calls` 升级为 `validated`。后续批次继续强制 `A + B + 剔除 = 草稿总数`，不能用飞书 manifest 的完成数替代情报分流对账。

### ✅ 第 4 步：`hk-market` / `sellside-research`（2026-09-02 迁入并完成真实只读验收）

**hk-market**

- [x] 把散在 `hk-volume-ratio/`、`ccass_southbound.py`、`hk_market_pulse.py` 的三类查询合并到
      `modules/hk_market/`，删除独立 CLI，唯一入口为 `ir hk-market ...`
- [x] 行情、南向、成交占比按需独立运行；manifest 只记实际执行项，不制造「另外两项没跑」的假待办
- [x] 港交所 CCASS 按实际持股日期去重，月初节假日回退到上月的数据不混入本月
- [x] 55% 监管状态只读**数据齐全的最近完整 FY**；缺一个月即显示数据不足，L12M/季度不得替代
- [x] akshare 闭区间与 yfinance 半开区间统一，防止历史 as-of 查询多吃一天
- [x] Windows Python 3.14 的 WMI 卡死兼容：只在模块内禁用 `platform` WMI 快路径，
      真实栈定位与取舍记入 `DECISIONS.md`
- [x] **真实查询验收**（2026-09-02）：恒指/恒科/携程周行情成功；CCASS 返回实际日期
      2026-09-01，12 家中 9 家有数据、3 家明确报缺；四只双重挂牌标的成交占比均成功，
      25FY 为携程 45.26%、华住 10.47%、网易 57.81%、百度 28.65%

**sellside-research**

- [x] 新建 `modules/sellside_research/` 与唯一入口 `ir sellside extract`
- [x] PDF 按页抽取并保留 PDF 查看器页码；扫描件/全空文本 hard block
- [x] SKILL 把公司披露事实、分析师判断、预测与估值变化分开，关键数字强制标页码
- [x] 落实 ADR 0004：不建索引、不进竞对情报库、不产生跨期 manifest
- [x] 按页抽取物含第三方大段原文，`outputs/sellside-research/**` 整体 Git 忽略
- [x] **真实输入验收（抽取层）**：UBS China hotel first read 13/13 页抽取成功，共 109,717 字符
- [x] **真实输入验收（摘读层）**：UBS 酒店 first read 已按事实/观点/预测/估值变化分开摘读并回核第 1 页关键数字；图表未可靠抽取的值未写成确定数据。产物不进 Git

### ⬛ 第 5 步：`peers-appendix`（2026-09-03 退役，不迁入）

- [x] 使用者确认：季度 Appendix / 业绩总结不适合做成工作台流水线
- [x] 从域注册表、CLI、功能清单和路由表移除；`modules/peers_appendix/` 与对应测试删除
- [x] 季度「这家做了什么 / 电话会怎么说」改走 `competitor-intel`
- [x] 旧仓 `peers_rs_update` 继续冻结，不回改、不作为工作台入口

### ✅ 第 6 步：`peers-model`（2026-09-03，机械维护，不恢复 Appendix）

- [x] 新建独立域，只做 Excel Model 与 Charts；Word Appendix 仍退役
- [x] 三份权威 Model 由本机 config 锁定：ABE 共用、美团独立、同程独立
- [x] 同程只写前两个 sheet；图表只改引用了本次实际更新数据 sheet 的 series
- [x] 季报 / 半年报 / 年报按模板已有区块分流；没有可比列就跳过
- [x] 图表政策：2019 同期起、排除 2020–2022、接 2023 至目标期；只给同期点打标签
- [x] 只输出 `outputs/peers-model/` 副本，不覆盖权威文件
- [x] 26Q2 holdout（删掉已有期间列再写回）：BKNG / EXPE / ABNB / 美团 / 同程全部通过
- [x] 26Q2 历史 PDF 盲填 → plan → apply 副本：五家全部通过关闭重开、PDF 第三遍与 Charts 审计
- [x] 年报 / 半年报路径 holdout：BKNG/EXPE/ABNB FY2025、美团 FY2022 与 20H1、同程 FY2022 通过

### ⬛ 第 7 步：`shareholder-list`（2026-09-04 迁入引擎）

- [x] 生成器、母版、市值、审计都放进 `modules/shareholder_list/`（与其它域同一形状）
- [x] 唯一入口 `ir shareholder-list rebuild`；不保留 `src/` 与 `scripts/rebuild.ps1`
- [x] 技能真源 `modules/shareholder_list/SKILL.md`；路由进 `router/ROUTER.md`
- [x] 源包 ADR 改编号为 0011–0014，不覆盖工作台 0001–0004
- [x] 用 Downloads 里的 CIQ 底表跑通锁定重建（exit 0、validate.ok、audit n=0）

下面仍保留迁移前审计，说明当初为什么难迁、以及为什么后来决定不迁 Appendix 写作。

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
