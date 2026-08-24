# industry-data 切换验收 runbook（下周实战）

**目的**：用一次**真实**的周度数据更新，验证 `industry-data` 从 `database_matain` 切到工作台后行为正确。
验收通过后才删旧仓已迁走的部分（`docs/MIGRATION.md` 四步法的第 3、4 步）。

**为什么等真实数据**：人造推送只能验证「同一份数据、新管道产出一致」。真实一周会额外走到
新周次追加、`dataUpdate` 自动盖章、洞察过期标记、飞书新建行——这些人造验证覆盖不到。

---

## 前提

- [ ] 会话里先设一次 UTF-8（PowerShell 默认 GBK 会静默损坏中文参数，ADR 0007）：
      `[Console]::OutputEncoding=[Text.Encoding]::UTF8; $OutputEncoding=[Text.Encoding]::UTF8`
- [ ] 新的 `国内行业数据_MMDD.xlsx` 已放进 `data/workbooks/`
- [ ] 已用 `ir config set industry <路径>` 锁定这一份（**不要按文件名猜**）
- [ ] `ir doctor` 全绿：两个工作簿 ✓，且**底稿结构校验全部通过**
      （工作表名、2026 块、16 个指标列表头、12 个月份行、Q1–Q4、QTD 块）
- [ ] `ir config publish-repo` 已指向发布仓本地副本

> 底稿结构校验若报 fail，**先别跑 merge**——列位挪动会让 `excel.py` 把别的指标当成这个指标
> 读进来，而且不报错。先按提示更新 `layout.py` 与 `excel.py` 的列号。

## 第一步：重建指标快照

```powershell
ir industry merge
```

**预期**：`success`，报「新增 N · 修改 0 · 清空 0」，并列出新时间标签（新的一周）。

核对：

- [ ] **数据截至日 = 新一周的结束日**（周标签 `8/9-8/15` → `2026-08-15`）。这是 `dataUpdate` 自动盖章，不该手改
- [ ] 底稿文件名与你刚锁定的那份一致
- [ ] 「新增」数量大致等于新一周填了几个指标格
- [ ] **「修改」应为 0**。若不为 0，说明历史数值被改动过——先弄清是有意修正还是填错行，不要放过
- [ ] **「清空」应为 0**

### 如果出现清空

会返回 `partial` 并列出将被清空的格，**不写入**。这是设计行为（ADR 0001）：

- 有意撤回 → 让 Agent 带 `--confirm-clears` 重跑
- 不该是空的 → 回底稿补上再重跑

### 如果返回 blocked

说明清空超阈值（> 10 格，或某序列 > 30% 且原有非空 ≥ 5 格），或底稿结构读不出。
**先核对底稿列位没变**：周轴 R、酒店 S/T/U、航空 W/X/Y。别绕过门禁。

## 第二步：生成看板投影

```powershell
ir industry generate-dashboard
```

**预期**：`partial`，并提示洞察已被标为可能过期（因为指标变了但洞察没重新确认）。

核对：

- [ ] `data.js` / `insights.js` / 洞察 Markdown 都已重写
- [ ] **有洞察过期提示**。没有提示反而是问题——说明过期标记没生效

## 第三步：刷新洞察（可选，但这次建议做，为了验证这条链）

```powershell
ir industry insights draft
```

- [ ] 草稿包写进 `scratch/insights-draft-all-<时间戳>.json`
- [ ] AI 按 `promptForAi` 填 `draftZh`
- [ ] **你确认中文**
- [ ] `ir industry insights confirm <草稿包路径>`
- [ ] 确认后过期标记清除，`archive/<新的数据截至日>/` 下出现快照

核对：

- [ ] 洞察只用了该粒度数据，没有跨粒度叙事
- [ ] 每条都有可核对数字和 `refs`
- [ ] 归因事件的时间窗口与指标时段重叠（对不齐就该省略归因）

## 第四步：飞书投影（dry-run 先看）

```powershell
ir industry feishu plan
```

核对：

- [ ] **新建**里应出现新的一周
- [ ] **冲突**（飞书已有值 ≠ 快照）：若不为 0，逐条看清楚，默认不覆盖
- [ ] 未确认时 `ir industry feishu apply` 必须返回 `blocked`

确认后再写入：

```powershell
ir industry feishu apply --yes
```

- [ ] 写入后回飞书多维表核对新一周的行确实建出来了

## 第五步：上线（本次切换的关键验收）

```powershell
ir industry publish
```

**这一步不写入任何东西。**它会复制四文件、算出线上会变什么、逐行摆出 diff，然后把发布仓还原干净。
五道硬检查（源文件齐全、必须 LF、发布仓无无关改动、diff 不是整份重写、无变化不空提交）任一不过就拒发。

**核对 diff**（这是切换验收的核心）：

- [ ] `index.html` / `i18n.js` 应显示**无变化**
- [ ] `data.js` 的变化 = 注释头 + 新一周数据 + 本次切换带来的三处修正：
      `monthly.hotelRevPAR` 7 月 `null → -0.05`、`quarterly.q2` 补 `hotelOccupancy` 与 `hotelADR`
- [ ] `insights.js` 的变化 = 本期确认的新洞察（若跳过第三步，则只有注释头 3 行）
- [ ] 没有任何**意料之外**的数值变化
- [ ] 改动行数是**十几到几十行**级别。若某个文件显示改动数百行，`publish` 会直接拒发
      并报「整份重写」——那是格式问题（换行符/序列化写法），先查清再发

确认无误后：

```powershell
ir industry publish --yes
```

- [ ] 返回 `success`，并给出发布仓的提交号
- [ ] EdgeOne 控制台 → 该项目 → **构建部署**：出现本次 push 触发的成功记录
- [ ] 打开 https://datamax.fun 硬刷新（Ctrl+F5）

**页面核对**：

- [ ] 新一周出现在周度图表里
- [ ] **月度酒店 RevPAR 7 月出现约 -5.0% 的点**（切换前这条线断在 6 月）
- [ ] **季度 Q2 多出入住率 -0.8% 与 ADR +2.9%**（切换前 Q2 只有 RevPAR +2.0%）
- [ ] 洞察区显示本次确认的新洞察
- [ ] 中英切换正常
- [ ] 其他图表、页面结构无异常
- [ ] 办公室（新加坡出口）与手机微信都能打开

## 第六步：验收通过后的收尾

- [ ] 把 `database_matain/CONTEXT.md` 的术语归并进工作台 `docs/GLOSSARY.md`，重复条款改为指向
- [ ] 标注 `database_matain/docs/adr/0002`（canonical 为权威）已被工作台 ADR 0001 取代
- [ ] 标注 `database_matain/docs/adr/0004`（Gitee Pages）已被放弃
- [ ] 删 `database_matain` 里已迁走的部分（`data_source/`、`dashboard/`、指标链 `scripts/`）
      —— 保留 git 历史、`docs/`、`MIGRATED.md`
- [ ] 更新 `docs/MIGRATION.md`：第 1 步全部打勾，进入第 2 步 `aviation-monthly`

## 核对线上必须绕开 CDN 缓存

**这条先看，否则会把「已经生效」误判成「没部署」。**

datamax.fun 走 EdgeOne 边缘节点，`Cache-Control: no-cache` 请求头**不足以**拿到最新内容 ——
边缘会返回自己缓存的副本，响应头里 `age` 是几十到几百秒。实测回退时因此连续 3 分多钟
看到旧内容，误以为部署没生效，实际推送后一分钟内就已经生效。

判断方法：给 URL 加一个随机查询参数（`?nocache=<随机数>`）再请求一次，对比两者。

| 加参数后 | 不加参数 | 结论 |
|---|---|---|
| 新内容（`age: 0`） | 旧内容（`age: N`） | **已生效**，只是边缘缓存未过期 |
| 旧内容 | 旧内容 | 部署确实还没完成，继续等 |

浏览器里对应的动作是硬刷新（Ctrl+F5）。看 `last-modified` 响应头能直接确认源站文件的更新时间。

## 出问题怎么退

**这条路径已于 2026-08-24 实测通过**，不是纸面方案。

1. 发布仓：`git revert HEAD` → push，线上回到上一版（`publish --yes` 成功时的输出里也写了这条）
2. **恢复用 `ir industry publish`，不要手动 git** —— dry-run 会认出线上缺什么并逐行摆出来，
   确认后 `--yes` 推回去。这条才是接手人能走的路（他只会说「重新上线」）
3. 工作台：`data/canonical/travel.json` 在 git 里，可回退
4. 旧仓 `database_matain` 完整保留，必要时可临时解封（**须先撕掉 `MIGRATED.md` 的停用声明，
   并记录为什么退回**，不要悄悄双轨运行）

### 实测记录（2026-08-24）

| 步骤 | 结果 |
|---|---|
| 发布仓 `git revert HEAD` + push | 提交 `43aa291` |
| 线上回到上一版 | `dataUpdate` 回到 `2026-08-08`，新周次消失；推送后约 1 分钟生效 |
| `ir industry publish`（dry-run） | 正确认出线上缺 `data.js` 56 行、`insights.js` 12 行 |
| `ir industry publish --yes` | 提交 `e07a610`，线上恢复 `2026-08-15` |
| 中断窗口 | 约 6 分钟（含中间的缓存误判等待） |

发布仓历史里会留下 revert 与恢复两个提交，这是有意的 —— 事故痕迹可追溯，比强推覆盖干净。

## 已知会变的东西（不是 bug）

| 变化 | 原因 |
|---|---|
| `monthly.hotelRevPAR` 7 月由空变 `-0.05` | 旧 parser 在 `7月 (preliminary)` 处提前终止，漏读；已修（ADR 0001） |
| `quarterly.q2` 多出 `hotelOccupancy` / `hotelADR` | 同上，旧管道漏写 |
| `quarterly` 各季字段顺序 | 全量重建按固定列序归一，一次性变化 |
| `travel.json` 换行符由 CRLF 变 LF | 统一为 LF（ADR 0006）；只在内部仓，不影响发布 |
