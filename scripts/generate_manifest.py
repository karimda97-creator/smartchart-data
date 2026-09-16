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
        "opentime", "closetime", "opendatetime", "closedatetime"
    ]
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None

def timestamp_to_milliseconds(value):
    value = str(value).strip()
    if not value:
        raise ValueError("Empty timestamp")

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

    formats = [
        None,
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
    ]

    for fmt in formats:
        try:
            if fmt is None:
                dt = datetime.fromisoformat(text)
            else:
                dt = datetime.strptime(text, fmt)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return int(dt.timestamp() * 1000)
        except ValueError:
            continue

    raise ValueError(f"Unsupported timestamp format: {value}")

def get_csv_times(file_path):
    encodings = ["utf-8-sig", "utf-8", "cp1252"]
    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding, newline="") as file:
                reader = csv.DictReader(file)
                if not reader.fieldnames:
                    continue

                time_column = find_time_column(reader.fieldnames)
                if not time_column:
                    continue

                timestamps = []
                for row in reader:
                    raw_value = row.get(time_column)
                    if raw_value and raw_value.strip():
                        try:
                            timestamps.append(timestamp_to_milliseconds(raw_value))
                        except ValueError:
                            continue

                if timestamps:
                    return min(timestamps), max(timestamps)
        except UnicodeDecodeError:
            continue

    raise RuntimeError(f"Could not extract timestamps from {file_path}")

def parse_filename(filename):
    # Base: BTCUSD_D1.csv
    base_match = re.fullmatch(r"(.+?)_(D1|H4)\.csv", filename, re.IGNORECASE)
    if base_match:
        return {
            "symbol": base_match.group(1).upper(),
            "timeframe_code": base_match.group(2).upper(),
            "patch_number": None,
        }

    # Patch: BTCUSD_D1_update_1.csv
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

    # سورت کردن پچ‌ها بر اساس شماره update
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
