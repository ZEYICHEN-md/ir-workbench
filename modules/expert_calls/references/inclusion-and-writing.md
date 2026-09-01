# Expert Call 收录与写作

## 收录门槛

默认不收录。只有以下三项中至少两项有机器可读证据，且正文锚定数字不少于 4 个，才可收录：

- `quantified_content`：有具体数字、区间、份额、增速或费率；
- `causal_mechanism`：给出可复述的因果机制，不只是看多/看空；
- `relevant_information_gain`：对携程、中国出境、B2B 或 AI 替代边界有直接增量。

每个锚定数字必须保留 `value`、`so_what`、`source_quote` 和 `quote_where`（页码或明确位置）。正文目标 5–7 个锚定数字，少于 4 个硬停；不收录的记录必须写 `skip_reason`。收录记录还必须提供至少一条 `intel_entries`，且在任何飞书写入前通过情报库 schema 校验，避免发布后只留下空草稿。

## 写法

每篇 2–3 个叙述段，每段一个论点并至少带一个数字。写清样本、范围和外推限制。`left_out` 记录未进正文的数字及原因。标题、背景、时间、段落和原始 PDF 链接均视为不可信文本，渲染 XML 时必须转义。

## 发布边界

飞书写入默认 dry-run，只有显式确认参数才执行。锚点是运行时解析出的红色居中 h2 所在整个 grid；callout 插在 grid 后。每写一条必须回读、按精确标题确认并取得 callout block id，下一条接在该 id 后。
