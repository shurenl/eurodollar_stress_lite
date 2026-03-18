"""
Tests for data source clients.
"""

from __future__ import annotations

import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_sources.bis_client import BISClient
from data_sources.fred_client import FREDClient


class TestDataClients(unittest.TestCase):
    """Client-level behaviour checks for reviewed fixes."""

    @patch("data_sources.fred_client.requests.get")
    def test_fred_uses_public_csv_without_api_key(self, mock_get: Mock) -> None:
        """FRED should remain usable without an API key."""
        mock_get.return_value = Mock(
            status_code=200,
            text="observation_date,SOFR\n2024-01-01,5.31\n2024-01-02,5.30\n",
        )
        mock_get.return_value.raise_for_status = Mock()

        client = FREDClient(
            {
                "api_key": "",
                "series": {"sofr": "SOFR"},
                "timeout": 5,
                "retry_attempts": 1,
            }
        )

        result = client.fetch_multiple()

        self.assertIn("sofr", result)
        self.assertIsNotNone(result["sofr"])
        self.assertEqual(result["sofr"].name, "SOFR")
        self.assertEqual(len(result["sofr"]), 2)

    @patch("data_sources.bis_client.requests.get")
    def test_bis_auto_mode_parses_official_csv(self, mock_get: Mock) -> None:
        """BIS auto mode should parse SDMX CSV payloads."""
        mock_get.return_value = Mock(
            status_code=200,
            text=(
                "TIME_PERIOD,OBS_VALUE\n"
                "2024-Q1,100\n"
                "2024-Q2,110\n"
                "2024-Q3,120\n"
            ),
        )
        mock_get.return_value.raise_for_status = Mock()

        client = BISClient(
            {
                "mode": "auto",
                "timeout": 5,
                "retry_attempts": 1,
                "freshness": {"enabled": False},
                "series": {
                    "usd_credit_yoy": {
                        "dataset": "BIS,WS_GLI,1.0",
                        "series_code": "Q.USD.3P.N.A.I.B.USD",
                    }
                },
            }
        )

        result = client.fetch_from_api("usd_credit_yoy")

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(result.index))
        self.assertAlmostEqual(float(result.iloc[-1]), 120.0)

    def test_bis_csv_fallback_rejects_stale_local_data(self) -> None:
        """Stale local BIS CSV data should not be treated as fresh output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "bis.csv"
            csv_path.write_text(
                "date,value\n2024-01-01,100\n2024-04-01,110\n",
                encoding="utf-8",
            )

            client = BISClient(
                {
                    "mode": "csv",
                    "csv_path": str(csv_path),
                    "freshness": {"enabled": True, "max_age_days": 30},
                    "series": {
                        "usd_credit_yoy": {
                            "dataset": "BIS,WS_GLI,1.0",
                            "series_code": "Q.USD.3P.N.A.I.B.USD",
                        }
                    },
                }
            )

            result = client.fetch_from_csv("usd_credit_yoy")

            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
