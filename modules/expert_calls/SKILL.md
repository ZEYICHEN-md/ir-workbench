# expert-calls · 专家访谈精选

目标：访谈 PDF → 按页抽取 → 收录判断与摘要 manifest → revision 1680 callout 草稿 → 明确确认后写飞书 → 内部情报库草稿。飞书 Wiki 是权威稿；本地 XML 与情报条目都是投影。

## 一句话如何路由

- 「只提取/总结这份专家访谈」：做到 `validate` + `render`，停在草稿。
- 「更新 Expert Call / 写入飞书」：先给用户审草稿；只有明确说**「发布专家访谈精选」**才执行发布。
- 飞书发布成功只生成情报草稿；另经用户确认后才可 `ir intel add --commit`。

## 主链

1. `ir expert-calls extract --pdf ... --run-id YYYYMMDD-HHMMSS`：用 `pdfplumber` 按页抽到 Git 忽略的 `scratch/`。
2. Agent 按 [收录与写作规则](references/inclusion-and-writing.md) 形成 manifest；每个数字保留原话和页码。
3. `validate`：字段、2/3 收录信号、至少 4 个锚定数字、每段数字、原话/位置、情报条目 schema 全部过门禁。
4. `render`：只渲染本目录模板，不接触飞书。
5. `publish` 默认 dry-run，列出精确重复和将写标题；确认后才带发布开关。
6. 每条写后立即回读并取得新 block id，下一条接在新 id 后。中断返回 `partial`，manifest 保留已写 ids；重跑会按标题/PDF 链接跳过。

同一批必须沿用同一个 run id；状态在 `runs/expert-calls/<run-id>/manifest.json`。

## Manifest 契约

顶层必填 `run_id`（`YYYYMMDD-HHMMSS`）。收录记录必填：`include`、`title`、`expert_background`、`interview_time`、`anchor_numbers`、`paragraphs`、`left_out`、`pdf_name`、`pdf_href`、`value_reason`、`inclusion_evidence` 和非空 `intel_entries`。每个 `anchor_numbers` 项必填 `value`、`so_what`、`source_quote`、`quote_where`。不收录记录必填 `skip_reason`。合成示例见 `templates/expert_calls.manifest.example.json`。

`intel_entries` 不得把摘要转述当原话：`statement` 仍须 `quote` + `quote_where`，位置至少写到「文件名 · 第 N 页/段」。发布后只生成 draft；`channel` 强制 `expert-call`，`sensitivity` 强制 `internal`。

## 线上唯一版式

2026-09-01 只读回读目标 Wiki revision 1680，现有三条均为：`border-color="rgb(239,240,241)"` + 📌；粗体标题；斜体专家背景与时间；blockquote 内 2–3 个 `<p>`；灰色「更多详情请见：」后直接放飞书文件裸 URL。

旧浅蓝 `background-color` 与 `<bookmark>` 模板已废弃。`Expert Call 精选` 是三栏 grid 中红色居中 h2；callout 必须插在**整个 grid 后**，不得插进中间列。

## 安全边界

- 真实 PDF/TXT 只在飞书或 Git 忽略目录，不进 Git。
- 空文本/扫描件返回 `blocked` 并提示 OCR，绝不静默继续。
- 所有 XML 动态内容转义；所有飞书操作只用 `lark-cli --as user`、参数数组、`shell=False`。
- 写前按精确标题或 PDF 链接判重；没有用户发布确认时，测试和运行都不得调用写命令。
