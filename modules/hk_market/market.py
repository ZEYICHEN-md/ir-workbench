"""恒指、恒生科技与携程港股周度行情。"""

from __future__ import annotations

import time

import pandas as pd

YI = 1e8


def _retry(call, *, tries: int = 4, sleep: float = 2.5, label: str = ""):
    last: Exception | None = None
    for attempt in range(tries):
        try:
            return call()
        except Exception as error:  # noqa: BLE001 - 外部行情源统一重试
            last = error
            time.sleep(sleep * (attempt + 1))
    raise RuntimeError(f"{label} 连续 {tries} 次失败：{last}")


def _iso(value) -> tuple[int, int]:
    calendar = value.isocalendar()
    return int(calendar[0]), int(calendar[1])


def fetch_index(symbol: str) -> pd.DataFrame:
    import akshare as ak

    frame = _retry(
        lambda: ak.stock_hk_index_daily_sina(symbol=symbol),
        label=f"指数 {symbol}（新浪）",
    )
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.sort_values("date").reset_index(drop=True)


def fetch_ctrip(start: str, end: str) -> tuple[pd.DataFrame, str]:
    import akshare as ak

    try:
        frame = _retry(
            lambda: ak.stock_hk_daily(symbol="09961", adjust=""),
            tries=3,
            label="携程 09961（新浪）",
        )
        frame = frame[["date", "close", "amount"]].copy()
        frame["date"] = pd.to_datetime(frame["date"])
        return frame.sort_values("date").reset_index(drop=True), "akshare-新浪（成交额）"
    except Exception:
        pass
    try:
        # 调用方给的是 yfinance 使用的半开区间；东财 end_date 为闭区间。
        inclusive_end = (
            pd.to_datetime(end) - pd.Timedelta(days=1)
        ).strftime("%Y%m%d")
        frame = _retry(
            lambda: ak.stock_hk_hist(
                symbol="09961",
                period="daily",
                start_date=start,
                end_date=inclusive_end,
                adjust="",
            ),
            tries=2,
            label="携程 09961（东财）",
        )
        frame = frame.rename(columns={"日期": "date", "收盘": "close", "成交额": "amount"})
        frame["date"] = pd.to_datetime(frame["date"])
        return frame.sort_values("date").reset_index(drop=True), "akshare-东财（成交额）"
    except Exception:
        pass

    import yfinance as yf

    history = yf.download(
        "9961.HK",
        start=pd.to_datetime(start).strftime("%Y-%m-%d"),
        end=pd.to_datetime(end).strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=False,
    )
    close = history["Close"]
    volume = history["Volume"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    if hasattr(volume, "columns"):
        volume = volume.iloc[:, 0]
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(close.index),
            "close": close.values,
            "amount": close.values * volume.values,
        }
    )
    return frame.reset_index(drop=True), "yfinance（Volume×Close 近似成交额）"


def week_stats(
    frame: pd.DataFrame,
    as_of: str,
    *,
    close_col: str = "close",
    amount_col: str = "amount",
) -> dict | None:
    day = pd.to_datetime(as_of)
    this_week = _iso(day)
    previous_week = _iso(day - pd.Timedelta(days=7))
    data = frame.copy()
    data["isoyw"] = data["date"].apply(_iso)
    current = data[data["isoyw"] == this_week]
    previous = data[data["isoyw"] == previous_week]
    if current.empty or previous.empty:
        return None
    current_close = float(current[close_col].iloc[-1])
    previous_close = float(previous[close_col].iloc[-1])
    current_amount = float(current[amount_col].sum())
    previous_amount = float(previous[amount_col].sum())
    return {
        "this_week_days": [value.strftime("%Y-%m-%d") for value in current["date"]],
        "prev_week_last": previous["date"].iloc[-1].strftime("%Y-%m-%d"),
        "close_this": round(current_close, 2),
        "close_prev": round(previous_close, 2),
        "wow_pct": round((current_close / previous_close - 1) * 100, 2),
        "turnover_this_yi": round(current_amount / YI, 1),
        "turnover_prev_yi": round(previous_amount / YI, 1),
        "turnover_avg_yi": round(current_amount / len(current) / YI, 1),
        "turnover_wow_pct": (
            round((current_amount / previous_amount - 1) * 100, 1)
            if previous_amount
            else None
        ),
    }


def fetch_valuation() -> dict[str, float | None]:
    import yfinance as yf

    peers = {"携程": "9961.HK", "Booking": "BKNG", "同程": "0780.HK"}
    values: dict[str, float | None] = {}
    for name, ticker in peers.items():
        try:
            value = yf.Ticker(ticker).info.get("forwardPE")
            values[name] = round(float(value), 1) if value else None
        except Exception:
            values[name] = None
    return values


def analyze(as_of: str | None = None, *, with_valuation: bool = False) -> dict:
    hsi = fetch_index("HSI")
    hstech = fetch_index("HSTECH")
    query_date = as_of or hsi["date"].max().strftime("%Y-%m-%d")
    start = (pd.to_datetime(query_date) - pd.Timedelta(days=20)).strftime("%Y%m%d")
    end = (pd.to_datetime(query_date) + pd.Timedelta(days=1)).strftime("%Y%m%d")
    ctrip, ctrip_source = fetch_ctrip(start, end)
    result = {
        "as_of": query_date,
        "indices": {
            "恒生指数 HSI": week_stats(hsi, query_date),
            "恒生科技 HSTECH": week_stats(hstech, query_date),
        },
        "ctrip": week_stats(ctrip, query_date),
        "ctrip_source": ctrip_source,
        "index_source": "akshare 新浪指数日线 amount（指数成分股成交额，非全市场成交额）",
    }
    if with_valuation:
        result["valuation_fwd_pe"] = fetch_valuation()
        result["valuation_basis"] = "yfinance forwardPE；仅作月度观察"
    return result
