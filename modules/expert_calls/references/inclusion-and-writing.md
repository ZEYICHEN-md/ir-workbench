# Expert Call 候选排序、收录与写作

## 先排序，后决定

每批访谈先形成**候选排序报告**，不直接生成待发布列表。报告逐篇展示：一句话概述、最有价值的数据、具有高参考意义的行业事实与洞察、专家来源与职能、证据局限、六维评分和 A/B/C 建议档位。`include: null` 表示等待人工决定；排序只辅助选择，不代替人决定。

六维评分均为 0–5 分，并必须写理由；代码按权重计算 100 分：

- `ir_relevance`（30%）：对携程经营、中国及跨境需求、全球 OTA 竞争或 AI 旅行分发的直接相关性；
- `information_gain`（20%）：相对已知信息是否带来新的、能改变判断的事实；
- `expert_authority`（20%）：专家所在公司的全球规模、职位层级及其与议题的职能接近度；
- `evidence_quality`（15%）：信息是否为专家主动给出的一手内容，口径、样本与原话是否清楚；
- `causal_depth`（10%）：是否解释“为什么”和传导机制，而非只报数字；
- `freshness`（5%）：信息距访谈时间、专家离职时间及当前判断期有多近。

A 档为 80 分及以上，优先考虑进入飞书；B 档为 65–79.9 分，需人工权衡；C 档低于 65 分，建议不收录。无直接 IR 信息增量或少于 4 个锚定数字时，不论总分均强制 C 档。`information_gain` 另设档位上限：0–1 分最高 C，2 分最高 B，只有 3 分及以上才允许进入 A。这样专家身份、议题相关性或数字数量不能把与财报、电话会大体重复的内容抬进 A 档。

## 专家来源偏好与档位上限

携程 IR 优先大型跨国平台或集团（如 Booking、Airbnb、Expedia 等）中真正接近业务决策的一手高管。职位高低不能单独加分，必须同时看公司规模、全球覆盖、职能是否直接负责该议题、是否亲自掌握数据以及离职时点。

- `global_leader`：大型跨国平台/集团，可进入 A 档；
- `scaled_multimarket`：有规模的多市场公司，最高 B 档；
- `regional_or_niche`：区域性或细分公司通常最高 C 档；但若直接覆盖 Trip.com 国际扩张重点的中国或亚太市场，最高可到 B 档；
- `single_property_or_local`：单体酒店或本地小型公司，最高 C 档。

公司规模影响的是**专家背书强度**，不等于信息本身无效。亚太区域公司的专家若能提供直接关联 Trip.com 重点市场的需求、竞争、渠道或用户行为信息，应在 `ir_relevance` 中获得高分，同时因来源规模较弱在 `expert_authority` 中降分，最终通常落在 B 档。非重点区域的小公司、地方公司或单体酒店即使数字很多，原则上仍不进入精选；其材料可作为背景，但不能与 Booking/Airbnb/Expedia 相关业务高管等权。大型公司高管也不是自动高分：传播、公共事务等相邻职能谈供给或财务数据时，要在 `functional_proximity`、`expert_authority` 和 `evidence_quality` 中降分。

亚太竞争映射中，**Agoda 和 Traveloka 是 Trip.com 的重点直接竞对**。Agoda 隶属 Booking Holdings，相关业务专家的 `organization_scope` 按 `global_leader` 评估；Traveloka 覆盖多个东南亚市场，按 `scaled_multimarket` 评估。两者的 `strategic_market_scope` 均为 `china_or_apac_priority`。如果访谈直接涉及亚太市场份额、流量、供给、定价、用户行为或渠道竞争，`ir_relevance` 可以给高分；`expert_authority` 仍取决于职位、职能和数据接近度。因此，Agoda 相关业务高管可进入 A 档，Traveloka 专家按现行公司规模上限最高为 B 档。

## 直接 IR 信息增量

收录记录必须至少命中以下一个受控范围，并写清“为什么会改变 IR 判断”：

- `tcom_operations`：携程经营与财务判断；
- `china_cross_border`：中国及跨境旅行需求；
- `global_ota_competition`：全球 OTA 竞争格局；
- `ai_travel_distribution`：AI 对旅行搜索、流量入口与交易转化的影响。

**B2B 不是独立收录理由。**只有当 B2B 信息显著影响某家竞对的增长结构、利润率、渠道黏性或 AI 防御能力时，才可作为上述范围的经营机制和证据。单纯的企业差旅、物业管理或分销操作细节不构成相关性。

## 硬门槛与证据

默认不收录。人工选择为 `include: true` 的访谈必须：有直接 IR 信息增量；至少 4 个锚定数字；量化证据、原话与页码齐全；正文每段至少一个数字；并提供至少一条合规的 `intel_entries`。每个锚定数字必须保留 `value`、`so_what`、`source_quote` 和 `quote_where`。

采访者先提出、专家仅弱确认的数字必须在 `caveats` 标注，并在 `evidence_quality` 中降分；不能与专家主动给出的一手数字等权。正文目标 5–7 个锚定数字，`left_out` 记录未进正文的数字及原因。不收录记录必须写 `skip_reason`。

## 写法

每篇 2–3 个叙述段，每段一个论点并至少带一个数字。写清样本、范围和外推限制。标题、背景、时间、段落和原始 PDF 链接均视为不可信文本，渲染 XML 时必须转义。

## 发布边界

候选排序和 callout 渲染均不接触飞书。飞书写入默认 dry-run，只有用户明确说“发布专家访谈精选”才执行。锚点是运行时解析出的红色居中 h2 所在整个 grid；callout 插在 grid 后。每写一条必须回读、按精确标题确认并取得 callout block id，下一条接在该 id 后。
