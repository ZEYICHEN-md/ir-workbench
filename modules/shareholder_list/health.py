"""shareholder-list 健康检查。"""

from __future__ import annotations

import importlib.util

from workbench.paths import Paths


def checks(base: Paths) -> list[dict]:
    rows: list[dict] = []
    engine = importlib.util.find_spec("shareholder_list") is not None
    rows.append(
        {
            "name": "生成引擎",
            "level": "ok" if engine else "fail",
            "detail": "shareholder_list 可导入" if engine else "缺少 shareholder_list；请 pip install -e .",
        }
    )

    try:
        from shareholder_list.discover import PRIOR_TEMPLATE
        from shareholder_list.build import VALID_AS_OF, output_filename
    except Exception as error:  # noqa: BLE001
        rows.append({"name": "引擎常量", "level": "fail", "detail": str(error)})
        return rows

    template_ok = PRIOR_TEMPLATE.is_file()
    rows.append(
        {
            "name": "母版骨架",
            "level": "ok" if template_ok else "fail",
            "detail": PRIOR_TEMPLATE.name if template_ok else f"找不到 {PRIOR_TEMPLATE}",
        }
    )

    market = base.data / "market_caps.json"
    rows.append(
        {
            "name": "市值快照",
            "level": "ok" if market.is_file() else "fail",
            "detail": str(market.relative_to(base.root)) if market.is_file() else "缺少 data/market_caps.json",
        }
    )

    rebuild = base.root / "scripts" / "rebuild.ps1"
    rows.append(
        {
            "name": "一键入口",
            "level": "ok" if rebuild.is_file() else "fail",
            "detail": "scripts/rebuild.ps1" if rebuild.is_file() else "缺少 scripts/rebuild.ps1",
        }
    )

    wording = base.root / "templates" / "Investor List_26Q1_20260518.xlsx"
    rows.append(
        {
            "name": "5 月文案权威",
            "level": "ok" if wording.is_file() else "warn",
            "detail": wording.name if wording.is_file() else "CLI 不读此文件；对照用模板缺失",
        }
    )

    from shareholder_list.discover import default_combined, default_peer

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
            "detail": f"{VALID_AS_OF} → {output_filename()}",
        }
    )
    rows.append(
        {
            "name": "写入边界",
            "level": "ok",
            "detail": "copy-then-write；不手改 output/*.xlsx；不迁飞书",
        }
    )
    return rows
