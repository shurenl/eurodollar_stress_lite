"""
Availability Tracker Module

Tracks availability status of all data sources and indicators.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class AvailabilityTracker:
    """Tracks availability of data sources and indicators."""
    
    def __init__(self):
        """Initialize availability tracker."""
        self.source_status: Dict[str, Dict[str, Any]] = {}
        self.indicator_status: Dict[str, Dict[str, Any]] = {}
        self.last_update: Optional[str] = None
        
        logger.info("Availability Tracker initialized")
    
    def update_source_status(
        self, 
        source_name: str, 
        status: Dict[str, Any]
    ) -> None:
        """
        Update status for a data source.
        
        Args:
            source_name: Name of the data source
            status: Status dictionary
        """
        self.source_status[source_name] = {
            **status,
            "last_checked": datetime.now().isoformat(),
        }
    
    def update_indicator_status(
        self, 
        indicator_id: str, 
        status: Dict[str, Any]
    ) -> None:
        """
        Update status for an indicator.
        
        Args:
            indicator_id: Indicator identifier
            status: Status dictionary
        """
        self.indicator_status[indicator_id] = {
            **status,
            "last_updated": datetime.now().isoformat(),
        }
    
    def get_available_sources(self) -> List[str]:
        """
        Get list of available data sources.
        
        Returns:
            List of available source names
        """
        return [
            name for name, status in self.source_status.items()
            if status.get("available", False)
        ]
    
    def get_unavailable_sources(self) -> List[str]:
        """
        Get list of unavailable data sources.
        
        Returns:
            List of unavailable source names
        """
        return [
            name for name, status in self.source_status.items()
            if not status.get("available", False)
        ]
    
    def get_available_indicators(self) -> List[str]:
        """
        Get list of available indicators.
        
        Returns:
            List of available indicator IDs
        """
        return [
            ind_id for ind_id, status in self.indicator_status.items()
            if status.get("available", False)
        ]
    
    def get_unavailable_indicators(self) -> List[Dict[str, Any]]:
        """
        Get list of unavailable indicators with details.
        
        Returns:
            List of unavailable indicator dictionaries
        """
        unavailable = []
        for ind_id, status in self.indicator_status.items():
            if not status.get("available", False):
                unavailable.append({
                    "id": ind_id,
                    "error": status.get("error", "Unknown error"),
                    "source": status.get("source", "unknown"),
                })
        return unavailable
    
    def get_low_frequency_indicators(self) -> List[Dict[str, Any]]:
        """
        Get list of low-frequency indicators.
        
        Returns:
            List of low-frequency indicator dictionaries
        """
        low_freq = []
        for ind_id, status in self.indicator_status.items():
            if status.get("low_frequency", False) and status.get("available", False):
                low_freq.append({
                    "id": ind_id,
                    "name": status.get("name", ind_id),
                    "frequency": status.get("frequency", "unknown"),
                })
        return low_freq
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get availability summary.
        
        Returns:
            Dictionary with availability summary
        """
        total_sources = len(self.source_status)
        available_sources = len(self.get_available_sources())
        
        total_indicators = len(self.indicator_status)
        available_indicators = len(self.get_available_indicators())
        
        return {
            "sources": {
                "total": total_sources,
                "available": available_sources,
                "unavailable": total_sources - available_sources,
            },
            "indicators": {
                "total": total_indicators,
                "available": available_indicators,
                "unavailable": total_indicators - available_indicators,
            },
            "last_update": self.last_update,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert tracker state to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            "source_status": self.source_status,
            "indicator_status": self.indicator_status,
            "last_update": self.last_update,
            "summary": self.get_summary(),
        }
