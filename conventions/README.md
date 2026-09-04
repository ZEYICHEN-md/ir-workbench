# 跨域约定

只放**多个域共用**的规则。单个域自己的流程放 `modules/<域>/SKILL.md`。

| 文件 | 管什么 |
|---|---|
| [data-provenance.md](data-provenance.md) | 取数溯源、数据冲突处理、缺失披露 |
| [file-naming.md](file-naming.md) | 工作簿、原件、交付物、文档的命名 |
| [file-lifecycle.md](file-lifecycle.md) | 文件怎么进工作台、放哪、过期什么能删 |
| [lark-cli-windows.md](lark-cli-windows.md) | 飞书身份与个人账号解耦；lark-cli 在 Windows 上的编码与传参坑、授权顺序、身份与群聊限制 |

## 待迁入（随对应域迁移一起做）

**填这张表有一条硬要求：写「已被 X 取代 / 已覆盖」时，必须指出覆盖它的是
哪份文件的哪一节，并且真的去看过。**

理由是踩过：lark-cli 那一行原本写「全局规范，工作台不再抄一份」，
但全局那份只有策略、一条编码坑都没有。**「不抄第二份」原则没错，前提是第一份真的覆盖。**
那次是没核对就下了结论——比单纯漏抄更危险，因为它留下一句「已覆盖」，
让后来的人不会再去查。

| 内容 | 现位置 | 归属 / 覆盖它的具体是哪儿 |
|---|---|---|
| 工作区布局约定 | `0703_Travel_Pulse/conventions/workspace-layout.md` | 已由 `file-naming.md` 的三件套表覆盖（`inputs/<域>/<周期>`、`runs/`、`outputs/`，比旧仓多了域一层）。**已核对** |
| 飞书新闻归档约定 | `0703_Travel_Pulse/conventions/news-digest-feishu-archive.md` | ✅ 已迁入 `modules/news_digest/references/feishu-publish.md`（逐段一致，只改路径） |
| lark-cli 编码与传参坑 | `0703_Travel_Pulse/.kiro/steering/feishu-cli-usage.md` | ✅ 已迁入本目录 `lark-cli-windows.md`。**全局 steering 只有策略，不覆盖这些坑** |

## 加新约定之前先问一句

这条规则是**真的跨域**，还是只服务一个域？只服务一个域就放那个域的 `SKILL.md`。
本目录膨胀的代价是没人知道该去哪找规则。
