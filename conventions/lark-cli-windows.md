# lark-cli 在 Windows 上的踩坑（编码与传参）

> **迁移说明（2026-08-25）**：从旧仓 `.kiro/steering/feishu-cli-usage.md` 搬入。
>
> **第一次迁移没搬，理由记错了。**`conventions/README.md` 当时把它标成
> 「全局规范，工作台不再抄一份」——但全局那份 `~/.kiro/steering/lark-cli.md` 只有**策略**
> （优先用 CLI、先查 schema、写操作先 dry-run、high-risk 须确认），**一条编码与传参的坑都没有**。
>
> 「不抄第二份」这条原则是对的，前提是第一份真的覆盖。那次是**没核对就下了结论**——
> 这比单纯漏抄更危险，因为它留下一句「已被 X 覆盖」，让后来的人不会再去查。

**为什么放跨域**：`news-digest` 要写飞书 Wiki 文档、发卡片周报，`industry-data` 要写飞书多维表，
`expert-calls` 要写 Wiki 精选，三个域都用 lark-cli。

## 飞书身份：跟个人账号解耦

工作台是要分发给部门同事的包，**所有飞书工作流跟「谁第一次写过它」无关**。
身份永远是**本机当前 `lark-cli` 登录的那位同事**。换人、换电脑，只要对方用自己的飞书完成过 CLI 授权，同一套流程就能跑。

| 写进仓库的 | 绝不写进仓库的 |
|---|---|
| 部门共享资源：旅业资讯库 / 历史周报汇总 / Expert Call 等 Wiki URL 与文档 token；群名「IR小分队」 | 某个人的 `open_id`、`user_id`、CLI 应用 `cli_xxx`、个人机器人名 |
| 操作步骤：`whoami` → `--as user` 写文档 / `--as bot` 给当前操作者发卡 | 上一次会话里抄来的 ID；「发给陈则易」这类指名 |

跑任何飞书步骤之前：

```powershell
lark-cli whoami
lark-cli auth status --json --verify
```

`whoami` 失败或 `user.status` 不是 ready → **`blocked`**，说明「请用你自己的飞书完成 lark-cli 授权」，不要用仓库里、聊天记录里、上一个同事留下的身份接着发。

部门 Wiki 能写，是因为这位同事对那份文档有权限，不是因为应用绑死了某个人。卡片默认发给 **whoami 返回的当前操作者**，由 TA 转发进群——每个人的 CLI 应用可见范围通常是「仅本人」，这条路径换人仍然成立。

## 传 JSON 的黄金法则（最容易踩）

**绝不**把复杂或带中文的 JSON 直接塞进 `--content` / `--data` 命令行参数——
PowerShell 会按空格拆成一堆位置参数，中文还会乱码。

统一走「写文件 → `@file` 读入」，而且**必须用 .NET 写 UTF-8 无 BOM**：

```powershell
[System.IO.File]::WriteAllText("$PWD\req.json", $bodyJson, (New-Object System.Text.UTF8Encoding($false)))
```

⚠️ **`Out-File -Encoding utf8` 在 PowerShell 5.1 会写 BOM 头**，CLI 读 `@file` 时报
`invalid JSON`。这个坑最费时间，因为报错信息完全指不向真正的原因。

其余几条：

- `--data` / `--params` **支持** `@file` 与 `-`(stdin)；`--content`（im 快捷命令）**不支持**。
  传卡片这类大 JSON 优先用原生 `api` 命令 + `--data @file`。
- 读文件构造对象时用 `Get-Content -Raw -Encoding UTF8`，否则中文乱码。
- `receive_id_type` 这类 query 参数用 `--params @file`，**不要写进 URL 的 `?a=b`**——
  CLI 的路径解析会把 query 丢掉。
- 读 CLI 输出前先设 `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`，
  或把输出重定向到文件再读。
- 静默 JSON：`$env:LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1; $env:LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1`。
- 临时文件（req / params / 输出 json / 二维码 png）用完即删。

## 授权：两层，顺序不能乱

**应用层审批**与**用户授权**是两层，都要满足，且**必须先审批后授权**。顺序反了报
`Authorization failed / rejected`。

前三步只能在开放平台网页后台做（CLI 代劳不了）。**每位接手人在自己电脑上做一遍**，用的是自己的飞书，不要复用上一位同事的应用：

1. 创建个人应用（这是「当前这台电脑上的 CLI」，不是部门公用机器人）
2. 可见范围设为「仅申请人本人」——这样发卡路径（发给自己再转发）换人也能跑
3. 导入默认权限包 → **提交审批**。状态要走到「已通过 / 已发布」；
   「待申请」= 还没提交，需要点「申请发布」
4. 用户授权（CLI 做，见下）：扫的是**这位同事自己的**飞书二维码

### 用户授权走 split-flow，不要在同一轮阻塞等待

```powershell
lark-cli auth login --scope "<空格分隔的 scope>" --no-wait --json   # 立即返回 device_code + URL
lark-cli auth qrcode "<verification_url>" --output "qr.png"          # 相对路径
# 用户授权后由 Agent 自己收尾；device_code 不缓存，过期就重新生成
lark-cli auth login --device-code "<device_code>"
lark-cli auth status --json --verify    # 确认 user.status=ready, tokenStatus=valid
```

## 身份：`--as bot` 还是 `--as user`

| | 是什么 | 用于 |
|---|---|---|
| `--as bot` | 应用身份（tenant_access_token） | 发消息、发卡片、建群（`im:message:send_as_bot`、`cardkit:*` 都是 tenant 权限） |
| `--as user` | 用户身份（user_access_token） | 「你本人有权限」的资源：个人云盘、日历、你能看到的文档与群 |

读某个文档或 wiki 通常 bot 就能读（前提是 bot 有权限）；个人资源必须 user。

> 新闻精选的 Wiki 归档、专家访谈精选**一律 `--as user`**（当前登录同事的身份，且 TA 须对那份部门文档有权限）。
> 飞书卡片周报默认 `--as bot` 发给 **whoami 的当前操作者**，不是发给仓库里记着的某个人。

## 群聊的硬限制

- 机器人**能建群**（`im:chat:create`），建的群它是成员。
- 机器人**不能自己加入已有的群**：`im:chat.members:write_only` 只授权给 user。
  要进已有群 → 让群成员手动拉，或用 `--as user`（你是群主/管理员时）把它加进去。
- bot 只能给「应用可见范围内的用户」私聊，或「自己已在其中的群」发消息。
  可见范围是「仅申请人本人」时，只能私聊**当前这台机器上授权的那位同事**——这正是可分发的默认发卡路径。

## 安装失败其实可能已装好

`npm install -g @larksuite/cli` 若报 `EPERM` / `ENOTEMPTY`，但日志里有
`lark-cli vX.Y.Z installed successfully`——说明二进制装好了，只是清理临时目录被
Windows 文件锁挡住，npm 判定失败并回滚删包。

```powershell
npm uninstall -g @larksuite/cli
Remove-Item -Recurse -Force "$env:APPDATA\npm\node_modules\@larksuite" -ErrorAction SilentlyContinue
Remove-Item -Force "$env:APPDATA\npm\lark-cli*" -ErrorAction SilentlyContinue
npm install -g @larksuite/cli --ignore-scripts   # 跳过会失败的 postinstall
lark-cli --version                               # 首次运行自动补装二进制
```

长耗时安装走后台进程，不要用会超时的前台命令。

## 与全局规范的分工

| | 管什么 |
|---|---|
| 全局 `~/.kiro/steering/lark-cli.md` | **策略**：优先用 CLI、先查 schema、写操作先 dry-run、high-risk 须用户确认、不输出 token |
| 本文件 | **Windows 上的编码与传参坑、授权顺序、身份与群聊限制** |

两者不重叠。策略变了改全局，坑变了改这里。
