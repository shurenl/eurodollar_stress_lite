"""
Tests for indicator calculation behaviours introduced during review.
"""

from __future__ import annotations

import unittest

import pandas as pd

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from indicators.calculations import IndicatorCalculator


class TestIndicatorCalculations(unittest.TestCase):
    """Targeted calculation checks."""

    def test_bis_yoy_transform_is_applied(self) -> None:
        """BIS USD credit should be converted to YoY before normalization."""
        calculator = IndicatorCalculator(
            {
                "indicators": {
                    "rolling_window": {"zscore": 20},
                    "definitions": {
                        "bis_usd_credit_yoy": {
                            "name": "BIS USD Credit YoY",
                            "source": "bis",
                            "series_id": "usd_credit_yoy",
                            "direction": "positive",
                            "frequency": "quarterly",
                            "low_frequency": False,
                            "transform": "yoy",
                            "transform_periods": 4,
                        }
                    },
                },
                "stress_index": {
                    "standardization": {
                        "min_observations": 1,
                        "zscore_clip_min": -3.0,
                        "zscore_clip_max": 3.0,
                    }
                },
                "sanity_checks": {"checks": {}},
            }
        )

        dates = pd.period_range("2020Q1", periods=5, freq="Q").to_timestamp(how="end")
        series = pd.Series([100.0, 105.0, 110.0, 115.0, 140.0], index=dates, name="usd_credit_yoy")

        calculator.load_raw_data({"usd_credit_yoy": series})
        indicators = calculator.calculate_all()

        result = indicators["bis_usd_credit_yoy"]
        self.assertAlmostEqual(float(result.iloc[-1]), 40.0)


if __name__ == "__main__":
    unittest.main()
