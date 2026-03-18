"""
Tests for indicator transforms module.
"""

import unittest
import numpy as np
import pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from indicators.transforms import (
    calculate_rolling_volatility,
    calculate_change,
    calculate_zscore,
    normalize_direction,
    forward_fill_low_frequency,
    check_empty_columns,
    check_consecutive_missing,
    check_zscore_infinity,
)


class TestTransforms(unittest.TestCase):
    """Test cases for transform functions."""
    
    def setUp(self):
        """Set up test data."""
        dates = pd.date_range(start="2020-01-01", periods=100, freq="D")
        self.test_series = pd.Series(
            np.random.randn(100).cumsum() + 100,
            index=dates,
            name="TEST"
        )
    
    def test_calculate_rolling_volatility(self):
        """Test rolling volatility calculation."""
        vol = calculate_rolling_volatility(self.test_series, window=20)
        
        # Should return a series
        self.assertIsInstance(vol, pd.Series)
        
        # First 19 values should be NaN (not enough data)
        self.assertTrue(vol.iloc[:19].isna().all())
        
        # Values should be non-negative
        self.assertTrue((vol.dropna() >= 0).all())
    
    def test_calculate_change(self):
        """Test change calculation."""
        change = calculate_change(self.test_series, periods=5)
        
        # Should return a series
        self.assertIsInstance(change, pd.Series)
        
        # First 5 values should be NaN
        self.assertTrue(change.iloc[:5].isna().all())
        
        # Manual check
        expected_change = self.test_series.iloc[5] - self.test_series.iloc[0]
        self.assertAlmostEqual(change.iloc[5], expected_change)
    
    def test_calculate_zscore(self):
        """Test z-score calculation."""
        zscore = calculate_zscore(self.test_series, window=20, min_periods=5)
        
        # Should return a series
        self.assertIsInstance(zscore, pd.Series)
        
        # Values should be clipped to [-3, 3]
        self.assertTrue((zscore.dropna() >= -3).all())
        self.assertTrue((zscore.dropna() <= 3).all())
    
    def test_normalize_direction_positive(self):
        """Test direction normalization (positive)."""
        normalized = normalize_direction(self.test_series, direction="positive")
        
        # Should return same series
        pd.testing.assert_series_equal(normalized, self.test_series)
    
    def test_normalize_direction_inverse(self):
        """Test direction normalization (inverse)."""
        normalized = normalize_direction(self.test_series, direction="inverse")
        
        # Should return negated series
        expected = -self.test_series
        pd.testing.assert_series_equal(normalized, expected)
    
    def test_forward_fill_low_frequency(self):
        """Test forward fill for low frequency data."""
        # Create quarterly data
        dates = pd.date_range(start="2020-01-01", periods=10, freq="QE")
        quarterly = pd.Series(np.random.randn(10), index=dates, name="QUARTERLY")
        
        filled, is_low_freq = forward_fill_low_frequency(quarterly, max_fill_days=95)
        
        # Should return daily frequency series
        self.assertEqual(filled.index.freqstr, "D")
        
        # Should be marked as low frequency
        self.assertTrue(is_low_freq)
        
        # Original values should be preserved
        for date in quarterly.index:
            self.assertAlmostEqual(filled[date], quarterly[date])
    
    def test_check_empty_columns(self):
        """Test empty columns check."""
        df = pd.DataFrame({
            "A": [1, 2, 3, 4, 5],
            "B": [np.nan, np.nan, np.nan, np.nan, np.nan],
            "C": [1, np.nan, 3, np.nan, 5],
        })
        
        empty_cols = check_empty_columns(df, threshold=0.8)
        
        # Column B should be flagged
        self.assertIn("B", empty_cols)
        
        # Column A should not be flagged
        self.assertNotIn("A", empty_cols)
    
    def test_check_consecutive_missing(self):
        """Test consecutive missing check."""
        series = pd.Series([1, 2, np.nan, np.nan, np.nan, np.nan, 3, 4, 5])
        
        result = check_consecutive_missing(series, threshold=3)
        
        # Should detect 4 consecutive missing
        self.assertTrue(result)
    
    def test_check_zscore_infinity(self):
        """Test z-score infinity check."""
        # Series with infinite values
        series_with_inf = pd.Series([1, 2, np.inf, 4, 5])
        
        result = check_zscore_infinity(series_with_inf)
        
        # Should detect infinity
        self.assertTrue(result)
        
        # Series without infinite values
        series_normal = pd.Series([1, 2, 3, 4, 5])
        
        result_normal = check_zscore_infinity(series_normal)
        
        # Should not detect infinity
        self.assertFalse(result_normal)


if __name__ == "__main__":
    unittest.main()
