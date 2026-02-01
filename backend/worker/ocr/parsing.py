from __future__ import annotations

import re
import unicodedata
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
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", text)
    return (
        text.replace(" ", "")
        .replace("　", "")
        .replace("：", ":")
        .replace("／", "/")
        .replace("ー", "-")
        .replace("‐", "-")
        .replace("－", "-")
        .replace("−", "-")
        .replace("，", ",")
        .replace("．", ".")
    )


def normalize_alnum(text: str) -> str:
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.upper().replace(" ", "").replace("　", "")
    return re.sub(r"[^0-9A-Z]", "", text)


def normalize_digits(text: str) -> str:
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", text)
    trans = str.maketrans(
        {"O": "0", "o": "0", "I": "1", "l": "1", "|": "1", "!": "1", "S": "5", "B": "8"}
    )
    text = text.translate(trans)
    return re.sub(r"\D", "", text)


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
        digits = normalize_digits(cleaned)
        if not digits:
            return None
        value = int(digits)
        if value < 100000:
            value *= 10000
        return value
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
        digits = normalize_digits(cleaned)
        if not digits:
            return None, None, text
        numbers = [digits]
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
    digits = normalize_digits(cleaned)
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
    normalized = normalize_text(text)
    found = [code for code in EQUIPMENT_CODES if code in normalized]
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
        value_norm = normalize_text(value) if value else ""

        # Handle compound labels with "/" separator
        parsed = _parse_compound_cell(label_norm, value_norm, value)
        for key, field in parsed.items():
            if key not in results:
                results[key] = field

        # Fall back to simple label matching for non-compound labels
        if not parsed:
            for key, patterns in LABEL_MAP.items():
                if any(re.search(pat, label_norm) for pat in patterns):
                    if key not in results:
                        results[key] = ParsedField(value=value, confidence=0.97, bbox=None, raw=value)
    return results


def parse_header_tokens_vl(tokens: list[OCRToken]) -> dict[str, ParsedField]:
    """Parse header tokens from VL OCR that combine 'label value' in single tokens."""
    results: dict[str, ParsedField] = {}

    for token in tokens:
        text = token.text or ""
        text_norm = normalize_text(text)

        # Try to extract known label-value pairs from combined token text
        extracted = _extract_from_combined_token(text_norm, text, token.bbox)
        for key, field in extracted.items():
            if key not in results:
                results[key] = field

    # Also try pattern-based extraction on all token text combined
    all_text = " ".join([t.text or "" for t in tokens])
    pattern_results = _extract_header_by_patterns(all_text)
    for key, field in pattern_results.items():
        if key not in results:
            results[key] = field

    return results


def _extract_header_by_patterns(text: str) -> dict[str, ParsedField]:
    """Extract header values by pattern matching on combined text."""
    results: dict[str, ParsedField] = {}
    text_norm = normalize_text(text)

    # Date pattern (e.g., "24/10/18" or "2024-10-18")
    if "auction_date" not in results:
        date_match = re.search(r"\b(\d{2,4}[/.-]\d{1,2}[/.-]\d{1,2})\b", text_norm)
        if date_match:
            results["auction_date"] = ParsedField(
                value=date_match.group(1), confidence=0.7, bbox=None, raw=date_match.group(0)
            )

    # Venue pattern (major auction venues)
    if "auction_venue" not in results:
        venues = ["東京", "名古屋", "大阪", "福岡", "札幌", "仙台", "広島"]
        for venue in venues:
            if venue in text:
                results["auction_venue"] = ParsedField(
                    value=venue, confidence=0.8, bbox=None, raw=venue
                )
                break

    # Round pattern (e.g., "2057回" or "1488回")
    if "auction_venue_round" not in results:
        round_match = re.search(r"(\d{3,4})回", text_norm)
        if round_match:
            results["auction_venue_round"] = ParsedField(
                value=round_match.group(0), confidence=0.8, bbox=None, raw=round_match.group(0)
            )

    # Lot number pattern (5-digit number, usually near 出品番号)
    if "lot_no" not in results:
        lot_match = re.search(r"(?:出品番号|No\.?)\s*[:\s]*(\d{4,6})", text_norm)
        if lot_match:
            results["lot_no"] = ParsedField(
                value=lot_match.group(1), confidence=0.8, bbox=None, raw=lot_match.group(0)
            )
        else:
            # Look for standalone 5-digit number that's NOT a round number
            lot_standalone = re.findall(r"\b(\d{4,6})\b", text_norm)
            for lot_candidate in lot_standalone:
                # Skip if it's part of a round pattern (ends with 回)
                if f"{lot_candidate}回" in text_norm:
                    continue
                # Skip if it's a date
                if "/" in text_norm and lot_candidate in text_norm.split("/"):
                    continue
                results["lot_no"] = ParsedField(
                    value=lot_candidate, confidence=0.6, bbox=None, raw=lot_candidate
                )
                break

    # Year pattern (e.g., "R05", "R03", "令和5年")
    # Must NOT be followed by 回 (that's the round pattern)
    if "model_year" not in results:
        year_match = re.search(r"\bR\s*(\d{1,2})(?!回|\d)", text_norm)
        if year_match:
            year_val = year_match.group(1)
            # Year should be reasonable (1-10 for Reiwa, started 2019)
            if year_val.isdigit() and 1 <= int(year_val) <= 10:
                results["model_year"] = ParsedField(
                    value=f"R{year_val.zfill(2)}",
                    confidence=0.8, bbox=None, raw=year_match.group(0)
                )

    # Transmission pattern (AT, FA, CA, CVT, MT)
    if "shift_engine" not in results:
        trans_match = re.search(r"\b(AT|FA|CA|CVT|MT)\b", text_norm, re.IGNORECASE)
        if trans_match:
            # Also try to find engine CC nearby
            engine_match = re.search(r"(\d{3,4})\s*(?:cc)?", text_norm, re.IGNORECASE)
            engine_val = engine_match.group(1) if engine_match else ""
            combined = f"{trans_match.group(1).upper()} {engine_val}".strip()
            results["shift_engine"] = ParsedField(
                value=combined, confidence=0.7, bbox=None, raw=combined
            )

    # Score pattern (e.g., "4.5", "5", "R", "RA")
    if "score" not in results:
        # First check for R or RA (problem cars)
        ra_match = re.search(r"\b(RA?)\b(?!\d)", text_norm)
        if ra_match and "評価" in text_norm:
            results["score"] = ParsedField(
                value=ra_match.group(1), confidence=0.7, bbox=None, raw=ra_match.group(0)
            )
        else:
            # Numeric score
            score_match = re.search(r"\b([1-5](?:\.[05])?)\b", text_norm)
            if score_match:
                results["score"] = ParsedField(
                    value=score_match.group(1), confidence=0.6, bbox=None, raw=score_match.group(0)
                )

    # Result pattern (落札 = sold, 流札 = unsold)
    if "result" not in results:
        if "落札" in text:
            results["result"] = ParsedField(
                value="落札", confidence=0.9, bbox=None, raw="落札"
            )
        elif "流札" in text:
            results["result"] = ParsedField(
                value="流札", confidence=0.9, bbox=None, raw="流札"
            )

    # Bid pattern (e.g., "3,040万円" or "30400000")
    if "final_bid" not in results:
        # Look for 万円 format first
        man_match = re.search(r"(\d{1,4}(?:,\d{3})*)万", text_norm)
        if man_match:
            results["final_bid"] = ParsedField(
                value=man_match.group(1).replace(",", ""),
                confidence=0.7, bbox=None, raw=man_match.group(0)
            )
        else:
            # Look for raw large numbers (likely in yen)
            large_num = re.search(r"(\d{7,9})", text_norm)
            if large_num:
                results["final_bid"] = ParsedField(
                    value=large_num.group(1), confidence=0.5, bbox=None, raw=large_num.group(0)
                )

    # Color pattern (common colors in Japanese)
    if "color" not in results:
        colors = ["パール", "ホワイト", "ブラック", "クロ", "グレー", "シルバー", "レッド", "ブルー", "ゴールド", "ベージュ", "ブラウン"]
        for color in colors:
            if color in text:
                results["color"] = ParsedField(
                    value=color, confidence=0.8, bbox=None, raw=color
                )
                break

    # Mileage pattern (digits + km or ㎞)
    if "mileage" not in results:
        mileage_match = re.search(r"(\d{2,6})(?:,\d{3})*\s*(?:km|㎞|ｋｍ)", text_norm, re.IGNORECASE)
        if mileage_match:
            results["mileage"] = ParsedField(
                value=mileage_match.group(1), confidence=0.7, bbox=None, raw=mileage_match.group(0)
            )

    # Inspection expiry pattern (e.g., "R08.03", "R07.12")
    if "inspection" not in results:
        insp_match = re.search(r"R\s*(\d{1,2})[./](\d{1,2})", text_norm)
        if insp_match:
            results["inspection"] = ParsedField(
                value=f"R{insp_match.group(1).zfill(2)}.{insp_match.group(2).zfill(2)}",
                confidence=0.7, bbox=None, raw=insp_match.group(0)
            )

    # Model code pattern (alphanumeric, e.g., "MXUA80", "VJA300W", "ZN8")
    if "model_code" not in results:
        model_patterns = [
            r"\b([A-Z]{2,4}\d{1,3}[A-Z]?)\b",  # e.g., MXUA80, VJA300W
            r"\b(\d{5,6}[A-Z])\b",  # e.g., 118347M
            r"\b([A-Z]\d[A-Z]{2})\b",  # e.g., J1NE
        ]
        for pattern in model_patterns:
            match = re.search(pattern, text_norm)
            if match:
                model_code = match.group(1)
                # Skip if it looks like a chassis number (too long)
                if len(model_code) <= 10:
                    results["model_code"] = ParsedField(
                        value=model_code, confidence=0.6, bbox=None, raw=match.group(0)
                    )
                    break

    return results


def _extract_from_combined_token(
    text_norm: str, raw_text: str, bbox: tuple[int, int, int, int] | None
) -> dict[str, ParsedField]:
    """Extract field values from a token that contains 'label value' combined."""
    results: dict[str, ParsedField] = {}

    # 開催日 + date pattern (e.g., "開催日 24/10/18")
    date_match = re.search(r"開催日\s*[:\s]*(\d{2,4}[/.-]\d{1,2}[/.-]\d{1,2})", text_norm)
    if date_match:
        results["auction_date"] = ParsedField(
            value=date_match.group(1), confidence=0.9, bbox=bbox, raw=raw_text
        )

    # Also look for standalone date pattern if it starts with a date
    if "開催日" not in text_norm:
        standalone_date = re.match(r"^(\d{2,4}[/.-]\d{1,2}[/.-]\d{1,2})\b", text_norm)
        if standalone_date:
            results["auction_date"] = ParsedField(
                value=standalone_date.group(1), confidence=0.7, bbox=bbox, raw=raw_text
            )

    # 出品番号 + number (e.g., "出品番号 35408")
    lot_match = re.search(r"出品番号\s*[:\s]*(\d{3,8})", text_norm)
    if lot_match:
        results["lot_no"] = ParsedField(
            value=lot_match.group(1), confidence=0.9, bbox=bbox, raw=raw_text
        )

    # Look for standalone 5-digit lot number at start of token
    if "lot_no" not in results and "出品番号" not in text_norm:
        lot_standalone = re.match(r"^(\d{4,6})\b", text_norm)
        if lot_standalone:
            results["lot_no"] = ParsedField(
                value=lot_standalone.group(1), confidence=0.6, bbox=bbox, raw=raw_text
            )

    # 会場 + venue name (Japanese chars)
    venue_match = re.search(r"会場\s*[:\s]*([\u4E00-\u9FFF]+)", text_norm)
    if venue_match:
        results["auction_venue"] = ParsedField(
            value=venue_match.group(1), confidence=0.9, bbox=bbox, raw=raw_text
        )

    # 開催回 + round number
    round_match = re.search(r"開催回?\s*[:\s]*(\d+回?)", text_norm)
    if round_match:
        round_val = round_match.group(1)
        if not round_val.endswith("回"):
            round_val += "回"
        results["auction_venue_round"] = ParsedField(
            value=round_val, confidence=0.9, bbox=bbox, raw=raw_text
        )

    # 年式 + Reiwa year (R## or just digits)
    year_match = re.search(r"年式\s*[:\s]*(R?\d{1,2})", text_norm)
    if year_match:
        year_val = year_match.group(1)
        if not year_val.startswith("R"):
            year_val = "R" + year_val
        results["model_year"] = ParsedField(
            value=year_val, confidence=0.9, bbox=bbox, raw=raw_text
        )

    # 車種名/グレード - extract make/model and grade
    if "車種名" in text_norm or "グレード" in text_norm:
        # Remove the labels and get the value
        value = re.sub(r"車種名|グレード|/", " ", text_norm).strip()
        if value:
            make_model, grade = _split_make_model_grade(value)
            if make_model:
                results["make_model"] = ParsedField(
                    value=make_model, confidence=0.85, bbox=bbox, raw=raw_text
                )
            if grade:
                results["grade"] = ParsedField(
                    value=grade, confidence=0.85, bbox=bbox, raw=raw_text
                )

    # シフト/排気量 - extract transmission and engine cc
    if "シフト" in text_norm or "排気量" in text_norm or "ミッション" in text_norm:
        value = re.sub(r"シフト|排気量|ミッション|/", " ", text_norm).strip()
        if value:
            trans, engine = _split_shift_engine(value)
            if trans or engine:
                engine_str = str(engine) if engine else ""
                results["shift_engine"] = ParsedField(
                    value=f"{trans or ''} {engine_str}".strip(),
                    confidence=0.85, bbox=bbox, raw=raw_text
                )

    # 走行/車検 - extract mileage and inspection
    if "走行" in text_norm:
        # Remove labels
        value = re.sub(r"走行|車検|/|距離|km|㎞", " ", text_norm, flags=re.IGNORECASE).strip()
        if value:
            mileage, inspection = _split_mileage_inspection(value)
            if mileage:
                results["mileage"] = ParsedField(
                    value=mileage, confidence=0.85, bbox=bbox, raw=raw_text
                )
            if inspection:
                results["inspection"] = ParsedField(
                    value=inspection, confidence=0.85, bbox=bbox, raw=raw_text
                )

    # 色 - color
    if "色" in text_norm and len(text_norm) > 1:
        # Remove the label
        value = re.sub(r"色|カラー", " ", text_norm).strip()
        # Color values are typically short Japanese words
        color_match = re.search(
            r"(パール|ホワイト|ブラック|クロ|グレー|シルバー|レッド|ブルー|ゴールド|ベージュ)",
            value, re.IGNORECASE
        )
        if color_match:
            results["color"] = ParsedField(
                value=color_match.group(1), confidence=0.85, bbox=bbox, raw=raw_text
            )
        elif value and not any(x in value for x in ["型式", "装備", "エアコン"]):
            # Use the first word as color if it's not another label
            first_word = value.split()[0] if value.split() else value
            if first_word and len(first_word) <= 8:
                results["color"] = ParsedField(
                    value=first_word, confidence=0.7, bbox=bbox, raw=raw_text
                )

    # 型式 - model code
    if "型式" in text_norm:
        # Remove labels
        value = re.sub(r"型式|エアコン|装備|/", " ", text_norm).strip()
        if value:
            model_code, _ = _split_model_equipment(value)
            if model_code:
                results["model_code"] = ParsedField(
                    value=model_code, confidence=0.85, bbox=bbox, raw=raw_text
                )

    # セリ結果 - auction result
    if "セリ結果" in text_norm or "結果" in text_norm:
        if "落札" in text_norm:
            results["result"] = ParsedField(
                value="落札", confidence=0.9, bbox=bbox, raw=raw_text
            )
        elif "流札" in text_norm:
            results["result"] = ParsedField(
                value="流札", confidence=0.9, bbox=bbox, raw=raw_text
            )

    # 応札額/スタート金額 - bids
    if ("応札" in text_norm or "スタート" in text_norm) and "金額" in text_norm:
        value = re.sub(r"応札額?|スタート金額|/|万円|円", " ", text_norm).strip()
        numbers = re.findall(r"\d[\d,]*", value)
        if numbers:
            if len(numbers) >= 2:
                results["final_bid"] = ParsedField(
                    value=numbers[0], confidence=0.85, bbox=bbox, raw=raw_text
                )
                results["starting_bid"] = ParsedField(
                    value=numbers[1], confidence=0.85, bbox=bbox, raw=raw_text
                )
            elif len(numbers) == 1:
                results["final_bid"] = ParsedField(
                    value=numbers[0], confidence=0.7, bbox=bbox, raw=raw_text
                )

    # 評価点 - score
    if "評価" in text_norm or "点" in text_norm:
        value = re.sub(r"評価点?|瑕疵", " ", text_norm).strip()
        score = _extract_score_value(value)
        if score:
            results["score"] = ParsedField(
                value=score, confidence=0.85, bbox=bbox, raw=raw_text
            )

    return results


def _parse_compound_cell(label: str, value_norm: str, raw_value: str) -> dict[str, ParsedField]:
    """Parse cells with compound labels like '車種名/グレード' or '走行/車検'."""
    results: dict[str, ParsedField] = {}

    # 車種名/グレード → make_model + grade
    if "車種名" in label and "グレード" in label:
        make_model, grade = _split_make_model_grade(value_norm)
        if make_model:
            results["make_model"] = ParsedField(value=make_model, confidence=0.95, bbox=None, raw=raw_value)
        if grade:
            results["grade"] = ParsedField(value=grade, confidence=0.95, bbox=None, raw=raw_value)
        return results

    # 車種名 alone (without グレード) - full value is make_model
    if "車種名" in label and "グレード" not in label:
        results["make_model"] = ParsedField(value=raw_value, confidence=0.97, bbox=None, raw=raw_value)
        return results

    # グレード alone
    if "グレード" in label and "車種名" not in label:
        results["grade"] = ParsedField(value=raw_value, confidence=0.97, bbox=None, raw=raw_value)
        return results

    # シフト/排気量 → transmission + engine_cc
    if ("シフト" in label or "ミッション" in label) and "排気量" in label:
        trans, engine = _split_shift_engine(value_norm)
        if trans:
            results["shift_engine"] = ParsedField(value=f"{trans} {engine or ''}", confidence=0.95, bbox=None, raw=raw_value)
        return results

    # 走行/車検 → mileage + inspection
    if "走行" in label and "車検" in label:
        mileage, inspection = _split_mileage_inspection(value_norm)
        if mileage:
            results["mileage"] = ParsedField(value=mileage, confidence=0.95, bbox=None, raw=raw_value)
        if inspection:
            results["inspection"] = ParsedField(value=inspection, confidence=0.95, bbox=None, raw=raw_value)
        return results

    # 走行 alone
    if "走行" in label and "車検" not in label:
        results["mileage"] = ParsedField(value=raw_value, confidence=0.97, bbox=None, raw=raw_value)
        return results

    # 車検 alone
    if "車検" in label and "走行" not in label:
        results["inspection"] = ParsedField(value=raw_value, confidence=0.97, bbox=None, raw=raw_value)
        return results

    # 型式/エアコン/装備 or 型式 → model_code (+ equipment_codes)
    if "型式" in label:
        model_code, equipment = _split_model_equipment(value_norm)
        if model_code:
            results["model_code"] = ParsedField(value=model_code, confidence=0.95, bbox=None, raw=raw_value)
        return results

    # 応札額/スタート金額 → final_bid + starting_bid
    if ("応札" in label or "落札" in label) and "スタート" in label:
        final_bid, start_bid = _split_bids(value_norm)
        if final_bid:
            results["final_bid"] = ParsedField(value=final_bid, confidence=0.95, bbox=None, raw=raw_value)
        if start_bid:
            results["starting_bid"] = ParsedField(value=start_bid, confidence=0.95, bbox=None, raw=raw_value)
        return results

    # 応札額 or 落札 alone
    if "落札" in label or "応札額" in label:
        results["final_bid"] = ParsedField(value=raw_value, confidence=0.97, bbox=None, raw=raw_value)
        return results

    # スタート金額 alone
    if "スタート" in label:
        results["starting_bid"] = ParsedField(value=raw_value, confidence=0.97, bbox=None, raw=raw_value)
        return results

    # セリ結果 (auction result)
    if "セリ結果" in label or "結果" in label:
        results["result"] = ParsedField(value=raw_value, confidence=0.97, bbox=None, raw=raw_value)
        return results

    # 評価点 (score)
    if "評価" in label or "点" in label:
        score = _extract_score_value(value_norm)
        if score:
            results["score"] = ParsedField(value=score, confidence=0.95, bbox=None, raw=raw_value)
        return results

    # 色 (color)
    if "色" in label:
        results["color"] = ParsedField(value=raw_value, confidence=0.97, bbox=None, raw=raw_value)
        return results

    return results


def _split_make_model_grade(value: str) -> tuple[str | None, str | None]:
    """Split combined make_model and grade value.

    Japanese auction format typically has:
    - Make/Model as first part (e.g., 'MB CLAクラス', 'ポル タイカン')
    - Grade as remainder (e.g., 'CLA250 4M AMGライン', 'GTS 4+1シート')
    """
    if not value:
        return None, None

    # Try to find a natural split point - grades often start with alphanumeric codes
    # or version indicators like digits, letters, or specific keywords
    value = value.strip()

    # Common grade patterns: alphanumeric code at start of grade
    # e.g., "CLA250", "RZ", "GTS", "NX250", etc.
    patterns = [
        # Grade starts with a model variant code (letters + numbers)
        r"^(.+?)\s+([A-Z]{1,3}\d{2,4}[A-Z]?\s*.*)$",
        # Grade starts with a short code like "RZ", "GTS", "G", "S"
        r"^(.+?)\s+([A-Z]{1,3}(?:\s+.*)?)$",
        # Grade with specific keywords
        r"^(.+?)\s+(バージョン.*)$",
        r"^(.+?)\s+(Fスポーツ.*)$",
        r"^(.+?)\s+(Mスポ.*)$",
        r"^(.+?)\s+(AMG.*)$",
        r"^(.+?)\s+(レザー.*)$",
        r"^(.+?)\s+(Cパッケージ.*)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, value, re.IGNORECASE)
        if match:
            make_model = match.group(1).strip()
            grade = match.group(2).strip()
            # Validate: make_model should contain Japanese chars or known make names
            if re.search(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]|MB|BMW|ポル|GR", make_model):
                return make_model, grade

    # If no pattern matched, try splitting on common delimiters
    # Look for space followed by uppercase letter or digit
    parts = re.split(r"\s+", value, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()

    # No split found, return full value as make_model
    return value, None


def _split_shift_engine(value: str) -> tuple[str | None, int | None]:
    """Split shift/transmission and engine cc from combined value."""
    if not value:
        return None, None

    # Find transmission type
    trans_match = re.search(r"(AT|FA|CA|CVT|MT)", value, re.IGNORECASE)
    trans = trans_match.group(1).upper() if trans_match else None

    # Find engine displacement - typically 3-4 digit number
    # EV cars may have "EV" instead
    if "EV" in value.upper():
        return trans, None

    engine_match = re.search(r"(\d{3,4})", value)
    engine = int(engine_match.group(1)) if engine_match else None

    return trans, engine


def _split_mileage_inspection(value: str) -> tuple[str | None, str | None]:
    """Split mileage and inspection date from combined value."""
    if not value:
        return None, None

    # Mileage is typically a number (possibly with commas)
    # Inspection is typically a date like "R08.03" or "R07.12"
    mileage = None
    inspection = None

    # Look for mileage: digits possibly with commas
    mileage_match = re.search(r"(\d[\d,]*)", value)
    if mileage_match:
        mileage = mileage_match.group(1)

    # Look for inspection: R + year + period + month
    insp_match = re.search(r"R\d{1,2}[./年]\d{1,2}", value)
    if insp_match:
        inspection = insp_match.group(0)
    else:
        # Try other date formats like "令和8年3月" or just digits after mileage
        insp_match2 = re.search(r"(?:令和)?(\d{1,2})[./年](\d{1,2})", value)
        if insp_match2:
            inspection = f"R{insp_match2.group(1)}.{insp_match2.group(2).zfill(2)}"

    return mileage, inspection


def _split_model_equipment(value: str) -> tuple[str | None, str | None]:
    """Split model code from equipment codes.

    Model codes are typically alphanumeric (e.g., '118347M', 'AAZA20', 'VJA300W')
    Equipment codes are keywords like 'AAC', 'ナビ', 'SR', etc.
    """
    if not value:
        return None, None

    # Model code is typically at the start - alphanumeric pattern
    model_match = re.match(r"^([A-Z0-9]{3,12})", value, re.IGNORECASE)
    if model_match:
        model_code = model_match.group(1)
        remainder = value[len(model_code):].strip()
        equipment = remainder if remainder else None
        return model_code, equipment

    # If no clear alphanumeric prefix, look for model code pattern anywhere
    model_patterns = [
        r"(\d{5,6}[A-Z])",  # Like 118347M
        r"([A-Z]{2,4}\d{2,3}[A-Z]?)",  # Like AAZA20, VJA300W
        r"([A-Z]{1,2}\d[A-Z]{1,2})",  # Like J1NE
    ]

    for pattern in model_patterns:
        match = re.search(pattern, value)
        if match:
            return match.group(1), None

    return None, None


def _split_bids(value: str) -> tuple[str | None, str | None]:
    """Split final bid and starting bid from combined value."""
    if not value:
        return None, None

    # Find all numbers in the value (could be with commas or in 万円 format)
    numbers = re.findall(r"(\d[\d,]*)", value)

    if not numbers:
        return None, None

    if len(numbers) == 1:
        return numbers[0], None

    # First number is typically final bid, second is starting bid
    return numbers[0], numbers[1]


def _extract_score_value(value: str) -> str | None:
    """Extract evaluation score from value, handling OCR errors."""
    if not value:
        return None

    # Common OCR confusions for score values
    value_cleaned = value.strip()

    # Handle "RA" or "R" scores (problem cars)
    if re.search(r"R\s*A", value_cleaned, re.IGNORECASE):
        return "RA"
    if re.match(r"R$", value_cleaned, re.IGNORECASE):
        return "R"

    # Look for numeric score (0-5, possibly with .5)
    score_match = re.search(r"(\d(?:\.\d)?)", value_cleaned)
    if score_match:
        return score_match.group(1)

    # Handle common OCR errors
    # "联説" etc. might be OCR errors for numbers
    ocr_fixes = {
        "联": "4",
        "說": "5",
        "联説": "4.5",
    }
    for error, fix in ocr_fixes.items():
        if error in value_cleaned:
            return fix

    return value_cleaned


def parse_sheet(tokens: list[OCRToken]) -> dict[str, ParsedField]:
    results: dict[str, ParsedField] = {}
    if not tokens:
        return results

    rows = group_tokens_by_row(tokens)
    row_entries: list[dict[str, object]] = []
    for row in rows:
        row_sorted = sorted(row, key=lambda t: t.bbox[0])
        row_text = " ".join([t.text for t in row_sorted if t.text])
        row_entries.append(
            {
                "tokens": row_sorted,
                "text": row_text,
                "norm": normalize_text(row_text),
                "bbox": _row_bbox(row_sorted),
            }
        )

    full_text = "\n".join([entry["text"] for entry in row_entries if entry["text"]])

    # Try multiple strategies to find chassis number
    chassis_field = _find_labeled_value(
        row_entries,
        [r"車台", r"車体", r"車台No", r"車台番号", r"車両No", r"車体番号"],
        value_regex=r"[A-HJ-NPR-Z0-9=-]{8,20}",
    )
    if not chassis_field:
        chassis_field = _find_regex_field(
            full_text, r"(?:車台|車体)[:\s]*([A-HJ-NPR-Z0-9=-]{8,20})"
        )
    if not chassis_field:
        # Use improved pattern matching for various chassis formats
        chassis_candidates = _find_chassis_patterns(full_text)
        if chassis_candidates:
            # Pick the longest candidate as it's likely the most complete
            best_candidate = max(chassis_candidates, key=len)
            chassis_field = ParsedField(
                value=best_candidate, confidence=0.6, bbox=None, raw=best_candidate
            )
    if not chassis_field:
        chassis_field = _find_regex_field(full_text, r"\b([A-HJ-NPR-Z0-9=-]{8,20})\b")

    if chassis_field:
        normalized = _normalize_chassis_value(str(chassis_field.value))
        if normalized:
            chassis_field = ParsedField(
                value=normalized,
                confidence=chassis_field.confidence,
                bbox=chassis_field.bbox,
                raw=chassis_field.raw,
            )
        results["chassis"] = chassis_field

    mileage_field = _find_labeled_value(
        row_entries,
        [r"走行", r"走行距離", r"走行km", r"走行Ｋｍ", r"走行㎞"],
        value_regex=r"\d[\d,]*(?:\.\d+)?",
    )
    if not mileage_field:
        mileage_field = _find_regex_field(
            full_text, r"走行[:\s]*([0-9,]+)\s*(?:km|㎞|ｋｍ|KM)?"
        )
    if not mileage_field:
        # Look for patterns like "21300km" or digits followed by km suffix
        mileage_match = re.search(
            r"(\d{2,6})(?:km|kふ|㎞|ｋｍ|KM)",
            normalize_text(full_text),
            re.IGNORECASE,
        )
        if mileage_match:
            mileage_field = ParsedField(
                value=mileage_match.group(1),
                confidence=0.7,
                bbox=None,
                raw=mileage_match.group(0),
            )
    if mileage_field:
        results["mileage"] = mileage_field

    recycle_field = _find_regex_field(
        full_text, r"リサイクル[:\s]*([0-9,]+)\s*円"
    )
    if recycle_field:
        results["recycle_fee"] = recycle_field

    inspector_field = _extract_block(
        row_entries,
        [r"検査員報告", r"検査報告", r"検査員コメント"],
        stop_patterns=[
            r"車台",
            r"走行",
            r"注意",
            r"備考",
            r"装備",
            r"オプション",
            r"リサイクル",
        ],
    )
    if inspector_field:
        results["inspector_report"] = inspector_field

    notes_field = _extract_block(
        row_entries,
        [r"注意事項", r"注意", r"特記事項", r"備考"],
        stop_patterns=[
            r"車台",
            r"走行",
            r"検査員報告",
            r"装備",
            r"オプション",
            r"リサイクル",
        ],
    )
    if notes_field:
        results["notes"] = notes_field

    options_field = _extract_block(
        row_entries,
        [r"装備", r"オプション", r"OP", r"セールスポイント"],
        stop_patterns=[r"車台", r"走行", r"注意", r"検査員報告", r"リサイクル"],
    )
    if options_field:
        results["options"] = options_field

    equipment_codes = parse_equipment(full_text)
    if equipment_codes:
        results["equipment_codes"] = ParsedField(
            equipment_codes, 0.6, None, raw=equipment_codes
        )

    lane_field = _extract_lane_type(row_entries)
    if lane_field:
        results["lane_type"] = lane_field

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
    if "options" in sheet:
        data["options_text"] = sheet["options"].value
    if "lane_type" in sheet:
        data["lane_type"] = sheet["lane_type"].value
    if "equipment_codes" in sheet and not data.get("equipment_codes"):
        data["equipment_codes"] = sheet["equipment_codes"].value

    inspector_notes = {}
    if "inspector_report" in sheet:
        inspector_notes["inspector_report"] = sheet["inspector_report"].value
    if "recycle_fee" in sheet:
        inspector_notes["recycle_fee_yen"] = parse_yen(str(sheet["recycle_fee"].value))
    if inspector_notes:
        data["inspector_notes"] = inspector_notes

    damage_text = " ".join(
        [
            str(sheet.get("notes").value) if "notes" in sheet else "",
            str(sheet.get("inspector_report").value) if "inspector_report" in sheet else "",
        ]
    ).strip()
    damage_codes = _extract_damage_codes(damage_text)
    if damage_codes:
        data["damage_locations"] = [{"code": code} for code in damage_codes]

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


def _extract_damage_codes(text: str) -> list[str]:
    if not text:
        return []
    codes = re.findall(r"[A-Z]{1,2}\d", normalize_alnum(text))
    seen = []
    for code in codes:
        if code not in seen:
            seen.append(code)
    return seen


def _normalize_chassis_value(value: str) -> str | None:
    if not value:
        return None

    # First, handle common OCR character confusions in raw text
    # These patterns are based on observed OCR errors
    text = value.upper()
    text = text.replace("=", "-")  # = often misread for -
    text = text.replace("_", "-")
    text = text.replace(" ", "")

    # Normalize to alphanumeric
    normalized = normalize_alnum(text)
    if not normalized:
        return None

    # VINs avoid I/O/Q; map OCR confusions when seen
    normalized = normalized.replace("I", "1").replace("O", "0").replace("Q", "0")

    # Handle specific OCR confusion patterns for Japanese model codes
    # e.g., "0N0N80" should be "MXUA80" - this is harder to fix generically
    # but we can try to match known patterns and restore them

    if len(normalized) < 6:
        return None

    return normalized


def _find_chassis_patterns(text: str) -> list[str]:
    """Find potential chassis numbers using multiple patterns."""
    results = []
    text_norm = normalize_text(text)

    # Pattern 1: Standard VIN format (17 alphanumeric, no I/O/Q)
    vin_matches = re.findall(r"[A-HJ-NPR-Z0-9]{17}", text_norm, re.IGNORECASE)
    results.extend(vin_matches)

    # Pattern 2: Japanese model code format: PREFIX-SERIAL (e.g., MXUA80-0040656, VJA300-4081487)
    jp_model_matches = re.findall(
        r"([A-Z]{2,6}\d{1,3}[A-Z]?)[-=]?(\d{5,8})",
        text_norm,
        re.IGNORECASE,
    )
    for prefix, serial in jp_model_matches:
        results.append(f"{prefix}-{serial}")

    # Pattern 3: Short prefix with serial (e.g., ZN8-028109)
    short_matches = re.findall(
        r"([A-Z]{2,4}\d?)[-=]?(\d{5,7})",
        text_norm,
        re.IGNORECASE,
    )
    for prefix, serial in short_matches:
        combined = f"{prefix}-{serial}"
        if combined not in results:
            results.append(combined)

    # Pattern 4: Mercedes/BMW style (e.g., W1K1183472N307785)
    euro_matches = re.findall(
        r"W[A-Z0-9]{2}[A-Z0-9]{11,14}",
        text_norm,
        re.IGNORECASE,
    )
    results.extend(euro_matches)

    # Pattern 5: Porsche style (e.g., WP0ZZZY1ZPSA85157)
    porsche_matches = re.findall(
        r"WP0[A-Z0-9]{14}",
        text_norm,
        re.IGNORECASE,
    )
    results.extend(porsche_matches)

    return results


def _row_bbox(tokens: list[OCRToken]) -> tuple[int, int, int, int] | None:
    if not tokens:
        return None
    xs0 = [t.bbox[0] for t in tokens]
    ys0 = [t.bbox[1] for t in tokens]
    xs1 = [t.bbox[2] for t in tokens]
    ys1 = [t.bbox[3] for t in tokens]
    return (min(xs0), min(ys0), max(xs1), max(ys1))


def _find_labeled_value(
    rows: list[dict[str, object]],
    patterns: list[str],
    *,
    value_regex: str | None = None,
) -> ParsedField | None:
    for idx, row in enumerate(rows):
        row_tokens = row["tokens"]
        for token_index, token in enumerate(row_tokens):
            token_norm = normalize_text(token.text)
            if any(re.search(pat, token_norm) for pat in patterns):
                value_tokens = row_tokens[token_index + 1 :]
                value_text = " ".join([t.text for t in value_tokens if t.text]).strip()
                value_bbox = _row_bbox(value_tokens) if value_tokens else None
                if not value_text and idx + 1 < len(rows):
                    next_tokens = rows[idx + 1]["tokens"]
                    value_text = " ".join([t.text for t in next_tokens if t.text]).strip()
                    value_bbox = _row_bbox(next_tokens)
                if value_regex and value_text:
                    match = re.search(value_regex, normalize_text(value_text))
                    if match:
                        value_text = match.group(0)
                if value_text:
                    return ParsedField(
                        value=value_text,
                        confidence=token.confidence,
                        bbox=value_bbox,
                        raw=value_text,
                    )
    return None


def _find_regex_field(text: str, pattern: str) -> ParsedField | None:
    if not text:
        return None
    match = re.search(pattern, normalize_text(text))
    if not match:
        return None
    value = match.group(1) if match.lastindex else match.group(0)
    return ParsedField(value=value, confidence=0.5, bbox=None, raw=value)


def _extract_block(
    rows: list[dict[str, object]],
    patterns: list[str],
    *,
    stop_patterns: list[str],
    max_rows: int = 6,
) -> ParsedField | None:
    for idx, row in enumerate(rows):
        if any(re.search(pat, row["norm"]) for pat in patterns):
            lines = []
            bbox = row["bbox"]
            row_text = row["text"]
            if row_text:
                for pat in patterns:
                    row_text = re.sub(pat, "", row_text)
                row_text = row_text.strip(" :：")
                if row_text:
                    lines.append(row_text)
            for offset in range(1, max_rows + 1):
                next_idx = idx + offset
                if next_idx >= len(rows):
                    break
                next_row = rows[next_idx]
                if any(re.search(pat, next_row["norm"]) for pat in stop_patterns):
                    break
                if next_row["text"]:
                    lines.append(next_row["text"])
                if bbox and next_row["bbox"]:
                    bbox = (
                        min(bbox[0], next_row["bbox"][0]),
                        min(bbox[1], next_row["bbox"][1]),
                        max(bbox[2], next_row["bbox"][2]),
                        max(bbox[3], next_row["bbox"][3]),
                    )
            joined = " / ".join([line for line in lines if line])
            if joined:
                return ParsedField(value=joined, confidence=0.55, bbox=bbox, raw=joined)
    return None


def _extract_lane_type(rows: list[dict[str, object]]) -> ParsedField | None:
    keywords = ["輸入車", "国産", "外車", "ディーラー", "業販", "評価点"]
    if not rows:
        return None
    top_rows = rows[:3]
    for row in top_rows:
        text = row["text"]
        if not text:
            continue
        for keyword in keywords:
            if keyword in text:
                return ParsedField(value=keyword, confidence=0.6, bbox=row["bbox"], raw=text)
    return None
