import csv
import json
import os
import re
import sys
from datetime import datetime, timezone


OUTPUT_FILE = "manifest.json"
DATA_DIR = "data"


# ============================================================
# Header detection
# ============================================================

def normalize_header(value):
    return re.sub(
        r"[^a-z0-9]",
        "",
        value.strip().lower()
    )


def find_time_column(headers):
    normalized = {
        normalize_header(header): header
        for header in headers
    }

    candidates = [
        "timestamp",
        "time",
        "datetime",
        "date",
        "opentime",
        "closetime",
        "opendatetime",
        "closedatetime",
        "gmttime",
        "timeutc",
        "dateutc",
    ]

    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]

    return None


# ============================================================
# Timestamp conversion
# ============================================================

def timestamp_to_milliseconds(value):
    value = str(value).strip()

    if not value:
        raise ValueError("Empty timestamp")

    # --------------------------------------------------------
    # Unix timestamp
    # --------------------------------------------------------

    try:
        number = float(value)

        # Seconds
        if number < 100_000_000_000:
            return int(number * 1000)

        # Milliseconds
        if number < 100_000_000_000_000:
            return int(number)

        # Microseconds
        if number < 100_000_000_000_000_000:
            return int(number / 1000)

        # Nanoseconds
        return int(number / 1_000_000)

    except ValueError:
        pass

    # --------------------------------------------------------
    # Date / Time strings
    # --------------------------------------------------------

    text = value

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

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
                dt = datetime.fromisoformat(
                    text_clean
                )

            else:

                if "/" in fmt:
                    dt = datetime.strptime(
                        text,
                        fmt
                    )
                else:
                    dt = datetime.strptime(
                        text_clean,
                        fmt
                    )

            if dt.tzinfo is None:
                dt = dt.replace(
                    tzinfo=timezone.utc
                )

            return int(
                dt.timestamp() * 1000
            )

        except ValueError:
            continue

    raise ValueError(
        f"Unsupported timestamp format: {value}"
    )


# ============================================================
# CSV time extraction
# ============================================================

def get_csv_times(file_path):

    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin-1",
    ]

    delimiters = [
        ",",
        "\t",
        ";",
    ]

    for encoding in encodings:

        for delimiter in delimiters:

            try:

                with open(
                    file_path,
                    "r",
                    encoding=encoding,
                    newline=""
                ) as file:

                    reader = csv.reader(
                        file,
                        delimiter=delimiter
                    )

                    rows = [
                        row
                        for row in reader
                        if row and any(
                            cell.strip()
                            for cell in row
                        )
                    ]

                    if not rows:
                        continue

                    first_row = rows[0]

                    time_col_idx = 0
                    has_header = False

                    # ------------------------------------------------
                    # Detect time column from header
                    # ------------------------------------------------

                    for idx, cell in enumerate(first_row):

                        if find_time_column([cell]):

                            time_col_idx = idx
                            has_header = True
                            break

                    start_idx = (
                        1
                        if has_header
                        else 0
                    )

                    timestamps = []

                    # ------------------------------------------------
                    # Read timestamps
                    # ------------------------------------------------

                    for row in rows[start_idx:]:

                        if len(row) <= time_col_idx:
                            continue

                        raw_value = row[
                            time_col_idx
                        ].strip()

                        if not raw_value:
                            continue

                        try:

                            timestamp = (
                                timestamp_to_milliseconds(
                                    raw_value
                                )
                            )

                            timestamps.append(
                                timestamp
                            )

                        except ValueError:

                            continue

                    if timestamps:

                        return (
                            min(timestamps),
                            max(timestamps)
                        )

            except Exception:

                continue

    raise RuntimeError(
        f"Could not extract timestamps from {file_path}"
    )


# ============================================================
# Filename parser
# ============================================================

def parse_filename(filename):

    # ------------------------------------------------------------
    # Supported timeframes:
    #
    # M1
    # M5
    # M15
    # M30
    # H1
    # H4
    # D1
    # ------------------------------------------------------------

    timeframe_pattern = (
        r"M1|M5|M15|M30|H1|H4|D1"
    )

    # ------------------------------------------------------------
    # Base file
    # ------------------------------------------------------------

    base_match = re.fullmatch(
        rf"(.+?)_({timeframe_pattern})\.csv",
        filename,
        re.IGNORECASE
    )

    if base_match:

        return {
            "symbol": base_match.group(1).upper(),
            "timeframe_code": base_match.group(2).upper(),
            "patch_number": None,
        }

    # ------------------------------------------------------------
    # Patch file
    # ------------------------------------------------------------

    patch_match = re.fullmatch(
        rf"(.+?)_({timeframe_pattern})_update_(\d+)\.csv",
        filename,
        re.IGNORECASE
    )

    if patch_match:

        return {
            "symbol": patch_match.group(1).upper(),
            "timeframe_code": patch_match.group(2).upper(),
            "patch_number": int(
                patch_match.group(3)
            ),
        }

    return None


# ============================================================
# Manifest key
# ============================================================

def manifest_key(
    symbol,
    timeframe_code
):

    mapping = {
        "D1": "1D",
        "H4": "4H",
        "H1": "1H",
        "M30": "30M",
        "M15": "15M",
        "M5": "5M",
        "M1": "1M",
    }

    if timeframe_code not in mapping:

        raise ValueError(
            f"Unsupported timeframe: {timeframe_code}"
        )

    return (
        f"{symbol}_{mapping[timeframe_code]}"
    )


# ============================================================
# Manifest timeframe value
# ============================================================

def timeframe_value(
    timeframe_code
):

    mapping = {
        "D1": "1d",
        "H4": "4h",
        "H1": "1h",
        "M30": "30m",
        "M15": "15m",
        "M5": "5m",
        "M1": "1m",
    }

    if timeframe_code not in mapping:

        raise ValueError(
            f"Unsupported timeframe: {timeframe_code}"
        )

    return mapping[timeframe_code]


# ============================================================
# Patch description
# ============================================================

def patch_description(
    symbol,
    timeframe_code,
    end_time
):

    date_text = datetime.fromtimestamp(
        end_time / 1000,
        tz=timezone.utc
    ).strftime("%d %B %Y")

    timeframe_names = {
        "D1": "روزانه",
        "H4": "چهارساعته",
        "H1": "یک‌ساعته",
        "M30": "سی‌دقیقه‌ای",
        "M15": "پانزده‌دقیقه‌ای",
        "M5": "پنج‌دقیقه‌ای",
        "M1": "یک‌دقیقه‌ای",
    }

    tf_name = timeframe_names.get(
        timeframe_code,
        timeframe_code
    )

    return (
        f"بروزرسانی {tf_name} "
        f"{symbol} تا {date_text}"
    )


# ============================================================
# Scan CSV files
# ============================================================

def scan_csv_files():

    if not os.path.isdir(DATA_DIR):

        raise RuntimeError(
            f"Data directory not found: {DATA_DIR}"
        )

    files = []

    for filename in os.listdir(DATA_DIR):

        if not filename.lower().endswith(".csv"):
            continue

        file_path = os.path.join(
            DATA_DIR,
            filename
        )

        parsed = parse_filename(
            filename
        )

        if parsed is None:

            print(
                f"Skipping unsupported filename: "
                f"{filename}"
            )

            continue

        files.append(
            (
                file_path,
                filename,
                parsed
            )
        )

    return files


# ============================================================
# Generate manifest
# ============================================================

def generate_manifest():

    csv_files = scan_csv_files()

    if not csv_files:

        raise RuntimeError(
            "No supported CSV files found."
        )

    symbols = {}

    for (
        file_path,
        filename,
        parsed
    ) in csv_files:

        symbol = parsed["symbol"]
        tf_code = parsed["timeframe_code"]
        patch_num = parsed["patch_number"]

        key = manifest_key(
            symbol,
            tf_code
        )

        # --------------------------------------------------------
        # Create symbol/timeframe entry
        # --------------------------------------------------------

        if key not in symbols:

            symbols[key] = {

                "symbol": symbol,

                "timeframe":
                    timeframe_value(
                        tf_code
                    ),

                "baseFile":
                    f"{symbol}_{tf_code}.csv",

                "baseStartTime": 0,

                "baseEndTime": 0,

                "baseSizeBytes": 0,

                "patches": [],
            }

        # --------------------------------------------------------
        # Extract metadata
        # --------------------------------------------------------

        start_time, end_time = (
            get_csv_times(
                file_path
            )
        )

        size_bytes = os.path.getsize(
            file_path
        )

        # --------------------------------------------------------
        # Base file
        # --------------------------------------------------------

        if patch_num is None:

            symbols[key][
                "baseStartTime"
            ] = start_time

            symbols[key][
                "baseEndTime"
            ] = end_time

            symbols[key][
                "baseSizeBytes"
            ] = size_bytes

            print(
                f"BASE  {filename} | "
                f"{start_time} -> {end_time} | "
                f"{size_bytes} bytes"
            )

        # --------------------------------------------------------
        # Patch file
        # --------------------------------------------------------

        else:

            patch = {

                "id":
                    f"update_{patch_num}",

                "file":
                    filename,

                "startTime":
                    start_time,

                "endTime":
                    end_time,

                "sizeBytes":
                    size_bytes,

                "description":
                    patch_description(
                        symbol,
                        tf_code,
                        end_time
                    ),
            }

            symbols[key][
                "patches"
            ].append(
                patch
            )

            print(
                f"PATCH {filename} | "
                f"{start_time} -> {end_time} | "
                f"{size_bytes} bytes"
            )

    # --------------------------------------------------------
    # Sort patches
    # --------------------------------------------------------

    for item in symbols.values():

        item["patches"].sort(
            key=lambda patch:
                int(
                    patch["id"].replace(
                        "update_",
                        ""
                    )
                )
        )

    # --------------------------------------------------------
    # Sort symbols
    #
    # Timeframe order:
    #
    # D1
    # H4
    # H1
    # M30
    # M15
    # M5
    # M1
    #
    # Symbols are sorted alphabetically.
    # Timeframes inside each symbol are high → low.
    # --------------------------------------------------------

    timeframe_order = {
        "1d": 0,
        "4h": 1,
        "1h": 2,
        "30m": 3,
        "15m": 4,
        "5m": 5,
        "1m": 6,
    }

    sorted_symbols = dict(
        sorted(
            symbols.items(),
            key=lambda item: (
                item[1]["symbol"],
                timeframe_order.get(
                    item[1]["timeframe"],
                    999
                )
            )
        )
    )

    # --------------------------------------------------------
    # Final manifest
    # --------------------------------------------------------

    return {
        "version": 1,
        "symbols": sorted_symbols
    }


# ============================================================
# Main
# ============================================================

def main():

    print(
        "======================================"
    )

    print(
        "Generating manifest.json"
    )

    print(
        "Supported timeframes:"
    )

    print(
        "D1 H4 H1 M30 M15 M5 M1"
    )

    print(
        "======================================"
    )

    manifest = generate_manifest()

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
        newline="\n"
    ) as file:

        json.dump(
            manifest,
            file,
            ensure_ascii=False,
            indent=2
        )

        file.write("\n")

    print()

    print(
        "Manifest generated successfully."
    )

    print(
        f"Configurations found: "
        f"{len(manifest['symbols'])}"
    )

    print()

    for key, item in (
        manifest["symbols"].items()
    ):

        print(
            f"{key}: "
            f"{len(item['patches'])} patch(es)"
        )

    print(
        "======================================"
    )


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print(
            f"ERROR: {error}",
            file=sys.stderr
        )

        sys.exit(1)
