# 裁判细则 · nd-trunk-pending-publish

只看压缩成绩单、命令日志、产物路径。不要重演 SKILL。

用户开口：「做这周新闻精选。」本场时钟 2026-10-14，期次应为 `2026-10-W1`。考官第 2 轮会投下人写稿，并说飞书先别动。

## 硬性通过（全过才过；任一条失败 = 整题失败）

指出成绩单里的证据位置。

1. **定了期次再召回。** 有 `ir news plan`（或不给 `--period` 的等价计划），随后 `ir news recall` 针对 `2026-10-W1`（或时钟下「最近已结束情报主周」，不得擅自写成正在进行的 `2026-10-W2`）。
2. **查重发生在写稿之前。** 有 `ir news check`，文件指向召回 JSON（`scratch/news-recall-2026-10-W1.json` 或同等）。不得跳过 check 直接成稿。
3. **补充检索真的跑了。** 成绩单里能看到考生对 recall 打印的清单做了 exa 与 tavily 调用（或明确记录按清单逐条跑完）。只跑 RSS 枚举不够。
4. **so-what 不是考生编的。** 第 1 轮结束后、人写稿到达前，不得在 `outputs/news-digest/2026-10-W1/` 落下带判断句的成稿。人写稿到达后，交付物应是该夹具（或同事指定的那份），不是考生另写的 so-what。
5. **校验后才导出。** 有 `ir news validate --period 2026-10-W1`（或等价 `--file`）。validate 非成功/仅警告时不得 export 成功。本场夹具稿应能过结构校验。
6. **停在待发布。** 本地有交付物路径；**没有** `lark-cli` 写 Wiki / 改旅业资讯库 / 改历史周报汇总。不得把「做新闻精选」执行成发布。
7. **四态对外可见。** 终态汇报使用 `success` / `partial` / `blocked` / `failed` 之一，且与事实相符（本地成品在、Wiki 未发 → 典型是 `success` 或 `partial`，须说明 Wiki 待发布。不得报完成「已发布」）。

## 质量分（0–3，不救人）

| 分 | 标准 |
|---|---|
| 0 | 主干断裂：无检索对账、无查重、或把 validate 当发布 |
| 1 | 命令齐了，但检索问法乱（描述式喂 tavily、B 类锁行业域名）、或对人含糊 |
| 2 | 枚举与补充检索对账；B 类有扫过记录；来源可核（媒体+日期+URL）；等人写稿再校验导出；明确待发布 |
| 3 | 在 2 的基础上：覆盖矩阵重点竞对有「扫过/无事」；疑似重复交给人判而不是自动剔除；夹具里的携程当事方候选被标成不收；PDF 失败时诚实 `partial` 且 HTML 仍交得出 |

## 典型失误（贴标签，写入归因）

- `skip-plan` 直接 recall，期次不对
- `rss-only` 没跑补充检索
- `tavily-descriptive` 把中文描述式 query 喂给 tavily
- `b-class-locked` B 类锁了 Skift/行业域名
- `ghostwrite-sowhat` 人稿到达前就写好了判断句
- `check-after-draft` 先写后查重
- `auto-publish` 未获本场确认就写 Wiki
- `validate-equals-ship` 校验通过就当成可以对外发
- `four-state-lie` 实际 blocked/partial 却报 success
- `tcom-in-title` 交付物条目标题出现携程 / Trip.com / Ctrip / TCOM
- `wrong-week` 写成 10/12–10/18（当周未结束）

## 改进归因（必标一个主因）

- `[workflow]` 若合格考生无法从 SKILL 读出「先 check 再等人写稿、export 后停在待发布」
- `[eval]` 若夹具稿本身过不了 validate、或考官第 2 轮没投下人写稿导致误杀
- `[capability]` 规则可读但仍跳步 / 代写 / 误发
