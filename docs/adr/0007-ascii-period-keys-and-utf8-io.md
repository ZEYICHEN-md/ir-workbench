# ADR 0007 — 周期键一律 ASCII；CLI 输出强制 UTF-8

- 状态：**Accepted**（2026-08-22）
- 日期：2026-08-22

## 背景

接上状态机后，第一次真实调用就暴露两个 Windows 编码缺陷，**而且都是静默的**。

### 缺陷 1：输出被捕获时 CLI 直接崩

```
UnicodeEncodeError: 'gbk' codec can't encode character '\u2713'
```

Windows 上 stdout 被重定向或管道捕获时，Python 退回控制台代码页（中文机器是 GBK），
输出里的 `✓` 直接抛异常。**而 Agent 捕获命令输出是常态**——也就是说这条路径平时就在踩。

### 缺陷 2：中文命令行参数被静默损坏

实测：

| 调用方式 | `sys.argv[1]` |
|---|---|
| `py -c "..." 上线验证`（输出到终端） | `'上线验证'` ✅ |
| `$out = py -c "..." 上线验证`（捕获输出） | `'涓婄嚎楠岃瘉'` ❌ |
| 先设 `$OutputEncoding=UTF8` 再捕获 | `'上线验证'` ✅ |

根因：PowerShell 用 `$OutputEncoding`（默认为 ANSI/GBK）编码传给原生命令的参数。
捕获输出时走的路径会用到它。**不报错，只是数据坏掉。**

这个 bug 已经实际发生过一次：`ir industry mark publish skipped --note "..."` 写进
manifest 的备注是乱码 `涓婄嚎楠岃瘉...`。

### 为什么这件事很严重

原设计（ADR 0003 §3）里 `news-digest` 与 `competitor-intel` 的周期键是 **`2026年8月第2周`**。
周期键既是命令行参数，又是目录名。一次编码事故就会造出
`runs/news-digest/2026骞?鏈?../` 这种目录——**难发现、难清理，而且下次调用会当成另一期。**

## 决策

### 1. 周期键一律 ASCII

| 域 | 旧键 | 新键 |
|---|---|---|
| `news-digest` | `2026年8月第2周` | **`2026-08-W2`** |
| `competitor-intel`（周度） | 同上 | **`2026-08-W2`** |

其余域本来就是 ASCII（`2026-08-08` / `202607` / `26Q2`），不动。

给人看的中文标签由 `Domain.label(period)` 生成：`2026-08-W2` → `2026年8月第2周`。
**标签用于汇报与交付文件名，永不用作键或目录名。**

交付物文件名保持中文（`旅行行业新闻精选-2026年8月第2周.md`）——文件名由程序拼接，
不经过 argv，没有这个风险。

### 2. CLI 输出强制 UTF-8

`workbench/cli.py` 在入口 `reconfigure(encoding="utf-8", errors="replace")`。
无论输出去终端还是被捕获，都不再因编码崩溃。

### 3. doctor 检查并给出修法

检测调用方编码；不是 UTF-8 时提醒，并给出一行修复命令。同时写进 `AGENTS.md`，
让 Agent 在会话开始就设好：

```powershell
[Console]::OutputEncoding=[Text.Encoding]::UTF8; $OutputEncoding=[Text.Encoding]::UTF8
```

## 为什么不靠「在 Python 里修复乱码」

理论上可以试 `arg.encode('gbk').decode('utf-8')` 把乱码救回来。不采用，因为：

- 无法可靠区分「本来就是这些字」和「乱码」，会引入新的静默错误；
- 修复的是症状。**真正的解法是不让关键标识符经过这条脆弱路径**——这也是选 ASCII 键的理由。

## 后果

**好的：**
- 周期键在 argv、目录名、URL、跨平台环境下都安全。
- 机器键与人类标签分离，本身就是更清楚的设计（此前是一个值兼两职）。
- CLI 输出不再因被捕获而崩。

**要接受的：**
- 多一个概念：键 vs 标签。落在 `workbench/domains.py` 一处，靠 `Domain.label()` 转换。
- 中文备注类参数仍依赖调用方编码正确。已由 doctor 检查 + `AGENTS.md` 提示覆盖，
  但**这不是硬保障**——如果将来发现备注还在被损坏，就改成 `--note-file` 传文件。

## 相关

- 修订 ADR 0003 §3（周期键定义）
- `workbench/domains.py`（`PERIOD_PATTERNS` / `period_label`）、`workbench/cli.py`、`workbench/doctor.py`
