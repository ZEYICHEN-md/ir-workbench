# 长期数据

部门一直要用的底稿和情报在这里。当期原件去 `inputs/`，交差成品去 `outputs/`。
完整地图：[docs/MAP.md](../docs/MAP.md)。

| 子文件夹 | 是什么 | 你怎么用 |
|---|---|---|
| `workbooks/` | 《国内行业数据》和 Airline Data。全部门只认被锁定的那一份 | 改数只改这一份；换表放进来再说「换一份」 |
| `workbooks/archived/` | 换表前、自动写入前的备份 | **不要删** |
| `models/` | Peers 三份权威 Model（随仓走） | 新版本放这里让 Agent 锁定；更新只出副本 |
| `workbook-lock.json` | 当前锁定哪几份 Excel | 换表时由 Agent 改；不要手改 |
| `canonical/` | 从底稿生成的指标快照和洞察 | **不要手改** |
| `intel/` | 竞对情报库 | 对 Agent 按公司 / 主题查；不要手改 JSONL |
