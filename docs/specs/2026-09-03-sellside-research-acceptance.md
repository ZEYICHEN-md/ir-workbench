# sellside-research 可持续验收记录

日期：2026-09-03

## 目的

给卖方研报轻量域留下一份CI可重放的证据，同时不把真实研报、逐页抽取原文或截图写进Git。
本记录验证的是抽取与边界契约，不证明某一份券商报告的业务结论正确。

## 材料

测试只使用自造文件名、字节和句子，例如 `synthetic-report.pdf`、`Page one 10%`。
测试通过 mock 提供 PDF 页对象，不读取真实研报，也不访问网络。

真实材料的首次业务验收仍记录在 `docs/MIGRATION.md` 的 sellside-research 小节：
13/13页完成抽取，并完成事实、观点、预测和估值变化的分层摘读。真实原件及抽取物受
`.gitignore` 保护，不作为CI固定件。

## 可重放契约

`tests/test_sellside_research.py` 固定以下行为：

1. 抽取结果保留PDF查看器页码和页面顺序，Markdown明确写“第N页”。
2. 整份没有可提取文字时返回扫描件提示，不把空结果包装成完成。
3. CLI只生成当次按页底稿，状态为 `partial`，提醒Agent继续摘读。
4. 空白图表页会给出提醒。
5. 不创建 `runs/sellside-research` 周期记录，不写 `data/intel`。
6. 非PDF输入被拦住，不生成输出。

## 取舍

没有把真实UBS研报放进测试固定件。那样能提高表面上的可复现性，但会把第三方大段原文永久写进
仓库历史，也会违反ADR 0004“不建持久档案”的边界。合成测试只能证明程序契约，不能替代真实
材料的业务验收；两类证据分别保留，不互相冒充。

没有为本域新增manifest。低频按需摘读不需要跨期待办；强行建manifest会让状态页制造“还没跑过”
或“尚未完成”的假任务。Control Plane以 `validation_state=lightweight` 明确表达这个有意边界。

## 验证结果

- `tests.test_sellside_research`：4项通过。
- 季度材料RNS与Atour别名：2项新增回归通过。
- 全量测试：351项通过。
- `ir doctor`：7个域的目录、CLI与health全部就绪，环境检查通过。
- `ir status`：5个完整验收、1个部分验收、1个轻量能力；总体如实返回 `partial`。
- 全仓LF与 `git diff --check`：通过。
