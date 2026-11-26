import hashlib
import io
import unittest
import zipfile
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import binance_history as history


class HistoryTest(unittest.TestCase):
    def zipped(self, body, member="ETHUSDT-5m-2025-01.csv", extra=None):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(member, body)
            if extra:
                archive.writestr(extra, "ignored")
        return buffer.getvalue()

    def test_real_archive_shape_header_and_microseconds(self):
        body = "open_time,open,high,low,close,volume,close_time,quote_volume\n1735689600000000,10,12,9,11,2,1735689899999999,0\n"
        rows = history.archive_rows(self.zipped(body), "ETHUSDT-5m-2025-01.zip", 300000)
        self.assertEqual(rows, [(1735689600000, "10", "12", "9", "11", "2", 1735689899999)])

    def test_unsafe_zip_member_is_rejected_even_without_extraction(self):
        payload = self.zipped("", extra="../outside.csv")
        with self.assertRaisesRegex(history.DataError, "unsafe ZIP"):
            history.archive_rows(payload, "ETHUSDT-5m-2025-01.zip", 300000)

    def test_invalid_ohlc_and_nan_are_rejected(self):
        for price in ("10,9,8,11,2", "NaN,12,9,11,2"):
            body = "1735689600000,{},1735689899999\n".format(price)
            with self.assertRaises(history.DataError):
                history.archive_rows(self.zipped(body), "ETHUSDT-5m-2025-01.zip", 300000)

    def test_missing_internal_candle_is_not_silently_accepted(self):
        start = 1735689600000
        rows = [(start, "1", "1", "1", "1", "0", start + 299999),
                (start + 600000, "1", "1", "1", "1", "0", start + 899999)]
        with self.assertRaisesRegex(history.DataError, "incomplete"):
            history.validate_range(rows, start, start + 900000, 300000, start + 900001)

    def test_identical_duplicates_deduplicate_conflicts_reject(self):
        start = 1735689600000
        row = (start, "1", "1", "1", "1", "0", start + 299999)
        self.assertEqual(history.validate_range([row, row], start, start + 300000, 300000, start + 400000), [row])
        conflict = row[:5] + ("2", row[-1])
        with self.assertRaisesRegex(history.DataError, "conflicting duplicate"):
            history.validate_range([row, conflict], start, start + 300000, 300000, start + 400000)

    def test_unfinished_bar_is_excluded(self):
        start = 1735689600000
        rows = [(start + i * 300000, "1", "1", "1", "1", "0", start + (i + 1) * 300000 - 1) for i in range(2)]
        result = history.validate_range(rows, start, start + 600000, 300000, start + 450000)
        self.assertEqual(result, rows[:1])

    def test_corrupt_cached_checksum_stops_download(self):
        with TemporaryDirectory() as temporary:
            cache = Path(temporary)
            filename = "ETHUSDT-5m-2025-01.zip"
            (cache / filename).write_bytes(b"corrupt")
            (cache / (filename + ".CHECKSUM")).write_text("{}  {}\n".format(hashlib.sha256(b"good").hexdigest(), filename))
            with patch.object(history, "fetch", side_effect=AssertionError("no network expected")):
                with self.assertRaisesRegex(history.DataError, "SHA256 mismatch"):
                    history.archive_bytes("https://data.binance.vision/" + filename, cache)

    def test_date_must_be_exact_iso(self):
        self.assertEqual(history.parse_date("2025-01-01"), date(2025, 1, 1))
        for invalid in ("20250101", "2025-1-1", "2025-02-30", "2025-01-01T00:00"):
            with self.assertRaises(Exception):
                history.parse_date(invalid)


if __name__ == "__main__":
    unittest.main()
