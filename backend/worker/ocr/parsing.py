from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import median
from typing import Iterable

from worker.ocr.date_parsing import parse_auction_date, parse_reiwa_year, parse_reiwa_year_month
from worker.ocr.image_utils import OCRToken


@dataclass
class ParsedField:
    value: str | int | float | None
    confidence: float
    bbox: tuple[int, int, int, int] | None
    raw: str | None = None


LABEL_MAP = {
    "auction_date": [r"開催日"],
    "auction_venue": [r"会場"],
    "auction_venue_round": [r"開催回"],
    "lot_no": [r"出品番号"],
    "make_model": [r"車種名", r"車種名/グレード"],
    "grade": [r"グレード"],
    "model_year": [r"年式"],
    "shift_engine": [r"シフト/排気量"],
    "mileage": [r"走行"],
    "inspection": [r"車検"],
    "color": [r"色"],
    "model_code": [r"型式"],
    "result": [r"セリ結果"],
    "starting_bid": [r"応札額", r"スタート金額", r"スタート"],
    "final_bid": [r"落札"],
    "bid_start": [r"応札額", r"スタート金額"],
    "score": [r"評価点"],
}

EQUIPMENT_CODES = {"AAC", "ナビ", "SR", "AW", "革", "PS", "PW", "DR"}


def normalize_text(text: str) -> str:
    return (
        text.replace(" ", "")
        .replace("　", "")
        .replace("：", ":")
        .replace("／", "/")
        .replace("ー", "-")
    )


def group_tokens_by_row(tokens: Iterable[OCRToken]) -> list[list[OCRToken]]:
    tokens_list = list(tokens)
    if not tokens_list:
        return []
    heights = [abs(t.bbox[3] - t.bbox[1]) for t in tokens_list]
    row_height = median(heights) if heights else 10
    threshold = max(6, row_height * 0.6)

    tokens_sorted = sorted(tokens_list, key=lambda t: (t.bbox[1], t.bbox[0]))
    rows: list[list[OCRToken]] = []
    for token in tokens_sorted:
        cy = (token.bbox[1] + token.bbox[3]) / 2
        placed = False
        for row in rows:
            row_cy = sum((t.bbox[1] + t.bbox[3]) / 2 for t in row) / len(row)
            if abs(cy - row_cy) <= threshold:
                row.append(token)
                placed = True
                break
        if not placed:
            rows.append([token])
    return rows


def find_value_for_label(tokens: list[OCRToken], patterns: list[str]) -> ParsedField | None:
    rows = group_tokens_by_row(tokens)
    for row in rows:
        row_sorted = sorted(row, key=lambda t: t.bbox[0])
        for idx, token in enumerate(row_sorted):
            text_norm = normalize_text(token.text)
            if any(re.search(pat, text_norm) for pat in patterns):
                # Try inline value
                value = re.sub("|".join(patterns), "", text_norm)
                value = value.strip(":/ ")
                if value:
                    return ParsedField(value=value, confidence=token.confidence, bbox=token.bbox, raw=token.text)
                # Else pick nearest token to the right
                for candidate in row_sorted[idx + 1 :]:
                    if candidate.bbox[0] > token.bbox[0]:
                        return ParsedField(
                            value=candidate.text,
                            confidence=candidate.confidence,
                            bbox=candidate.bbox,
                            raw=candidate.text,
                        )
    return None


def parse_price_pair(text: str | None) -> tuple[int | None, int | None]:
    if not text:
        return None, None
    cleaned = normalize_text(text)
    numbers = re.findall(r"\d+(?:,\d{3})*", cleaned)
    if not numbers:
        return None, None
    values = [int(num.replace(",", "")) for num in numbers]
    if len(values) == 1:
        final = values[0]
        start = None
    else:
        final, start = values[0], values[1]

    if final is not None and final < 100000:
        final *= 10000
    if start is not None and start < 100000:
        start *= 10000
    return final, start


def parse_yen(text: str | None) -> int | None:
    if not text:
        return None
    cleaned = normalize_text(text)
    numbers = re.findall(r"\d+(?:,\d{3})*", cleaned)
    if not numbers:
        return None
    value = int(numbers[0].replace(",", ""))
    if value < 100000:
        value *= 10000
    return value


def parse_mileage(text: str | None) -> tuple[int | None, int | None, str | None]:
    if not text:
        return None, None, None
    cleaned = normalize_text(text)
    numbers = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", cleaned)
    if not numbers:
        return None, None, text
    raw = numbers[0]
    value = float(raw.replace(",", ""))
    multiplier = 1
    if value < 1000:
        multiplier = 1000
    mileage_km = int(value * multiplier)
    return mileage_km, multiplier, raw


def parse_mileage_header(text: str | None) -> tuple[int | None, int | None, float | None, str | None]:
    if not text:
        return None, None, 0.0, None
    cleaned = normalize_text(text)
    digits = re.sub(r"\D", "", cleaned)
    if not digits:
        return None, None, 0.0, text
    if "," in cleaned or len(digits) >= 4:
        return int(digits), 1, 0.95, text
    try:
        value = int(digits)
    except ValueError:
        return None, None, 0.0, text
    if 0 <= value <= 300:
        return value * 1000, 1000, 0.7, text
    return value, 1, 0.3, text


def parse_score(text: str | None) -> tuple[str | None, float | None]:
    if not text:
        return None, None
    cleaned = normalize_text(text)
    if "RA" in cleaned.upper():
        return "RA", None
    if "R" in cleaned.upper():
        return "R", None
    match = re.search(r"\d(?:\.\d)?", cleaned)
    if not match:
        return cleaned, None
    score_str = match.group(0)
    try:
        return score_str, float(score_str)
    except ValueError:
        return score_str, None


def parse_shift_engine(text: str | None) -> tuple[str | None, int | None]:
    if not text:
        return None, None
    cleaned = normalize_text(text)
    trans_match = re.search(r"(AT|FA|CA|CVT)", cleaned, re.IGNORECASE)
    trans = trans_match.group(1).upper() if trans_match else None
    engine_match = re.search(r"(\d{3,4})", cleaned)
    engine = int(engine_match.group(1)) if engine_match else None
    return trans, engine


def parse_equipment(text: str | None) -> str | None:
    if not text:
        return None
    found = [code for code in EQUIPMENT_CODES if code in text]
    return " ".join(found) if found else None


def parse_header(tokens: list[OCRToken]) -> dict[str, ParsedField]:
    results: dict[str, ParsedField] = {}
    for key, patterns in LABEL_MAP.items():
        field = find_value_for_label(tokens, patterns)
        if field:
            results[key] = field

    return results


def parse_header_cells(cells: dict[str, str]) -> dict[str, ParsedField]:
    results: dict[str, ParsedField] = {}
    for label, value in cells.items():
        label_norm = normalize_text(label)
        for key, patterns in LABEL_MAP.items():
            if any(re.search(pat, label_norm) for pat in patterns):
                if key not in results:
                    results[key] = ParsedField(value=value, confidence=0.97, bbox=None, raw=value)
    return results


def parse_sheet(tokens: list[OCRToken]) -> dict[str, ParsedField]:
    results: dict[str, ParsedField] = {}

    for token in tokens:
        text_norm = normalize_text(token.text)
        if "車台" in text_norm and token.text:
            results["chassis"] = ParsedField(token.text, token.confidence, token.bbox, raw=token.text)
            break

    if "chassis" not in results:
        for token in tokens:
            if re.match(r"[A-HJ-NPR-Z0-9]{8,17}", token.text or ""):
                results["chassis"] = ParsedField(token.text, token.confidence, token.bbox, raw=token.text)
                break

    for token in tokens:
        text_norm = normalize_text(token.text)
        if "km" in text_norm.lower() or "ｋｍ" in text_norm.lower():
            results["mileage"] = ParsedField(token.text, token.confidence, token.bbox, raw=token.text)
            break

    notes = [token.text for token in tokens if "注意" in token.text or "検査" in token.text]
    if notes:
        joined = " / ".join(notes)
        results["notes"] = ParsedField(joined, 0.5, None, raw=joined)

    return results


def build_record_fields(header: dict[str, ParsedField], sheet: dict[str, ParsedField]) -> dict:
    data: dict[str, object] = {}

    auction_date = parse_auction_date(_value(header, "auction_date"))
    data["auction_date"] = auction_date
    venue_raw = _value(header, "auction_venue")
    if venue_raw:
        match = re.search(r"(.+?)(\d+回)", venue_raw)
        if match:
            data["auction_venue"] = match.group(1).strip()
            data["auction_venue_round"] = match.group(2)
        else:
            data["auction_venue"] = venue_raw
    else:
        data["auction_venue"] = None
    venue_round = _value(header, "auction_venue_round")
    if venue_round:
        data["auction_venue_round"] = venue_round

    lot_raw = _value(header, "lot_no")
    data["lot_no"] = lot_raw

    lot_guess, venue_guess, round_guess = _parse_lot_venue_round(
        lot_raw or venue_raw or venue_round
    )
    if lot_guess and (not lot_raw or not lot_raw.strip().isdigit()):
        data["lot_no"] = lot_guess
    if venue_guess:
        current_venue = data.get("auction_venue")
        if not current_venue or any(ch.isdigit() for ch in str(current_venue)):
            data["auction_venue"] = venue_guess
    if round_guess:
        current_round = data.get("auction_venue_round")
        if not current_round or not _is_clean_round(current_round):
            data["auction_venue_round"] = round_guess

    make_model = _value(header, "make_model")
    data["make_model"] = make_model
    data["grade"] = _value(header, "grade")

    model_year_text = _value(header, "model_year")
    data["model_year_reiwa"] = model_year_text
    data["model_year_gregorian"] = parse_reiwa_year(model_year_text)

    inspection_raw = _value(header, "inspection")
    data["inspection_expiry_raw"] = inspection_raw
    data["inspection_expiry_month"] = parse_reiwa_year_month(inspection_raw)

    transmission, engine_cc = parse_shift_engine(_value(header, "shift_engine"))
    data["transmission"] = transmission
    data["engine_cc"] = engine_cc

    mileage_text = _value(header, "mileage")
    mileage_km, multiplier, mileage_conf, mileage_raw = parse_mileage_header(mileage_text)
    if mileage_km is None and "mileage" in sheet:
        mileage_km, multiplier, mileage_raw = parse_mileage(str(sheet["mileage"].value))
        mileage_conf = None
    data["mileage_km"] = mileage_km
    data["mileage_multiplier"] = multiplier
    data["mileage_raw"] = mileage_raw
    data["mileage_inference_conf"] = mileage_conf

    score_text = _value(header, "score")
    score, score_numeric = parse_score(score_text)
    data["score"] = score
    data["score_numeric"] = score_numeric

    data["color"] = _value(header, "color")
    data["model_code"] = _value(header, "model_code")

    result_text = _value(header, "result")
    if result_text and "落札" in result_text:
        data["result"] = "sold"
    elif result_text and "流札" in result_text:
        data["result"] = "unsold"
    else:
        data["result"] = result_text

    final_bid = parse_yen(_value(header, "final_bid"))
    starting_bid = parse_yen(_value(header, "starting_bid"))
    if final_bid is None or starting_bid is None:
        final_pair, start_pair = parse_price_pair(_value(header, "bid_start"))
        if final_bid is None:
            final_bid = final_pair
        if starting_bid is None:
            starting_bid = start_pair
    data["final_bid_yen"] = final_bid
    data["starting_bid_yen"] = starting_bid

    data["equipment_codes"] = parse_equipment(_value(header, "make_model"))

    if "chassis" in sheet:
        data["chassis_no"] = sheet["chassis"].value
    if "notes" in sheet:
        data["notes_text"] = sheet["notes"].value

    return data


def merge_fields(
    primary: dict[str, ParsedField], secondary: dict[str, ParsedField]
) -> dict[str, ParsedField]:
    merged: dict[str, ParsedField] = {}
    keys = set(primary.keys()) | set(secondary.keys())
    for key in keys:
        first = primary.get(key)
        second = secondary.get(key)
        if first and second:
            merged[key] = ParsedField(
                value=first.value or second.value,
                confidence=max(first.confidence, second.confidence),
                bbox=second.bbox if _values_match(first.value, second.value) else first.bbox or second.bbox,
                raw=first.raw or second.raw,
            )
        elif first:
            merged[key] = first
        elif second:
            merged[key] = second
    return merged


def _values_match(left: str | int | float | None, right: str | int | float | None) -> bool:
    if left is None or right is None:
        return False
    left_str = normalize_text(str(left))
    right_str = normalize_text(str(right))
    if not left_str or not right_str:
        return False
    return left_str in right_str or right_str in left_str


def _value(fields: dict[str, ParsedField], key: str) -> str | None:
    field = fields.get(key)
    return field.value if field else None


def _parse_lot_venue_round(
    text: str | None,
) -> tuple[str | None, str | None, str | None]:
    if not text:
        return None, None, None
    cleaned = normalize_text(text)
    match = re.match(r"(?P<lot>\d{3,8})?(?P<venue>[^\d]+)?(?P<round>\d+回)?", cleaned)
    if not match:
        return None, None, None
    lot = match.group("lot")
    venue = match.group("venue") or None
    round_val = match.group("round")
    if venue:
        venue = venue.replace("会場", "").replace("開催回", "").strip() or None
    return lot, venue, round_val


def _is_clean_round(value: object) -> bool:
    text = normalize_text(str(value))
    return bool(re.fullmatch(r"\d+回", text))
