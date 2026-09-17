import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from database_sync import sync_csv_to_database


class FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: {self.text}")


class DatabaseSyncCompatibilityTest(unittest.TestCase):
    def test_sync_falls_back_when_rain_columns_are_missing(self):
        csv_file = Path(tempfile.gettempdir()) / "leituras_compat.csv"
        state_file = Path(tempfile.gettempdir()) / "ultima_sincronizacao_compat.json"
        csv_file.write_text(
            "data,hora,chuva_acumulada,taxa_chuva,temperatura,umidade\n"
            "16/09/2026,21:08:00,0.6,0.0,21.9,85.0\n",
            encoding="utf-8",
        )
        if state_file.exists():
            state_file.unlink()

        calls = []

        def fake_post(url, json, headers, timeout):
            calls.append(json)
            if len(calls) == 1:
                raise RuntimeError("Missing rain columns")
            return FakeResponse(200)

        with patch("database_sync.requests.post", side_effect=fake_post), patch(
            "database_sync.get_supabase_config", return_value=("https://example.com", "token")
        ):
            with self.assertRaises(RuntimeError):
                sync_csv_to_database(csv_file, state_file)

        # This assertion documents the desired behavior: old schemas should be retried without rain fields.
        self.assertEqual(len(calls), 2)

        if csv_file.exists():
            csv_file.unlink()
        if state_file.exists():
            state_file.unlink()


if __name__ == "__main__":
    unittest.main()
