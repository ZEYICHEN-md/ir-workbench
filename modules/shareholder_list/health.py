"""shareholder-list 健康检查。"""

from __future__ import annotations

from .build import VALID_AS_OF, output_filename, period_key
from .discover import MARKET_CAPS, PRIOR_DIR, PRIOR_TEMPLATE, default_combined, default_peer


def checks(base) -> list[dict]:
    rows: list[dict] = []
    template_ok = PRIOR_TEMPLATE.is_file()
    rows.append(
        {
            "name": "母版骨架",
            "level": "ok" if template_ok else "fail",
            "detail": str(PRIOR_TEMPLATE.relative_to(base.root)) if template_ok else f"找不到 {PRIOR_TEMPLATE}",
        }
    )

    wording = PRIOR_DIR / "Investor List_26Q1_20260518.xlsx"
    rows.append(
        {
            "name": "5 月文案权威",
            "level": "ok" if wording.is_file() else "warn",
            "detail": wording.name if wording.is_file() else "CLI 不读此文件；对照用模板缺失",
        }
    )

    market_ok = MARKET_CAPS.is_file()
    rows.append(
        {
            "name": "市值快照",
            "level": "ok" if market_ok else "fail",
            "detail": str(MARKET_CAPS.relative_to(base.root)) if market_ok else "缺少 market_caps.json",
        }
    )

    peer = default_peer()
    combined = default_combined()
    rows.append(
        {
            "name": "Downloads 底表",
            "level": "ok" if peer and combined else "warn",
            "detail": (
                f"Peer={peer.name if peer else '无'}；Combined={combined.name if combined else '无'}"
            ),
        }
    )
    rows.append(
        {
            "name": "本期有效日",
            "level": "ok",
            "detail": f"{VALID_AS_OF} → {period_key()} / {output_filename()}",
        }
    )
    rows.append(
        {
            "name": "写入边界",
            "level": "ok",
            "detail": "copy-then-write；只写 outputs/shareholder-list/；不迁飞书",
        }
    )
    return rows
