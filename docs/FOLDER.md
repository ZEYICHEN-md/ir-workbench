# 目录约定

目标：**打开就能找到东西；临时垃圾不进根目录。**

## 树形一览

```text
IR_workbench/
├── AGENTS.md               # Agent 入口（各客户端都会自动读到）
├── CLAUDE.md               # 薄壳 → AGENTS.md
├── README.md               # 人的入口
├── pyproject.toml          # 安装：py -m pip install -e .
├── .gitattributes          # 生成文件一律 LF（见 ADR 0006）
├── .ir-workbench/          # 本机配置（Git 忽略；本机配置与共享代码分离）
│
├── router/ROUTER.md        # 意图路由表：人说什么 → 走哪个域
├── workbench/              # Control Plane（Agent 的手，不是人的入口）
│   ├── domains.py          #   八个域的注册表（ADR 0003 的可执行版本）
│   ├── paths.py            #   全部路径只在这里定义一次
│   ├── config.py           #   工作簿显式锁定，绝不代选
│   ├── doctor.py           #   环境自检
│   ├── status.py           #   按域报告，不合成全局进度条
│   ├── manifest.py         #   运行留痕：域 + 周期键，输入输出 SHA-256
│   ├── result.py           #   四态语义 success/partial/blocked/failed
│   ├── fileio.py           #   统一 UTF-8 + LF 写出
│   └── cli.py              #   ir ...
│
├── modules/<域>/           # 各域实现（目录用下划线，域键用连字符）
│   └── SKILL.md            #   该域的端到端流程
│
├── conventions/            # 跨域约定（溯源、命名）
├── docs/                   # 给人读的持久文档
│   ├── CAPABILITIES.md     #   功能清单（给部门同事看）
│   ├── GLOSSARY.md         #   统一语言
│   ├── DECISIONS.md        #   全部设计选择：问题 → 结论 → 理由
│   ├── MIGRATION.md        #   迁移计划与进度
│   ├── FOLDER.md           #   本文件
│   ├── adr/                #   难逆决策
│   ├── specs/              #   设计说明（-design.md）与操作手册（-runbook.md）
│   ├── analyst/            #   非技术同事的操作手册
│   └── operator/           #   维护人排错手册
│
├── data/                   # 共享数据层，跨域共用，不在任何模块内
│   ├── workbooks/          #   指标底稿 Excel（唯一人工编辑面）
│   ├── canonical/          #   指标快照 + 洞察底稿
│   └── intel/              #   竞对情报库
│
├── inputs/<域>/<周期>/     # 本期原件
├── outputs/<域>/<周期>/    # 交付物
├── runs/<域>/<周期>/       # manifest
├── dashboard/travel/       # 看板投影（复制到发布仓上线）
├── tests/                  # 回归测试
└── scratch/                # 一次性产物，可随时清空，不入库
```

## 各目录放什么

| 路径 | 放 | 不放 |
|---|---|---|
| `data/workbooks/` | 作为编辑面的 Excel | 快照、脚本输出、导出草稿 |
| `data/canonical/` | 指标快照、洞察底稿 | Excel、scratch dump、密钥 |
| `data/intel/` | 情报库 JSONL 真源 | 财报原件（归 `peers-appendix` 的 `companies/`） |
| `inputs/<域>/<周期>/` | 只服务这一期的原件 | 长期数据、交付物 |
| `outputs/<域>/<周期>/` | 交付成品 | 中间产物 |
| `runs/<域>/<周期>/` | manifest（机器写，一般不手改） | 交付物 |
| `modules/<域>/` | 该域的代码、SKILL、references | 跨域约定、共享数据 |
| `conventions/` | **真的跨域**的规则 | 单域流程 |
| `docs/adr/` | 难逆、有取舍的决策 | 日常操作笔记 |
| `docs/specs/` | 某次任务的设计说明或 runbook | 临时 JSON、聊天摘录 |
| `scratch/` | dry-run 产物、字段 dump、探测脚本 | 任何需要长期保留的东西 |
| 根目录 | 入口文档、约定级配置 | **禁止**堆 `_*.json`、临时 txt |

## 命名

见 [../conventions/file-naming.md](../conventions/file-naming.md)。

## 三条容易踩的

1. **域键用连字符，目录与 Python 包用下划线。**`industry-data` ↔ `modules/industry_data/`。
   映射规则只有这一条，在 `workbench/paths.py` 的 `Paths.module` 里。
2. **周期键按域定义，不强行统一。**周报期次 / 数据截至日 / 年月 / 财季各不相同，
   见 `workbench/domains.py`。
3. **`data/` 在模块之外。**Excel 和情报库都跨域，放进任何一个模块就又变成一处私有一处复制。

## 改本约定时

先改本文与 `workbench/paths.py`（`required_dirs`），再搬文件——避免规则与实物脱节。
`ir doctor` 会检查 `required_dirs` 是否齐全。
