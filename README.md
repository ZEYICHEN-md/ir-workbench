# IR 工作台

携程 IR 部门的 AI 自动化工作台。把部门高频工作沉淀为可分发、可移交、可持续使用的系统。

## 我该看哪份文档

| 你是 | 看这个 |
|------|--------|
| **部门同事 / 接手人**（不写代码） | [docs/CAPABILITIES.md](docs/CAPABILITIES.md) —— 工作台能做什么、怎么开口 |
| Agent | [router/ROUTER.md](router/ROUTER.md) —— 意图路由 |
| 想知道为什么这么设计 | [docs/adr/](docs/adr/) · [docs/GLOSSARY.md](docs/GLOSSARY.md) · [docs/DECISIONS.md](docs/DECISIONS.md) |
| 目录里什么放哪 | [docs/FOLDER.md](docs/FOLDER.md) |

首次安装引导（`docs/analyst/`）与维护人手册（`docs/operator/`）**尚未编写**，
排在迁移完成之后。现阶段装机步骤见本文末「维护人：装一下」。

## 怎么用

打开这个文件夹（Kiro、Cursor 或 Claude Code 均可），对 Agent 说话。不需要记命令，不需要开终端。

不确定能做什么时，问一句「**工作台现在能做什么 / 什么状态**」。

## 八个域

| 域 | 面向 | 节奏 |
|---|---|---|
| 旅行行业新闻精选 | **对外交付** | 每周 |
| 国内行业数据与看板 | 内部 | 每周 / 每月 |
| 航空月度数据写入 | 内部 | 每月 |
| 港股市场数据 | 内部查询 | 按需 |
| 竞对情报库 | 内部 | 每周 / 每季 / 按访谈 |
| 专家访谈情报与精选 | 内部 | 按访谈到达 |
| Peers 财务模型维护 | 内部 | 每季 / 半年 / 年度 |
| 卖方研报摘读 | 内部查询 | 按需 |

对外交付物只有新闻精选一个。

## 决策记录

整合过程中的全部设计选择（问题 → 结论 → 理由）见 [docs/DECISIONS.md](docs/DECISIONS.md)，
难逆决策见 [docs/adr/](docs/adr/)。

## 迁移状态

工作台正在把三个旧项目整合进来。当前 **8** 个域挂上统一入口；前五个已完成真实业务验收，
`expert-calls` 飞书发布已完成首次真实验收、情报入库仍待下一批访谈核对，
`sellside-research` 已完成真实抽取与摘读。`peers-model` 做 Model / Charts 机械维护；
`peers-appendix` 写作流水线仍退役。

- [x] 骨架 + Control Plane（`ir doctor` / `ir status` / Windows CI）
- [x] `industry-data`（含指标底稿归位与真实上线）
- [x] `aviation-monthly`（含 2026 年 7 月真实写入）
- [x] `news-digest` + `competitor-intel`（含 2026-08-W4 真实验收）
- [x] `expert-calls`（情报优先采集 + 独立飞书精选；飞书分支已验收，情报分支待下一批）
- [x] `hk-market` / `sellside-research`（2026-09-02 真实只读验收）
- [x] `peers-appendix` **退役**（不维护 Word Appendix 流水线；旧仓冻结）
- [x] `peers-model`（PDF → Model / Charts 机械更新；权威文件只出副本）

顺序与理由见 [docs/adr/0003-single-repo-and-module-layout.md](docs/adr/0003-single-repo-and-module-layout.md)。

## 维护人：装一下

```powershell
py -m pip install -e .
py -m workbench doctor
py -m workbench domains
```

`ir` 命令与 `py -m workbench` 等价。**这些命令是给 Agent 和维护人用的，不写进面向同事的手册。**
