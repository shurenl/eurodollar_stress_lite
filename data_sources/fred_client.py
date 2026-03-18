"""
FRED (Federal Reserve Economic Data) client.

Supports both the authenticated JSON API and the official public CSV endpoint.
The public CSV endpoint keeps the Lite version runnable without an API key.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta
from io import StringIO
from typing import Any, Dict, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


class FREDClient:
    """Client for fetching data from official FRED endpoints."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_url = config.get("base_url", "https://api.stlouisfed.org/fred")
        self.public_csv_url = config.get(
            "public_csv_url",
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
        )
        self.timeout = int(config.get("timeout", 30))
        self.retry_attempts = int(config.get("retry_attempts", 3))
        self.retry_delay = int(config.get("retry_delay", 2))

        api_key = config.get("api_key", "")
        if isinstance(api_key, str) and api_key.startswith("${") and api_key.endswith("}"):
            api_key = os.getenv(api_key[2:-1], "")
        self.api_key = api_key

        self.series_config = config.get("series", {})
        self.frequency_map = config.get("frequency", {})

        logger.info("FRED client initialized. API key present: %s", bool(self.api_key))

    def _fetch_series_from_api(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[pd.Series]:
        """Fetch a series from the authenticated JSON API."""
        if not self.api_key:
            return None

        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")

        url = f"{self.base_url}/series/observations"
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start_date,
            "observation_end": end_date,
        }

        for attempt in range(self.retry_attempts):
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                payload = response.json()

                observations = payload.get("observations", [])
                if not observations:
                    logger.warning("No API observations found for %s", series_id)
                    return None

                frame = pd.DataFrame(observations)
                frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
                frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
                frame = frame.dropna(subset=["date", "value"]).sort_values("date")

                if frame.empty:
                    logger.warning("No valid API data for %s", series_id)
                    return None

                series = pd.Series(frame["value"].to_numpy(), index=frame["date"], name=series_id)
                logger.info("Fetched %s from FRED API: %s observations", series_id, len(series))
                return series
            except requests.exceptions.RequestException as exc:
                logger.warning("FRED API attempt %s failed for %s: %s", attempt + 1, series_id, exc)
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
            except Exception as exc:
                logger.error("Unexpected FRED API error for %s: %s", series_id, exc)
                return None

        logger.error("Failed to fetch %s from FRED API after %s attempts", series_id, self.retry_attempts)
        return None

    def _fetch_series_from_csv(self, series_id: str) -> Optional[pd.Series]:
        """Fetch a series from the public FRED CSV endpoint."""
        url = self.public_csv_url.format(series_id=series_id)

        for attempt in range(self.retry_attempts):
            try:
                response = requests.get(url, timeout=self.timeout)
                response.raise_for_status()

                frame = pd.read_csv(StringIO(response.text))
                if frame.shape[1] < 2:
                    logger.warning("Unexpected CSV format for %s", series_id)
                    return None

                frame.columns = ["date", "value"]
                frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
                frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
                frame = frame.dropna(subset=["date", "value"]).sort_values("date")

                if frame.empty:
                    logger.warning("No valid CSV data for %s", series_id)
                    return None

                series = pd.Series(frame["value"].to_numpy(), index=frame["date"], name=series_id)
                logger.info("Fetched %s from public FRED CSV: %s observations", series_id, len(series))
                return series
            except requests.exceptions.RequestException as exc:
                logger.warning("FRED CSV attempt %s failed for %s: %s", attempt + 1, series_id, exc)
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
            except Exception as exc:
                logger.error("Unexpected FRED CSV error for %s: %s", series_id, exc)
                return None

        logger.error("Failed to fetch %s from public FRED CSV after %s attempts", series_id, self.retry_attempts)
        return None

    def fetch_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[pd.Series]:
        """Fetch a single FRED series with API-first / CSV-fallback logic."""
        series = self._fetch_series_from_api(series_id, start_date=start_date, end_date=end_date)
        if series is not None:
            return series

        if self.api_key:
            logger.warning("FRED API fetch failed for %s, falling back to public CSV", series_id)
        return self._fetch_series_from_csv(series_id)

    def fetch_multiple(
        self,
        series_ids: Optional[list] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Optional[pd.Series]]:
        """
        Fetch multiple series.

        Returns config aliases when `series_ids` is omitted so downstream code can
        depend on logical series names instead of raw FRED ids.
        """
        if series_ids is None:
            series_map = self.series_config
        else:
            series_map = {series_id: series_id for series_id in series_ids}

        results: Dict[str, Optional[pd.Series]] = {}
        for alias, series_id in series_map.items():
            results[alias] = self.fetch_series(series_id, start_date=start_date, end_date=end_date)
        return results

    def get_series_info(self, series_id: str) -> Optional[Dict[str, Any]]:
        """Return API metadata for a FRED series when an API key is configured."""
        if not self.api_key:
            logger.info("Skipping metadata lookup for %s because no API key is configured", series_id)
            return None

        url = f"{self.base_url}/series"
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            series_list = payload.get("seriess", [])
            return series_list[0] if series_list else None
        except Exception as exc:
            logger.error("Error fetching series info for %s: %s", series_id, exc)
            return None

    def check_availability(self) -> Dict[str, Any]:
        """Check whether at least one official FRED endpoint is reachable."""
        status = {
            "available": False,
            "api_key_present": bool(self.api_key),
            "mode": "api" if self.api_key else "public_csv",
            "error": None,
        }

        try:
            test_series = self.fetch_series(
                "SOFR",
                start_date=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
            )
            if test_series is not None and not test_series.empty:
                status["available"] = True
            else:
                status["error"] = "Test fetch returned no data"
        except Exception as exc:
            status["error"] = str(exc)

        return status
