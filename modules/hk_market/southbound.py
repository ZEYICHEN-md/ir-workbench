"""港交所 CCASS 港股通持股查询。"""

from __future__ import annotations

import time
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

URL = "https://www3.hkexnews.hk/sdw/search/mutualmarket_c.aspx?t=hk"
WATCHLIST = {
    9961: "携程集团",
    780: "同程旅行",
    1179: "华住集团",
    3690: "美团",
    9988: "阿里巴巴",
    700: "腾讯",
    9618: "京东",
    1024: "快手",
    9999: "网易",
    9888: "百度",
    1810: "小米集团",
    9626: "哔哩哔哩",
}
THRESHOLDS = [10.0]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TIMEOUT = 30
RETRIES = 3


def _request(call):
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            return call()
        except Exception as error:  # noqa: BLE001 - 网络错误统一重试
            last = error
            time.sleep(1.2 * (attempt + 1))
    assert last is not None
    raise last


def _hidden(soup: BeautifulSoup) -> dict[str, str]:
    return {
        item["name"]: item.get("value", "")
        for item in soup.find_all("input", {"type": "hidden"})
        if item.get("name")
    }


def _parse(soup: BeautifulSoup) -> tuple[str | None, dict[int, dict]]:
    date_input = soup.find(id="txtShareholdingDate")
    actual_date = date_input.get("value") if date_input else None
    rows: dict[int, dict] = {}
    table = soup.find(id="mutualmarket-result")
    if not table:
        return actual_date, rows

    def body(cell) -> str:
        mobile = cell.find(class_="mobile-list-body")
        return (mobile or cell).get_text(strip=True)

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        try:
            code = int(body(cells[0]))
        except ValueError:
            continue
        try:
            percentage = float(body(cells[3]).replace("%", "").replace(",", "").strip())
        except ValueError:
            percentage = None
        rows[code] = {
            "name": body(cells[1]),
            "shares": body(cells[2]),
            "pct": percentage,
        }
    return actual_date, rows


class CCASS:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        response = _request(lambda: self.session.get(URL, timeout=TIMEOUT))
        response.raise_for_status()
        self.hidden = _hidden(BeautifulSoup(response.text, "html.parser"))
        self.today = self.hidden.get("today", "")

    def query(self, date_text: str) -> tuple[str | None, dict[int, dict]]:
        form = dict(self.hidden)
        form.update(
            {
                "__EVENTTARGET": "btnSearch",
                "__EVENTARGUMENT": "",
                "txtShareholdingDate": date_text,
                "sortBy": "stockcode",
                "sortDirection": "asc",
            }
        )
        response = _request(lambda: self.session.post(URL, data=form, timeout=TIMEOUT))
        response.raise_for_status()
        return _parse(BeautifulSoup(response.text, "html.parser"))

    def latest(self) -> tuple[str | None, dict[int, dict]]:
        requested = (
            f"{self.today[:4]}/{self.today[4:6]}/{self.today[6:]}"
            if len(self.today) == 8
            else date.today().strftime("%Y/%m/%d")
        )
        return self.query(requested)


def _date_from_text(value: str) -> date:
    year, month, day = map(int, value.replace("-", "/").split("/"))
    return date(year, month, day)


def scan_month(as_of: str | None = None, *, client: CCASS | None = None):
    source = client or CCASS()
    if as_of:
        actual, _ = source.query(_date_from_text(as_of).strftime("%Y/%m/%d"))
    else:
        actual, _ = source.latest()
    if not actual:
        raise RuntimeError("港交所没有返回实际持股日期")
    actual_day = _date_from_text(actual)

    series: dict[str, dict[int, dict]] = {}
    cursor = date(actual_day.year, actual_day.month, 1)
    while cursor <= actual_day:
        if cursor.weekday() < 5:
            disclosed, rows = source.query(cursor.strftime("%Y/%m/%d"))
            if disclosed and rows and disclosed[:7] == actual_day.strftime("%Y/%m"):
                series[disclosed] = rows
        cursor += timedelta(days=1)
    return actual_day, sorted(series), series


def analyze(as_of: str | None = None, *, client: CCASS | None = None) -> dict:
    _actual_day, dates, series = scan_month(as_of, client=client)
    if not dates:
        return {"error": "本月没有可用持股数据", "source_url": URL}
    latest_date = dates[-1]
    previous_date = dates[-2] if len(dates) >= 2 else None
    first_date = dates[0]
    result = {
        "as_of": latest_date,
        "prev": previous_date,
        "month_start": first_date,
        "trading_days": dates,
        "source_url": URL,
        "stocks": {},
    }
    for code, name in WATCHLIST.items():
        observations = [
            (day, series[day].get(code, {}).get("pct"))
            for day in dates
            if series[day].get(code, {}).get("pct") is not None
        ]
        if not observations:
            result["stocks"][str(code)] = {"name": name, "code": code, "missing": True}
            continue
        latest = series[latest_date].get(code, {}).get("pct")
        previous = series[previous_date].get(code, {}).get("pct") if previous_date else None
        start = series[first_date].get(code, {}).get("pct")
        high_date, high = max(observations, key=lambda item: item[1])
        low_date, low = min(observations, key=lambda item: item[1])
        alerts = []
        for threshold in THRESHOLDS:
            if latest is not None and latest < threshold:
                alerts.append(f"低于{threshold:g}%")
            if latest is not None and previous is not None and (previous - threshold) * (latest - threshold) < 0:
                alerts.append(f"{'跌破' if latest < threshold else '升破'}{threshold:g}%")
        result["stocks"][str(code)] = {
            "name": name,
            "code": code,
            "latest": latest,
            "prev": previous,
            "day_change_pp": None if previous is None or latest is None else round(latest - previous, 2),
            "month_start_pct": start,
            "month_change_pp": None if start is None or latest is None else round(latest - start, 2),
            "month_high": high,
            "month_high_date": high_date,
            "month_low": low,
            "month_low_date": low_date,
            "alerts": alerts,
        }
    return result
