# ADR 0006 — 单一运行时：Node 脚本改写为 Python

- 状态：**Accepted**（2026-08-22）
- 日期：2026-08-22

## 背景

`industry-data` 链条原本**同时依赖 Python 和 Node**：`sync_travel.py` 用 `subprocess`
调 9 个 `.js` 脚本（约 427 行）完成看板投影与洞察草稿。

| 脚本 | 行数 | 作用 |
|---|---|---|
| `generate_data_js.js` + `lib/paths.js` | 46 | 快照 → `data.js` |
| `generate_insights_js.js` + `lib/insights.js` | 110 | 洞察 → `insights.js` |
| `generate_insights_md.js` + `lib/insights_md.js` | 149 | 洞察 → Markdown |
| `prepare_insights_draft.js` / `confirm_insights_draft.js` | 166 | 洞察草稿与入库 |
| `mark_insights_stale.js` | 24 | 指标更新后标洞察过期 |
| `bootstrap_canonical.js` | 30 | 从 `data.js` 冷启动 |

## 决策

**改写为 Python，工作台只要一个运行时。**

`bootstrap_canonical.js` 直接废弃——ADR 0001 之后 Excel 是权威，从 `data.js` 冷启动
与之矛盾。其余约 397 行改写进 `modules/industry_data/`。

## 理由

1. **安装门槛。**接手人非技术。双运行时意味着装工作台要装 Python **和** Node，
   `doctor` 要检查两个，zip 安装多一个失败点。这与「开箱即用」直接冲突。
2. **路径逻辑单一真源。**原来 `lib/paths.js` 与 Python 侧各算一套路径。改写后统一走
   `workbench/paths.py`。
3. **等价性可证明。**看板文件是纯生成产物，可拿现有输出**逐字节比对**——不靠肉眼审。

## 一个必须处理的细节：两种 JSON 数字写法

改写时发现权威文件与投影文件的序列化规则**本来就不同**，因为它们原本由不同运行时写出：

| 文件 | 原写出方 | `0.0` 的写法 |
|---|---|---|
| `travel.json` / `travel-insights.json` | Python `json.dumps` | `0.0` |
| `data.js` / `insights.js` | Node `JSON.stringify` | `0` |

若一律用 Python 写出，看板文件会产生与内容无关的差异噪音。故 `jsonio.py` 提供两个函数：
`dumps`（复刻 `JSON.stringify(data, null, 2)`，用于看板投影）与 `dumps_canonical`
（Python 原生写法，用于权威文件）。两者的差异有回归测试固定。

## 同一类问题的第二处：换行符

上线前比对时发现换行符也分家，而且比数字写法更混乱：

| 文件 | 原写出方 | 换行 |
|---|---|---|
| `travel.json` | Python `write_text` | **CRLF** |
| `travel-insights.json` | Node | LF |
| `data.js` / `insights.js` / 洞察 Markdown | Node | LF |

`travel.json` 的 CRLF 是 Python 在 Windows 上的默认行为，**不是任何人做过的约定**。

**决定：全部统一为 LF，不忠实复刻这套混乱。**代价是 `travel.json` 出现一次性全文件 diff
（412 行），而它只在内部仓、不进发布仓，且内部仓历史本来就是新起的——实际成本接近零。

落地：`workbench/fileio.py` 提供 `write_text` / `write_text_atomic`，一律 UTF-8 + LF；
仓库根 `.gitattributes` 固定 `eol=lf` 防止 Windows 检出时被换回来；回归测试断言生成的
看板文件不含 CRLF。

**这件事的一般教训**：跨运行时改写的等价性，不只是「内容一样」——序列化细节（数字写法、
换行符、键顺序）都会变成 diff 噪音，把真正的内容变化埋掉。验证必须比到字节。

## 验证结果

| 项 | 结果 |
|---|---|
| `insights.js` body | **逐字节完全一致** |
| `data.js` body | 仅差 3 处数据（旧 parser 漏读，见 ADR 0001）+ q2 键顺序归一 |
| `travel-insights.json` 往返 | 逐字节一致 |
| 回归测试 | 22 项全过 |

## 后果

**好的：**
- 安装只需 Python 3.14+，`doctor` 少一项外部依赖。
- 看板投影与洞察逻辑进入同一套类型与测试体系。

**要接受的：**
- `jsonio` 里那个 JS 数字写法的复刻是**长期负担**：它存在的唯一理由是让看板文件保持
  低差异噪音。若将来接受一次性重排看板文件，可以删掉它并统一用 Python 写法。
- 键顺序归一使 `quarterly` 各季字段顺序变化了一次（一次性，之后稳定）。

## 相关

- ADR 0001（指标底稿权威）、ADR 0003（模块划分）
- `modules/industry_data/jsonio.py`、`tests/test_industry_data.py`
