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

操作一律 `lark-cli`、`--as user`。Wiki URL 先 `wiki +node-get` 核对 `obj_token`。

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

1. `docs +fetch --scope range`：从「行业新闻周报」标题 grid 到下一节「Peers 季度业绩更新」标题 grid，`--detail with-ids`
2. 读现有 `<figure><source name="…">`：文件名里的周期 **等于** 刚交付的周期 → 已是最新，**不要动**
3. 过时则：
   - `docs +update --command block_delete` 删掉旧 `<figure>`（只删附件块，不要动标题 grid、往期 callout、Peers 节）
   - `docs +media-insert --type file --file-view preview`，锚在「行业新闻周报」标题之后、往期 callout 之前
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
