"""
Indicator Calculations Module

Provides high-level interface for calculating all ESI-Lite indicators
from raw data sources.
"""

import logging
from typing import Dict, Optional, Any, List
from datetime import datetime

import numpy as np
import pandas as pd

from .transforms import (
    calculate_rolling_volatility,
    calculate_change,
    calculate_zscore,
    normalize_direction,
    forward_fill_low_frequency,
    check_empty_columns,
    check_consecutive_missing,
    check_zscore_infinity,
)

logger = logging.getLogger(__name__)


class IndicatorCalculator:
    """Calculator for all ESI-Lite indicators."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize indicator calculator.
        
        Args:
            config: Configuration dictionary from config.yaml
        """
        self.config = config
        self.indicator_config = config.get("indicators", {})
        self.rolling_config = self.indicator_config.get("rolling_window", {})
        self.zscore_config = config.get("stress_index", {}).get("standardization", {})
        
        # Store raw data
        self.raw_data: Dict[str, pd.Series] = {}
        
        # Store calculated indicators
        self.indicators: Dict[str, pd.Series] = {}
        self.zscores: Dict[str, pd.Series] = {}
        self.indicator_metadata: Dict[str, Dict[str, Any]] = {}
        
        logger.info("Indicator Calculator initialized")
    
    def load_raw_data(self, data: Dict[str, Optional[pd.Series]]) -> None:
        """
        Load raw data from data sources.
        
        Args:
            data: Dictionary mapping series names to pandas Series
        """
        for name, series in data.items():
            if series is not None and len(series) > 0:
                self.raw_data[name] = series
                logger.info(f"Loaded raw data: {name} ({len(series)} observations)")
            else:
                logger.warning(f"No data available for: {name}")
    
    def calculate_all(self) -> Dict[str, pd.Series]:
        """
        Calculate all indicators.
        
        Returns:
            Dictionary mapping indicator names to calculated series
        """
        definitions = self.indicator_config.get("definitions", {})
        
        for indicator_id, indicator_def in definitions.items():
            try:
                self._calculate_single_indicator(indicator_id, indicator_def)
            except Exception as e:
                logger.error(f"Failed to calculate indicator {indicator_id}: {e}")
                self.indicator_metadata[indicator_id] = {
                    "available": False,
                    "error": str(e),
                }
        
        logger.info(f"Calculated {len(self.indicators)} indicators")
        return self.indicators
    
    def _calculate_single_indicator(
        self, 
        indicator_id: str, 
        indicator_def: Dict[str, Any]
    ) -> None:
        """
        Calculate a single indicator.
        
        Args:
            indicator_id: Indicator identifier
            indicator_def: Indicator definition from config
        """
        source = indicator_def.get("source", "")
        direction = indicator_def.get("direction", "positive")
        frequency = indicator_def.get("frequency", "daily")
        is_low_freq = indicator_def.get("low_frequency", False)
        
        # Initialize metadata
        metadata = {
            "available": False,
            "source": source,
            "direction": direction,
            "frequency": frequency,
            "low_frequency": is_low_freq,
            "name": indicator_def.get("name", indicator_id),
        }
        
        # Calculate based on source type
        if source == "fred":
            series_id = indicator_def.get("series_id", "")
            if series_id in self.raw_data:
                raw_series = self._apply_transform(self.raw_data[series_id], indicator_def)
                processed_series = self._process_series(
                    raw_series, direction, is_low_freq
                )
                self.indicators[indicator_id] = processed_series
                metadata["available"] = True
                metadata["current_value"] = processed_series.iloc[-1] if len(processed_series) > 0 else None
            else:
                logger.warning(f"Raw data not available for {indicator_id} (series: {series_id})")
                
        elif source == "calculated":
            calculated = self._calculate_derived_indicator(indicator_id, indicator_def)
            if calculated is not None:
                processed_series = self._process_series(
                    calculated, direction, is_low_freq
                )
                self.indicators[indicator_id] = processed_series
                metadata["available"] = True
                metadata["current_value"] = processed_series.iloc[-1] if len(processed_series) > 0 else None
            else:
                logger.warning(f"Failed to calculate derived indicator: {indicator_id}")
                
        elif source == "bis":
            series_id = indicator_def.get("series_id", "")
            if series_id in self.raw_data:
                raw_series = self._apply_transform(self.raw_data[series_id], indicator_def)
                processed_series = self._process_series(
                    raw_series, direction, is_low_freq
                )
                self.indicators[indicator_id] = processed_series
                metadata["available"] = True
                metadata["current_value"] = processed_series.iloc[-1] if len(processed_series) > 0 else None
            else:
                logger.warning(f"Raw data not available for {indicator_id} (series: {series_id})")
        
        else:
            logger.warning(f"Unknown source type '{source}' for indicator {indicator_id}")
        
        self.indicator_metadata[indicator_id] = metadata

    def _apply_transform(self, series: pd.Series, indicator_def: Dict[str, Any]) -> pd.Series:
        """Apply optional per-indicator transforms before normalization."""
        transform = indicator_def.get("transform")
        if transform == "yoy":
            periods = int(indicator_def.get("transform_periods", 4))
            return series.pct_change(periods=periods) * 100.0
        return series
    
    def _process_series(
        self, 
        series: pd.Series, 
        direction: str,
        is_low_frequency: bool = False
    ) -> pd.Series:
        """
        Process a raw series: normalize direction and handle low frequency.
        
        Args:
            series: Raw time series
            direction: Direction normalization ("positive" or "inverse")
            is_low_frequency: Whether this is a low-frequency series
            
        Returns:
            Processed series
        """
        # Normalize direction
        processed = normalize_direction(series, direction)
        
        # Handle low frequency data
        if is_low_frequency:
            max_fill = self.config.get("sanity_checks", {}).get("checks", {}).get(
                "low_frequency_forward_fill", {}).get("max_fill_days", 95)
            processed, _ = forward_fill_low_frequency(
                processed, max_fill_days=max_fill, frequency="quarterly"
            )
        
        return processed
    
    def _calculate_derived_indicator(
        self, 
        indicator_id: str, 
        indicator_def: Dict[str, Any]
    ) -> Optional[pd.Series]:
        """
        Calculate a derived indicator from raw data.
        
        Args:
            indicator_id: Indicator identifier
            indicator_def: Indicator definition
            
        Returns:
            Calculated series or None if failed
        """
        depends_on = indicator_def.get("depends_on", [])
        
        if indicator_id == "sofr_obfr_spread":
            return self._calculate_spread("sofr", "obfr")
        
        elif indicator_id == "sofr_volatility_20d":
            window = self.rolling_config.get("volatility", 20)
            if "sofr" in self.raw_data:
                return calculate_rolling_volatility(self.raw_data["sofr"], window=window)
            return None
        
        elif indicator_id == "sofr_change_5d":
            periods = self.rolling_config.get("change_5d", 5)
            if "sofr" in self.raw_data:
                return calculate_change(self.raw_data["sofr"], periods=periods)
            return None
        
        elif indicator_id == "obfr_change_5d":
            periods = self.rolling_config.get("change_5d", 5)
            if "obfr" in self.raw_data:
                return calculate_change(self.raw_data["obfr"], periods=periods)
            return None
        
        elif indicator_id == "sofr30_minus_sofr":
            return self._calculate_spread("sofr30", "sofr")
        
        else:
            logger.warning(f"Unknown derived indicator: {indicator_id}")
            return None
    
    def _calculate_spread(
        self, 
        series1_name: str, 
        series2_name: str
    ) -> Optional[pd.Series]:
        """
        Calculate spread between two series.
        
        Args:
            series1_name: Name of first series
            series2_name: Name of second series
            
        Returns:
            Spread series or None if failed
        """
        if series1_name not in self.raw_data:
            logger.warning(f"Series {series1_name} not available for spread calculation")
            return None
        
        if series2_name not in self.raw_data:
            logger.warning(f"Series {series2_name} not available for spread calculation")
            return None
        
        series1 = self.raw_data[series1_name]
        series2 = self.raw_data[series2_name]
        
        # Align indices
        aligned1, aligned2 = series1.align(series2, join="inner")
        
        if len(aligned1) == 0:
            logger.warning("No overlapping dates for spread calculation")
            return None
        
        spread = aligned1 - aligned2
        spread.name = f"{series1_name}_{series2_name}_spread"
        
        logger.debug(f"Calculated spread: {spread.name}")
        return spread
    
    def calculate_zscores(self) -> Dict[str, pd.Series]:
        """
        Calculate z-scores for all indicators.
        
        Returns:
            Dictionary mapping indicator names to z-score series
        """
        window = self.rolling_config.get("zscore", 252)
        min_periods = self.zscore_config.get("min_observations", 60)
        clip_min = self.zscore_config.get("zscore_clip_min", -3.0)
        clip_max = self.zscore_config.get("zscore_clip_max", 3.0)
        
        for indicator_id, series in self.indicators.items():
            try:
                zscore = calculate_zscore(
                    series,
                    window=window,
                    min_periods=min_periods,
                    clip_range=(clip_min, clip_max)
                )
                self.zscores[indicator_id] = zscore
                
                # Update metadata with current z-score
                if indicator_id in self.indicator_metadata:
                    self.indicator_metadata[indicator_id]["current_zscore"] = (
                        zscore.iloc[-1] if len(zscore) > 0 else None
                    )
                
            except Exception as e:
                logger.error(f"Error calculating z-score for {indicator_id}: {e}")
        
        logger.info(f"Calculated z-scores for {len(self.zscores)} indicators")
        return self.zscores
    
    def get_available_indicators(self) -> List[str]:
        """
        Get list of available (successfully calculated) indicators.
        
        Returns:
            List of indicator IDs
        """
        return [
            ind_id for ind_id, meta in self.indicator_metadata.items()
            if meta.get("available", False)
        ]
    
    def get_missing_indicators(self) -> List[str]:
        """
        Get list of missing (failed) indicators.
        
        Returns:
            List of indicator IDs
        """
        return [
            ind_id for ind_id, meta in self.indicator_metadata.items()
            if not meta.get("available", False)
        ]
    
    def run_sanity_checks(self) -> Dict[str, Any]:
        """
        Run sanity checks on calculated indicators.
        
        Returns:
            Dictionary with check results
        """
        checks_config = self.config.get("sanity_checks", {}).get("checks", {})
        results = {
            "passed": True,
            "checks": {},
        }
        
        # Check empty columns
        if checks_config.get("empty_columns", {}).get("enabled", True):
            df = pd.DataFrame(self.indicators)
            empty_cols = check_empty_columns(
                df, 
                threshold=checks_config.get("empty_columns", {}).get("threshold", 0.9)
            )
            results["checks"]["empty_columns"] = {
                "passed": len(empty_cols) == 0,
                "empty_columns": empty_cols,
            }
            if empty_cols:
                results["passed"] = False
        
        # Check consecutive missing
        if checks_config.get("consecutive_missing", {}).get("enabled", True):
            consecutive_issues = []
            for ind_id, series in self.indicators.items():
                if check_consecutive_missing(
                    series,
                    threshold=checks_config.get("consecutive_missing", {}).get("threshold", 10)
                ):
                    consecutive_issues.append(ind_id)
            results["checks"]["consecutive_missing"] = {
                "passed": len(consecutive_issues) == 0,
                "issues": consecutive_issues,
            }
            if consecutive_issues:
                results["passed"] = False
        
        # Check z-score infinity
        if checks_config.get("zscore_infinity", {}).get("enabled", True):
            inf_issues = []
            for ind_id, zscore in self.zscores.items():
                if check_zscore_infinity(zscore):
                    inf_issues.append(ind_id)
            results["checks"]["zscore_infinity"] = {
                "passed": len(inf_issues) == 0,
                "issues": inf_issues,
            }
            if inf_issues:
                results["passed"] = False
        
        logger.info(f"Sanity checks passed: {results['passed']}")
        return results
