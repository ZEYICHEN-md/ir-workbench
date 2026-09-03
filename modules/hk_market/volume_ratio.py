"""港美两地成交额占比。

监管状态只看最近完整财年；L12M、季度和月度只用于观察趋势。
迁自 ``0703_Travel_Pulse/hk-volume-ratio``，去掉独立 CLI，由
``ir hk-market volume-ratio`` 统一编排。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

DEFAULT_STOCKS = [
    ("携程", "09961", "9961.HK", "TCOM"),
    ("华住", "01179", "1179.HK", "HTHT"),
    ("网易", "09999", "9999.HK", "NTES"),
    ("百度", "09888", "9888.HK", "BIDU"),
]
MIGRATION_THRESHOLD = 55.0


def default_window(as_of: date | None = None) -> tuple[str, str]:
    """返回覆盖最近完整财年与本年至今的半开区间。"""
    end_day = as_of or date.today()
    start = date(end_day.year - 1, 1, 1)
    return start.isoformat(), (end_day + timedelta(days=1)).isoformat()


def parse_stocks(raw: str | None) -> list[tuple[str, str, str, str]]:
    if not raw:
        return list(DEFAULT_STOCKS)
    parsed: list[tuple[str, str, str, str]] = []
    for item in raw.split(";"):
        parts = tuple(part.strip() for part in item.split(","))
        if len(parts) != 4 or not all(parts):
            raise ValueError(f"股票配置格式错误：{item!r}（应为 名,akCode,yfCode,usCode）")
        parsed.append(parts)  # type: ignore[arg-type]
    names = [item[0] for item in parsed]
    if len(names) != len(set(names)):
        raise ValueError("股票名称不能重复")
    return parsed


def validate_options(
    start: str,
    end: str,
    usd_hkd: float,
    threshold: float,
    stocks: list[tuple[str, str, str, str]],
) -> None:
    try:
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("start/end 必须是 YYYY-MM-DD") from exc
    if start_date >= end_date:
        raise ValueError("start 必须早于 end")
    if usd_hkd <= 0:
        raise ValueError("usd-hkd 必须大于 0")
    if not 0 < threshold <= 100:
        raise ValueError("threshold 必须在 (0, 100] 范围")
    if not stocks:
        raise ValueError("股票池不能为空")


def get_hk_turnover_akshare(code: str, start: str, end: str) -> pd.DataFrame:
    try:
        import akshare as ak

        # 本模块的 end 是半开区间；akshare 的 end_date 是闭区间。
        inclusive_end = (
            datetime.strptime(end, "%Y-%m-%d").date() - timedelta(days=1)
        ).strftime("%Y%m%d")
        frame = ak.stock_hk_hist(
            symbol=code,
            period="daily",
            start_date=start.replace("-", ""),
            end_date=inclusive_end,
            adjust="",
        )
        if frame is not None and not frame.empty:
            frame["日期"] = pd.to_datetime(frame["日期"])
            return pd.DataFrame({"Turnover_HKD": frame.set_index("日期")["成交额"]})
    except Exception:
        pass
    return pd.DataFrame()


def get_hk_turnover_yfinance(code: str, start: str, end: str) -> pd.DataFrame:
    try:
        import yfinance as yf

        history = yf.Ticker(code).history(start=start, end=end)
        if history.empty:
            return pd.DataFrame()
        history.index = history.index.tz_localize(None).normalize()
        return pd.DataFrame({"Turnover_HKD": history["Volume"] * history["Close"]})
    except Exception:
        return pd.DataFrame()


def get_us_turnover(code: str, start: str, end: str) -> pd.DataFrame:
    try:
        import yfinance as yf

        history = yf.Ticker(code).history(start=start, end=end)
        if history.empty:
            return pd.DataFrame()
        history.index = history.index.tz_localize(None).normalize()
        midpoint = (history["High"] + history["Low"]) / 2
        return pd.DataFrame({"Turnover_USD": history["Volume"] * midpoint})
    except Exception:
        return pd.DataFrame()


def aggregate_monthly(frame: pd.DataFrame, value_col: str) -> pd.Series:
    data = frame.copy()
    data["YearMonth"] = data.index.to_period("M")
    return data.groupby("YearMonth")[value_col].sum()


def _recent_full_year(monthly: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    years = sorted({period.year for period in monthly.index})
    if not years:
        return monthly.iloc[0:0], "FY"
    full = [year for year in years if sum(period.year == year for period in monthly.index) == 12]
    if full:
        selected = full[-1]
        subset = monthly.loc[[period for period in monthly.index if period.year == selected]]
        return subset, f"{str(selected)[2:]}FY"
    # 监管测试不能拿缺月的年份冒充完整 FY。仍返回候选标签，便于说明缺的是哪年。
    prior = [year for year in years if year < monthly.index[-1].year]
    selected = prior[-1] if prior else years[-1]
    return monthly.iloc[0:0], f"{str(selected)[2:]}FY（数据不完整）"


def summarize(monthly: pd.DataFrame) -> dict:
    def ratio(frame: pd.DataFrame) -> float | None:
        if frame.empty:
            return None
        denominator = float(frame["Global_Turnover_HKD"].sum())
        return None if denominator == 0 else float(frame["HK_Turnover_HKD"].sum()) / denominator * 100

    fiscal, label = _recent_full_year(monthly)
    return {
        "FY_label": label,
        "FY": ratio(fiscal),
        "L12M": ratio(monthly.iloc[-12:]),
        "latest_quarter": ratio(monthly.iloc[-3:]),
        "latest_month": float(monthly["HK_Ratio"].iloc[-1]),
        "latest_period": str(monthly.index[-1]),
    }


def threshold_flag(value: float | None, threshold: float) -> str:
    if value is None:
        return "数据缺失"
    gap = threshold - value
    if value >= threshold:
        return f"已达/超过阈值（+{value - threshold:.2f}pp）"
    if gap <= 5:
        return f"接近阈值（距 {gap:.2f}pp）"
    return f"距阈值 {gap:.2f}pp"


def regulatory_status(summary: dict, threshold: float = MIGRATION_THRESHOLD) -> str:
    """港交所 55% 测试只读最近完整财年。"""
    return threshold_flag(summary.get("FY"), threshold)


def calculate_stock(
    stock: tuple[str, str, str, str],
    start: str,
    end: str,
    usd_hkd: float,
    threshold: float,
) -> tuple[pd.DataFrame, dict] | None:
    name, hk_code_ak, hk_code_yf, us_code = stock
    hk_data = get_hk_turnover_akshare(hk_code_ak, start, end)
    hk_source = "akshare（港交所口径）"
    if hk_data.empty:
        hk_data = get_hk_turnover_yfinance(hk_code_yf, start, end)
        hk_source = "yfinance（Volume×Close 近似）"
    us_data = get_us_turnover(us_code, start, end)
    if hk_data.empty or us_data.empty:
        return None

    monthly = pd.DataFrame(
        {
            "HK_Turnover_HKD": aggregate_monthly(hk_data, "Turnover_HKD"),
            "US_Turnover_USD": aggregate_monthly(us_data, "Turnover_USD"),
        }
    ).dropna()
    if monthly.empty:
        return None
    monthly["US_Turnover_HKD"] = monthly["US_Turnover_USD"] * usd_hkd
    monthly["Global_Turnover_HKD"] = monthly["HK_Turnover_HKD"] + monthly["US_Turnover_HKD"]
    monthly["HK_Ratio"] = monthly["HK_Turnover_HKD"] / monthly["Global_Turnover_HKD"] * 100
    monthly["公司"] = name
    summary = summarize(monthly)
    summary.update(
        {
            "regulatory_status": regulatory_status(summary, threshold),
            "hk_source": hk_source,
            "us_source": "yfinance（Volume×日内高低价中点，近似 VWAP）",
        }
    )
    return monthly, summary


def calculate(
    *,
    start: str,
    end: str,
    usd_hkd: float,
    threshold: float,
    stocks: list[tuple[str, str, str, str]],
) -> tuple[pd.DataFrame, dict[str, dict], list[str]]:
    validate_options(start, end, usd_hkd, threshold, stocks)
    frames: list[pd.DataFrame] = []
    summaries: dict[str, dict] = {}
    failed: list[str] = []
    for stock in stocks:
        outcome = calculate_stock(stock, start, end, usd_hkd, threshold)
        if outcome is None:
            failed.append(stock[0])
            continue
        frame, summary = outcome
        frames.append(frame)
        summaries[stock[0]] = summary
    if not frames:
        return pd.DataFrame(), summaries, failed
    combined = pd.concat(frames)
    combined.index.name = "月份"
    return combined.reset_index(), summaries, failed
