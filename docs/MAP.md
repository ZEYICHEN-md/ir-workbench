# 工作台地图

给刚拿到这个文件夹的同事。你不需要知道它是怎么搭起来的，也不需要开终端。

打开方式：用 Cursor / Kiro / Claude Code 打开整个 `IR_workbench` 文件夹，对右侧 Agent 说话。能做什么见 [CAPABILITIES.md](CAPABILITIES.md)；怎么开口、怎么确认见 [HANDOVER.md](HANDOVER.md)。

---

## 它是什么

这是携程 IR 的日常工作台。九件事挂在同一个入口上：新闻精选、行业数据看板、航空月报、港股查询、竞对情报、专家访谈、Peers 财务模型、卖方研报摘读、机构股东名册。

你负责判断和确认。Agent 负责取数、核对、落文件、记进度。对外发布和改权威数据，一定要你先说「确认」。

```text
你说话
  → Agent 听懂是哪一类工作
    → 读写下面四层文件
      → 把结果用人话告诉你
```

---

## 四层文件（先记住这个）

| 层 | 文件夹 | 干什么 | 你要不要动手 |
|---|---|---|---|
| **长期数据** | `data/` | 部门一直要用的底稿、情报库、财务 Model | 改数只改被锁定的 Excel |
| **当期原件** | `inputs/` | 这一期刚拿到的中金表、研报、财报、访谈 | 拖进来或交给 Agent |
| **成品** | `outputs/` | 做完给你交差的东西 | 从这里取，不要手改格子 |
| **运行记录** | `runs/` | 做到哪一步了（给 Agent 用） | 一般不用看 |

临时草稿在 `scratch/`，可以清，不要当档案。

---

## 往哪存

日常三种交法，不必自己建子文件夹：

1. **拖进对话框**（最省事）。
2. **放进对应的 `inputs/…` 收件箱**，再说一声。
3. **行业数据 Excel** 放 `data/workbooks/`，Peers 权威 Model 放 `data/models/`，然后让 Agent 锁定。

| 你手里的东西 | 放到 | 随分发包走吗 |
|---|---|---|
| 国内行业数据 / Airline Data Excel | `data/workbooks/` | **走**（当前锁定的那份） |
| Peers 三份权威 Model | `data/models/` | **走** |
| 中金周报、STR 表 | `inputs/industry-data/` | 当期原件默认不走（下周会换）；目录说明走 |
| 新闻精选用的剪报 / 公众号 | `inputs/news-digest/` | 同上 |
| 卖方研报 PDF | `inputs/sellside-research/` | 同上 |
| Peers 财报 / 电话会 PDF | `inputs/peers-model/` | 同上 |
| 专家访谈 PDF | `inputs/expert-calls/` | 同上 |
| 季度披露材料包 | `inputs/intel-quarterly/` | 同上 |
| Capital IQ 股东底表 | 电脑「下载」 | 不进工作台 |
| 交差成品 | 不要手塞 | 问 Agent 去 `outputs/` 取 |

当期原件默认不进 Git：下周就会换成新的一份。部门一直要用的底稿（行业数据 Excel、Peers Model、情报库）随仓走。

---

## 从哪取

| 你想要 | 去哪 | 随包走吗 |
|---|---|---|
| 上期新闻精选正文 | `outputs/news-digest/<期次>/` 的 `.md` | **走**（HTML/PDF 本机生成） |
| 国内行业数据底稿 | `data/workbooks/` 被锁定的那份 | **走** |
| 看板数字 / 洞察 | `data/canonical/`，上线后看 datamax.fun | **走** |
| 竞对按公司/主题查 | 对 Agent 说；真源在 `data/intel/` | **走** |
| Peers Model 更新副本 | `outputs/peers-model/` | 不走（运行产物，可从权威文件再生成） |
| 权威 Model 原件 | `data/models/` | **走** |
| 股东名册交差 xlsx | `outputs/shareholder-list/<有效日>/` | 不走（可从 Downloads 底表再生成） |
| 「做到哪了」 | 问「现在什么状态」 | 进度在 `runs/`，**走** |

不确定就问 Agent：「这期新闻精选在哪」「BKNG 模型副本在哪」「股东名册在哪」。

---

## 每个文件夹是干什么的

只看你用得着的。标了「日常不用点」的，打开也没有要填的表。

### 你常会点开的

| 路径 | 放了什么 | 存 | 取 |
|---|---|---|---|
| `data/workbooks/` | 《国内行业数据》和 Airline Data。全部门只认被锁定的那一份 | 新表放进来，说「换一份」 | 改数只改这一份 |
| `data/workbooks/archived/` | 换表前、自动写入前的备份 | 不要往这里塞 | 出事时翻旧版；**不要删** |
| `data/models/` | BKNG/EXPE/ABNB 共用、美团、同程三份权威 Model | 新版本放这里让 Agent 锁定 | 更新只出副本，不覆盖这里 |
| `data/canonical/` | 从底稿生成的指标快照和洞察 | **不要手改** | 看板和洞察的机器源 |
| `data/intel/` | 竞对情报库（部门累积的 peers 事实与口径） | 由流程入库，不要手改 JSONL | 问「Booking 这季度做了什么」 |
| `inputs/` | 当期原件收件箱，按业务分子文件夹 | 见上表 | 核对「这期原件在哪」 |
| `outputs/` | 成品。新闻精选 Markdown 在这里；模型副本、股东名册 xlsx 也在对应子目录 | 不要手改生成的格子 | 交差从这里拷 |
| `dashboard/travel/` | 看板网页投影 | 不要手改 | 上线后看 datamax.fun |

每个收件箱里有一份 `README.md`（随包走），打开就能看到这个盒子收什么。

### 给 Agent / 系统用的（日常不用点）

| 路径 | 干什么 |
|---|---|
| `AGENTS.md` | Agent 一打开就会读的入口 |
| `router/` | 你说的话怎么分到九个域 |
| `workbench/` | Agent 的手（`ir …`），不是给你跑的 |
| `modules/` | 九个域的流程和代码 |
| `conventions/` | 跨域规矩（溯源、命名、文件生命周期） |
| `docs/` | 说明文档。你从本文件、HANDOVER、CAPABILITIES 看起即可 |
| `runs/` | 每一期做到哪一步 |
| `tests/` | 回归测试 |
| `scratch/` | 临时草稿，可清 |
| `.ir-workbench/` | 本机覆盖（看板发布仓路径等）。工作簿锁定在 `data/workbook-lock.json` | 不进 Git |

根目录不该再出现旧项目文件夹（例如以前的 `0703_Travel_Pulse`）。看到就当残留，不要往里面放东西。

---

## 分发包里已经有的部门 context

这些会跟着 Git / zip 走，换人拿到就能接着用：

- 九个域的流程与门禁
- 当前锁定用的行业数据 Excel 和归档
- Peers 三份权威 Model，以及 `data/workbook-lock.json`（哪几份被锁定）
- 指标快照、洞察、竞对情报库
- 已定稿的新闻精选 Markdown
- 各期运行记录
- 本地图、功能清单、开箱说明

这些**不随包走**——不是机密，而是可以再生成、或下周就会换掉：

- 当期中金周报 / 研报 / 财报 / 访谈 PDF（下周换新的；需要留底时再说一声）
- Peers 更新副本、股东名册生成的 xlsx（可从权威文件 / Downloads 底表再生成）
- 新闻精选的 HTML/PDF（可用 Markdown 再导出）
- 本机飞书登录、看板发布仓在这台电脑上的路径

---

## 和别的文档怎么分工

| 问题 | 看 |
|---|---|
| 文件夹是干什么的、存取去哪 | **本文件** |
| 能做什么、怎么开口 | [CAPABILITIES.md](CAPABILITIES.md) |
| 第一次怎么用、确认门禁 | [HANDOVER.md](HANDOVER.md) |
| Agent 执行时的落盘细则 | [../conventions/file-lifecycle.md](../conventions/file-lifecycle.md) |
| 改目录约定时的树形真源 | [FOLDER.md](FOLDER.md) |
