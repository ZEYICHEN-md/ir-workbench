# 内部群周报卡片

> 2026-09-01 按「IR小分队」历史卡片（2026-07-13《周报 | 7月第2周》）的两节骨架，
> 用 Card 2.0 复刻并经真人验收。这是**内部群聊卡片**，不是对外新闻精选，
> 也不是已停用的五部分周报。

JSON 骨架：[feishu-im-card.template.json](feishu-im-card.template.json)

## 这张卡是什么 / 不是什么

| 是 | 不是 |
|---|---|
| 给 IR 内部群看的飞书互动卡片 | 对外交付物（对外仍只有 Markdown / HTML / PDF 精选） |
| 两节：新闻精选 + 行业数据 | 五部分周报（卖方、港股不再进卡） |
| 压缩已定稿精选 + 已确认洞察 | 代写 so-what、现场编行业点评 |

Wiki 两份文档仍走 [feishu-publish.md](feishu-publish.md)，和这张卡互不替代。

## 骨架（4 个视觉块 + 1 个按钮）

1. **概览** `blue-50`：本周 2–3 条要点，来自精选定稿的「本周概览」
2. **一、OTA/旅游行业新闻精选**：每条 `图标 + 可点击标题 + 2–3 句`，从定稿压缩，不另写判断；标题链到来源表 URL
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

## 取数

- **新闻**：`outputs/news-digest/<期次键>/旅行行业新闻精选-*.md` 已定稿。标题沿用图标语义，并做成 Markdown 链接指向来源表 URL；正文可缩短，但数字和 so-what 不得改口径。不写携程当事方。
- **数据**：`data/canonical/travel.json` 取最新一周三个 KPI；`modules/industry_data/insights/travel-insights-zh.md` 取酒店 / 国内航空 / 出境航空评述。新闻主周和数据截至日经常错开一周，**两个日期都写上，不要假装对齐**。
- **不要**把港股、卖方、来源表塞进卡片。完整来源表在精选 Markdown 里。

## 怎么发

默认：**机器人私聊发给当前用户，由用户转发到群**。
「IR小分队」(`oc_9d2437490bdc33f010e928d777c20c2f`) 里没有 CLI 机器人；用户身份发卡片还缺 `im:message.send_as_user`。2026-09-01 实测这条路径可转发。

```powershell
# 1. 复制 template.json，替换占位符，写出 scratch/im-send-card.json
#    payload = { receive_id: 当前用户 open_id, msg_type: "interactive", content: <卡片 JSON 字符串> }
# 2. params 文件：{"receive_id_type":"open_id"}
# 3. 发送（Windows 必须 @file + UTF-8 无 BOM，见 conventions/lark-cli-windows.md）
lark-cli api POST /open-apis/im/v1/messages --as bot --params @scratch/im-send-params.json --data @scratch/im-send-card.json
```

当前用户 open_id 用 `lark-cli whoami`，不要写死。
只有用户明确说「发到某某群」且该群已有机器人时，才改 `receive_id_type=chat_id`。

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
