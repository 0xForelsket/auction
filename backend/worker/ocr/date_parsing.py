from __future__ import annotations

import re
from datetime import date


def parse_reiwa_year(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"R?(\d{1,2})", text)
    if not m:
        return None
    return int(m.group(1)) + 2018


def parse_reiwa_year_month(text: str | None) -> date | None:
    if not text:
        return None
    m = re.search(r"R?(\d{1,2})[年/.-](\d{1,2})", text)
    if not m:
        return None
    year = int(m.group(1)) + 2018
    month = int(m.group(2))
    return date(year, month, 1)


def parse_auction_date(text: str | None) -> date | None:
    if not text:
        return None
    m = re.search(r"(\d{2,4})[./-](\d{1,2})[./-](\d{1,2})", text)
    if not m:
        return None
    year = int(m.group(1))
    if year < 100:
        year += 2000
    month = int(m.group(2))
    day = int(m.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None
