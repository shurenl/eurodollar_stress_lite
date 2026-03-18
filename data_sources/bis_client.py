"""
BIS (Bank for International Settlements) client.

Supports:
- official BIS SDMX CSV downloads in auto mode
- local CSV fallback for manual maintenance
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from io import StringIO
from typing import Any, Dict, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


class BISClient:
    """Client for fetching BIS data."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.mode = config.get("mode", "auto")
        self.base_url = config.get("base_url", "https://stats.bis.org/api/v1")
        self.csv_path = config.get("csv_path", "data/bis_usd_credit.csv")
        self.timeout = int(config.get("timeout", 45))
        self.retry_attempts = int(config.get("retry_attempts", 3))
        self.retry_delay = int(config.get("retry_delay", 3))
        self.series_config = config.get("series", {})
        self.frequency_map = config.get("frequency", {})
        freshness_config = config.get("freshness", {})
        self.freshness_enabled = bool(freshness_config.get("enabled", True))
        self.max_age_days = int(freshness_config.get("max_age_days", 210))

        logger.info("BIS client initialized (mode: %s)", self.mode)

    @staticmethod
    def _parse_time_period(value: str) -> pd.Timestamp:
        """Parse BIS TIME_PERIOD values."""
        if isinstance(value, str) and "-Q" in value:
            return pd.Period(value, freq="Q").to_timestamp(how="end").normalize()
        return pd.to_datetime(value)

    def fetch_from_api(self, series_id: str) -> Optional[pd.Series]:
        """Fetch data from the official BIS SDMX endpoint."""
        series_config = self.series_config.get(series_id, {})
        dataset = series_config.get("dataset", "")
        series_code = series_config.get("series_code", "")
        period_column = series_config.get("period_column", "TIME_PERIOD")
        value_column = series_config.get("value_column", "OBS_VALUE")

        if not dataset or not series_code:
            logger.warning("Invalid BIS config for %s", series_id)
            return None

        url = f"{self.base_url}/data/{dataset}/{series_code}"

        for attempt in range(self.retry_attempts):
            try:
                response = requests.get(url, params={"format": "csvfile"}, timeout=self.timeout)
                response.raise_for_status()
                frame = pd.read_csv(StringIO(response.text))

                if period_column not in frame.columns or value_column not in frame.columns:
                    logger.warning(
                        "BIS response for %s missing %s or %s",
                        series_id,
                        period_column,
                        value_column,
                    )
                    return None

                frame["date"] = frame[period_column].map(self._parse_time_period)
                frame["value"] = pd.to_numeric(frame[value_column], errors="coerce")
                frame = frame.dropna(subset=["date", "value"]).sort_values("date")

                if frame.empty:
                    logger.warning("No valid BIS API data for %s", series_id)
                    return None

                series = pd.Series(frame["value"].to_numpy(), index=frame["date"], name=series_id)
                series = self._validate_freshness(series, series_id, source_label="api")
                if series is None:
                    return None
                logger.info("Fetched %s from BIS API: %s observations", series_id, len(series))
                return series
            except requests.exceptions.RequestException as exc:
                logger.warning("BIS API attempt %s failed for %s: %s", attempt + 1, series_id, exc)
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
            except Exception as exc:
                logger.error("Unexpected BIS API error for %s: %s", series_id, exc)
                return None

        logger.error("Failed to fetch %s from BIS API after %s attempts", series_id, self.retry_attempts)
        return None

    def fetch_from_csv(self, series_id: str) -> Optional[pd.Series]:
        """Fetch data from a local CSV fallback."""
        csv_path = os.path.expanduser(os.path.expandvars(self.csv_path))
        if not os.path.isabs(csv_path):
            csv_path = os.path.join(os.getcwd(), csv_path)

        if not os.path.exists(csv_path):
            logger.warning("BIS CSV file not found: %s", csv_path)
            return None

        try:
            frame = pd.read_csv(csv_path)
            if "date" not in frame.columns or "value" not in frame.columns:
                logger.warning("BIS CSV must contain date,value columns")
                return None

            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
            frame = frame.dropna(subset=["date", "value"]).sort_values("date")

            if frame.empty:
                logger.warning("No valid BIS CSV data for %s", series_id)
                return None

            series = pd.Series(frame["value"].to_numpy(), index=frame["date"], name=series_id)
            series = self._validate_freshness(series, series_id, source_label="csv")
            if series is None:
                return None
            logger.info("Loaded %s from BIS CSV: %s observations", series_id, len(series))
            return series
        except Exception as exc:
            logger.error("Error reading BIS CSV fallback for %s: %s", series_id, exc)
            return None

    def _validate_freshness(
        self,
        series: pd.Series,
        series_id: str,
        *,
        source_label: str,
    ) -> Optional[pd.Series]:
        """Reject stale BIS data so local fallbacks cannot masquerade as fresh output."""
        if not self.freshness_enabled or series.empty:
            return series

        latest_date = pd.Timestamp(series.index.max()).normalize()
        today = pd.Timestamp(datetime.now().date())
        age_days = int((today - latest_date).days)

        if age_days <= self.max_age_days:
            return series

        logger.warning(
            "Rejecting stale BIS %s data for %s: latest=%s age=%s days threshold=%s days",
            source_label,
            series_id,
            latest_date.strftime("%Y-%m-%d"),
            age_days,
            self.max_age_days,
        )
        return None

    def fetch_series(self, series_id: str) -> Optional[pd.Series]:
        """Fetch a BIS series with auto-to-CSV fallback."""
        if self.mode == "csv":
            return self.fetch_from_csv(series_id)

        result = self.fetch_from_api(series_id)
        if result is not None:
            return result

        logger.info("BIS API failed for %s, trying CSV fallback", series_id)
        return self.fetch_from_csv(series_id)

    def fetch_multiple(self, series_ids: Optional[list] = None) -> Dict[str, Optional[pd.Series]]:
        """Fetch multiple BIS series."""
        if series_ids is None:
            series_ids = list(self.series_config.keys())

        results: Dict[str, Optional[pd.Series]] = {}
        for series_id in series_ids:
            results[series_id] = self.fetch_series(series_id)
        return results

    def check_availability(self) -> Dict[str, Any]:
        """Check the currently configured BIS source path."""
        status = {
            "available": False,
            "mode": self.mode,
            "error": None,
        }

        try:
            if self.mode == "csv":
                sample = self.fetch_from_csv(next(iter(self.series_config.keys()), "usd_credit_yoy"))
            else:
                sample = self.fetch_series(next(iter(self.series_config.keys()), "usd_credit_yoy"))

            if sample is not None and not sample.empty:
                status["available"] = True
            else:
                status["error"] = "Test fetch returned no data"
        except Exception as exc:
            status["error"] = str(exc)

        return status
