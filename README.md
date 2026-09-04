# IR 工作台

携程 IR 部门的日常工作台。打开这个文件夹，对 Agent 说话即可。不需要记命令，不需要开终端。

你负责判断和确认。Agent 负责取数、核对、落文件。对外发布和改权威数据，一定要你先说「确认」。

## 打开之后看这三份

| 你想知道 | 看 |
|---|---|
| **文件夹是干什么的、东西往哪存、从哪取** | [docs/MAP.md](docs/MAP.md) |
| 能做什么、怎么开口 | [docs/CAPABILITIES.md](docs/CAPABILITIES.md) |
| 第一次怎么用、哪些事必须你点头 | [docs/HANDOVER.md](docs/HANDOVER.md) |

不确定时，问一句「**工作台现在能做什么 / 什么状态**」。

## 九个域

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
| 机构股东名册 | 内部 | 每季 / 按有效日 |

对外交付物只有新闻精选一个。

## 包里有什么

**会跟着走的部门 context：** 九个域的流程、当前锁定的行业数据 Excel 与归档、三份 Peers 权威 Model、指标快照、竞对情报库、已定稿的新闻精选 Markdown、各期运行记录、以及上面三份说明。

**不跟着走的：** 当期原件（下周会换）、每次跑出来的模型副本 / 股东名册 xlsx / 精选 HTML（都能再生成）、本机飞书登录。详见 [docs/MAP.md](docs/MAP.md)。

Agent 与维护人：[router/ROUTER.md](router/ROUTER.md) · [docs/operator/README.md](docs/operator/README.md) · [docs/adr/](docs/adr/)

## 维护人：装一下

```powershell
py -m pip install -e .
py -m workbench doctor
py -m workbench domains
```

`ir` 命令与 `py -m workbench` 等价。**这些命令是给 Agent 和维护人用的，不写进面向同事的手册。**
