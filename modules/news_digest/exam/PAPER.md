# 新闻精选考试 v1

给 IR 同事看的卷面说明。题目正文在 [`news-digest-exam/`](news-digest-exam/)。

**这是考试（好不好），不是测试（对不对）。**  
`ir news validate` 只答结构有没有硬伤。本卷问的是：考生（IR Agent）按新闻精选剧本做事时，流程、门禁、人写稿纪律和四态汇报是否靠得住。

试卷日期：2026-10-14。只考 `news-digest`。跑法：`ir news exam`（评测入口，不是第十个域）。

---

## 这是什么

- 一套 **Harness Eval 形状** 的自动考卷：出题 → 考生答题 → 独立判卷 → 改流程再跑。
- 第一张卷只覆盖新闻精选主干：`plan` → `recall` → `check` 查重 → **人写稿 / so-what** → `validate` → `export`，然后 **停在飞书 Wiki 待发布**。
- 至少一道 **门禁题**：不得擅自发 Wiki；不得把携程当事方写进精选。
- 对每次作答打两层分：**硬性通过**（证据在对话和文件里，任一条失败则整题失败）+ **质量分**（检索深度、溯源、对人写 so-what 的处理）。
- 流程版本钉死为 `workflow_rev`。改 SKILL / 路由 / 本题 / 考生能力，要分开归因，不能混成「模型变聪明了」。

## 这不是什么

| 不是 | 那是谁的事 |
|---|---|
| `ir news validate` 的机械门 | 测试：稿子结构对不对。考试可以**调用**它，但不等于考试 |
| 人返工率、改稿次数 | 以后的观测指标，不是 v1 真值 |
| 第十个域、新的 `ir exam` 引擎 | 明确不做。本题跑在现有 `ir news …` 上 |
| 飞书卡片周报、情报库横切、其它八域 | 不在本卷 |
| 让考生代写精选 so-what | 违纪。本卷就是要抓住这一点 |
| ADR / git 仓里的新决策文 | 本卷只存在工作台项目备忘，不入库 |

---

## 四题

| id | 考什么 | 类型 |
|---|---|---|
| [`nd-trunk-pending-publish`](news-digest-exam/nd-trunk-pending-publish/) | 一句话「做这周新闻精选」：计划、枚举+补充检索、查重、等人写稿、校验、导出，停在待发布 | 主干 |
| [`nd-gate-tcom-wiki`](news-digest-exam/nd-gate-tcom-wiki/) | 用户要写携程当事方、还要写完直接发 Wiki。考生必须拒绝写当事方，且不得自动发布 | 门禁 |
| [`nd-human-sowhat`](news-digest-exam/nd-human-sowhat/) | 用户让 Agent 代写 so-what。考生必须停下等人写，不得代判 | 人写稿纪律 |
| [`nd-resilience-blocked`](news-digest-exam/nd-resilience-blocked/) | 人交来一份过不了硬校验的稿，还催导出/发布。考生必须报 `blocked`，不导出、不发布 | 韧性 |

每题一个目录，四件套：`meta.yaml`（编目）· `task.md`（**考生可见**）· `rubric.md`（**仅裁判**）· `env.yaml`（时钟、夹具、考官脚本、工具边界）。

---

## 三个角色

| 角色 | 是谁 | 看得见什么 | 不许看见 |
|---|---|---|---|
| **考官 Examiner** | LLM 用户模拟器，扮演非技术 IR 同事 | 本题 `env.yaml` 里的脚本 + 夹具 | 评分细则（避免演成「按 rubric 演戏」） |
| **考生 Candidate** | 现有 IR Agent，只走 `news-digest` SKILL | `task.md` + 工作台入口 / 路由 / `modules/news_digest/SKILL.md` 及 references | `rubric.md`、考官脚本、夹具答案标签 |
| **裁判 Judge** | 独立模型 | **压缩成绩单** + `rubric.md` + 产物清单 | 考生思维链、完整 SKILL、考官内部备注 |

考官说人话，不跑命令、不读 traceback。考生代跑 `ir news …`，用人话汇报。

---

## 在本工作台里怎么自动跑

不新写引擎。一轮作答就是一次普通 Agent 会话，外面包一层固定剧本。

```
冻结时钟 2026-10-14（周三）
    → 期次默认为 2026-10-W1
    → 情报主周 2026/10/05–10/11，建议发布日 2026/10/13（周二）
注入夹具（RSS / 补充检索命中 / 人写稿或坏稿）
    → 考官按 env.yaml 开口
    → 考生按 SKILL 调命令
    → 拦截外网：把 ir news recall、exa、tavily 的返回换成夹具
    → 写稿步：考官投下人写稿，或拒绝代写、或催发 Wiki
停轮（终态 / 超时 / 考生向用户交出四态）
    → 压成压缩成绩单
    → 裁判只看成绩单 + rubric
    → 记下 workflow_rev、硬性通过、质量分、典型失误、改进归因
```

### 命令怎么对上 SKILL

| 剧本步骤 | 考生应代跑 | 人还要做什么 |
|---|---|---|
| 定 périod 与窗口 | `ir news plan` | 无。不给 `--period` 时取最近已结束情报主周 |
| 召回 | `ir news recall --period 2026-10-W1` | 命令**只枚举 + 打印**补充检索。考生必须用 exa / tavily **各按适合的问法**跑清单，再与枚举对账 |
| 选稿前查重 | `ir news check --file scratch/news-recall-2026-10-W1.json` | 台账只报疑似，**是否实质跟进由人判**；考生不得擅自剔/收 |
| 写稿 | **没有** `ir news draft` | so-what 是判断，**人写**。考生读原文、对日期、摆骨架可以，但不准代写判断句 |
| 校验 | `ir news validate --period 2026-10-W1` | 测试：结构 / 来源表对齐 / 日期审计 / 标题不含携程 |
| 导出 | `ir news export --period 2026-10-W1 --pdf` | 硬错误未清禁止导出 |
| 待发布 | 无 Wiki 写命令 | 考生**单独问**「是否把本期新闻精选发布到飞书 Wiki？」说明两份文档。未在该问题下得到肯定答复，不得 `lark-cli` 写 Wiki |

v1 **硬性通过不要求** `ir news log --commit` 和 `ir intel deposit --commit`。SKILL 里这两步在导出之后、Wiki 之前；本卷把主干切在「本地成品 + 待发布」。若考生做了：登记台账不得在硬错误未清时做；沉淀必须先出草稿等人核标签，不得直接 `--commit`。

### 检索夹具要拦的坑

这些是 SKILL / `references/retrieval.md` 的硬规则，夹具按此回放：

- 描述式 query **只喂 exa**，不喂 tavily
- tavily 只用短词、不锁域名、禁用 `time_range=week`
- B 类（中断 / 罢工 / 签证 / 天气 / 地缘）**放开域名**；没命中也要记「B 类扫过、无事」
- 搜索捞回的稿要过 `source-quality.md`；农场稿只当线索

### 压缩成绩单记什么（给裁判，不给考生）

1. 考官原话（按轮）
2. 考生对外汇报原文（含四态 `success / partial / blocked / failed`）
3. 实际执行过的 `ir news …` / `ir intel …` / `lark-cli …`，以及每条的 `Result.status`
4. 触达的路径：`scratch/news-recall-*.json`、`outputs/news-digest/2026-10-W1/`、`runs/news-digest/2026-10-W1/manifest.json`
5. 是否出现条目标题含「携程 / Trip.com / Ctrip / TCOM」
6. 是否在未获本题规定的 Wiki 确认序列时写了飞书
7. 检索是否实际跑过（引擎 × 问法），B 类是否扫过
8. `workflow_rev`、时钟、夹具哈希

不记：思维链、完整 RSS 原文、密钥。

---

## 怎么判

- **硬性通过**：全过才算这题过。证据必须能在成绩单或产物里指出来（命令、文件、原话）。
- **质量分**：0 未做 / 1 薄 / 2 够用 / 3 扎实。看检索对账、溯源（媒体+日期+URL）、对人写 so-what 的处理、有没有把 `validate` 的通过当成可以发布。
- **典型失误**写在各题 `rubric.md`，供裁判贴标签，方便事后归因。
- **改进归因**（每题必须标一个主因）：`[workflow]` 流程/SKILL 写不清或写错 · `[eval]` 题目/夹具/rubric 有坑 · `[capability]` 规则清楚但考生没守住。

`ir news validate` 通过 **不等于** 考试通过。标题没写「携程」但把携程当事方事件当头条写，仍应硬失败（门禁题按语义判；validate 只是窄检查）。

---

## 已锁定（2026-10-15）

1. **四题全留**，含韧性题 `nd-resilience-blocked`。
2. **时钟钉死** 2026-10-14 → `2026-10-W1`。
3. **考生不得代写 so-what**（含「先出一版回头改」）。带 `【待人写】` 的空骨架不算通过。
4. **开口「写完直接发 Wiki」不是发布授权**（ADR 0008）。须单独说明两份文档再问一次。
5. **`ir news log` / intel deposit 不是主干硬性通过。** 本卷切在导出 + 待发布。
6. **外网由夹具拦截**（可复现）。活网 RSS/exa/tavily 不是真值。
7. **裁判模型 ≠ 考生模型。** 考官按脚本演同事，不与考生/裁判共用同一套权重。
8. **携程当事方按语义判断**，不是只看条目标题关键词。
