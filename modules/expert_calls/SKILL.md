# expert-calls · 专家访谈精选

目标：访谈 PDF → 按页抽取 → **候选排序报告供人选择** → 人工决定收录 → revision 1680 callout 草稿 → 明确确认后写飞书 → 内部情报库草稿。飞书 Wiki 是权威稿；本地排序、XML 与情报条目都是投影。

## 一句话如何路由

- 「看看这些访谈哪些值得写 / 做 Expert Call 候选」：按页抽取后生成 A/B/C 排序报告，逐篇展示主题、关键数据、行业事实/洞察、局限与评分依据，停下来让人选。
- 「只提取/总结这份专家访谈」：先生成候选排序；人选择后做到 `validate` + `render`，停在草稿。
- 「更新 Expert Call / 写入飞书」：同样先给候选排序和草稿；只有明确说**「发布专家访谈精选」**才执行发布。
- 飞书发布成功只生成情报草稿；另经用户确认后才可 `ir intel add --commit`。

## 主链

1. `ir expert-calls extract --pdf ... --run-id YYYYMMDD-HHMMSS`：用 `pdfplumber` 按页抽到 Git 忽略的 `scratch/`。
2. Agent 按 [收录与写作规则](references/inclusion-and-writing.md) 为每篇形成候选记录：一句话概述、关键数字、行业事实/洞察、局限、相关范围和五维评分。此时 `include` 可为 `null`，表示待人决定。
3. `shortlist`：代码计算透明的 100 分排序与 A/B/C 档，写出人读 Markdown。A = 优先考虑，B = 可考虑，C = 建议不收录；排序只辅助判断，不替人选择。
4. 人工选择后，Agent 把每篇 `include` 落为 true/false；`validate` 校验直接 IR 信息增量、至少 4 个锚定数字、每段数字、原话/位置和情报条目 schema。
5. `render`：只为人工选中的访谈渲染本目录模板，不接触飞书。
6. `publish` 默认 dry-run，列出精确重复和将写标题；确认后才带发布开关。
7. 每条写后立即回读并取得新 block id，下一条接在新 id 后。中断返回 `partial`，manifest 保留已写 ids；重跑会按标题/PDF 链接跳过。

同一批必须沿用同一个 run id；状态在 `runs/expert-calls/<run-id>/manifest.json`。

## Manifest 契约

顶层必填 `run_id`（`YYYYMMDD-HHMMSS`）。候选阶段每篇必填 `title`、`expert_background`、`interview_time`、`pdf_name`、`anchor_numbers`、`inclusion_evidence` 与 `selection_review`；`include` 可为 `null`。`selection_review` 必须含一句话概述、关键洞察、局限和五维评分。人工决定后，`include` 必须变成 boolean；收录记录再必填 `paragraphs`、`left_out`、`pdf_href`、`value_reason` 和非空 `intel_entries`。每个 `anchor_numbers` 项必填 `value`、`so_what`、`source_quote`、`quote_where`。不收录记录必填 `skip_reason`。合成示例见 `templates/expert_calls.manifest.example.json`。

直接 IR 信息增量是收录硬门槛，受控范围只有：携程经营与财务判断、中国及跨境旅行需求、全球 OTA 竞争格局、AI 对旅行搜索/流量/交易转化的影响。**B2B 不是独立相关性分类**；只有当它显著影响竞对增长、利润率、渠道黏性或 AI 防御时，才作为经营机制写入。

`intel_entries` 不得把摘要转述当原话：`statement` 仍须 `quote` + `quote_where`，位置至少写到「文件名 · 第 N 页/段」。发布后只生成 draft；`channel` 强制 `expert-call`，`sensitivity` 强制 `internal`。

## 线上唯一版式

2026-09-01 只读回读目标 Wiki revision 1680，现有三条均为：`border-color="rgb(239,240,241)"` + 📌；粗体标题；斜体专家背景与时间；blockquote 内 2–3 个 `<p>`；灰色「更多详情请见：」后直接放飞书文件裸 URL。

旧浅蓝 `background-color` 与 `<bookmark>` 模板已废弃。`Expert Call 精选` 是三栏 grid 中红色居中 h2；callout 必须插在**整个 grid 后**，不得插进中间列。

## 安全边界

- 真实 PDF/TXT 只在飞书或 Git 忽略目录，不进 Git。
- 空文本/扫描件返回 `blocked` 并提示 OCR，绝不静默继续。
- 所有 XML 动态内容转义；所有飞书操作只用 `lark-cli --as user`、参数数组、`shell=False`。
- 写前按精确标题或 PDF 链接判重；没有用户发布确认时，测试和运行都不得调用写命令。
