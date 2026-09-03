# Peers Appendix · 当季材料 → Model → 写作

本模块唯一公开入口是 `ir peers ...`。旧 `peers_rs_update` 已冻结；运行时不得回读、导入或调用
旧仓脚本。本机 `peers-earnings-summary` skill 副本已过时，也不是权威来源。

## 使用范围

- 机械工作：材料归档与路径解析、Model 插列/填数/勾稽、图表更新与导出、事实 brief、
  `texts.json` 门禁、按公司模板写入 Word、嵌图和成品验收。
- 人工工作：从 IR 材料确认数字并填写 `ir_snapshot.json` / `fill_inputs.json`；
  决定战略段如何处理；根据当季材料写 `texts.json`。
- 不代做：战略判断、未披露数字推算、跨公司套模板、跳过失败门禁。

## 周期与目录

周期键为财季短键，例如 `26Q2`；Excel 内部季度标签为 `2026Q2`。

```text
inputs/peers-appendix/<TICKER>/<YYQn>/
  原始 IR / 8-K / transcript / 对应 txt
  source_model.xlsx
  template.docx
  ir_snapshot.json             # 人工
  fill_inputs.json             # 人工
  strategy_decision.json       # 人工明确确认
  texts.json                   # 人工写作
  chart_map.json               # ABNB/BKNG 嵌图时人工核对

outputs/peers-appendix/<TICKER>/<YYQn>/
runs/peers-appendix/<YYQn>/manifest.json
runs/peers-appendix/<YYQn>/<TICKER>/
```

先初始化并查看需要哪些文件：

```text
ir peers init --ticker EXPE --period 26Q2
ir peers resolve --ticker EXPE --period 26Q2
```

`init` 只建目录和 workbench Manifest，不会生成带假数字的 JSON。`resolve` 只读。

## 材料门禁

`ir_snapshot.json` 至少有：

```json
{
  "ticker": "EXPE",
  "quarter": "2026Q2",
  "sources": ["earnings-release.pdf", "transcript.txt"],
  "actuals": {
    "revenue": {
      "value": 4120,
      "yoy": 0.14,
      "model_row": 59,
      "yoy_model_row": 60
    }
  },
  "guidance": {},
  "must_cover_in_writing": []
}
```

`sources` 中每项必须能在材料目录解析到原文件或同 stem 的 `.txt` / `.md`。数字与出处不齐就停。

`fill_inputs.json` 由人依据 snapshot 和 IR 填写：

```json
{
  "sheet": "EXPE",
  "quarter": "2026Q2",
  "font_mode": "copy_prev_col",
  "inputs": [{"row": 59, "label": "Revenue", "value": 4120}]
}
```

不覆盖公式行。任何复杂公式的 audit WARN 在正式管道中也视为 hard stop。

## Model 阶段

```text
ir peers model --ticker EXPE --period 26Q2
```

固定顺序：

```text
materials → insert → fill → audit_model_quarter
→ charts → check_charts_gate → export
```

Excel COM 写步骤始终写到 sibling 文件，关闭 Excel 后再晋升为 work model；不对同一路径 `-o`
死等。COM 超过约 60 秒无输出、同一动作重试一次仍挂、或 clipboard 连续失败时停下找人。

四道 must-pass gate 不可跳过：

1. `audit_model_quarter`：fill 落地、格式、IR snapshot 与 ticker 对抗勾稽
2. `check_charts_gate`：系列到当季、整数季节标签、无重叠/贴 x 轴
3. `check_writing_gate`：槽位、表格、当季 must-cover 与原话出处
4. `accept_docx_gate`：季度文字、ticker 模板 re-apply、实际映射图位

只复查门禁：

```text
ir peers gate --ticker EXPE --period 26Q2 --phase model
ir peers gate --ticker EXPE --period 26Q2 --step audit_model_quarter
```

未知步骤必须报错；不允许像旧 orchestrator 那样打印 `skip unknown step` 后继续。

## Writing 阶段

```text
ir peers writing --ticker EXPE --period 26Q2
```

第一次通常会在缺人工文件处返回 `blocked`。先看生成的 `writing_brief.json`，再填写：

```json
{
  "ticker": "EXPE",
  "quarter": "2026Q2",
  "scope": "ops_finance",
  "paragraphs": [{"id": "ops_h1", "text": "业务运营"}],
  "tables": []
}
```

战略段须另外提供：

```json
{
  "decision": "preserve-template",
  "confirmed_by_human": true,
  "notes": "本次只更新业务运营和财务段"
}
```

`decision` 只接受 `preserve-template` / `mentor-supplied` / `out-of-scope`。系统不会创建或默认确认。

Word apply 路由：

- EXPE → EXPE 专用 anchors + 三张财务表
- ABNB → ABNB 专用 apply；只传 operations/finance slots，战略段不动
- BKNG → 原通用 finance/ops anchors
- 其他 ticker → 明确 blocked，不声称通用写作支持

图表导出路由：

- EXPE → EXPE clipboard 稀疏图号与已验证 Word map
- ABNB → ABNB clipboard 图 1–6
- BKNG / 其他 → 原生 `Chart.Export` 通用路径

旧仓没有经过验证的 ABNB/BKNG Word 图位映射，因此这两家导出后会在 embed 前 hard block，
要求人工提供本公司 `chart_map.json`；绝不套用 EXPE 的 image3–8 map。

## 状态

```text
ir peers status --period 26Q2
ir peers status --ticker ABNB --period 26Q2
```

季度共用一份 workbench Manifest，步骤用 `TICKER:step` 分隔，输入输出均留 SHA-256。

## 明确废弃、不迁

- `render_expe_finance_texts.py`
- `audit_expe_alignment.py`
- `verify_abnb_26q2_numbers.py`
- `verify_abnb_26q2_ops_finance.py`
- `_cleanup_wip_layout.py`
