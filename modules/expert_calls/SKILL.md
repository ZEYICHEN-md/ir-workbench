# expert-calls · 专家访谈情报与精选

目标：访谈 PDF → 按页抽取 → **先识别并生成公司情报库草稿** → 人工核对后独立入库；同时生成候选排序供人选择 → revision 1680 callout 草稿 → 明确确认后写飞书。公司情报库是专家访谈的首要沉淀方向，飞书 Wiki 是精选展示，两条分支互不作为前置条件。

## 一句话如何路由

- 「读一下这些专家访谈 / 把有价值的信息存进公司情报库」：按页抽取，识别公开渠道难以获得的行业事实、公司信息、内部经营数据与因果机制，生成带原话和页码的内部情报草稿；人工核对后走公司情报库现有确认门禁。
- 「看看这些访谈哪些值得写 / 做 Expert Call 候选」：完成情报提取后，再生成 A/B/C 排序报告，逐篇展示主题、关键数据、行业事实/洞察、局限与评分依据，停下来让人选。
- 「只提取/总结这份专家访谈」：同时形成情报草稿和候选排序；人选择后做到 `validate` + `render`，停在飞书草稿。
- 「更新 Expert Call / 写入飞书」：同样先做情报提取、候选排序和草稿；只有明确说**「发布专家访谈精选」**才执行发布。
- 情报草稿是否入库与是否入选飞书无关；正式写入公司情报库仍须用户另行确认。

## 主链

1. `extract`：用 `pdfplumber` 按页抽到 Git 忽略的 `scratch/`。
2. Agent 一次阅读同时形成两类结构化结果：逐篇候选记录，以及可进入公司情报库的 `intel_entries`。情报重点找公开渠道难以获得、**本身具有检索价值**的行业数据、公司事实、内部经营数据和因果机制；不要求它先支撑某个现成论点，也不能只保留支持当前判断的信息。反例、冲突信号和暂时无法形成结论的数据同样可以收。每条必须保留专家原话与 PDF 页码/位置，并写清口径和局限。
3. `intel-draft`：从**所有访谈**汇集有价值条目，不看飞书 `include`；强制 `channel=expert-call`、`sensitivity=internal`，只生成 ignored scratch 草稿，不访问飞书、不写情报库。具备独立检索价值的数字必须尽量拆成原子 `claim`，不要求先支撑论点；`claim` 记录稳定 `metric_key`、结构化 `scope`、数据期、值、单位、比较口径、证据类型、来源距离和置信度理由。
4. 人工核对情报草稿后，把条目分成 A（可正式入库）、B（有价值但暂不能脱离上下文使用）和剔除三组。A 类先走 `ir intel add --file ...` 预演；预演把同 `metric_key + 数据期` 的主张分成「新增 / 佐证 / 冲突 / 疑似口径不同」，逐条展示命中来自正式库、待核池还是本批。冲突双方都保留，不覆盖旧值、不自动选真值；只有用户明确确认才可带 `--commit` 追加到正式真源并重建公司档案。
5. 人工选定的 B 类走 `ir intel defer --file ...`，明确确认后写入跨批次 `data/intel/deferred.jsonl`。待核项不进入正式公司/主题/档案查询，但参与后续 claim 比较和召回。补齐第二来源、范围、分母、时点或直接证据后，只能经 `ir intel promote` dry-run 和另一次人工确认转正；禁止自动转正。
   情报分支只有在 `A + B + 剔除 = 草稿总数`、三组互斥且逐条有稳定 ID/原编号时才算完成；A 类须逐 ID 对上正式库，B 类须逐 ID 对上待核池，剔除项须在批准产物中保留原因。缺席不能自动解释为剔除，也不能用飞书分支的 6/6 状态替代这项对账。
6. `shortlist`：独立计算飞书展示候选的 100 分排序与 A/B/C 档。A = 优先考虑，B = 可考虑，C = 建议不收录；这里的 A/B/C 是飞书展示档位，与上一条情报 A/B 分组无关。`information_gain` 0–1 分最高 C、2 分最高 B，只有 3 分及以上才允许进入 A。排序只辅助判断，不替人选择。
7. 人工选择飞书展示项后，Agent 把 `include` 落为 true/false；`validate` 校验直接 IR 信息增量、至少 4 个锚定数字、每段数字及原话/位置。未入选飞书不影响其情报条目。
8. `render` 只为人工选中的访谈渲染 callout；`publish` 默认 dry-run，确认后逐条写入并回读。飞书发布不生成、覆盖或提交情报草稿。

同一批必须沿用同一个 run id；状态在 `runs/expert-calls/<run-id>/manifest.json`。状态顺序先记录 `intel-draft`，再记录独立的飞书精选分支。

## Manifest 契约

顶层必填 `run_id`（`YYYYMMDD-HHMMSS`）。候选阶段每篇必填 `title`、`expert_background`、`expert_profile`、`interview_time`、`pdf_name`、`anchor_numbers`、`inclusion_evidence` 与 `selection_review`；`include` 可为 `null`。`intel_entries` 与飞书 `include` 独立：任何访谈只要含有可核对、可索引的增量数据或事实，就可提供零到多条情报；未入选飞书的访谈同样可以贡献。每条专家访谈情报不论 `kind` 都必须带 `quote` 与 `quote_where`，位置至少写到「文件名 · 第 N 页/段」。`note` 说明留存理由、潜在检索用途和口径限制，可以明确写“当前无法判断净影响”；不得为了入库强行补一个论点。

情报条目中的独立数字使用可选 `claim`：`metric_key` 为稳定 ASCII slug；`scope` 为结构化字符串 object；`claim.period` 是指标数据期，不能与条目顶层采集期 `period` 混用；`value` 可为数字、`[下限, 上限]` 或无法安全数值化的原始值；同时必填 `unit`、`basis`、`evidence_type`、`source_proximity`、`confidence` 与 `confidence_reasons`。同一段包含多个可独立比较的指标时应拆成多个原子条目，避免一个 claim 同时代表两个值。

人工决定飞书展示后，`include` 必须变成 boolean；收录记录再必填 `paragraphs`、`left_out`、`pdf_href` 和 `value_reason`，但不再要求非空 `intel_entries`。不收录记录必填 `skip_reason`。每个 `anchor_numbers` 项必填 `value`、`so_what`、`source_quote`、`quote_where`。合成示例见 `templates/expert_calls.manifest.example.json`。

直接 IR 信息增量仍是**飞书精选**硬门槛，受控范围只有：携程经营与财务判断、中国及跨境旅行需求、全球 OTA 竞争格局、AI 对旅行搜索/流量/交易转化的影响。亚太竞争映射须把 Agoda 和 Traveloka 视为 Trip.com 的重点直接竞对。**B2B 不是飞书精选的独立相关性分类**；只有当它显著影响竞对增长、利润率、渠道黏性或 AI 防御时，才作为经营机制写入飞书摘要。

情报分支采用更低的留存门槛：某项数据、事实或机制只要相对公开渠道有增量，原话、时间、口径和位置可核对，并能按公司或主题找回，就可以进入草稿。它不必支持当前论点；与现有判断冲突或暂时无法解释，也应如实保留并标注不确定性。只有口径无法辨认、纯预测、纯观点或与公开材料完全重复且无检索增量的内容才排除。草稿不等于入库；正式写入沿用 competitor-intel 的人工确认门禁。

## 线上唯一版式

2026-09-01 只读回读目标 Wiki revision 1680，现有三条均为：`border-color="rgb(239,240,241)"` + 📌；粗体标题；斜体专家背景与时间；blockquote 内 2–3 个 `<p>`；灰色「更多详情请见：」后直接放飞书文件裸 URL。

旧浅蓝 `background-color` 与 `<bookmark>` 模板已废弃。`Expert Call 精选` 是三栏 grid 中红色居中 h2；callout 必须插在**整个 grid 后**，不得插进中间列。

## 安全边界

- 真实 PDF/TXT 只在飞书或 Git 忽略目录，不进 Git。
- 空文本/扫描件返回 `blocked` 并提示 OCR，绝不静默继续。
- 所有 XML 动态内容转义；所有飞书操作只用 `lark-cli --as user`、参数数组、`shell=False`。身份是本机当前登录的同事，见 `conventions/lark-cli-windows.md`。
- 写前按精确标题或 PDF 链接判重；没有用户发布确认时，测试和运行都不得调用写命令。
