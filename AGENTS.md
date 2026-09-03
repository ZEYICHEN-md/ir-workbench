# Agent 入口

这是**携程 IR 部门的 AI 自动化工作台**。使用者是非技术同事：他们只说自然语言，不跑命令、不看终端、不读 traceback。

## 先读这个

**[router/ROUTER.md](router/ROUTER.md)** —— 意图路由表，决定用户想干什么、走哪个模块。
接到任何请求先落到那张表的某一行；落不进去就问，别猜。

各域的操作流程在 `modules/<域>/SKILL.md`。跨域约定在 `conventions/`。
统一语言在 [docs/GLOSSARY.md](docs/GLOSSARY.md)，决策理由在 [docs/adr/](docs/adr/)。

## 五条纪律

1. **CLI 是你的手，不是用户的。**你代跑 `ir ...`，然后用人话汇报。不要把命令贴给用户让他自己跑。
2. **不代选、不代判。**工作簿多候选让用户指定；数据冲突先列出数值、口径、来源、日期，等确认。
3. **门禁不可绕过。**标了「须明确确认」的动作，没听到用户明确措辞前停在 dry-run / 草稿，并说明「需要你说什么才能继续」。
4. **不确定性要显式返回。**用 `success` / `partial` / `blocked` / `failed` 四态汇报，说明缺什么、下一步是什么。缺失、部分成功、失败都不能包装成完成。
5. **取数必须可核对。**Excel 标 sheet + 单元格；PDF 标页码 + 表/行；网页标标题 + URL + 位置。见 `conventions/data-provenance.md`。

## 绝对不做（即使用户没提，也要守住）

- **不擅自对外发布。**任何发布——推看板发布仓、写飞书、发新闻精选——都要用户明确说了才做。
- **不把飞书绑死在某个人账号上。**身份永远是本机当前 `lark-cli` 登录的同事；禁止把 `open_id` / CLI 应用 ID 写进仓库或沿用上一次会话的 ID。见 `conventions/lark-cli-windows.md`。
- **不在新闻精选里写任何携程（TCOM）自己的动作与表述。**这是编辑纪律，见 ADR 0002。
- **不手改权威文件。**`data/canonical/*.json` 是投影产物；要改数就去改 `data/workbooks/` 里的 Excel（ADR 0001）。

## Windows 上跑命令前先做一件事

PowerShell 默认用 GBK 编码传给命令的参数，**中文参数会静默变成乱码**（见 ADR 0007）。
在会话里先执行一次：

```powershell
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $OutputEncoding=[System.Text.Encoding]::UTF8
```

周期键与目录名都已设计成 ASCII 以规避这个问题，但备注、标签这类中文参数仍然依赖它。
`ir doctor` 会检查并提醒。

## 状态先看一眼

不确定环境能不能跑、或者不知道上次做到哪，先跑：

```powershell
ir doctor      # 环境自检
ir status      # 按域报告进度
ir domains     # 有哪些域、哪些已迁入
```

`ir` 与 `py -m workbench` 等价。

## 迁移中

工作台正在整合三个旧项目，当前 **7** 个域挂在统一入口。`industry-data`、
`aviation-monthly`、`news-digest`、`competitor-intel`、`hk-market` 已完成真实业务验收；
`expert-calls` 的真实批次已完成飞书回读、A 类 11 条入库和 B 类 8 条待核，但批准稿另有
6 条 B 类尚未完成最终处置对账，因此仍为 `partial`；`sellside-research` 抽取与摘读层已用真实研报验收。
`peers-appendix` 已退役：季度
Appendix / 业绩总结不走自动化，查库用情报库。进度见 [docs/MIGRATION.md](docs/MIGRATION.md)。

`database_matain` / `0703_Travel_Pulse` / `peers_rs_update` 三个旧文件夹里的流程**已停用或待迁**，
不要在那里面跑（`database_matain` 已有显式停用标记）。

---

> 本文件是**唯一保证被各客户端自动读到**的入口，因此刻意重复了最危险的几条禁令。
> 其余内容一律只指路，不复制正文——规则的真源在 `router/`、`modules/*/SKILL.md`、`conventions/`。
