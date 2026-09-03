# ADR 0009：恢复 Peers Model 机械维护，不恢复 Appendix 写作

- 日期：2026-09-03
- 状态：已采纳；26Q2 历史 PDF 与 holdout 已通过，下一次新季度仍需再跑

## 背景

`peers-appendix` 退役的原因是旧流程把 Excel、Charts、Word 写作和公司特化脚本绑在一起，且没有真实季度验收。用户仍有一项明确、可机械化的需求：给 Agent 财报 PDF 后，更新 BKNG/EXPE/ABNB、美团、同程的 Excel Model，并核对格式、公式、数据和 Charts。

用户补入三份明确模型：

- ABE 共用：`peers data comparison_20260807.xlsx`
- 美团：`Meituan Hotel comparison_26Q2.xlsx`
- 同程：`Tongcheng Travel Model_26Q2.xlsx`

## 决策

新建 `peers-model` 域，只做 Model 与 Charts。Word Appendix、业绩总结正文和研究判断继续由人完成，`peers-appendix` 仍保持退役。

三份 Model 通过本机 config 显式锁定，不按文件名或修改时间猜选。旧 `peers_rs_update` 与 `peers_model_scripts` 只读参考，新模块不 import 旧代码。

处理顺序固定为：PDF 第一遍抽取 → Agent 结构化 facts → 第二遍独立重读 PDF → 零写入计划 → 人确认 → 输出副本写入 → COM 重算与回读 → Charts gate。任何来源冲突先停下让人选择口径。

正式命令只在 `outputs/peers-model/` 生成新副本，不覆盖配置指向的 Model。同程数据写入 allowlist 只有前两个 sheet；`TCEL charts` 作为单独允许的图表 sheet，其余 sheet 禁写。

季度、半年和年度按模板实际存在的区块处理。季度继承上一季度，半年和年度继承上一年同期。不存在对应模板或可比期间时明确跳过，不自动创造布局。

Charts 的期间范围统一为：2019 对应期间起，排除 2020–2022，再接 2023 至目标期间；标签只落在 2019、2023 及以后各年的对应季度/半年度/年度。

## 后果

工作台域数是八个。`peers-model` 已用 26Q2 历史 PDF 盲填和 holdout 通过副本验收，标为 `partial`；下一次尚未写入的新季度仍要再跑一遍。不改变 `peers-appendix` 的退役状态。
