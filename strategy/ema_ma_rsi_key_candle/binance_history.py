#!/usr/bin/env python3
"""Download public Binance USD-M perpetual klines; no credentials required.

Dates are UTC, start inclusive and end exclusive. Source archives and their
available SHA256 checksum files are cached. Only Python's standard library is
required. Output is deliberately independent of any trading account or API key.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import io
import json
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Sequence, Tuple


BASE_URL = "https://data.binance.vision/data/futures/um"
FIELDS = ("open_time_ms", "open", "high", "low", "close", "volume", "close_time_ms")
INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
    "4h": 14_400_000, "6h": 21_600_000, "8h": 28_800_000,
    "12h": 43_200_000, "1d": 86_400_000,
}
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_CSV_BYTES = 512 * 1024 * 1024


class DataError(ValueError):
    """Invalid or incomplete historical market data."""


def parse_date(value: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD (UTC)")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def date_ms(value: date) -> int:
    return calendar.timegm(value.timetuple()) * 1000


def normalize_timestamp(value: str) -> int:
    """Binance archives use milliseconds or microseconds, depending on series."""
    try:
        number = int(value)
    except ValueError as exc:
        raise DataError("noninteger timestamp: {!r}".format(value)) from exc
    if number >= 100_000_000_000_000:
        number //= 1000
    if not 1_000_000_000_000 <= number < 100_000_000_000_000:
        raise DataError("timestamp is not a supported millisecond/microsecond epoch")
    return number


def checksum_for(text: str, filename: str) -> str:
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].lstrip("*") == filename:
            if re.fullmatch(r"[a-fA-F0-9]{64}", parts[0]):
                return parts[0].lower()
    raise DataError("checksum file has no valid SHA256 entry for {}".format(filename))


def fetch(url: str, limit: int, timeout: int = 30) -> bytes:
    last_error = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "my-quant-history/1.0"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content = response.read(limit + 1)
            if len(content) > limit:
                raise DataError("download exceeds size limit: {}".format(url))
            return content
        except urllib.error.HTTPError as exc:
            if exc.code < 500 and exc.code != 429:
                raise
            last_error = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        if attempt < 2:
            time.sleep(attempt + 1)
    raise DataError("download failed: {} ({})".format(url, last_error))


def atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=str(path.parent), delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content)
    try:
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def archive_bytes(url: str, cache_dir: Path) -> Tuple[bytes, dict]:
    filename = url.rsplit("/", 1)[1]
    cache_path = cache_dir / filename
    checksum_path = cache_dir / (filename + ".CHECKSUM")
    if cache_path.exists():
        if cache_path.stat().st_size > MAX_ARCHIVE_BYTES:
            raise DataError("cached archive exceeds size limit: {}".format(cache_path))
        content = cache_path.read_bytes()
    else:
        content = fetch(url, MAX_ARCHIVE_BYTES)
    checksum_text = None
    if checksum_path.exists():
        checksum_text = checksum_path.read_text(encoding="ascii")
    else:
        try:
            checksum_text = fetch(url + ".CHECKSUM", 64 * 1024).decode("ascii")
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            print("WARNING: official SHA256 unavailable (HTTP 404): " + url, file=sys.stderr)
    actual = hashlib.sha256(content).hexdigest()
    if checksum_text is not None:
        expected = checksum_for(checksum_text, filename)
        if actual != expected:
            raise DataError("SHA256 mismatch for {}; remove corrupt cache and retry".format(filename))
        atomic_bytes(checksum_path, checksum_text.encode("ascii"))
    atomic_bytes(cache_path, content)
    return content, {
        "url": url, "sha256": actual, "bytes": len(content),
        "official_sha256_verified": checksum_text is not None,
    }


def archive_rows(content: bytes, filename: str, interval_ms: int) -> List[Tuple]:
    result = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            for member in members:
                name = member.filename
                if "\\" in name or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
                    raise DataError("unsafe ZIP member path: {}".format(name))
            expected = filename[:-4] + ".csv"
            matches = [m for m in members if m.filename == expected and not m.is_dir()]
            if len(matches) != 1:
                raise DataError("archive must contain exactly one expected CSV: {}".format(expected))
            member = matches[0]
            if member.file_size > MAX_CSV_BYTES:
                raise DataError("uncompressed CSV exceeds size limit")
            with archive.open(member) as stream:
                reader = csv.reader(io.TextIOWrapper(stream, encoding="utf-8-sig", newline=""))
                for line_number, row in enumerate(reader, 1):
                    if not row or all(not x.strip() for x in row):
                        continue
                    if line_number == 1 and row[0].strip().lower().replace(" ", "_") in ("open_time", "open_time_ms"):
                        continue
                    if len(row) < 7:
                        raise DataError("{}:{} has fewer than 7 columns".format(expected, line_number))
                    try:
                        opened = normalize_timestamp(row[0].strip())
                        closed = normalize_timestamp(row[6].strip())
                        values = [Decimal(x.strip()) for x in row[1:6]]
                    except (InvalidOperation, DataError) as exc:
                        raise DataError("{}:{} invalid data: {}".format(expected, line_number, exc)) from exc
                    o, h, l, c, volume = values
                    if not all(x.is_finite() for x in values):
                        raise DataError("nonfinite price or volume")
                    if min(o, h, l, c) <= 0 or volume < 0 or not l <= min(o, c) <= max(o, c) <= h:
                        raise DataError("invalid OHLC/volume in {}:{}".format(expected, line_number))
                    if opened % interval_ms != 0 or closed != opened + interval_ms - 1:
                        raise DataError("invalid kline interval in {}:{}".format(expected, line_number))
                    result.append((opened,) + tuple(x.strip() for x in row[1:6]) + (closed,))
    except (zipfile.BadZipFile, UnicodeError) as exc:
        raise DataError("invalid ZIP/CSV: {}".format(exc)) from exc
    return result


def validate_range(rows: Sequence[Tuple], start_ms: int, end_ms: int, interval_ms: int, now_ms: int) -> List[Tuple]:
    effective_end = min(end_ms, (now_ms // interval_ms) * interval_ms)
    if effective_end <= start_ms:
        raise DataError("requested range contains no completed candles")
    by_open: Dict[int, Tuple] = {}
    for row in rows:
        if not start_ms <= row[0] < effective_end or row[6] >= now_ms:
            continue
        previous = by_open.get(row[0])
        if previous is not None and previous != row:
            raise DataError("conflicting duplicate kline at {}".format(row[0]))
        by_open[row[0]] = row
    ordered = [by_open[key] for key in sorted(by_open)]
    expected = (effective_end - start_ms) // interval_ms
    if not ordered or ordered[0][0] != start_ms or ordered[-1][0] != effective_end - interval_ms or len(ordered) != expected:
        raise DataError("incomplete requested range: expected {} candles, got {}".format(expected, len(ordered)))
    for previous, current in zip(ordered, ordered[1:]):
        if current[0] - previous[0] != interval_ms:
            raise DataError("kline gap after {}".format(previous[0]))
    return ordered


def download(symbol: str, interval: str, start: date, end: date, output: Path, cache_dir: Path) -> dict:
    if not re.fullmatch(r"[A-Z0-9]{3,30}", symbol):
        raise DataError("symbol must contain 3-30 uppercase letters/digits")
    if interval not in INTERVAL_MS:
        raise DataError("unsupported fixed intraday/daily interval: {}".format(interval))
    if start >= end:
        raise DataError("start must be earlier than exclusive end")
    now = datetime.now(timezone.utc)
    if start > now.date():
        raise DataError("start cannot be in the future")
    if end > now.date() + timedelta(days=1):
        raise DataError("exclusive end cannot be later than tomorrow UTC")
    rows = []
    provenance = []
    month = date(start.year, start.month, 1)
    while month < end:
        next_month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
        basename = "{}-{}-{}.zip".format(symbol, interval, month.strftime("%Y-%m"))
        url = "{}/monthly/klines/{}/{}/{}".format(BASE_URL, symbol, interval, basename)
        print("Reading " + url, file=sys.stderr, flush=True)
        try:
            content, source = archive_bytes(url, cache_dir)
            rows.extend(archive_rows(content, basename, INTERVAL_MS[interval]))
            provenance.append(source)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            # The current month's monthly archive may not yet be published.
            day = max(start, month)
            while day < min(end, next_month, now.date()):
                basename = "{}-{}-{}.zip".format(symbol, interval, day.isoformat())
                url = "{}/daily/klines/{}/{}/{}".format(BASE_URL, symbol, interval, basename)
                print("Reading " + url, file=sys.stderr, flush=True)
                content, source = archive_bytes(url, cache_dir)
                rows.extend(archive_rows(content, basename, INTERVAL_MS[interval]))
                provenance.append(source)
                day += timedelta(days=1)
        month = next_month
    ordered = validate_range(rows, date_ms(start), date_ms(end), INTERVAL_MS[interval], int(now.timestamp() * 1000))
    csv_buffer = io.StringIO(newline="")
    writer = csv.writer(csv_buffer)
    writer.writerow(FIELDS)
    writer.writerows(ordered)
    csv_bytes = csv_buffer.getvalue().encode("utf-8")
    metadata = {
        "market": "Binance USD-M perpetual", "symbol": symbol, "interval": interval,
        "timezone": "UTC", "start_inclusive": start.isoformat(), "end_exclusive": end.isoformat(),
        "rows": len(ordered), "first_open_time_ms": ordered[0][0], "last_close_time_ms": ordered[-1][6],
        "downloaded_at_utc": now.isoformat(), "output_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "sources": provenance,
    }
    atomic_bytes(output, csv_bytes)
    atomic_bytes(Path(str(output) + ".metadata.json"), (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return metadata


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="ETHUSDT")
    parser.add_argument("--interval", default="5m", choices=sorted(INTERVAL_MS))
    parser.add_argument("--start", required=True, type=parse_date)
    parser.add_argument("--end", required=True, type=parse_date)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cache-dir", type=Path, default=Path(__file__).resolve().parent / "data" / "cache")
    args = parser.parse_args(argv)
    try:
        metadata = download(args.symbol, args.interval, args.start, args.end, args.output, args.cache_dir)
    except (DataError, urllib.error.URLError, OSError) as exc:
        parser.exit(1, "ERROR: {}\n".format(exc))
    print(json.dumps({key: metadata[key] for key in ("symbol", "interval", "rows", "start_inclusive", "end_exclusive", "output_sha256")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
