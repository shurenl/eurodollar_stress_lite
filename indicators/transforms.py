"""
Indicator Transforms Module

Provides data transformation functions for calculating indicators:
- Rolling volatility
- Changes (5-day, 20-day)
- Z-score normalization
- Direction normalization
- Forward fill for low-frequency data
"""

import logging
from typing import Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_rolling_volatility(
    series: pd.Series,
    window: int = 20,
    min_periods: Optional[int] = None
) -> pd.Series:
    """
    Calculate rolling volatility (standard deviation).
    
    Args:
        series: Input time series
        window: Rolling window size
        min_periods: Minimum number of observations required
        
    Returns:
        Rolling volatility series
    """
    if series is None or len(series) == 0:
        logger.warning("Empty series provided for volatility calculation")
        return pd.Series(dtype=float)
    
    if min_periods is None:
        min_periods = window
    
    try:
        volatility = series.rolling(window=window, min_periods=min_periods).std()
        logger.debug(f"Calculated {window}-day volatility for {series.name}")
        return volatility
    except Exception as e:
        logger.error(f"Error calculating volatility: {e}")
        return pd.Series(dtype=float)


def calculate_change(
    series: pd.Series,
    periods: int = 5
) -> pd.Series:
    """
    Calculate change over specified periods.
    
    Args:
        series: Input time series
        periods: Number of periods for change calculation
        
    Returns:
        Change series
    """
    if series is None or len(series) == 0:
        logger.warning("Empty series provided for change calculation")
        return pd.Series(dtype=float)
    
    try:
        change = series.diff(periods=periods)
        logger.debug(f"Calculated {periods}-day change for {series.name}")
        return change
    except Exception as e:
        logger.error(f"Error calculating change: {e}")
        return pd.Series(dtype=float)


def calculate_zscore(
    series: pd.Series,
    window: int = 252,
    min_periods: int = 60,
    clip_range: Tuple[float, float] = (-3.0, 3.0)
) -> pd.Series:
    """
    Calculate rolling z-score.
    
    Z-score = (value - rolling_mean) / rolling_std
    
    Args:
        series: Input time series
        window: Rolling window size
        min_periods: Minimum observations required for calculation
        clip_range: Range to clip z-scores
        
    Returns:
        Z-score series
    """
    if series is None or len(series) == 0:
        logger.warning("Empty series provided for z-score calculation")
        return pd.Series(dtype=float)
    
    try:
        # Calculate rolling mean and std
        rolling_mean = series.rolling(window=window, min_periods=min_periods).mean()
        rolling_std = series.rolling(window=window, min_periods=min_periods).std()
        
        # Avoid division by zero
        rolling_std = rolling_std.replace(0, np.nan)
        
        # Calculate z-score
        zscore = (series - rolling_mean) / rolling_std
        
        # Clip to range
        zscore = zscore.clip(lower=clip_range[0], upper=clip_range[1])
        
        # Check for infinite values
        if np.isinf(zscore).any():
            logger.warning(f"Infinite values detected in z-score for {series.name}, replacing with NaN")
            zscore = zscore.replace([np.inf, -np.inf], np.nan)
        
        logger.debug(f"Calculated {window}-day z-score for {series.name}")
        return zscore
        
    except Exception as e:
        logger.error(f"Error calculating z-score: {e}")
        return pd.Series(dtype=float)


def normalize_direction(
    series: pd.Series,
    direction: str = "positive"
) -> pd.Series:
    """
    Normalize series direction so that higher values = more stress.
    
    Args:
        series: Input time series
        direction: "positive" (higher = more stress) or 
                   "inverse" (lower = more stress)
        
    Returns:
        Normalized series
    """
    if series is None or len(series) == 0:
        logger.warning("Empty series provided for direction normalization")
        return pd.Series(dtype=float)
    
    if direction == "positive":
        # Higher values = more stress, no change needed
        return series
    elif direction == "inverse":
        # Lower values = more stress, multiply by -1
        return -series
    else:
        logger.warning(f"Unknown direction '{direction}', returning original series")
        return series


def forward_fill_low_frequency(
    series: pd.Series,
    max_fill_days: int = 95,
    frequency: str = "quarterly"
) -> Tuple[pd.Series, bool]:
    """
    Forward fill low-frequency data (e.g., quarterly BIS data).
    
    Args:
        series: Input time series (low frequency)
        max_fill_days: Maximum number of days to forward fill
        frequency: Original frequency of the data
        
    Returns:
        Tuple of (filled_series, is_low_frequency_flag)
    """
    if series is None or len(series) == 0:
        logger.warning("Empty series provided for forward fill")
        return pd.Series(dtype=float), False
    
    try:
        # Create daily date range
        daily_index = pd.date_range(
            start=series.index.min(),
            end=series.index.max(),
            freq="D"
        )
        
        # Reindex to daily frequency
        daily_series = series.reindex(daily_index)
        
        # Forward fill with limit
        filled_series = daily_series.ffill(limit=max_fill_days)
        
        # Mark as low frequency
        is_low_frequency = True
        
        logger.debug(f"Forward filled {series.name} ({frequency}) to daily frequency")
        return filled_series, is_low_frequency
        
    except Exception as e:
        logger.error(f"Error forward filling series: {e}")
        return series, False


def check_empty_columns(
    df: pd.DataFrame,
    threshold: float = 0.9
) -> list:
    """
    Check for columns with excessive missing values.
    
    Args:
        df: Input DataFrame
        threshold: Missing value ratio threshold
        
    Returns:
        List of column names that exceed threshold
    """
    if df is None or df.empty:
        return []
    
    empty_cols = []
    for col in df.columns:
        missing_ratio = df[col].isna().sum() / len(df)
        if missing_ratio > threshold:
            empty_cols.append(col)
            logger.warning(f"Column '{col}' has {missing_ratio:.1%} missing values")
    
    return empty_cols


def check_consecutive_missing(
    series: pd.Series,
    threshold: int = 10
) -> bool:
    """
    Check for excessive consecutive missing values.
    
    Args:
        series: Input time series
        threshold: Maximum allowed consecutive missing values
        
    Returns:
        True if consecutive missing exceeds threshold
    """
    if series is None or len(series) == 0:
        return False
    
    # Find consecutive NaN runs
    is_na = series.isna()
    max_consecutive = 0
    current_consecutive = 0
    
    for is_missing in is_na:
        if is_missing:
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 0
    
    if max_consecutive > threshold:
        logger.warning(f"Series '{series.name}' has {max_consecutive} consecutive missing values")
        return True
    
    return False


def check_zscore_infinity(zscore_series: pd.Series) -> bool:
    """
    Check for infinite values in z-score series.
    
    Args:
        zscore_series: Z-score series
        
    Returns:
        True if infinite values found
    """
    if zscore_series is None or len(zscore_series) == 0:
        return False
    
    has_inf = np.isinf(zscore_series).any()
    if has_inf:
        inf_count = np.isinf(zscore_series).sum()
        logger.warning(f"Z-score series has {inf_count} infinite values")
    
    return has_inf
