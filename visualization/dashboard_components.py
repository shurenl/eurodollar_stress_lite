"""
Dashboard Components Module

Provides helper functions for Streamlit dashboard components.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


class DashboardComponents:
    """Helper class for creating dashboard components."""
    
    @staticmethod
    def format_stress_score(score: float) -> Dict[str, Any]:
        """
        Format stress score for display.
        
        Args:
            score: Stress index score
            
        Returns:
            Dictionary with formatted score and styling info
        """
        return {
            "value": f"{score:.1f}",
            "color": DashboardComponents._get_score_color(score),
        }
    
    @staticmethod
    def _get_score_color(score: float) -> str:
        """Get color based on stress score."""
        if score < 30:
            return "#2ecc71"  # Green
        elif score < 45:
            return "#27ae60"  # Dark green
        elif score < 60:
            return "#f39c12"  # Orange
        elif score < 75:
            return "#e67e22"  # Dark orange
        else:
            return "#e74c3c"  # Red
    
    @staticmethod
    def format_change(change: Optional[float]) -> Dict[str, str]:
        """
        Format change value for display.
        
        Args:
            change: Change value
            
        Returns:
            Dictionary with formatted change and direction
        """
        if change is None:
            return {"value": "N/A", "direction": "neutral"}
        
        sign = "+" if change > 0 else ""
        direction = "up" if change > 0 else "down" if change < 0 else "neutral"
        
        return {
            "value": f"{sign}{change:.2f}",
            "direction": direction,
        }
    
    @staticmethod
    def create_indicator_table(
        indicator_status: Dict[str, Any],
        indicator_metadata: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Create table data for indicator status.
        
        Args:
            indicator_status: Indicator status dictionary
            indicator_metadata: Indicator metadata dictionary
            
        Returns:
            List of row dictionaries for table display
        """
        table_data = []
        
        for ind_id, status in indicator_status.items():
            meta = indicator_metadata.get(ind_id, {})
            
            row = {
                "Indicator": meta.get("name", ind_id),
                "Current Value": status.get("current_value"),
                "Z-Score": status.get("z_score"),
                "Contribution": status.get("contribution"),
                "Weight": status.get("weight_effective"),
                "Available": "✓" if status.get("available", False) else "✗",
                "Source": status.get("source", ""),
            }
            table_data.append(row)
        
        return table_data
    
    @staticmethod
    def create_regime_legend(regimes: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Create legend data for risk regimes.
        
        Args:
            regimes: Regimes configuration dictionary
            
        Returns:
            List of regime dictionaries
        """
        legend = []
        for regime_id, regime in regimes.items():
            legend.append({
                "label": regime.get("label", regime_id),
                "range": f"{regime.get('min', 0)}-{regime.get('max', 100)}",
                "color": regime.get("color", "#808080"),
                "description": regime.get("description", ""),
            })
        return legend
    
    @staticmethod
    def create_source_status_cards(source_status: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Create card data for source status.
        
        Args:
            source_status: Source status dictionary
            
        Returns:
            List of source card dictionaries
        """
        cards = []
        for source_name, status in source_status.items():
            cards.append({
                "name": source_name,
                "available": "✓ Available" if status.get("available", False) else "✗ Unavailable",
                "status": status.get("error", "OK") if status.get("available", False) else status.get("error", "Unknown error"),
            })
        return cards
