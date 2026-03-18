"""
CSV Adapter

Provides interface to load data from local CSV files.
Useful for manual data import when APIs are unavailable.
"""

import logging
import os
from typing import Dict, Optional, Any
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


class CSVAdapter:
    """Adapter for loading data from CSV files."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize CSV adapter.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.data_dir = self.config.get("data_dir", "data")
        logger.info("CSV Adapter initialized")
    
    def load_series(
        self, 
        filepath: str,
        date_column: str = "date",
        value_column: str = "value",
        series_name: Optional[str] = None
    ) -> Optional[pd.Series]:
        """
        Load a time series from a CSV file.
        
        Args:
            filepath: Path to CSV file
            date_column: Name of date column
            value_column: Name of value column
            series_name: Name for the resulting series
            
        Returns:
            pandas Series with date index, or None if failed
        """
        # Expand path
        filepath = os.path.expandvars(filepath)
        filepath = os.path.expanduser(filepath)
        
        if not os.path.isabs(filepath):
            filepath = os.path.join(os.getcwd(), filepath)
        
        if not os.path.exists(filepath):
            logger.warning(f"CSV file not found: {filepath}")
            return None
        
        try:
            logger.debug(f"Loading data from CSV: {filepath}")
            df = pd.read_csv(filepath)
            
            if date_column not in df.columns:
                logger.warning(f"Date column '{date_column}' not found in {filepath}")
                return None
            
            if value_column not in df.columns:
                logger.warning(f"Value column '{value_column}' not found in {filepath}")
                return None
            
            # Parse dates
            df[date_column] = pd.to_datetime(df[date_column])
            df = df.set_index(date_column)
            df = df.sort_index()
            
            # Extract series
            series = df[value_column].copy()
            if series_name:
                series.name = series_name
            
            # Remove NaN values
            series = series.dropna()
            
            if len(series) == 0:
                logger.warning(f"No valid data in {filepath}")
                return None
            
            logger.info(f"Successfully loaded {series.name or 'series'} from CSV: {len(series)} observations")
            return series
            
        except Exception as e:
            logger.error(f"Error loading CSV file {filepath}: {e}")
            return None
    
    def save_series(
        self,
        series: pd.Series,
        filepath: str,
        date_column: str = "date",
        value_column: str = "value"
    ) -> bool:
        """
        Save a time series to a CSV file.
        
        Args:
            series: pandas Series to save
            filepath: Path to save CSV file
            date_column: Name for date column
            value_column: Name for value column
            
        Returns:
            True if successful, False otherwise
        """
        # Expand path
        filepath = os.path.expandvars(filepath)
        filepath = os.path.expanduser(filepath)
        
        if not os.path.isabs(filepath):
            filepath = os.path.join(os.getcwd(), filepath)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        try:
            df = pd.DataFrame({
                date_column: series.index,
                value_column: series.values
            })
            df.to_csv(filepath, index=False)
            logger.info(f"Successfully saved series to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving CSV file {filepath}: {e}")
            return False
    
    def check_availability(self) -> Dict[str, Any]:
        """
        Check if CSV data source is available.
        
        Returns:
            Dictionary with availability status
        """
        status = {
            "available": True,
            "data_dir": self.data_dir,
            "error": None,
        }
        
        data_dir = os.path.expandvars(os.path.expanduser(self.data_dir))
        if not os.path.isabs(data_dir):
            data_dir = os.path.join(os.getcwd(), data_dir)
        
        if not os.path.exists(data_dir):
            status["available"] = False
            status["error"] = f"Data directory not found: {data_dir}"
        
        return status
