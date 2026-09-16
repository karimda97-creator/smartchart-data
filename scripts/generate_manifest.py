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

    print("Generating guide.json...")

    manifest = {
        "version": 1,
        "releaseTag": TAG_NAME,
        "repository": REPO,
        "generatedAt": int(
            datetime.now(timezone.utc).timestamp() * 1000
        ),
        "symbols": {},
    }

    for key, config in DATASETS.items():

        print(f"Processing {config['file']}...")

        dataset = build_dataset(key, config)

        manifest["symbols"][key] = dataset

        print(
            f"  start: {dataset['baseStartTime']}"
        )

        print(
            f"  end:   {dataset['baseEndTime']}"
        )

        print(
            f"  size:  {dataset['sizeBytes']} bytes"
        )

    with open(
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
