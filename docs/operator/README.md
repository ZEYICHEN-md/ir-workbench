# 维护人手册

同事看 [../HANDOVER.md](../HANDOVER.md) 和 [../CAPABILITIES.md](../CAPABILITIES.md)。这里只给要改仓库、装机、清文件的人。

## 日常三问

```powershell
ir doctor
ir status
ir hygiene
```

过期临时文件：

```powershell
ir hygiene --prune          # 只列出
ir hygiene --prune --fix    # 须用户明确说「确认删除过期临时文件」之后才跑
```

规则：[../../conventions/file-lifecycle.md](../../conventions/file-lifecycle.md)。
`--fix` 只动 `scratch/`（≥14 天）、`_tmp/`、根目录 `output/`。
不删 `data/workbooks/archived/`、`runs/`、交付物、情报库。

## 冻结目录

本机若还有这些文件夹，不要在里面跑流程，也不要往里面提交：

- `0703_Travel_Pulse/`、`database_matain/`、`peers_rs_update/`（三个旧仓）
- `peers_model_scripts/`（`peers-model` 迁入时的只读摘录）
- `update-shareholder-list/`（`shareholder-list` 迁入前的交接包）

运行入口只有 `modules/<域>/` + `ir ...`。

## 文档以谁为准

| 问题 | 真源 |
|---|---|
| 用户想干什么 | `router/ROUTER.md` |
| 现在有几个域、验收到哪 | `workbench/domains.py`，进度叙事 `docs/MIGRATION.md` |
| 目录放什么 | `docs/FOLDER.md` + `conventions/file-lifecycle.md` |
| 为什么这么设计 | `docs/DECISIONS.md` 与 `docs/adr/` |
| `docs/PROJECT_STORY.md` | 历史快照，**不要**用它核对当前域数 |

## 装机

见仓库根 [../../README.md](../../README.md)「维护人：装一下」。飞书仍需要本机 Node + `lark-cli`；工作台业务代码本身只有 Python（ADR 0006）。
