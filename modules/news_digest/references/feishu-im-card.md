# 内部群周报卡片

> 2026-09-01 按「IR小分队」历史卡片（2026-07-13《周报 | 7月第2周》）的两节骨架，
> 用 Card 2.0 复刻并经真人验收。这是**内部群聊卡片**，不是对外新闻精选，
> 也不是已停用的五部分周报。

JSON 骨架：[feishu-im-card.template.json](feishu-im-card.template.json)

## 结构冻结

**每周只替换占位符里的文字和数字，不准改组件、顺序、配色、区块数量。**
2026-09-01 第二版（含新闻标题超链接、KPI 方块内周度口径、副标题「新闻情报主周」、脚注不写底稿文件名）即为稳定版。要改骨架，必须用户明确说「改周报卡片模板」，不能因为「看起来能更好」就动。

## 这张卡是什么 / 不是什么

| 是 | 不是 |
|---|---|
| 给 IR 内部群看的飞书互动卡片 | 对外交付物（对外仍只有 Markdown / HTML / PDF 精选） |
| 两节：新闻精选 + 行业数据 | 五部分周报（卖方、港股不再进卡） |
| 压缩已定稿精选 + 已确认洞察 | 代写 so-what、现场编行业点评 |

Wiki 两份文档仍走 [feishu-publish.md](feishu-publish.md)，和这张卡互不替代。

## 每周怎么触发

本卡片与新闻精选采编长程链路**解耦独立触发**。
当你完成了当周的新闻精选采编与云文档归档后，说 **「做这周飞书卡片周报」** 或 **「发飞书卡片周报」** 即可。

Agent 用本机当前 `lark-cli` 登录者的身份组卡，私聊发给**这位同事**，由 TA 转发到「IR小分队」。不写死任何人的飞书 ID。

缺料就停，不要凑：

| 状态 | 何时 |
|---|---|
| `blocked` | 没有当期 `outputs/news-digest/<期次键>/旅行行业新闻精选-*.md`；或 `travel.json` 最新一周缺 `hotelRevPAR` / `aviationPax` / `aviationTicket` 任一 |
| `partial` | 精选和 KPI 有了，但 `travel-insights-zh.md` 的 `basedOnTravelJsonUpdatedAt` 对不上 `travel.json` 的 `dataUpdate`：KPI 仍用快照数字，评述用已确认洞察，脚注写清两个日期 |
| `success` | 模板占位符填齐，并私聊发给当前 `lark-cli whoami` 的操作者 |

## 取数对照（每周只读这些地方）

不要打开 Excel 手抄，不要另写点评。卡片上每一块都有固定来源：

| 卡片位置 | 读哪里 | 取什么 |
|---|---|---|
| 标题 `周报 \| {月}月第{周}周` | `ir news plan` 的中文标签，或精选定稿文件名 | 如 `8月第4周` |
| 副标题新闻窗口 | 定稿开头「情报主周」 | `8/24–8/30` |
| 副标题数据截至 | `data/canonical/travel.json` → `meta.dataUpdate` | `8/22` |
| 本周概览 | 定稿「本周概览」列表 | 压缩成 2–3 条，不改判断 |
| 新闻标题 + 正文 | 定稿「一、OTA/旅游行业新闻精选」各条 | 标题可缩短显示，so-what 不改口径 |
| 新闻标题链接 | 定稿「新闻来源」表，**与正文同序同行** | `https://…` 必须来自该表，禁止另搜 |
| KPI 酒店 RevPAR | `travel.json` → `weekly.hotelRevPAR` **最后一格** | 带符号百分数，升绿降红 |
| KPI 航空客运量 | `weekly.aviationPax` 最后一格 | 同上 |
| KPI 机票票价 | `weekly.aviationTicket` 最后一格 | 同上 |
| KPI 三块里的口径 | `weekly.weeks` 最后一项 | 写成 `周度同比 8/16–8/22` |
| 国内酒店 / 国内航空 / 出境航空评述 | `modules/industry_data/insights/travel-insights-zh.md` 已确认中文 | 周度 + 最近完整月度，可压缩，不新写归因 |
| 脚注来源名单 | `travel.json` → `meta.dataSource` | 不要写底稿文件名 |
| 看板按钮 | 固定 | `https://datamax.fun` |

新闻主周和数据截至日经常错开一周，两个日期都写上，不要假装对齐。
不要把港股、卖方、来源表塞进卡片。完整来源表只在精选 Markdown 里。

## 骨架（4 个视觉块 + 1 个按钮）

1. **概览** `blue-50`：本周 2–3 条要点，来自精选定稿的「本周概览」
2. **一、OTA/旅游行业新闻精选**：标题下固定浅色小字「点击新闻标题可跳转原文」；每条 `图标 + 可点击标题 + 2–3 句`，从定稿压缩，不另写判断；标题链到来源表 URL
3. **三枚周度 KPI**：默认酒店 RevPAR / 航空客运量 / 机票票价；升绿降红，只作数字着色，块背景保持 `grey-50`。**每个方块内写清周度同比窗口**（如 `周度同比 8/16–8/22`），不要只写指标名。
4. **二、行业数据更新**：国内酒店 / 国内航空 / 出境航空；周度 + 最近完整月度；脚注写清两个截至日，**不要写底稿 Excel 文件名**
5. **打开行业数据看板** → https://datamax.fun

Header：`周报 | {月}月第{周}周`，副标题固定写成 `新闻情报主周 {窗口}  ·  行业数据截至 {日}`。

## 占位符

| 键 | 填什么 |
|---|---|
| `PERIOD_LABEL` | `8月第4周` |
| `SUMMARY_ONE_LINER` | 会话列表预览：一条新闻要点 + 一个数据要点 |
| `NEWS_WINDOW` | `8/24–8/30` |
| `DATA_AS_OF` | `travel.json` 的 `meta.dataUpdate`，如 `8/22` |
| `OVERVIEW_BULLETS` | `- 要点` 两到三条 |
| `NEWS_ITEMS` | 多条 `**图标 [标题](来源URL)**\n正文`，条与条之间空一行；标题必须能点开定稿来源表里的 URL |
| `KPI1/2/3_VALUE` | `+3.1%` / `-5.0%`（带符号） |
| `KPI1/2/3_LABEL` | `酒店 RevPAR` |
| `KPI1/2/3_COLOR` | 升 `green`，降 `red`，持平 `grey` |
| `KPI_SCOPE` | `周度同比 8/16–8/22`，三个方块用同一窗口 |
| `DATA_WINDOW_CAPTION` | `周度同比 8/16–8/22 · 月度为 7 月` |
| `HOTEL_BODY` / `AVIATION_DOM_BODY` / `AVIATION_INTL_BODY` | 来自已确认中文洞察，可压缩，不新写归因 |
| `FOOTNOTE` | 新闻期次与发布日、数据截至日、来源、仅供内部参考。**不要写底稿文件名** |

## 怎么发

默认：**本机 CLI 应用把卡片私聊发给当前操作者，由 TA 转发到群**。
这是可分发路径：每位同事用自己的飞书完成 `lark-cli` 授权后，应用可见范围通常是「仅本人」，发给自己再转发，换人仍然成立。不要把某个人的 `open_id` 或 CLI 应用 ID 写进仓库、脚本或下一轮对话。

群名「IR小分队」是部门共享目标，**默认不直发进群**——每个人的个人 CLI 应用未必已在该群里。只有当前操作者明确说「发到某某群」，且已确认该群里有**TA 这台机器上的** CLI 应用时，才改 `receive_id_type=chat_id`。

```powershell
# 0. 解析当前操作者，失败就 blocked，不要沿用任何人的旧 ID
lark-cli whoami
lark-cli auth status --json --verify

# 1. 复制 template.json，替换占位符，写出 scratch/im-send-card.json
#    payload = { receive_id: <本步 whoami 的 open_id>, msg_type: "interactive", content: <卡片 JSON 字符串> }
# 2. params 文件：{"receive_id_type":"open_id"}
# 3. 发送（Windows 必须 @file + UTF-8 无 BOM，见 conventions/lark-cli-windows.md）
lark-cli api POST /open-apis/im/v1/messages --as bot --params @scratch/im-send-params.json --data @scratch/im-send-card.json
```

## 构造时不要碰的坑

- `column` **没有** `corner_radius`。写了会 `parse card json err`（2026-09-01 踩过）。
- 卡片 JSON 必须放进 payload 的 `content` **字符串**，不能当对象嵌进去。
- PowerShell 不要把卡片 JSON 塞进 `--content` 命令行参数。
- 升/绿、降/红只涂 KPI 数字；header 保持 blue，不要再给块加红/绿底。
- `enable_forward` 必须为 true，否则用户转不出去。
- 新闻标题用 `[文字](https://...)`，链接必须带 `https://`；不要把链接做在正文段落上，只做在标题上。

## 验收样本

| 期次 | 说明 |
|---|---|
| 2026-07-13 群内旧卡 | 排版源头：两节 + 脚注；Card 1.0 行列格式 |
| 2026-09-01 8月第4周 | 本模板首张 Card 2.0，私聊发出后用户确认「呈现还不错」 |

## 质量评估与迭代门禁

命令是 `ir news card-eval`。它只评估本文件和 [feishu-im-card.template.json](feishu-im-card.template.json)。它不评估 Peers。它不调用 `lark-cli`，不发送卡片。它不合并。

打分对象是草稿（将要发送的卡片正文）。终稿只归档。

### 文件

| 文件 | 何时出现 |
|---|---|
| `outputs/news-digest/<期次键>/feishu-card-draft.txt` | 每次评估都写。内容是 `--draft-file` 传入的卡片正文；不传则沿用已保存的草稿。 |
| `outputs/news-digest/<期次键>/feishu-card-final.txt` | 仅当本次传入 `--final-file`（人粘回的修改稿）。不传则删除已有终稿。空文件不写入，也不删除已有终稿。 |
| `runs/news-digest/<期次键>/feishu-card-eval.json` | 仅当裁判打分成功。里面是基线、每次分数和建议。 |

两个正文文件名是 ASCII。期次键仍是 `2026-08-W4` 这种格式。

没有草稿时命令停住，不单独写终稿。

### 指标

裁判是外部模型，不是写这张卡的模型。用 `--writer-model` 写明写卡模型。两者相同则不打分。

必填环境变量是 `IR_CARD_JUDGE_API_KEY`。没有这个变量时，状态是 `blocked`。命令不编造信息量，也不编造隐喻率。

可选：`IR_CARD_JUDGE_MODEL`（默认 `gpt-4.1`）、`IR_CARD_JUDGE_BASE_URL`（默认 `https://api.openai.com/v1`）。接口是该地址上的 `POST /chat/completions`。

| 指标 | 算法 |
|---|---|
| 信息量 | 事实点个数。一个事实点是一条具体陈述：一个数字、一个日期、一个名称、一个产品，或一个事件。评价句不是事实点，例如「这很重要」。裁判不核对陈述是否为真。 |
| 隐喻率 | 隐喻个数 / 句子数 × 100。隐喻是可以换成更直白说法的词或短语。给不出更直白的说法，就不是隐喻。 |

句子由程序切，不由裁判切。切分符只有 `。？！`。半角 `.` `!` `?` 不切。没有句末标点的一行算一句。

不计入句子的行：

- 标题行：行首 1 到 6 个 `#`，后面还有文字。
- 表格行：以 `|` 开头或结尾，或一行里至少两个 `|`。
- 纯链接行：整行只有一个 `http(s)` URL，或只有一个 Markdown 链接。去掉首尾强调符号后仍是这样，也算。行里还有别的字，就要计入。

下列词或短语即使被裁判标成隐喻，也不计入：`字段`、`运行`、`面对挑战`、`神经网络`。按整词排除，不按子串排除。隐喻原文必须出现在计入的句子里。

### 门禁

同一期次的第一次成功打分是基线。以后每次评估都用这个期次，和这份基线比。本命令不改基线。另一期次有自己的基线，不拿来比。

仅当信息量不低于基线，且隐喻率不高于基线时，建议写成 `pending-confirm`。否则建议是 `reject`。信息量相等、隐喻率相等，可以是 `pending-confirm`。

`pending-confirm` 只是记录。人确认之前，不得合并本模板的改动。本命令没有合并动作。确认之后仍由人合并。

```powershell
ir news card-eval --period 2026-08-W4 --draft-file scratch/feishu-card.txt --writer-model <写卡模型名>
ir news card-eval --period 2026-08-W4 --draft-file scratch/feishu-card.txt --final-file scratch/feishu-card-final.txt --writer-model <写卡模型名>
```
