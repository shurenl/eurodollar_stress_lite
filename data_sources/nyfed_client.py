"""
New York Fed Client

Provides interface to fetch data from New York Fed Markets API.
"""

import logging
import time
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

import pandas as pd
import requests

logger = logging.getLogger(__name__)

DEFAULT_EFFR_PATH = "rates/unsecured/effr/search.json"
LEGACY_EFFR_PATHS = {
    "rates/all/fed-funds",
    "rates/all/fed-funds/",
}


class NYFedClient:
    """Client for fetching data from New York Fed API."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize NY Fed client.
        
        Args:
            config: Configuration dictionary from config.yaml
        """
        self.config = config
        self.base_url = config.get("base_url", "https://markets.newyorkfed.org/api")
        self.timeout = config.get("timeout", 30)
        self.retry_attempts = config.get("retry_attempts", 3)
        self.retry_delay = config.get("retry_delay", 2)
        
        self.series_config = config.get("series", {})
        
        logger.info("NY Fed Client initialized")

    def _get_effr_url(self) -> str:
        """
        Resolve the current EFFR search endpoint.

        The legacy `/rates/all/fed-funds` path now returns HTTP 400. This
        method normalizes legacy or incomplete config values to the live JSON
        search endpoint used for date-range requests.
        """
        configured_path = str(
            self.series_config.get("effective_fed_funds", DEFAULT_EFFR_PATH)
        ).strip()
        normalized_path = configured_path.strip("/")

        if (
            normalized_path in LEGACY_EFFR_PATHS
            or not normalized_path.endswith("search.json")
        ):
            if normalized_path and normalized_path != DEFAULT_EFFR_PATH:
                logger.info(
                    "Using updated NY Fed EFFR endpoint %s instead of legacy path %s",
                    DEFAULT_EFFR_PATH,
                    configured_path,
                )
            normalized_path = DEFAULT_EFFR_PATH

        return f"{self.base_url.rstrip('/')}/{normalized_path}"
    
    def fetch_effective_fed_funds(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.Series]:
        """
        Fetch Effective Federal Funds Rate from NY Fed.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            pandas Series with date index and values, or None if failed
        """
        # Set default dates
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
        
        url = self._get_effr_url()
        params = {
            "startDate": start_date,
            "endDate": end_date,
        }
        
        for attempt in range(self.retry_attempts):
            try:
                logger.debug(f"Fetching effective fed funds rate (attempt {attempt + 1})")
                response = requests.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                
                if "refRates" not in data:
                    logger.warning("No refRates found in NY Fed response")
                    return None
                
                rates = [
                    rate
                    for rate in data["refRates"]
                    if rate.get("type") in ("EFFR", None)
                ]
                if not rates:
                    logger.warning("No EFFR rows found in NY Fed response")
                    return None

                # Convert to pandas Series
                dates = [rate["effectiveDate"] for rate in rates]
                values = []
                for rate in rates:
                    val = rate.get("percentRate")
                    if val is None:
                        values.append(float("nan"))
                    else:
                        try:
                            values.append(float(val))
                        except (ValueError, TypeError):
                            values.append(float("nan"))
                
                series = pd.Series(
                    data=values,
                    index=pd.to_datetime(dates),
                    name="EFFR"
                )
                
                series = series.sort_index()
                series = series[~series.index.duplicated(keep="last")]
                series = series.dropna()
                
                if len(series) == 0:
                    logger.warning("No valid data for EFFR")
                    return None
                
                logger.info(f"Successfully fetched EFFR: {len(series)} observations")
                return series
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed for EFFR: {e}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    logger.error(f"Failed to fetch EFFR after {self.retry_attempts} attempts")
                    return None
            except Exception as e:
                logger.error(f"Unexpected error fetching EFFR: {e}")
                return None
        
        return None
    
    def fetch_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.Series]:
        """
        Fetch a time series from NY Fed.
        
        Args:
            series_id: Series identifier
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            pandas Series with date index and values, or None if failed
        """
        if series_id == "effective_fed_funds":
            return self.fetch_effective_fed_funds(start_date, end_date)
        
        logger.warning(f"Unknown NY Fed series: {series_id}")
        return None
    
    def check_availability(self) -> Dict[str, Any]:
        """
        Check if NY Fed API is available.
        
        Returns:
            Dictionary with availability status and details
        """
        status = {
            "available": False,
            "error": None,
        }
        
        try:
            # Try to fetch recent data
            test_series = self.fetch_effective_fed_funds(
                start_date=(datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            )
            if test_series is not None:
                status["available"] = True
            else:
                status["error"] = "Test fetch returned no data"
        except Exception as e:
            status["error"] = str(e)
        
        return status
