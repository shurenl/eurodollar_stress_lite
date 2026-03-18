"""
Premium Adapter

Provides unified interface for premium data sources.
This is a placeholder for future expansion to support:
- Bloomberg
- Refinitiv (Reuters)
- Wind/iFinD
- CSV files with premium data

All premium indicators are disabled by default in the free version.
"""

import logging
import os
from typing import Dict, Optional, Any, Protocol
from datetime import datetime
from abc import ABC, abstractmethod

import pandas as pd

logger = logging.getLogger(__name__)


class PremiumDataSource(ABC):
    """Abstract base class for premium data sources."""
    
    @abstractmethod
    def fetch_series(self, series_id: str, **kwargs) -> Optional[pd.Series]:
        """Fetch a time series."""
        pass
    
    @abstractmethod
    def check_availability(self) -> Dict[str, Any]:
        """Check if data source is available."""
        pass


class BloombergSource(PremiumDataSource):
    """Bloomberg data source (placeholder)."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", False)
        logger.info(f"Bloomberg source initialized (enabled: {self.enabled})")
    
    def fetch_series(self, series_id: str, **kwargs) -> Optional[pd.Series]:
        if not self.enabled:
            logger.debug(f"Bloomberg source disabled, cannot fetch {series_id}")
            return None
        
        logger.warning(f"Bloomberg fetch not implemented for {series_id}")
        # TODO: Implement Bloomberg API integration
        return None
    
    def check_availability(self) -> Dict[str, Any]:
        return {
            "source": "Bloomberg",
            "available": False,
            "enabled": self.enabled,
            "error": "Not implemented in free version",
        }


class RefinitivSource(PremiumDataSource):
    """Refinitiv (Reuters) data source (placeholder)."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", False)
        logger.info(f"Refinitiv source initialized (enabled: {self.enabled})")
    
    def fetch_series(self, series_id: str, **kwargs) -> Optional[pd.Series]:
        if not self.enabled:
            logger.debug(f"Refinitiv source disabled, cannot fetch {series_id}")
            return None
        
        logger.warning(f"Refinitiv fetch not implemented for {series_id}")
        # TODO: Implement Refinitiv API integration
        return None
    
    def check_availability(self) -> Dict[str, Any]:
        return {
            "source": "Refinitiv",
            "available": False,
            "enabled": self.enabled,
            "error": "Not implemented in free version",
        }


class WindSource(PremiumDataSource):
    """Wind/iFinD data source (placeholder)."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", False)
        logger.info(f"Wind source initialized (enabled: {self.enabled})")
    
    def fetch_series(self, series_id: str, **kwargs) -> Optional[pd.Series]:
        if not self.enabled:
            logger.debug(f"Wind source disabled, cannot fetch {series_id}")
            return None
        
        logger.warning(f"Wind fetch not implemented for {series_id}")
        # TODO: Implement Wind API integration
        return None
    
    def check_availability(self) -> Dict[str, Any]:
        return {
            "source": "Wind/iFinD",
            "available": False,
            "enabled": self.enabled,
            "error": "Not implemented in free version",
        }


class PremiumCSVSource(PremiumDataSource):
    """
    CSV-based premium data source.
    Allows loading premium indicator data from manually maintained CSV files.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", False)
        self.data_dir = config.get("data_dir", "data/premium")
        logger.info(f"Premium CSV source initialized (enabled: {self.enabled})")
    
    def fetch_series(self, series_id: str, **kwargs) -> Optional[pd.Series]:
        if not self.enabled:
            logger.debug(f"Premium CSV source disabled, cannot fetch {series_id}")
            return None
        
        # Look for CSV file named after series_id
        filepath = os.path.join(self.data_dir, f"{series_id}.csv")
        filepath = os.path.expandvars(filepath)
        filepath = os.path.expanduser(filepath)
        
        if not os.path.isabs(filepath):
            filepath = os.path.join(os.getcwd(), filepath)
        
        if not os.path.exists(filepath):
            logger.debug(f"Premium CSV file not found: {filepath}")
            return None
        
        try:
            logger.debug(f"Loading premium data from CSV: {filepath}")
            df = pd.read_csv(filepath)
            
            if "date" not in df.columns or "value" not in df.columns:
                logger.warning(f"Premium CSV must have 'date' and 'value' columns")
                return None
            
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            df = df.sort_index()
            
            series = df["value"].copy()
            series.name = series_id
            series = series.dropna()
            
            if len(series) == 0:
                logger.warning(f"No valid data in premium CSV for {series_id}")
                return None
            
            logger.info(f"Successfully loaded premium {series_id} from CSV: {len(series)} observations")
            return series
            
        except Exception as e:
            logger.error(f"Error loading premium CSV file {filepath}: {e}")
            return None
    
    def check_availability(self) -> Dict[str, Any]:
        status = {
            "source": "Premium CSV",
            "available": False,
            "enabled": self.enabled,
            "data_dir": self.data_dir,
            "error": None,
        }
        
        if not self.enabled:
            status["error"] = "Source disabled"
            return status
        
        data_dir = os.path.expandvars(os.path.expanduser(self.data_dir))
        if not os.path.isabs(data_dir):
            data_dir = os.path.join(os.getcwd(), data_dir)
        
        if os.path.exists(data_dir):
            status["available"] = True
        else:
            status["error"] = f"Data directory not found: {data_dir}"
        
        return status


class PremiumAdapter:
    """
    Unified adapter for all premium data sources.
    
    This adapter provides a single interface for accessing premium indicators,
    with automatic fallback between different sources.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize premium adapter.
        
        Args:
            config: Configuration dictionary from config.yaml
        """
        self.config = config
        self.enabled = config.get("enabled", False)
        
        # Initialize data sources
        self.sources = {
            "bloomberg": BloombergSource(config.get("bloomberg", {})),
            "refinitiv": RefinitivSource(config.get("refinitiv", {})),
            "wind": WindSource(config.get("wind", {})),
            "csv": PremiumCSVSource(config.get("csv", {})),
        }
        
        # Indicator to source mapping
        self.indicator_sources = {
            "fra_ois": ["csv", "bloomberg", "refinitiv"],
            "cp_ois": ["csv", "bloomberg", "refinitiv"],
            "eur_usd_basis": ["csv", "bloomberg", "refinitiv"],
            "usd_jpy_basis": ["csv", "bloomberg", "refinitiv"],
            "on_rrp": ["csv", "bloomberg"],
            "srf": ["csv", "bloomberg"],
        }
        
        logger.info(f"Premium Adapter initialized (enabled: {self.enabled})")
    
    def fetch_series(
        self, 
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.Series]:
        """
        Fetch a premium time series.
        
        Args:
            series_id: Premium series identifier
            start_date: Start date (not used in free version)
            end_date: End date (not used in free version)
            
        Returns:
            pandas Series with date index, or None if not available
        """
        if not self.enabled:
            logger.debug(f"Premium adapter disabled, cannot fetch {series_id}")
            return None
        
        # Try each source in order
        sources_to_try = self.indicator_sources.get(series_id, ["csv"])
        
        for source_name in sources_to_try:
            source = self.sources.get(source_name)
            if source:
                result = source.fetch_series(series_id)
                if result is not None:
                    return result
        
        logger.debug(f"Premium series {series_id} not available from any source")
        return None
    
    def fetch_multiple(
        self, 
        series_ids: Optional[list] = None
    ) -> Dict[str, Optional[pd.Series]]:
        """
        Fetch multiple premium time series.
        
        Args:
            series_ids: List of series IDs. If None, tries all configured indicators.
            
        Returns:
            Dictionary mapping series IDs to pandas Series (or None if failed)
        """
        if series_ids is None:
            series_ids = list(self.indicator_sources.keys())
        
        results = {}
        for series_id in series_ids:
            results[series_id] = self.fetch_series(series_id)
        
        return results
    
    def check_availability(self) -> Dict[str, Any]:
        """
        Check availability of all premium data sources.
        
        Returns:
            Dictionary with availability status for each source
        """
        status = {
            "enabled": self.enabled,
            "sources": {},
            "any_available": False,
        }
        
        for name, source in self.sources.items():
            source_status = source.check_availability()
            status["sources"][name] = source_status
            if source_status.get("available", False):
                status["any_available"] = True
        
        return status
    
    def get_supported_indicators(self) -> Dict[str, Dict[str, Any]]:
        """
        Get list of supported premium indicators.
        
        Returns:
            Dictionary with indicator definitions
        """
        indicators = self.config.get("definitions", {})
        return {
            name: defn for name, defn in indicators.items()
            if self.enabled
        }
