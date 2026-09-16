import csv
import json
import os
import re
import sys
from datetime import datetime, timezone

OUTPUT_FILE = "manifest.json"
DATA_DIR = "data"

def normalize_header(value):
    return re.sub(r"[^a-z0-9]", "", value.strip().lower())

def find_time_column(headers):
    normalized = {normalize_header(header): header for header in headers}
    candidates = [
        "timestamp", "time", "datetime", "date",
        "opentime", "closetime", "opendatetime", "closedatetime",
        "gmttime", "timeutc", "dateutc"
    ]
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None

def timestamp_to_milliseconds(value):
    value = str(value).strip()
    if not value:
        raise ValueError("Empty timestamp")

    # عدد خام (Unix Timestamp)
    try:
        number = float(value)
        if number < 100_000_000_000:
            return int(number * 1000)
        if number < 100_000_000_000_000:
            return int(number)
        if number < 100_000_000_000_000_000:
            return int(number / 1000)
        return int(number / 1_000_000)
    except ValueError:
        pass

    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    # تبدیل نقطه‌ها و اسلش‌ها برای یکسان‌سازی
    text_clean = text.replace(".", "-")

    formats = [
        None,
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%m-%d-%Y %H:%M:%S",
        "%m-%d-%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            if fmt is None:
                dt = datetime.fromisoformat(text_clean)
            else:
                dt = datetime.strptime(text if "/" in fmt else text_clean, fmt)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return int(dt.timestamp() * 1000)
        except ValueError:
            continue

    raise ValueError(f"Unsupported timestamp format: {value}")

def get_csv_times(file_path):
    encodings = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
    delimiters = [",", "\t", ";"]

    for encoding in encodings:
        for delimiter in delimiters:
            try:
                with open(file_path, "r", encoding=encoding, newline="") as file:
                    reader = csv.reader(file, delimiter=delimiter)
                    rows = [row for row in reader if row and any(cell.strip() for cell in row)]
                    
                    if not rows:
                        continue

                    first_row = rows[0]
                    first_cell = first_row[0].strip()

                    # تشخیص اینکه آیا سطر اول هدر دارد یا مستقیماً داده است
                    time_col_idx = 0
                    has_header = False

                    # اگر سطر اول دارای نام‌های ستون معروف باشد
                    for idx, cell in enumerate(first_row):
                        if find_time_column([cell]):
                            time_col_idx = idx
                            has_header = True
                            break

                    start_idx = 1 if has_header else 0
                    timestamps = []

                    for row in rows[start_idx:]:
                        if len(row) > time_col_idx:
                            raw_val = row[time_col_idx].strip()
                            if raw_val:
                                try:
                                    timestamps.append(timestamp_to_milliseconds(raw_val))
                                except ValueError:
                                    continue

                    if timestamps:
                        return min(timestamps), max(timestamps)
            except Exception:
                continue

    raise RuntimeError(f"Could not extract timestamps from {file_path}.")

def parse_filename(filename):
    base_match = re.fullmatch(r"(.+?)_(D1|H4)\.csv", filename, re.IGNORECASE)
    if base_match:
        return {
            "symbol": base_match.group(1).upper(),
            "timeframe_code": base_match.group(2).upper(),
            "patch_number": None,
        }

    patch_match = re.fullmatch(r"(.+?)_(D1|H4)_update_(\d+)\.csv", filename, re.IGNORECASE)
    if patch_match:
        return {
            "symbol": patch_match.group(1).upper(),
            "timeframe_code": patch_match.group(2).upper(),
            "patch_number": int(patch_match.group(3)),
        }

    return None

def manifest_key(symbol, timeframe_code):
    return f"{symbol}_1D" if timeframe_code == "D1" else f"{symbol}_4H"

def timeframe_value(timeframe_code):
    return "1d" if timeframe_code == "D1" else "4h"

def patch_description(symbol, timeframe_code, end_time):
    date_text = datetime.fromtimestamp(end_time / 1000, tz=timezone.utc).strftime("%d %B %Y")
    tf_str = "روزانه" if timeframe_code == "D1" else "چهارساعته"
    return f"بروزرسانی {tf_str} {symbol} تا {date_text}"

def generate_manifest():
    if not os.path.isdir(DATA_DIR):
        raise RuntimeError(f"Data directory not found: {DATA_DIR}")

    symbols = {}
    csv_files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith(".csv")]

    if not csv_files:
        raise RuntimeError("No CSV files downloaded from Release.")

    for filename in csv_files:
        file_path = os.path.join(DATA_DIR, filename)
        parsed = parse_filename(filename)

        if not parsed:
            print(f"Skipping unsupported filename: {filename}")
            continue

        symbol = parsed["symbol"]
        tf_code = parsed["timeframe_code"]
        patch_num = parsed["patch_number"]
        key = manifest_key(symbol, tf_code)

        if key not in symbols:
            symbols[key] = {
                "symbol": symbol,
                "timeframe": timeframe_value(tf_code),
                "baseFile": f"{symbol}_{tf_code}.csv",
                "baseStartTime": 0,
                "baseEndTime": 0,
                "baseSizeBytes": 0,
                "patches": [],
            }

        start_time, end_time = get_csv_times(file_path)
        size_bytes = os.path.getsize(file_path)

        if patch_num is None:
            symbols[key]["baseStartTime"] = start_time
            symbols[key]["baseEndTime"] = end_time
            symbols[key]["baseSizeBytes"] = size_bytes
        else:
            symbols[key]["patches"].append({
                "id": f"update_{patch_num}",
                "file": filename,
                "startTime": start_time,
                "endTime": end_time,
                "sizeBytes": size_bytes,
                "description": patch_description(symbol, tf_code, end_time),
            })

    for item in symbols.values():
        item["patches"].sort(key=lambda p: int(p["id"].replace("update_", "")))

    return {
        "version": 1,
        "symbols": dict(sorted(symbols.items()))
    }

def main():
    print("Generating manifest.json from downloaded release files...")
    manifest = generate_manifest()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Manifest successfully generated. Found {len(manifest['symbols'])} symbol configurations.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
