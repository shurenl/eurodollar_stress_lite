"""
Data Sources Module for ESI-Lite

This module provides unified interfaces for fetching data from various sources:
- FRED (Federal Reserve Economic Data)
- New York Fed
- BIS (Bank for International Settlements)
- CSV files (for manual data import)
- Premium data sources (for future expansion)
"""

from .fred_client import FREDClient
from .nyfed_client import NYFedClient
from .bis_client import BISClient
from .csv_adapter import CSVAdapter
from .premium_adapter import PremiumAdapter

__all__ = [
    "FREDClient",
    "NYFedClient", 
    "BISClient",
    "CSVAdapter",
    "PremiumAdapter",
]
