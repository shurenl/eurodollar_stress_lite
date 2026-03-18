"""
Stress Index Builder Module

Builds the Eurodollar Stress Index Lite (ESI-Lite) from calculated indicators.
"""

import logging
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class StressIndexBuilder:
    """Builder for ESI-Lite stress index."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize stress index builder.
        
        Args:
            config: Configuration dictionary from config.yaml
        """
        self.config = config
        self.stress_config = config.get("stress_index", {})
        self.indicator_config = config.get("indicators", {})
        self.formula_config = self.stress_config.get("formula", {})
        
        # Store results
        self.stress_index: Optional[pd.Series] = None
        self.contributions: Dict[str, pd.Series] = {}
        self.weights: Dict[str, float] = {}
        self.effective_weights: Dict[str, float] = {}
        self.weight_history: pd.DataFrame = pd.DataFrame()
        
        logger.info("Stress Index Builder initialized")

    def _get_output_start_date(self) -> Optional[pd.Timestamp]:
        """Get the configured output start date, if any."""
        start_date = self.indicator_config.get("start_date")
        if not start_date:
            return None

        try:
            return pd.Timestamp(start_date)
        except (TypeError, ValueError):
            logger.warning("Invalid indicators.start_date %r; ignoring output clipping", start_date)
            return None
    
    def build_index(
        self, 
        zscores: Dict[str, pd.Series],
        available_indicators: List[str]
    ) -> pd.Series:
        """
        Build stress index from z-scores.
        
        Args:
            zscores: Dictionary of z-score series
            available_indicators: List of available indicator IDs
            
        Returns:
            Stress index series (0-100 scale)
        """
        definitions = self.indicator_config.get("definitions", {})
        self.stress_index = None
        self.contributions = {}
        self.weights = {}
        self.effective_weights = {}
        self.weight_history = pd.DataFrame()
        
        # Get raw weights from config
        raw_weights = {
            ind_id: defn.get("weight", 0.0)
            for ind_id, defn in definitions.items()
        }
        
        # Filter to indicators that are configured, available, and have z-scores
        available_weights = {
            ind_id: weight 
            for ind_id, weight in raw_weights.items()
            if ind_id in available_indicators and ind_id in zscores and weight > 0
        }
        
        total_weight = sum(available_weights.values())
        if total_weight == 0:
            logger.error("No valid weights available for stress index calculation")
            return pd.Series(dtype=float)
        
        base_weights = pd.Series(available_weights, dtype=float)
        self.weights = base_weights.to_dict()
        
        logger.info(f"Using {len(base_weights)} indicators with dynamic renormalized weights")
        logger.info(f"Total configured raw weight: {float(base_weights.sum()):.4f}")
        
        # Create DataFrame with all z-scores
        zscore_df = pd.DataFrame({
            ind_id: zscores[ind_id]
            for ind_id in base_weights.index
        })
        
        # Renormalize on each date using only indicators available on that date.
        availability = zscore_df.notna()
        weight_mask = availability.mul(base_weights, axis=1)
        weight_sums = weight_mask.sum(axis=1)
        normalized_weights = weight_mask.div(weight_sums.replace(0, np.nan), axis=0)
        contribution_df = zscore_df.mul(normalized_weights)
        weighted_z = contribution_df.sum(axis=1, min_count=1)

        valid_dates = weighted_z.dropna().index
        output_start_date = self._get_output_start_date()
        if output_start_date is not None:
            valid_dates = valid_dates[valid_dates >= output_start_date]

        if len(valid_dates) == 0:
            logger.error("No valid stress index observations remain after filtering")
            self.weight_history = pd.DataFrame()
            self.contributions = {}
            self.effective_weights = {}
            self.stress_index = pd.Series(dtype=float)
            return self.stress_index

        normalized_weights = normalized_weights.loc[valid_dates]
        contribution_df = contribution_df.loc[valid_dates]
        weighted_z = weighted_z.loc[valid_dates]

        self.weight_history = normalized_weights

        latest_weight_row = normalized_weights.dropna(how="all").tail(1)
        self.effective_weights = (
            latest_weight_row.iloc[0].dropna().to_dict()
            if not latest_weight_row.empty
            else {}
        )

        for ind_id in zscore_df.columns:
            self.contributions[ind_id] = contribution_df[ind_id]
        
        # Apply formula: clip(50 + 15 * weighted_z, 0, 100)
        base_score = self.formula_config.get("base_score", 50)
        multiplier = self.formula_config.get("multiplier", 15)
        min_score = self.formula_config.get("min_score", 0)
        max_score = self.formula_config.get("max_score", 100)
        
        stress_index = base_score + multiplier * weighted_z
        stress_index = stress_index.clip(lower=min_score, upper=max_score)
        
        self.stress_index = stress_index
        
        logger.info(f"Stress index calculated: {len(stress_index)} observations")
        logger.info(f"Latest value: {stress_index.iloc[-1]:.2f}")
        
        return stress_index
    
    def get_regime(self, score: float) -> Dict[str, Any]:
        """
        Determine risk regime from stress index score.
        
        Args:
            score: Stress index score (0-100)
            
        Returns:
            Dictionary with regime information
        """
        regimes = self.stress_config.get("regimes", {})
        
        for regime_id, regime_def in regimes.items():
            min_val = regime_def.get("min", 0)
            max_val = regime_def.get("max", 100)
            if min_val <= score < max_val:
                return {
                    "id": regime_id,
                    "label": regime_def.get("label", regime_id),
                    "color": regime_def.get("color", "#808080"),
                    "description": regime_def.get("description", ""),
                    "min": min_val,
                    "max": max_val,
                }
        
        # Default to stress if score >= 100
        if score >= 100:
            return {
                "id": "stress",
                "label": "Stress",
                "color": "#e74c3c",
                "description": "Maximum stress level",
                "min": 100,
                "max": 100,
            }
        
        # Default fallback
        return {
            "id": "unknown",
            "label": "Unknown",
            "color": "#808080",
            "description": "Unable to determine regime",
            "min": 0,
            "max": 100,
        }
    
    def get_changes(self, periods: List[int] = [5, 20]) -> Dict[str, Optional[float]]:
        """
        Calculate changes in stress index over specified periods.
        
        Args:
            periods: List of periods (in days) for change calculation
            
        Returns:
            Dictionary mapping period labels to change values
        """
        if self.stress_index is None or len(self.stress_index) == 0:
            return {f"change_{p}d": None for p in periods}
        
        changes = {}
        for period in periods:
            if len(self.stress_index) > period:
                change = self.stress_index.iloc[-1] - self.stress_index.iloc[-(period + 1)]
                changes[f"change_{period}d"] = change
            else:
                changes[f"change_{period}d"] = None
        
        return changes
    
    def get_top_contributors(
        self, 
        n: int = 3,
        direction: str = "positive"
    ) -> List[Dict[str, Any]]:
        """
        Get top contributors to stress index.
        
        Args:
            n: Number of top contributors to return
            direction: "positive" for stress contributors, "negative" for relief
            
        Returns:
            List of contributor dictionaries
        """
        if not self.contributions:
            return []
        
        # Get latest contribution values
        latest_contributions = {
            ind_id: contrib.iloc[-1] if len(contrib) > 0 else np.nan
            for ind_id, contrib in self.contributions.items()
        }
        latest_contributions = {
            ind_id: value
            for ind_id, value in latest_contributions.items()
            if pd.notna(value)
        }
        if not latest_contributions:
            return []
        
        # Sort by contribution value
        if direction == "positive":
            sorted_contribs = sorted(
                latest_contributions.items(),
                key=lambda x: x[1],
                reverse=True
            )
        else:
            sorted_contribs = sorted(
                latest_contributions.items(),
                key=lambda x: x[1]
            )
        
        # Get indicator definitions for names
        definitions = self.indicator_config.get("definitions", {})
        
        top_contributors = []
        for ind_id, contribution in sorted_contribs[:n]:
            ind_def = definitions.get(ind_id, {})
            top_contributors.append({
                "id": ind_id,
                "name": ind_def.get("name", ind_id),
                "contribution": contribution,
                "weight": self.effective_weights.get(ind_id, 0),
            })
        
        return top_contributors
    
    def get_historical_stats(self) -> Dict[str, Any]:
        """
        Calculate historical statistics for stress index.
        
        Returns:
            Dictionary with historical statistics
        """
        if self.stress_index is None or len(self.stress_index) == 0:
            return {}
        
        return {
            "mean": self.stress_index.mean(),
            "std": self.stress_index.std(),
            "min": self.stress_index.min(),
            "max": self.stress_index.max(),
            "percentile_5": self.stress_index.quantile(0.05),
            "percentile_95": self.stress_index.quantile(0.95),
            "current": self.stress_index.iloc[-1],
            "current_date": self.stress_index.index[-1].strftime("%Y-%m-%d"),
        }
    
    def check_historical_events(self) -> Dict[str, Any]:
        """
        Check stress index behavior around historical events.
        
        Returns:
            Dictionary with event analysis
        """
        events = self.config.get("historical_events", [])
        
        if self.stress_index is None or len(self.stress_index) == 0:
            return {"events": [], "note": "No stress index data available"}
        
        event_results = []
        for event in events:
            event_date = event.get("date", "")
            try:
                event_dt = pd.to_datetime(event_date)
                
                # Find closest available date
                if event_dt in self.stress_index.index:
                    score = self.stress_index[event_dt]
                else:
                    # Find nearest date
                    nearest_idx = self.stress_index.index.get_indexer([event_dt], method="nearest")[0]
                    if nearest_idx >= 0:
                        score = self.stress_index.iloc[nearest_idx]
                        event_dt = self.stress_index.index[nearest_idx]
                    else:
                        continue
                
                regime = self.get_regime(score)
                
                event_results.append({
                    "name": event.get("name", ""),
                    "date": event_date,
                    "nearest_date": event_dt.strftime("%Y-%m-%d"),
                    "score": score,
                    "regime": regime["label"],
                    "expected_regime": event.get("expected_regime", ""),
                    "validated": regime["id"] == event.get("expected_regime", ""),
                })
                
            except Exception as e:
                logger.warning(f"Error checking event {event.get('name', '')}: {e}")
        
        return {
            "events": event_results,
            "total_events": len(events),
            "validated_events": sum(1 for e in event_results if e.get("validated", False)),
        }
    
    def run_sanity_checks(self) -> Dict[str, Any]:
        """
        Run sanity checks on stress index.
        
        Returns:
            Dictionary with check results
        """
        checks_config = self.config.get("sanity_checks", {}).get("checks", {})
        results = {
            "passed": True,
            "checks": {},
        }
        
        if self.stress_index is None or len(self.stress_index) == 0:
            results["passed"] = False
            results["checks"]["data_available"] = {
                "passed": False,
                "error": "No stress index data available",
            }
            return results
        
        # Check index range
        if checks_config.get("index_range", {}).get("enabled", True):
            min_val = self.stress_index.min()
            max_val = self.stress_index.max()
            expected_min = checks_config.get("index_range", {}).get("min", 0)
            expected_max = checks_config.get("index_range", {}).get("max", 100)
            
            in_range = (min_val >= expected_min) and (max_val <= expected_max)
            results["checks"]["index_range"] = {
                "passed": in_range,
                "min_observed": min_val,
                "max_observed": max_val,
                "expected_range": [expected_min, expected_max],
            }
            if not in_range:
                results["passed"] = False
        
        # Check weight normalization
        if checks_config.get("weight_normalization", {}).get("enabled", True):
            total_weight = sum(self.effective_weights.values())
            tolerance = checks_config.get("weight_normalization", {}).get("tolerance", 0.001)
            normalized = abs(total_weight - 1.0) < tolerance
            
            results["checks"]["weight_normalization"] = {
                "passed": normalized,
                "total_weight": total_weight,
                "tolerance": tolerance,
            }
            if not normalized:
                results["passed"] = False
        
        logger.info(f"Stress index sanity checks passed: {results['passed']}")
        return results
