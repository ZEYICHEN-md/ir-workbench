# 新闻精选 · 飞书发布

> **迁移说明（2026-08-25）**：本文件从 `0703_Travel_Pulse/conventions/news-digest-feishu-archive.md`
> 整体搬入，只改了路径（`reports/{周期}/` → `outputs/news-digest/<期次键>/`、`_tmp/` → `scratch/`）。
> 里面的坑与写语义一个字没动——那些是跑了几期才摸出来的，重写只会丢。
>
> 第一次迁移时**漏了这份文件**，导致 SKILL 里的「发布到飞书」指向一个不存在的章节：
> 状态机留了一步，既没实现也没流程。这类悬空引用比缺功能更坏——它看起来是有的。

HTML 导出完成后，同步两份飞书文档（用户明确要求发布/归档时执行）。
**两份文档写语义相反，不要搞混。**

| 文档 | 角色 | 写语义 |
|------|------|--------|
| [旅业资讯库](https://trip.larkenterprise.com/wiki/JobqwazW9ivX2ykm4Jqc8dXwnBd) | 行业数据库主文档，只挂**最新一期** | **撤旧换新** |
| [历史周报汇总](https://trip.larkenterprise.com/wiki/G4GPwwRoQiDUCYkXVMncvwYKnCb) | 历史归档 | **末尾追加**，不覆盖已有期次 |

操作一律 `lark-cli`、`--as user`（**当前登录同事**的身份）。Wiki URL 先 `wiki +node-get` 核对 `obj_token`。
这两份是部门共享文档，不是某个人的云空间；换同事跑，只要 TA 对 Wiki 有编辑权限即可。开跑前 `lark-cli whoami`，不要沿用上一位操作者的 ID。

---

## 一、旅业资讯库（只挂最新一期）

| 项 | 值 |
|---|---|
| Wiki URL | `https://trip.larkenterprise.com/wiki/JobqwazW9ivX2ykm4Jqc8dXwnBd` |
| 文档 token | `ADJHdO2CWo0TMNxTZ2ecfHJAnlh` |
| 标题 | 旅业资讯库 |
| 章节 | 「行业新闻周报」（居中 h2，夹在左右 hr 的三栏 grid 里） |

当前结构（用户手调版）：

```
grid「行业新闻周报」标题
figure view-type="Preview"  ← 当期 HTML（文件名含周期，如 旅行行业新闻精选-2026年8月第2周.html）
callout 📇 往期周报详见：<cite>历史周报汇总</cite>
grid「Peers 季度业绩更新」
```

### 步骤

> **2026-08-25 实跑修正**：`--scope section --start-block-id <h2 的 id>` 在这里**不管用**——
> 那个 h2 嵌在三栏 grid 的中间一列里，section 只会回到该 column 内部，看不到 grid 之后的
> figure 与 callout。直接 `--scope full --detail with-ids` 最省事（这份文档只有约 15 KB）。
>
> 另：**`docs +fetch` 的文档参数是 `--doc`，不是 `--document-id`。**

1. `docs +fetch --scope full --detail with-ids`，在返回的 XML 里定位
   `<grid>`（含「行业新闻周报」h2）→ `<figure>` → `📇 往期 callout` → 下一个 `<grid>`（Peers 节）
2. 读现有 `<figure><source name="…">`：文件名里的周期 **等于** 刚交付的周期 → 已是最新，**不要动**
3. 过时则 —— **先插新、再删旧**（与本文件早前的写法相反，实跑后改的）：
   - `docs +media-insert --type file --file-view preview --selection-with-ellipsis "行业新闻周报"`
     （selection 命中的是 h2，附件落在其**顶层祖先**即那个 grid 之后，正好在往期 callout 之前）
   - 回读确认新附件在位后，再 `docs +update --command block_delete --block-id <旧 figure id>`
     （只删附件块，不要动标题 grid、往期 callout、Peers 节）

   **为什么把顺序反过来**：先删后插的话，中间态是「主文档这一节没有附件」；
   插入失败（实跑遇到过 `mcp.feishu.cn` TLS 超时）就会留下一个空节。
   先插后删则任何一步失败都不会让文档比原来更差。

   ⚠️ **主文档的附件用中文标准名** `旅行行业新闻精选-<中文标签>.html`——
   它对读者可见，而且第 2 步的判据就是「读附件名里的周期」。
   为避开中文**路径**问题只需把文件复制到 `scratch/` 下，**不必改文件名**（实测中文文件名可以上传）。
   曾经图省事传成 `news-digest-2026-08-W3.html`，与历史命名不一致，又重做了一遍。
   - `--selection-with-ellipsis` 必须用**当期独有**文本（如新 HTML 文件名片段或该节内不会与历史文档撞车的词），不要只用「要点新闻」（主文档没有这个词；历史汇总里每期都有，会插错位置）
4. `docs +fetch` 回读：确认该节只有 **一个** Preview HTML，且 `name` 对应当期

### 纪律

- 主文档**只保留一期**新闻精选 HTML；旧期去历史汇总，不在主文档堆多份
- 不要 overwrite 整篇「旅业资讯库」
- 往期 callout 里的 `<cite>` 指向历史汇总，不要改、不要删

---

## 二、历史周报汇总（只追加）

| 项 | 值 |
|---|---|
| Wiki URL | `https://trip.larkenterprise.com/wiki/G4GPwwRoQiDUCYkXVMncvwYKnCb` |
| 文档 token | `DvnEdJT5uosMKvxY79Dcz0Hongd` |
| 标题 | 历史周报汇总 |

### 文档结构（与用户手调版一致）

```
页头 blockquote（说明）
callout 📇 目录（灰色高亮块，可点击跳转各期 h2）
hr
每期：h2 → blockquote（发布｜情报主周）→ callout 💡 要点新闻 → HTML 预览
hr
下一期 …
```

### 页头（仅一次）

```xml
<blockquote><p>本文档归档各期「旅行行业新闻精选」。完整正文见下方 HTML 附件。</p></blockquote>
```

### 目录（期次增多时维护）

紧跟页头 blockquote 之后，放在 **灰色高亮块** 内（emoji 📇）：

```xml
<callout emoji="📇" background-color="light-gray" text-color="gray">
<p><b>目录</b></p>
<ul>
<li><a href="https://trip.larkenterprise.com/wiki/G4GPwwRoQiDUCYkXVMncvwYKnCb#{h2_block_id}">2026年7月第3周</a>（情报主周 07/20–07/26）</li>
</ul>
</callout>
```

- 链接格式：Wiki URL + `#` + 该期 `<h2>` 的 block id
- 新期归档后：`docs +fetch --detail with-ids` 取新 `h2` 的 id，在目录 `<ul>` **按时间顺序**插入一行（补历史空档插在相邻两期之间；最新一期加在目录末尾）
- 目录顺序与正文一致（先归档的在上）

> **实跑做法**：用 `docs +update --command block_replace --block-id <目录 callout id>`
> **整块重写**这个 callout，而不是往里插一个 `<li>`。callout 是容器块，整块替换更可控，
> 也能一次保证顺序。重写时要**原样带上它的属性**
> （`background-color="rgb(245,246,247)" emoji="📇" text-color="rgb(143,149,158)"`），
> 漏了颜色属性会让目录块的观感变掉。
>
> **含中文的 XML 一律走 `--content "@file"`，且文件必须 UTF-8 无 BOM。**
> 用 Python 的 `Path.write_bytes(s.encode("utf-8"))` 写，**不要用 `Out-File -Encoding utf8`**
> （PS 5.1 会写 BOM）。本次实跑连这份 fetch 输出都被 BOM 绊过一次。
> 见 `conventions/lark-cli-windows.md`。

### 每期结构

1. `<hr/>`
2. `<h2>{周期}</h2>`
3. `<blockquote><p>发布：{发布日}｜情报主周：{起止}</p></blockquote>`
4. **要点新闻** — `<callout emoji="💡">` 内：`<p><b>要点新闻</b></p>` + `<ul>`，只列 **1–2 条**（最多 3 条）标题
5. HTML 附件：`docs +media-insert --type file --file-view preview`，插在要点新闻 callout 之后

完整一期示例：

```xml
<hr/>
<h2>2026年7月第3周</h2>
<blockquote><p>发布：2026/07/29（周二）｜情报主周：2026/07/20–07/26</p></blockquote>
<callout emoji="💡">
<p><b>要点新闻</b></p>
<ul>
<li>Expedia 与 Allegiant 签署 12 个月独家 OTA 合作</li>
<li>西南航空改商业模式：收费行李、优选座位并接入 OTA 分销</li>
</ul>
</callout>
<!-- 随后 media-insert HTML preview -->
```

### 要点新闻写法

- 来源：`outputs/news-digest/<期次键>/旅行行业新闻精选-<中文标签>.md` 第一章各条 **标题**（加粗行）
- 从当期约 10 条中**只挑 1–2 条**（原则上不超过 3 条），选当周最具代表性的
- 只写标题，不写综述、不写正文；完整内容见 HTML 预览

### 插入位置

- **最新一期**：正文末尾 append；目录末尾加链接
- **补历史空档**（如先有 7月第3周、8月第1周，再补 7月第4周）：插在时间相邻的两期 **之间**，目录同样按时间插到对应位置，不要一律 append 到最后

### 附件定位（易错）

`+media-insert --selection-with-ellipsis` 会命中**文档里第一处**匹配。历史汇总每期都有「要点新闻」，只用这个词会把附件插到第 1 期下面。

正确做法：

1. 先写入当期 h2 + 发布信息 + 💡 callout
2. `docs +fetch --detail with-ids` 拿到**当期** callout 的 block id
3. `+media-insert` 用当期**独有**片段作 selection（如该期第二条要点标题），或插完后用 `block_move_after --block-id {当期 callout id}` 把 figure 挪到当期 callout 之后
4. 回读确认：该期 h2 → callout → **对应文件名**的 figure，且没有插到别的期下面

> **2026-08-25 实跑发现：归档最新一期时根本不需要 selection。**
> 最新一期的 h2/callout 刚 append 到文档末尾，`+media-insert` **不带 selection 就是追加到文末**，
> 正好落在当期 callout 之后。位置对，还绕开了 `--selection-with-ellipsis` 依赖的
> `mcp.feishu.cn` locate 服务（实跑时它 TLS 超时两次，不带 selection 一次就成）。
>
> **selection 只在补历史空档时才需要**——那时要插到中间，没法靠 append。
>
> ⚠️ 历史汇总的附件名沿用 **ASCII 小写** `news-digest-<期次键小写>.html`
> （既有 4 期都是这个形状），与主文档的中文名不同。两边各自沿用，不要统一。

### 历史汇总纪律

- **append / 定点插入**，不 overwrite（除非用户明确要求重建整页）
- 不写完整新闻正文、来源表进归档页（均在 HTML 内）
- 目录用 📇 灰色 callout，要点新闻用 💡 callout——不要用裸 `<p>` 代替

---

## 三、交付后的默认顺序

当期 HTML 已导出且用户要发布/归档时：

1. 旅业资讯库：过时则撤旧 HTML，插入新 HTML（Preview）
2. 历史周报汇总：若该期尚不在目录/正文中，按上面结构追加（或补空档）
3. 两份都 `docs +fetch` 回读

本地 HTML 先复制到 `scratch/news-digest-<期次键>.html` 再用相对路径上传
（`+media-insert --file` 不接受仓库外绝对路径；中文路径也可先复制成短英文名）。

## 共用纪律

- 用 `lark-cli`，不用浏览器自动化
- 不覆盖原始 `outputs/news-digest/` 文件
- 未完成 HTML 导出不要改飞书
- **发布是对外动作，须用户明确要求**（AGENTS.md「绝对不做」第 1 条）
- 开跑前先 `lark-cli whoami` 与 `auth status --json --verify` 确认**当前同事**的 user 身份 ready、token 有效；失败则 `blocked`，不要借用其他人的登录态
- 命令前设 `$env:LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1; $env:LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1` 静默噪音

## 回读校验时的一个坑

写完用脚本核对时，**不要用 `content.find("2026年8月第3周")` 定位当期那一组块**——
期次名在文档里至少出现两次（目录里的链接文字在文档开头，真正的 h2 在末尾），
`find` 会先命中目录，于是"当期"从目录一路算到文档结束，把全部期次的附件都算进来。

要匹配真正的标题块：`re.search(r'<h2 id="[^"]+"[^>]*>2026年8月第3周</h2>', content)`。
本次实跑就被这条绊了一次，第一版校验报「附件插到别期下面了」，其实是校验脚本自己错。

## 一期做完的验收清单

- [ ] 旅业资讯库：`<figure>` 只有 **1 个**，附件名含当期中文标签
- [ ] 旅业资讯库：📇 往期 callout 与 Peers 节都还在
- [ ] 历史周报汇总：**期次数 == 附件数 == 目录行数**
- [ ] 历史周报汇总：当期块顺序是 `h2 → blockquote → callout → figure`，且该段内只有 1 个附件
