# Peers 权威 Model

三份 Excel 随工作台一起走。clone / 解压之后就可以用，不必再拷一遍。

当前锁定哪几份，以 `data/workbook-lock.json` 为准。换新版本：把文件放进本文件夹，对 Agent 说「锁定这三份 Model」。

| 用途 | 文件名大致长这样 |
|---|---|
| BKNG / EXPE / ABNB 共用 | `peers data comparison_*.xlsx` |
| 美团 | `Meituan*.xlsx` |
| 同程 | `Tongcheng*Model*.xlsx` |

不要手改格子来「更新一季」。更新只出副本，副本在 `outputs/peers-model/`（运行产物，不进 Git，需要时从这里的权威文件再生成）。
