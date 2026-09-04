# 文件怎么进工作台、放哪、什么时候能删

给 Agent 与维护人。同事不用记路径：把文件拖进对话、放在「下载」里、或说一声即可。

规则只有这一份。目录树在 [../docs/FOLDER.md](../docs/FOLDER.md)；命名在 [file-naming.md](file-naming.md)。

## 人怎么存取（开口即可）

| 人想做的事 | 怎么开口 / 怎么交文件 | Agent 做什么 | 人之后去哪取 |
|---|---|---|---|
| 交一份原件（中金周报、STR、研报、财报 PDF、专家访谈） | 拖进对话框，或告诉本地路径 / 飞书链接 | 复制到 `inputs/<域>/<周期>/`，**不改原文件名** | 不用自己找；要核对就问「这期原件在哪」 |
| 交 Capital IQ 股东底表 | 留在电脑 **下载** 文件夹，说「更新 shareholder list」 | 按 mtime 发现 Downloads 里最新的 Peer / Combined | 交差文件在 `outputs/shareholder-list/<有效日>/` |
| 换一份国内行业数据 Excel | 把表放进 `data/workbooks/`，说「换一份新的国内行业数据」 | 列候选，**等人指定**后锁定；旧表归档到 `data/workbooks/archived/` | 永远只改被锁定的那一份 |
| 取上期新闻精选 / 模型副本 / 股东名册 | 「上期新闻精选在哪」「BKNG 模型副本在哪」 | 用人话报 `outputs/<域>/<周期>/` 的路径，必要时帮打开 | 交付物在 `outputs/`，不要翻 `scratch/` |
| 清理过期临时文件 | 「清理过期的临时文件」 | 先 `ir hygiene --prune` 列出；**须明确说「确认删除过期临时文件」** 才 `--fix` | 只清安全桶；原件与底稿归档不动 |

不要让同事自己建 `inputs/` 子目录，也不要把命令贴给人跑。

## 如果一定要自己拖进文件夹

日常仍建议拖进对话框或放「下载」。非要在资源管理器里放，只进这些位置，**不要放仓库根目录，也不要放旧仓文件夹**：

| 你手里的东西 | 拖到这里 |
|---|---|
| 国内行业数据 / Airline Data 新 Excel | `data/workbooks/`（放下后说「换一份新的国内行业数据」，等人指定锁定） |
| 中金周报、STR 表 | `inputs/industry-data/`（Agent 会再按截至日归期） |
| 卖方研报 PDF | `inputs/sellside-research/` |
| Peers 财报 / 电话会 PDF | `inputs/peers-model/`（或直接拖进对话） |
| 专家访谈 PDF | `inputs/expert-calls/`（或直接拖进对话 / 贴飞书链接） |
| 季度披露材料包 | `inputs/intel-quarterly/<公司>/<财季>/` |
| Capital IQ 股东底表 | 电脑 **下载**，不要进工作台 |
| 交差成品、模型副本 | 不要手塞；问 Agent 去 `outputs/` 取 |

根目录的 `0703_Travel_Pulse/`、`database_matain/`、`peers_rs_update/`、`peers_model_scripts/`、`update-shareholder-list/`、`test_expert_calls/` **不是收件箱**。


## 各层放什么

| 路径 | 谁写 | 进 Git？ | 能不能删 |
|---|---|---|---|
| `data/workbooks/` | 人编辑的指标底稿 | 当前锁定的表进 Git | **当前表不删**。换新版时旧表进归档 |
| `data/workbooks/archived/` | 换表或自动写入前的整份备份 | 进 Git | **只增不删** |
| `data/canonical/` | 机器从底稿重建 | 进 Git | 不删、不手改 |
| `data/intel/` | 情报库真源 | 进 Git | 不删 |
| `inputs/<域>/<周期>/` | 人交来的原件（Agent 代放） | **不进**（体积大、第三方材料） | 超 90 天只**报告**，问人后才删 |
| `outputs/<域>/<周期>/` | 交付物 | 新闻精选的 `.md` 进 Git；HTML/PDF、模型副本、股东名册 xlsx、研报摘读 **不进** | 交付物不自动删 |
| `runs/<域>/<周期>/` | manifest | 进 Git | 不删（体积小，是进度记忆） |
| `scratch/` | dry-run、抽取文本、探测 | **不进** | **超 14 天可自动清** |
| `_tmp/`、根目录 `output/` | 历史残留 | 不进 | **整桶可清**（真源是 `outputs/`，注意多一个 `s`） |
| `dashboard/travel/` | 看板投影 | 进 Git | 不删；上线走发布仓 |
| `.ir-workbench/` | 本机配置 | **不进** | 不删 |

卖方研报、专家访谈 PDF/TXT、Peers 模型副本、股东名册 xlsx 只留本机，见 `.gitignore`。

## 冻结目录（本机可有，不是入口）

这些文件夹**可以留在磁盘上当历史**，但工作台不从里面跑、不按本仓规则改写、不进 Git：

| 目录 | 是什么 |
|---|---|
| `0703_Travel_Pulse/` | 旧仓，已拆完。GitHub `Travel_Pulse` 留历史，本机可删 |
| `database_matain/` | 旧仓，已迁完并停用。GitHub 留历史，本机可删 |
| `peers_rs_update/` | 旧仓，Appendix 退役后冻结。**例外**：本机 config 仍把三份权威 Model 锁在这里，搬走并重新锁定之前不要删 |
| `peers_model_scripts/` | 迁 `peers-model` 时的只读摘录，可删 |
| `update-shareholder-list/` | 迁 `shareholder-list` 前的交接包，可删 |
| `test_expert_calls/` | 专家访谈验收用过的 PDF，不是入口；可删，下一批评 `inputs/expert-calls/` 或拖进对话 |

真源在 `modules/<域>/`。发现第二套 `src/`、`scripts/rebuild.ps1` 或旧仓脚本，不要用。

## 过期怎么清

命令是 Agent 的手：

1. `ir hygiene --prune` —— 只列出，不删。
2. 把清单用人话告诉用户。
3. 用户说「确认删除过期临时文件」之后，才 `ir hygiene --prune --fix`。

`--fix` 只删安全桶：`scratch/`（≥14 天）、`_tmp/`、根目录 `output/`。
`inputs/` 超 90 天会出现在清单里，但命令不会删。
`data/workbooks/archived/`、`runs/`、`outputs/` 交付物、情报库，永远不走这条命令。

换行符卫生仍是 `ir hygiene` / `ir hygiene --fix`（ADR 0006），与过期清理互相独立；两个开关可以一起加。
