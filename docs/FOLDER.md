# 目录约定

目标：**打开就能找到东西；临时垃圾不进根目录。**

人怎么交文件、怎么取回、过期什么能删，见 [../conventions/file-lifecycle.md](../conventions/file-lifecycle.md)。本文只画树、钉「放 / 不放」。

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
│   ├── domains.py          #   九个域的注册表（ADR 0003 的可执行版本）
│   ├── paths.py            #   全部路径只在这里定义一次
│   ├── lifecycle.py        #   过期文件扫描与安全删除
│   ├── hygiene.py          #   换行符 + 过期清理入口
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
├── conventions/            # 跨域约定（溯源、命名、文件生命周期）
├── docs/                   # 给人读的持久文档
│   ├── CAPABILITIES.md     #   功能清单（给部门同事看）
│   ├── HANDOVER.md         #   同事开箱与日常开口
│   ├── GLOSSARY.md         #   统一语言
│   ├── DECISIONS.md        #   全部设计选择：问题 → 结论 → 理由
│   ├── MIGRATION.md        #   迁移计划与进度
│   ├── FOLDER.md           #   本文件
│   ├── PROJECT_STORY.md    #   历史快照，不以它核对当前域数
│   ├── adr/                #   难逆决策
│   ├── specs/              #   设计说明（-design.md）与操作手册（-runbook.md）
│   ├── analyst/            #   指向 HANDOVER / CAPABILITIES
│   ├── operator/           #   维护人：卫生、冻结目录、排错
│   └── shareholder-list/   #   股东名册域内术语
│
├── data/                   # 共享数据层，跨域共用，不在任何模块内
│   ├── workbooks/          #   指标底稿 Excel（唯一人工编辑面）
│   │   └── archived/       #   往期底稿与写入前备份，只增不删
│   ├── models/             #   Peers 权威 Model（本机锁定，不进 Git）
│   ├── canonical/          #   指标快照 + 洞察底稿
│   └── intel/              #   竞对情报库
│
├── inputs/<域>/<周期>/     # 本期原件（Git 忽略）
├── outputs/<域>/<周期>/    # 交付物（.md 精选进 Git；xlsx/PDF 等只留本机）
├── runs/<域>/<周期>/       # manifest
├── dashboard/travel/       # 看板投影（复制到发布仓上线）
├── tests/                  # 回归测试
└── scratch/                # 一次性产物，超 14 天可清，不入库
```

本机不应再嵌旧仓。若磁盘上还留着 `0703_Travel_Pulse/` 这类目录，见 file-lifecycle：不是入口，可删。
根目录 `output/`（少一个 s）是历史残留，可清。

## 各目录放什么

| 路径 | 放 | 不放 |
|---|---|---|
| `data/workbooks/` | 作为编辑面的 Excel | 快照、脚本输出、导出草稿 |
| `data/models/` | Peers 权威 Model（config 锁定） | 指标底稿、运行副本 |
| `data/workbooks/archived/` | 换表时的旧版、自动写入前的整份备份 | 当前正在用的底稿 |
| `data/canonical/` | 指标快照、洞察底稿 | Excel、scratch dump、密钥 |
| `data/intel/` | 情报库 JSONL 真源 | 财报原件（用户指定材料目录或 `inputs/intel-quarterly/`，情报库只存引用） |
| `inputs/<域>/<周期>/` | 只服务这一期的原件 | 长期数据、交付物 |
| `outputs/<域>/<周期>/` | 交付成品 | dry-run、抽取中间页 |
| `runs/<域>/<周期>/` | manifest（机器写，一般不手改） | 交付物 |
| `modules/<域>/` | 该域的代码、SKILL、references | 跨域约定、共享数据 |
| `conventions/` | **真的跨域**的规则 | 单域流程 |
| `docs/adr/` | 难逆、有取舍的决策 | 日常操作笔记 |
| `docs/specs/` | 某次任务的设计说明或 runbook | 临时 JSON、聊天摘录 |
| `scratch/` | dry-run 产物、字段 dump、探测脚本 | 任何需要长期保留的东西 |
| 根目录 | 入口文档、约定级配置 | **禁止**堆 `_*.json`、临时 txt、`output/` |

## 命名

见 [../conventions/file-naming.md](../conventions/file-naming.md)。周期键一律 ASCII。

## 三条容易踩的

1. **域键用连字符，目录与 Python 包用下划线。**`industry-data` ↔ `modules/industry_data/`。
   映射规则只有这一条，在 `workbench/paths.py` 的 `Paths.module` 里。
2. **周期键按域定义，不强行统一。**周报期次 / 数据截至日 / 年月 / 财季各不相同，
   见 `workbench/domains.py`。键是 ASCII，中文只作标签。
3. **`data/` 在模块之外。**Excel 和情报库都跨域，放进任何一个模块就又变成一处私有一处复制。

## 改本约定时

先改本文与 `workbench/paths.py`（`required_dirs`），以及 `conventions/file-lifecycle.md`，再搬文件——避免规则与实物脱节。
`ir doctor` 会检查 `required_dirs` 是否齐全。
