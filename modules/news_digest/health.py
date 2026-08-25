"""news-digest 的健康检查，供 `ir doctor` 调用。

这个域的失效方式和别的域不同：它靠外部 RSS 与几个 Python 包，而**这些东西坏掉的时候
不会有人立刻发现**——直到某个周二要发稿。所以检查在这里，而不是等召回的时候报错。

刻意**不在 doctor 里发网络请求**：doctor 要能离线跑，也不该每次自检都去敲两个外站。
源可达性由 `ir news recall` 自己报（单源失败不阻断整期）。
"""

from __future__ import annotations

import importlib.util

from workbench.paths import Paths

from . import ledger

#: 召回与导出各自的依赖。分开报，因为缺哪一半的后果不同：
#: 缺 requests 连候选都拿不到；缺 markdown/playwright 只是出不了 HTML/PDF（可后补）。
RECALL_DEPS = {"requests": "抓 RSS"}
EXPORT_DEPS = {"markdown": "Markdown → HTML"}


def checks(base: Paths) -> list[dict]:
    rows: list[dict] = []

    missing = [f"{name}（{why}）" for name, why in RECALL_DEPS.items()
               if importlib.util.find_spec(name) is None]
    rows.append(
        {
            "name": "召回依赖",
            "level": "fail" if missing else "ok",
            "detail": "缺：" + "、".join(missing) if missing else "齐全",
            **({"advice": "对 Agent 说「安装工作台依赖」。"} if missing else {}),
        }
    )

    missing = [f"{name}（{why}）" for name, why in EXPORT_DEPS.items()
               if importlib.util.find_spec(name) is None]
    rows.append(
        {
            "name": "导出依赖",
            "level": "warn" if missing else "ok",
            "detail": "缺：" + "、".join(missing) if missing else "齐全",
            **({"advice": "只影响导出 HTML/PDF，写稿与沉淀不受影响。"} if missing else {}),
        }
    )

    # PDF 需要 playwright 的 chromium，装包不等于装浏览器 —— 这一步最容易漏
    if importlib.util.find_spec("playwright") is None:
        rows.append(
            {
                "name": "PDF 导出",
                "level": "warn",
                "detail": "没有 playwright，只能出 HTML",
                "advice": "要 PDF 就装 playwright 并跑一次 `playwright install chromium`；"
                "装包不等于装浏览器。",
            }
        )
    else:
        rows.append({"name": "PDF 导出", "level": "ok", "detail": "playwright 可用"})

    # 台账是跨期去重的唯一持久状态
    try:
        rows_in_ledger = ledger.load(base)
    except ledger.LedgerError as error:
        return rows + [
            {
                "name": "去重台账",
                "level": "fail",
                "detail": str(error),
                "advice": "上面写了是第几行，去 modules/news_digest/news-log.jsonl 修那一行。",
            }
        ]

    periods = ledger.periods(base)
    rows.append(
        {
            "name": "去重台账",
            "level": "ok" if rows_in_ledger else "warn",
            "detail": f"{len(rows_in_ledger)} 条，覆盖 {len(periods)} 期"
            if rows_in_ledger
            else "还是空的（跨期去重会失效）",
        }
    )
    return rows
