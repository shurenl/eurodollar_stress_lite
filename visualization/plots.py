"""
Plots Module

Provides matplotlib-based plotting functions for ESI-Lite.
"""

import logging
import os
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime

import matplotlib
# Use headless backend for GitHub Actions compatibility
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PlotManager:
    """Manager for creating all ESI-Lite plots."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize plot manager.
        
        Args:
            config: Configuration dictionary from config.yaml
        """
        self.config = config
        self.plot_config = config.get("output", {}).get("plots", {})
        self.output_dir = config.get("output", {}).get("directories", {}).get("plots", "outputs/plots")
        
        # Plot settings
        self.dpi = self.plot_config.get("dpi", 150)
        self.figsize = (
            self.plot_config.get("figsize_width", 12),
            self.plot_config.get("figsize_height", 6)
        )
        
        # Set style
        style = self.plot_config.get("style", "default")
        try:
            plt.style.use(style)
        except OSError:
            logger.warning(f"Style '{style}' not available, using default")
            plt.style.use("default")
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        logger.info(f"Plot Manager initialized (output: {self.output_dir})")
    
    def _save_figure(self, filename: str) -> str:
        """
        Save figure to output directory.
        
        Args:
            filename: Output filename
            
        Returns:
            Full path to saved file
        """
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=self.dpi, bbox_inches="tight")
        plt.close()
        logger.debug(f"Saved plot: {filepath}")
        return filepath
    
    def plot_stress_index(
        self, 
        stress_index: pd.Series,
        historical_events: Optional[List[Dict]] = None,
        filename: str = "stress_index.png"
    ) -> str:
        """
        Plot main stress index with regime shading.
        
        Args:
            stress_index: Stress index series
            historical_events: List of historical events to mark
            filename: Output filename
            
        Returns:
            Path to saved plot
        """
        fig, ax = plt.subplots(figsize=self.figsize)
        
        # Plot stress index
        ax.plot(stress_index.index, stress_index.values, 
                linewidth=2, color="#2c3e50", label="ESI-Lite")
        
        # Add regime shading
        regimes = self.config.get("stress_index", {}).get("regimes", {})
        for regime_id, regime in regimes.items():
            min_val = regime.get("min", 0)
            max_val = regime.get("max", 100)
            color = regime.get("color", "#808080")
            ax.axhspan(min_val, max_val, alpha=0.1, color=color)
        
        # Mark historical events
        if historical_events:
            for event in historical_events:
                event_date = event.get("date", "")
                try:
                    dt = pd.to_datetime(event_date)
                    if dt >= stress_index.index.min() and dt <= stress_index.index.max():
                        ax.axvline(x=dt, color="red", linestyle="--", alpha=0.7)
                        ax.text(dt, stress_index.max() * 0.9, event.get("name", ""),
                               rotation=90, fontsize=8, ha="right")
                except:
                    pass
        
        # Formatting
        ax.set_title("Eurodollar Stress Index Lite (ESI-Lite)", fontsize=14, fontweight="bold")
        ax.set_xlabel("Date", fontsize=10)
        ax.set_ylabel("Stress Score (0-100)", fontsize=10)
        ax.set_ylim(0, 100)
        ax.legend(loc="upper left")
        
        # Add current value annotation
        current_value = stress_index.iloc[-1]
        current_date = stress_index.index[-1]
        ax.annotate(f"{current_value:.1f}",
                   xy=(current_date, current_value),
                   xytext=(10, 10), textcoords="offset points",
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.7),
                   fontsize=10, fontweight="bold")
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        return self._save_figure(filename)
    
    def plot_indicator(
        self, 
        series: pd.Series,
        indicator_id: str,
        indicator_name: str,
        filename: Optional[str] = None
    ) -> str:
        """
        Plot a single indicator.
        
        Args:
            series: Indicator series
            indicator_id: Indicator identifier
            indicator_name: Human-readable name
            filename: Output filename (default: {indicator_id}.png)
            
        Returns:
            Path to saved plot
        """
        if filename is None:
            filename = f"{indicator_id}.png"
        
        fig, ax = plt.subplots(figsize=self.figsize)
        
        # Plot indicator
        ax.plot(series.index, series.values, linewidth=1.5, color="#3498db")
        
        # Add current value annotation
        current_value = series.iloc[-1]
        current_date = series.index[-1]
        ax.annotate(f"{current_value:.4f}",
                   xy=(current_date, current_value),
                   xytext=(10, 10), textcoords="offset points",
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.7),
                   fontsize=9)
        
        # Formatting
        ax.set_title(f"{indicator_name}", fontsize=12, fontweight="bold")
        ax.set_xlabel("Date", fontsize=10)
        ax.set_ylabel("Value", fontsize=10)
        ax.grid(True, alpha=0.3)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        return self._save_figure(filename)
    
    def plot_contributions(
        self, 
        contributions: Dict[str, pd.Series],
        effective_weights: Dict[str, float],
        filename: str = "contribution.png"
    ) -> str:
        """
        Plot indicator contributions to stress index.
        
        Args:
            contributions: Dictionary of contribution series
            effective_weights: Dictionary of effective weights
            filename: Output filename
            
        Returns:
            Path to saved plot
        """
        fig, ax = plt.subplots(figsize=self.figsize)
        
        # Create stacked area chart
        contrib_df = pd.DataFrame(contributions)
        contrib_df = contrib_df.fillna(0)
        
        # Only plot if we have data
        if len(contrib_df) > 0:
            ax.stackplot(contrib_df.index, 
                        *[contrib_df[col] for col in contrib_df.columns],
                        labels=contrib_df.columns,
                        alpha=0.7)
        
        # Formatting
        ax.set_title("Indicator Contributions to ESI-Lite", fontsize=12, fontweight="bold")
        ax.set_xlabel("Date", fontsize=10)
        ax.set_ylabel("Contribution", fontsize=10)
        ax.legend(loc="upper left", fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        return self._save_figure(filename)
    
    def plot_event_window(
        self, 
        stress_index: pd.Series,
        event_date: str,
        event_name: str,
        window_days: int = 30,
        filename: Optional[str] = None
    ) -> str:
        """
        Plot stress index around a specific event.
        
        Args:
            stress_index: Stress index series
            event_date: Event date (YYYY-MM-DD)
            event_name: Event name
            window_days: Days before and after event to show
            filename: Output filename
            
        Returns:
            Path to saved plot
        """
        if filename is None:
            filename = f"event_{event_date.replace('-', '')}.png"
        
        try:
            event_dt = pd.to_datetime(event_date)
        except:
            logger.warning(f"Invalid event date: {event_date}")
            return ""
        
        # Extract window
        start_date = event_dt - pd.Timedelta(days=window_days)
        end_date = event_dt + pd.Timedelta(days=window_days)
        
        window_data = stress_index[(stress_index.index >= start_date) & 
                                   (stress_index.index <= end_date)]
        
        if len(window_data) == 0:
            logger.warning(f"No data available for event window: {event_name}")
            return ""
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Plot stress index
        ax.plot(window_data.index, window_data.values, 
                linewidth=2, color="#2c3e50")
        
        # Mark event date
        ax.axvline(x=event_dt, color="red", linestyle="--", linewidth=2, label=event_name)
        
        # Add regime shading
        regimes = self.config.get("stress_index", {}).get("regimes", {})
        for regime_id, regime in regimes.items():
            min_val = regime.get("min", 0)
            max_val = regime.get("max", 100)
            color = regime.get("color", "#808080")
            ax.axhspan(min_val, max_val, alpha=0.1, color=color)
        
        # Formatting
        ax.set_title(f"ESI-Lite: {event_name} ({event_date})", fontsize=12, fontweight="bold")
        ax.set_xlabel("Date", fontsize=10)
        ax.set_ylabel("Stress Score", fontsize=10)
        ax.set_ylim(0, 100)
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return self._save_figure(filename)
    
    def plot_all_event_windows(
        self, 
        stress_index: pd.Series,
        events: List[Dict[str, Any]],
        window_days: int = 30
    ) -> List[str]:
        """
        Plot event windows for all historical events.
        
        Args:
            stress_index: Stress index series
            events: List of event dictionaries
            window_days: Days before and after event
            
        Returns:
            List of saved file paths
        """
        paths = []
        for event in events:
            path = self.plot_event_window(
                stress_index,
                event.get("date", ""),
                event.get("name", ""),
                window_days=window_days
            )
            if path:
                paths.append(path)
        
        return paths
    
    def plot_zscore(
        self, 
        zscore_series: pd.Series,
        indicator_id: str,
        indicator_name: str,
        filename: Optional[str] = None
    ) -> str:
        """
        Plot z-score for an indicator.
        
        Args:
            zscore_series: Z-score series
            indicator_id: Indicator identifier
            indicator_name: Human-readable name
            filename: Output filename
            
        Returns:
            Path to saved plot
        """
        if filename is None:
            filename = f"{indicator_id}_zscore.png"
        
        fig, ax = plt.subplots(figsize=self.figsize)
        
        # Plot z-score
        ax.plot(zscore_series.index, zscore_series.values, 
                linewidth=1.5, color="#9b59b6")
        
        # Add reference lines
        ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
        ax.axhline(y=2, color="orange", linestyle="--", linewidth=0.5, alpha=0.7)
        ax.axhline(y=-2, color="orange", linestyle="--", linewidth=0.5, alpha=0.7)
        ax.axhline(y=3, color="red", linestyle="--", linewidth=0.5, alpha=0.7)
        ax.axhline(y=-3, color="red", linestyle="--", linewidth=0.5, alpha=0.7)
        
        # Add current value annotation
        current_value = zscore_series.iloc[-1]
        current_date = zscore_series.index[-1]
        ax.annotate(f"{current_value:.2f}",
                   xy=(current_date, current_value),
                   xytext=(10, 10), textcoords="offset points",
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="plum", alpha=0.7),
                   fontsize=9)
        
        # Formatting
        ax.set_title(f"{indicator_name} (Z-Score)", fontsize=12, fontweight="bold")
        ax.set_xlabel("Date", fontsize=10)
        ax.set_ylabel("Z-Score", fontsize=10)
        ax.set_ylim(-3.5, 3.5)
        ax.grid(True, alpha=0.3)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        return self._save_figure(filename)
    
    def create_all_plots(
        self, 
        stress_index: pd.Series,
        indicators: Dict[str, pd.Series],
        zscores: Dict[str, pd.Series],
        contributions: Dict[str, pd.Series],
        effective_weights: Dict[str, float],
        indicator_metadata: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        """
        Create all required plots.
        
        Args:
            stress_index: Stress index series
            indicators: Dictionary of indicator series
            zscores: Dictionary of z-score series
            contributions: Dictionary of contribution series
            effective_weights: Dictionary of effective weights
            indicator_metadata: Dictionary of indicator metadata
            
        Returns:
            List of saved file paths
        """
        paths = []
        
        # Main stress index plot
        historical_events = self.config.get("historical_events", [])
        paths.append(self.plot_stress_index(stress_index, historical_events))
        
        # Contribution plot
        paths.append(self.plot_contributions(contributions, effective_weights))
        
        # Individual indicator plots
        for ind_id, series in indicators.items():
            meta = indicator_metadata.get(ind_id, {})
            name = meta.get("name", ind_id)
            
            # Plot indicator value
            paths.append(self.plot_indicator(series, ind_id, name))
            
            # Plot z-score if available
            if ind_id in zscores:
                paths.append(self.plot_zscore(zscores[ind_id], ind_id, name))
        
        # Event window plots
        event_paths = self.plot_all_event_windows(stress_index, historical_events)
        paths.extend(event_paths)
        
        logger.info(f"Created {len(paths)} plots")
        return paths
