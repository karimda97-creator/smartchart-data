import csv
import json
import os
import re
import sys
from datetime import datetime, timezone


OUTPUT_FILE = "manifest.json"
DATA_DIR = "data"


# ==========================================================
# Header utilities
# ==========================================================

def normalize_header(value):
    return re.sub(r"[^a-z0-9]", "", value.strip().lower())


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
    ]

    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]

    return None


# ==========================================================
# Timestamp conversion
# ==========================================================

def timestamp_to_milliseconds(value):
    value = value.strip()

    if not value:
        raise ValueError("Empty timestamp")

    # Numeric timestamp
    try:
        number = float(value)

        # seconds
        if number < 100_000_000_000:
            return int(number * 1000)

        # milliseconds
        if number < 100_000_000_000_000:
            return int(number)

        # microseconds
        if number < 100_000_000_000_000_000:
            return int(number / 1000)

        # nanoseconds
        return int(number / 1_000_000)

    except ValueError:
        pass

    # ISO/date formats
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

    raise ValueError(
        f"Unsupported timestamp format: {value}"
    )


# ==========================================================
# CSV time extraction
# ==========================================================

def get_csv_times(file_path):

    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp1252",
    ]

    last_error = None

    for encoding in encodings:

        try:

            with open(
                file_path,
                "r",
                encoding=encoding,
                newline=""
            ) as file:

                reader = csv.DictReader(file)

                if not reader.fieldnames:
                    raise ValueError(
                        "CSV has no header"
                    )

                time_column = find_time_column(
                    reader.fieldnames
                )

                if not time_column:
                    raise ValueError(
                        f"No time column found. "
                        f"Headers: {reader.fieldnames}"
                    )

                timestamps = []

                for row_number, row in enumerate(
                    reader,
                    start=2
                ):

                    raw_value = row.get(time_column)

                    if raw_value is None:
                        continue

                    raw_value = raw_value.strip()

                    if not raw_value:
                        continue

                    try:

                        timestamp = (
                            timestamp_to_milliseconds(
                                raw_value
                            )
                        )

                        timestamps.append(timestamp)

                    except ValueError as error:

                        print(
                            f"Warning: "
                            f"{file_path}:{row_number}: "
                            f"{error}"
                        )

                if not timestamps:
                    raise ValueError(
                        f"No valid timestamps found "
                        f"in {file_path}"
                    )

                return (
                    min(timestamps),
                    max(timestamps)
                )

        except UnicodeDecodeError as error:

            last_error = error
            continue

    raise RuntimeError(
        f"Could not decode {file_path}: "
        f"{last_error}"
    )


# ==========================================================
# File size
# ==========================================================

def get_file_size(file_path):
    return os.path.getsize(file_path)


# ==========================================================
# Filename parser
# ==========================================================

def parse_filename(filename):

    # Base:
    # BTCUSD_D1.csv
    # BTCUSD_H4.csv

    base_match = re.fullmatch(
        r"(.+?)_(D1|H4)\.csv",
        filename,
        re.IGNORECASE
    )

    if base_match:

        symbol = base_match.group(1).upper()

        timeframe_code = (
            base_match.group(2).upper()
        )

        return {
            "symbol": symbol,
            "timeframe_code": timeframe_code,
            "patch_number": None,
        }

    # Patch:
    # BTCUSD_D1_update_1.csv
    # BTCUSD_H4_update_2.csv

    patch_match = re.fullmatch(
        r"(.+?)_(D1|H4)_update_(\d+)\.csv",
        filename,
        re.IGNORECASE
    )

    if patch_match:

        symbol = patch_match.group(1).upper()

        timeframe_code = (
            patch_match.group(2).upper()
        )

        patch_number = int(
            patch_match.group(3)
        )

        return {
            "symbol": symbol,
            "timeframe_code": timeframe_code,
            "patch_number": patch_number,
        }

    return None


# ==========================================================
# Manifest naming
# ==========================================================

def manifest_key(
    symbol,
    timeframe_code
):

    if timeframe_code == "D1":
        return f"{symbol}_1D"

    if timeframe_code == "H4":
        return f"{symbol}_4H"

    raise ValueError(
        f"Unsupported timeframe: "
        f"{timeframe_code}"
    )


def timeframe_value(
    timeframe_code
):

    if timeframe_code == "D1":
        return "1d"

    if timeframe_code == "H4":
        return "4h"

    raise ValueError(
        f"Unsupported timeframe: "
        f"{timeframe_code}"
    )


# ==========================================================
# Patch description
# ==========================================================

def patch_description(
    symbol,
    timeframe_code,
    end_time
):

    date_text = (
        datetime.fromtimestamp(
            end_time / 1000,
            tz=timezone.utc
        ).strftime("%d %B %Y")
    )

    if timeframe_code == "D1":

        return (
            f"بروزرسانی روزانه "
            f"{symbol} تا {date_text}"
        )

    return (
        f"بروزرسانی چهارساعته "
        f"{symbol} تا {date_text}"
    )


# ==========================================================
# Scan CSV files
# ==========================================================

def scan_csv_files():

    files = []

    if not os.path.isdir(DATA_DIR):
        raise RuntimeError(
            f"Data directory not found: "
            f"{DATA_DIR}"
        )

    for filename in os.listdir(DATA_DIR):

        if not filename.lower().endswith(".csv"):
            continue

        path = os.path.join(
            DATA_DIR,
            filename
        )

        parsed = parse_filename(
            filename
        )

        if parsed is None:

            print(
                f"Skipping unsupported CSV: "
                f"{filename}"
            )

            continue

        files.append(
            (
                path,
                filename,
                parsed
            )
        )

    return files


# ==========================================================
# Generate manifest
# ==========================================================

def generate_manifest():

    csv_files = scan_csv_files()

    if not csv_files:
        raise RuntimeError(
            "No supported CSV files found"
        )

    symbols = {}

    for (
        file_path,
        filename,
        parsed
    ) in csv_files:

        symbol = parsed["symbol"]

        timeframe_code = (
            parsed["timeframe_code"]
        )

        patch_number = (
            parsed["patch_number"]
        )

        key = manifest_key(
            symbol,
            timeframe_code
        )

        if key not in symbols:

            symbols[key] = {

                "symbol": symbol,

                "timeframe":
                    timeframe_value(
                        timeframe_code
                    ),

                "baseFile":
                    f"{symbol}_{timeframe_code}.csv",

                "baseStartTime": 0,

                "baseEndTime": 0,

                "baseSizeBytes": 0,

                "patches": [],
            }

        # --------------------------------------------------
        # Base file
        # --------------------------------------------------

        if patch_number is None:

            start_time, end_time = (
                get_csv_times(file_path)
            )

            size = get_file_size(
                file_path
            )

            symbols[key][
                "baseStartTime"
            ] = start_time

            symbols[key][
                "baseEndTime"
            ] = end_time

            symbols[key][
                "baseSizeBytes"
            ] = size

            print(
                f"BASE  {filename} | "
                f"{start_time} -> {end_time} | "
                f"{size} bytes"
            )

        # --------------------------------------------------
        # Patch
        # --------------------------------------------------

        else:

            start_time, end_time = (
                get_csv_times(file_path)
            )

            size = get_file_size(
                file_path
            )

            patch = {

                "id":
                    f"update_{patch_number}",

                "file":
                    filename,

                "startTime":
                    start_time,

                "endTime":
                    end_time,

                "sizeBytes":
                    size,

                "description":
                    patch_description(
                        symbol,
                        timeframe_code,
                        end_time
                    ),
            }

            symbols[key][
                "patches"
            ].append(patch)

            print(
                f"PATCH {filename} | "
                f"{start_time} -> {end_time} | "
                f"{size} bytes"
            )

    # ------------------------------------------------------
    # Sort patches
    # ------------------------------------------------------

    for key, item in symbols.items():

        item["patches"].sort(
            key=lambda patch:
                int(
                    patch["id"]
                    .replace(
                        "update_",
                        ""
                    )
                )
        )

    # ------------------------------------------------------
    # Final manifest
    # ------------------------------------------------------

    manifest = {

        "version": 1,

        "symbols":
            dict(
                sorted(
                    symbols.items()
                )
            ),
    }

    return manifest


# ==========================================================
# Main
# ==========================================================

def main():

    print(
        "======================================"
    )

    print(
        "Generating manifest.json"
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
        f"Output: {OUTPUT_FILE}"
    )

    print(
        f"Symbols: "
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


if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print(
            f"ERROR: {error}",
            file=sys.stderr
        )

        sys.exit(1)
