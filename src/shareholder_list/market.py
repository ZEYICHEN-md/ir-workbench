"""Refresh Yahoo market caps + USD/HKD into data/market_caps.json."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

USD_TICKERS = {
    "TCOM": "TCOM",
    "BABA": "BABA",
    "NTES": "NTES",
    "PDD": "PDD",
    "JD": "JD",
    "BIDU": "BIDU",
    "ABNB": "ABNB",
    "BKNG": "BKNG",
    "EXPE": "EXPE",
    "MMYT": "MMYT",
    "TRIP": "TRIP",
    "TRVG": "TRVG",
}
HKD_TICKERS = {
    "700_XHKG": "0700.HK",
    "3690_XHKG": "3690.HK",
    "780_XHKG": "0780.HK",
}
FX_SYMBOL = "USDHKD=X"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _session() -> tuple[urllib.request.OpenerDirector, str]:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def get(url: str) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with opener.open(req, timeout=30) as resp:
            return resp.read()

    try:
        get("https://fc.yahoo.com")
    except urllib.error.HTTPError:
        pass
    crumb = get("https://query1.finance.yahoo.com/v1/test/getcrumb").decode("utf-8").strip()
    if not crumb or "<" in crumb:
        raise RuntimeError(f"Yahoo crumb failed: {crumb[:80]!r}")
    return opener, crumb


def _quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    opener, crumb = _session()
    joined = ",".join(symbols)
    url = (
        "https://query1.finance.yahoo.com/v7/finance/quote"
        f"?symbols={joined}&crumb={urllib.request.quote(crumb)}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with opener.open(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    rows = payload.get("quoteResponse", {}).get("result") or []
    out = {row["symbol"]: row for row in rows if "symbol" in row}
    missing = [s for s in symbols if s not in out]
    if missing:
        raise KeyError(f"Yahoo quote missing {missing}")
    return out


def fetch_market() -> dict[str, Any]:
    symbols = list(USD_TICKERS.values()) + list(HKD_TICKERS.values()) + [FX_SYMBOL]
    quotes = _quotes(symbols)
    usd = {key: int(quotes[sym]["marketCap"]) for key, sym in USD_TICKERS.items()}
    hkd = {key: int(quotes[sym]["marketCap"]) for key, sym in HKD_TICKERS.items()}
    fx = float(quotes[FX_SYMBOL]["regularMarketPrice"])
    tcom = quotes["TCOM"]
    so = int(tcom.get("impliedSharesOutstanding") or tcom["sharesOutstanding"])
    return {
        "as_of": date.today().isoformat(),
        "fx_usd_hkd": round(fx, 4),
        "source": "Yahoo Finance v7 quote (crumb), marketCap + impliedSharesOutstanding",
        "tcom_shares_outstanding": so,
        "usd_market_cap": usd,
        "hkd_market_cap": hkd,
    }


def save_market(path: Path, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = payload or fetch_market()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data
