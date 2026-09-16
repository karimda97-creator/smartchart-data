import csv
import json
import os
import sys
from datetime import datetime, timezone


REPO = os.environ.get("REPO", "")
TAG_NAME = os.environ.get("TAG_NAME", "")

OUTPUT_FILE = "guide.json"


# فایل‌های داده و مشخصات آن‌ها
DATASETS = {
    "BTCUSD_D1": {
        "symbol": "BTCUSD",
        "timeframe": "1d",
        "file": "BTCUSD_D1.csv",
    },
    "BTCUSD_H4": {
        "symbol": "BTCUSD",
        "timeframe": "4h",
        "file": "BTCUSD_H4.csv",
    },
    "XAUUSD_H4": {
        "symbol": "XAUUSD",
        "timeframe": "4h",
        "file": "XAUUSD_H4.csv",
    },
    "XAGUSD_H4": {
        "symbol": "XAGUSD",
        "timeframe": "4h",
        "file": "XAGUSD_H4.csv",
    },
}


def find_csv_file(filename):
    """
    فایل CSV را در Repository پیدا می‌کند.
    ابتدا ریشه و سپس پوشه data را بررسی می‌کند.
    """

    candidates = [
        filename,
        os.path.join("data", filename),
    ]

    for path in candidates:
        if os.path.isfile(path):
            return path

    return None


def detect_csv_columns(path):
    """
    نام ستون‌های CSV را تشخیص می‌دهد.
    """

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)

        header = next(reader, None)

        if not header:
            raise ValueError(f"CSV header not found: {path}")

        return [column.strip().lower() for column in header]


def find_time_column(columns):
    """
    ستون timestamp/time/date را پیدا می‌کند.
    """

    candidates = [
        "timestamp",
        "time",
        "datetime",
        "date",
        "open_time",
        "opentime",
    ]

    for candidate in candidates:
        if candidate in columns:
            return candidate

    return None


def read_first_last_timestamp(path):
    """
    اولین و آخرین timestamp موجود در CSV را پیدا می‌کند.
    """

    with open(path, "r", encoding="utf-8-sig", newline="") as f:

        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError(f"CSV header not found: {path}")

        original_columns = reader.fieldnames
        normalized_columns = {
            column.strip().lower(): column
            for column in original_columns
        }

        time_column = find_time_column(list(normalized_columns.keys()))

        if not time_column:
            raise ValueError(
                f"Could not find timestamp column in {path}. "
                f"Columns: {original_columns}"
            )

        real_column = normalized_columns[time_column]

        first_value = None
        last_value = None

        for row in reader:

            value = row.get(real_column)

            if value is None:
                continue

            value = value.strip()

            if not value:
                continue

            if first_value is None:
                first_value = value

            last_value = value

        if first_value is None or last_value is None:
            raise ValueError(f"No timestamp data found in {path}")

        return first_value, last_value


def timestamp_to_milliseconds(value):
    """
    Timestamp را به milliseconds تبدیل می‌کند.

    پشتیبانی از:
    - milliseconds
    - seconds
    - ISO datetime
    - YYYY-MM-DD HH:MM:SS
    """

    value = value.strip()

    # عدد
    try:
        number = float(value)

        # milliseconds
        if number > 100000000000:
            return int(number)

        # seconds
        return int(number * 1000)

    except ValueError:
        pass

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue

    raise ValueError(f"Unsupported timestamp format: {value}")


def build_download_url(filename):
    """
    لینک دانلود فایل از GitHub Release.
    """

    if not REPO or not TAG_NAME:
        return ""

    return (
        f"https://github.com/{REPO}/releases/download/"
        f"{TAG_NAME}/{filename}"
    )


def build_dataset(key, config):

    filename = config["file"]

    path = find_csv_file(filename)

    if not path:
        raise FileNotFoundError(
            f"CSV file not found: {filename}"
        )

    first_raw, last_raw = read_first_last_timestamp(path)

    first_timestamp = timestamp_to_milliseconds(first_raw)
    last_timestamp = timestamp_to_milliseconds(last_raw)

    size_bytes = os.path.getsize(path)

    return {
        "symbol": config["symbol"],
        "timeframe": config["timeframe"],
        "baseFile": filename,
        "baseStartTime": first_timestamp,
        "baseEndTime": last_timestamp,
        "sizeBytes": size_bytes,
        "downloadUrl": build_download_url(filename),
    }


def main():

import csv
import json
import os
import re
import sys
from datetime import datetime, timezone


OUTPUT_FILE = "manifest.json"


def find_csv_files():
    csv_files = []

    search_dirs = [
        ".",
        "data",
    ]

    for directory in search_dirs:
        if not os.path.isdir(directory):
            continue

        for filename in os.listdir(directory):
            if not filename.lower().endswith(".csv"):
                continue

            path = os.path.join(directory, filename)

            if os.path.isfile(path):
                csv_files.append(path)

    return sorted(set(csv_files))


def timestamp_to_milliseconds(value):
    value = value.strip()

    if not value:
        raise ValueError("Empty timestamp")

    # Unix timestamp
    try:
        number = float(value)

        if number > 100000000000:
            return int(number)

        return int(number * 1000)

    except ValueError:
        pass

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue

    raise ValueError(f"Unsupported timestamp format: {value}")


def find_time_column(fieldnames):
    candidates = [
        "timestamp",
        "time",
        "datetime",
        "date",
        "open_time",
        "opentime",
    ]

    normalized = {
        field.strip().lower(): field
        for field in fieldnames
        if field
    }

    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]

    raise ValueError(
        f"Timestamp column not found. Columns: {fieldnames}"
    )


def read_csv_metadata(path):
    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError(
                f"CSV header not found: {path}"
            )

        time_column = find_time_column(reader.fieldnames)

        first_timestamp = None
        last_timestamp = None

        for row in reader:

            value = row.get(time_column)

            if value is None:
                continue

            value = value.strip()

            if not value:
                continue

            timestamp = timestamp_to_milliseconds(value)

            if first_timestamp is None:
                first_timestamp = timestamp

            last_timestamp = timestamp

        if first_timestamp is None:
            raise ValueError(
                f"No timestamp data found: {path}"
            )

        return first_timestamp, last_timestamp


def parse_filename(filename):
    """
    Supported examples:

    BTCUSD_D1.csv
    BTCUSD_H4.csv

    BTCUSD_D1_update_1.csv
    BTCUSD_H4_update_2.csv
    """

    name = os.path.basename(filename)

    base_pattern = re.compile(
        r"^(.+?)_(D1|H4)\.csv$",
        re.IGNORECASE
    )

    patch_pattern = re.compile(
        r"^(.+?)_(D1|H4)_update_(\d+)\.csv$",
        re.IGNORECASE
    )

    patch_match = patch_pattern.match(name)

    if patch_match:
        symbol = patch_match.group(1).upper()
        timeframe_code = patch_match.group(2).upper()
        update_number = int(patch_match.group(3))

        timeframe = (
            "1d"
            if timeframe_code == "D1"
            else "4h"
        )

        return {
            "type": "patch",
            "symbol": symbol,
            "timeframe": timeframe,
            "timeframeCode": timeframe_code,
            "updateNumber": update_number,
            "filename": name,
        }

    base_match = base_pattern.match(name)

    if base_match:
        symbol = base_match.group(1).upper()
        timeframe_code = base_match.group(2).upper()

        timeframe = (
            "1d"
            if timeframe_code == "D1"
            else "4h"
        )

        return {
            "type": "base",
            "symbol": symbol,
            "timeframe": timeframe,
            "timeframeCode": timeframe_code,
            "filename": name,
        }

    return None


def make_dataset_key(symbol, timeframe):
    suffix = "1D" if timeframe == "1d" else "4H"
    return f"{symbol}_{suffix}"


def make_patch_description(symbol, timeframe, end_timestamp):
    dt = datetime.fromtimestamp(
        end_timestamp / 1000,
        tz=timezone.utc
    )

    timeframe_text = (
        "روزانه"
        if timeframe == "1d"
        else "چهارساعته"
    )

    return (
        f"بروزرسانی {timeframe_text} "
        f"{symbol} تا {dt.day} "
        f"{dt.strftime('%B')} {dt.year}"
    )


def build_manifest():
    csv_files = find_csv_files()

    if not csv_files:
        raise FileNotFoundError(
            "No CSV files found."
        )

    print(f"Found {len(csv_files)} CSV files.")

    datasets = {}

    for path in csv_files:

        filename = os.path.basename(path)

        parsed = parse_filename(filename)

        if parsed is None:
            print(
                f"Skipping unsupported filename: {filename}"
            )
            continue

        print(f"Processing: {filename}")

        start_time, end_time = read_csv_metadata(path)
        size_bytes = os.path.getsize(path)

        symbol = parsed["symbol"]
        timeframe = parsed["timeframe"]

        key = make_dataset_key(
            symbol,
            timeframe
        )

        if parsed["type"] == "base":

            datasets[key] = {
                "symbol": symbol,
                "timeframe": timeframe,
                "baseFile": filename,
                "baseStartTime": start_time,
                "baseEndTime": end_time,
                "baseSizeBytes": size_bytes,
                "patches": [],
            }

        else:

            if key not in datasets:

                datasets[key] = {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "baseFile": "",
                    "baseStartTime": 0,
                    "baseEndTime": 0,
                    "baseSizeBytes": 0,
                    "patches": [],
                }

            patch = {
                "id": f"update_{parsed['updateNumber']}",
                "file": filename,
                "startTime": start_time,
                "endTime": end_time,
                "sizeBytes": size_bytes,
                "description": make_patch_description(
                    symbol,
                    timeframe,
                    end_time
                ),
            }

            datasets[key]["patches"].append(patch)

    # مرتب‌سازی Patchها
    for dataset in datasets.values():

        dataset["patches"].sort(
            key=lambda patch: (
                int(
                    patch["id"].replace(
                        "update_",
                        ""
                    )
                )
            )
        )

    # مرتب‌سازی Datasetها
    datasets = dict(
        sorted(datasets.items())
    )

    manifest = {
        "version": 1,
        "symbols": datasets,
    }

    return manifest


def main():

    print("Generating manifest.json...")

    manifest = build_manifest()

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            manifest,
            file,
            ensure_ascii=False,
            indent=2
        )

    print()
    print(
        f"Manifest generated successfully: "
        f"{OUTPUT_FILE}"
    )

    print(
        f"Datasets: {len(manifest['symbols'])}"
    )


if __name__ == "__main__":

    try:
        main()

    except Exception as error:

        print(f"ERROR: {error}")
        sys.exit(1)
n(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            manifest,
            f,
            ensure_ascii=False,
            indent=2
        )

    print()
    print(f"Manifest generated successfully: {OUTPUT_FILE}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
