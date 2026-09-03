"""港股市场内部查询命令，挂在 ``ir hk-market ...`` 下。"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from workbench.fileio import write_text
from workbench.manifest import Manifest
from workbench.result import Result

from . import market, southbound, volume_ratio

DOMAIN = "hk-market"


def _query_date(raw: str | None) -> date:
    if raw is None:
        return date.today()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as error:
        raise ValueError("日期必须是 YYYY-MM-DD") from error


def _json_output(base, period: str, name: str, payload: dict) -> Path:
    target = base.outputs(DOMAIN, period) / f"{name}.json"
    write_text(target, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return target


def _record(base, period: str, step: str, output: Path, note: str) -> None:
    manifest = Manifest(base, DOMAIN, period)
    manifest.set_step(step, "done")
    manifest.record_output(step, output)
    manifest.note(note)


def cmd_market(args, base) -> Result:
    try:
        requested = _query_date(args.as_of)
        payload = market.analyze(requested.isoformat(), with_valuation=args.with_valuation)
    except Exception as error:  # noqa: BLE001 - 外部行情接口失败须显式返回
        return Result(
            status="failed",
            summary=f"港股行情查询失败：{type(error).__name__}: {error}",
            domain=DOMAIN,
        )
    period = payload["as_of"]
    output = _json_output(base, period, "market", payload)
    _record(
        base,
        period,
        "market",
        output,
        "周涨跌 close-to-close；指数 amount 为新浪指数口径，非港股全市场成交额。",
    )
    checks = []
    for name, stats in payload["indices"].items():
        checks.append(
            {
                "name": name,
                "level": "ok" if stats else "warn",
                "detail": (
                    f"周涨跌 {stats['wow_pct']:+.2f}% · 日均成交额 {stats['turnover_avg_yi']} 亿"
                    if stats
                    else "本周或上周数据不足"
                ),
            }
        )
    ctrip = payload.get("ctrip")
    checks.append(
        {
            "name": "携程 09961",
            "level": "ok" if ctrip else "warn",
            "detail": (
                f"周涨跌 {ctrip['wow_pct']:+.2f}% · 本周成交额 {ctrip['turnover_this_yi']} 亿港元"
                if ctrip
                else "本周或上周数据不足"
            ),
        }
    )
    return Result(
        status="success" if all(row["level"] == "ok" for row in checks) else "partial",
        summary=f"港股周度行情已查询（截至 {period}）。",
        domain=DOMAIN,
        period=period,
        checks=checks,
        warnings=[
            "指数成交额是新浪指数日线 amount，不是港股全市场成交额。",
            "yfinance 回退的个股成交额为 Volume×Close 近似值。",
        ],
        data={"output": str(output), **payload},
    )


def cmd_southbound(args, base) -> Result:
    try:
        requested = _query_date(args.as_of)
        payload = southbound.analyze(requested.isoformat())
    except Exception as error:  # noqa: BLE001 - 港交所接口失败须显式返回
        return Result(
            status="failed",
            summary=f"南向持股查询失败：{type(error).__name__}: {error}",
            domain=DOMAIN,
        )
    if payload.get("error"):
        return Result(
            status="failed",
            summary=payload["error"],
            domain=DOMAIN,
            data=payload,
        )
    period = payload["as_of"].replace("/", "-")
    output = _json_output(base, period, "southbound", payload)
    _record(
        base,
        period,
        "southbound",
        output,
        f"来源：港交所 CCASS 沪港通及深港通持股纪录；扫描 {len(payload['trading_days'])} 个实际披露日。",
    )
    checks = []
    for row in payload["stocks"].values():
        checks.append(
            {
                "name": f"{row['name']}（{row['code']:05d}）",
                "level": "warn" if row.get("missing") else "ok",
                "detail": (
                    "数据缺失"
                    if row.get("missing")
                    else f"{row['latest']:.2f}% · 日变动 {row['day_change_pp'] or 0:+.2f}pp"
                    f" · 月内 {row['month_change_pp'] or 0:+.2f}pp"
                ),
            }
        )
    return Result(
        status="partial" if any(row["level"] == "warn" for row in checks) else "success",
        summary=f"南向持股已查询（实际持股日期 {payload['as_of']}）。",
        domain=DOMAIN,
        period=period,
        checks=checks,
        warnings=["节假日请求会回退到最近交易日；结果按实际持股日期去重。"],
        data={"output": str(output), **payload},
    )


def _write_csv(path: Path, frame) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="\n") as handle:
        frame.to_csv(handle, index=False, lineterminator="\n")
    return path


def cmd_volume_ratio(args, base) -> Result:
    try:
        as_of = _query_date(args.as_of)
        default_start, exclusive_end = volume_ratio.default_window(as_of)
        start = args.start or default_start
        stocks = volume_ratio.parse_stocks(args.stocks)
        frame, summaries, failed = volume_ratio.calculate(
            start=start,
            end=exclusive_end,
            usd_hkd=args.usd_hkd,
            threshold=args.threshold,
            stocks=stocks,
        )
    except ValueError as error:
        return Result(status="blocked", summary=str(error), domain=DOMAIN)
    except Exception as error:  # noqa: BLE001 - 外部行情接口失败须显式返回
        return Result(
            status="failed",
            summary=f"港美成交占比查询失败：{type(error).__name__}: {error}",
            domain=DOMAIN,
        )

    period = as_of.isoformat()
    if frame.empty:
        return Result(
            status="failed",
            summary="所有标的均未取得完整的港股与美股成交数据。",
            domain=DOMAIN,
            period=period,
            missing=failed,
        )

    csv_path = _write_csv(base.outputs(DOMAIN, period) / "volume-ratio.csv", frame)
    payload = {
        "as_of": period,
        "start": start,
        "end_exclusive": exclusive_end,
        "usd_hkd": args.usd_hkd,
        "threshold": args.threshold,
        "regulatory_basis": "latest_complete_fiscal_year",
        "trend_windows": ["L12M", "latest_quarter", "latest_month"],
        "summaries": summaries,
        "failed": failed,
    }
    json_path = _json_output(base, period, "volume-ratio", payload)
    _record(
        base,
        period,
        "volume-ratio",
        json_path,
        "监管状态仅按最近完整 FY；L12M、季度、月度只作趋势。美股成交额为近似值。",
    )
    Manifest(base, DOMAIN, period).record_output("volume-ratio-csv", csv_path)
    checks = []
    for name, summary in summaries.items():
        fiscal = "—" if summary["FY"] is None else f"{summary['FY']:.2f}%"
        l12m = "—" if summary["L12M"] is None else f"{summary['L12M']:.2f}%"
        checks.append(
            {
                "name": name,
                "level": "warn" if summary["FY"] is None else "ok",
                "detail": (
                    f"{summary['FY_label']} {fiscal} · "
                    f"{summary['regulatory_status']} · L12M {l12m}"
                ),
            }
        )
    checks.extend(
        {"name": name, "level": "fail", "detail": "港股或美股数据缺失"} for name in failed
    )
    incomplete_fy = [name for name, summary in summaries.items() if summary["FY"] is None]
    return Result(
        status="partial" if failed or incomplete_fy else "success",
        summary=f"港美成交占比完成：成功 {len(summaries)}，失败 {len(failed)}。",
        domain=DOMAIN,
        period=period,
        checks=checks,
        warnings=[
            "55% 监管判断只看最近完整财年 FY；L12M 与季度不能替代。",
            f"美元成交额统一按 1 USD={args.usd_hkd} HKD 换算；美股为 Volume×日内高低价中点近似。",
        ] + (
            ["这些标的缺完整 FY，不能判断监管状态：" + "、".join(incomplete_fy)]
            if incomplete_fy
            else []
        ),
        data={"csv": str(csv_path), "manifest": str(json_path), **payload},
    )


def register(subparsers, common) -> None:
    parser = subparsers.add_parser("hk-market", help="港股行情、南向持股、港美成交占比")
    sub = parser.add_subparsers(dest="hk_market_command", required=True)

    p_market = sub.add_parser("market", help="恒指、恒生科技与携程周度行情", parents=[common])
    p_market.add_argument("--as-of", help="查询日 YYYY-MM-DD；默认今天")
    p_market.add_argument("--with-valuation", action="store_true", help="附 Forward P/E（月度观察）")
    p_market.set_defaults(func=cmd_market)

    p_south = sub.add_parser("southbound", help="港交所 CCASS 南向持股月内扫描", parents=[common])
    p_south.add_argument("--as-of", help="查询日 YYYY-MM-DD；默认今天")
    p_south.set_defaults(func=cmd_southbound)

    p_ratio = sub.add_parser("volume-ratio", help="港美成交额占比与 55%% FY 测试", parents=[common])
    p_ratio.add_argument("--as-of", help="查询日 YYYY-MM-DD；默认今天")
    p_ratio.add_argument("--start", help="查询起日；默认上一完整财年 1 月 1 日")
    p_ratio.add_argument("--usd-hkd", type=float, default=7.78)
    p_ratio.add_argument("--threshold", type=float, default=55.0)
    p_ratio.add_argument("--stocks", help="名,akCode,yfCode,usCode；多只用分号分隔")
    p_ratio.set_defaults(func=cmd_volume_ratio)
