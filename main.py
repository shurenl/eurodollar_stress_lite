"""
ESI-Lite Main Program

Entry point for the Eurodollar Stress Index Lite system.
Handles data fetching, processing, and report generation.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import yaml
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from data_sources import FREDClient, NYFedClient, BISClient, PremiumAdapter
from indicators import IndicatorCalculator, StressIndexBuilder, AvailabilityTracker
from visualization import PlotManager
from reporting import PDFReportGenerator, EmailSender, HTMLSummaryGenerator

# Configure logging
def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    """Setup logging configuration."""
    log_config = config.get("logging", {})
    level = getattr(logging, log_config.get("level", "INFO").upper())
    format_str = log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    
    # Add file handler if enabled
    file_handler_config = log_config.get("handlers", {}).get("file", {})
    if file_handler_config.get("enabled", False):
        filename = file_handler_config.get("filename", "esi_lite.log")
        file_handler = logging.FileHandler(filename)
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(format_str))
        logging.getLogger().addHandler(file_handler)
    
    return logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_directories(config: Dict[str, Any]) -> None:
    """Create necessary directories if they don't exist."""
    dirs = config.get("output", {}).get("directories", {})
    for dir_path in dirs.values():
        Path(dir_path).mkdir(parents=True, exist_ok=True)


class ESILitePipeline:
    """Main pipeline for ESI-Lite processing."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize pipeline with configuration."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize data sources
        self.fred_client = FREDClient(config.get("fred", {}))
        self.nyfed_client = NYFedClient(config.get("nyfed", {}))
        self.bis_client = BISClient(config.get("bis", {}))
        self.premium_adapter = PremiumAdapter(config.get("premium_indicators", {}))
        
        # Initialize processing components
        self.calculator = IndicatorCalculator(config)
        self.stress_builder = StressIndexBuilder(config)
        self.availability_tracker = AvailabilityTracker()
        
        # Initialize output components
        self.plot_manager = PlotManager(config)
        self.pdf_generator = PDFReportGenerator(config)
        self.email_sender = EmailSender(config)
        self.html_generator = HTMLSummaryGenerator(config)
        
        # Results storage
        self.raw_data: Dict[str, pd.Series] = {}
        self.indicators: Dict[str, pd.Series] = {}
        self.zscores: Dict[str, pd.Series] = {}
        self.stress_index: Optional[pd.Series] = None
        self.contributions: Dict[str, pd.Series] = {}
        
        self.logger.info("ESI-Lite Pipeline initialized")
    
    def fetch_data(self) -> Dict[str, Any]:
        """Fetch data from all sources."""
        self.logger.info("Starting data fetch...")
        
        # Fetch FRED data
        try:
            fred_data = self.fred_client.fetch_multiple()
            for series_id, series in fred_data.items():
                if series is not None:
                    self.raw_data[series_id.lower()] = series
            
            fred_status = self.fred_client.check_availability()
            self.availability_tracker.update_source_status("FRED", fred_status)
            self.logger.info(f"FRED data fetched: {len([s for s in fred_data.values() if s is not None])} series")
        except Exception as e:
            self.logger.error(f"Error fetching FRED data: {e}")
            self.availability_tracker.update_source_status("FRED", {"available": False, "error": str(e)})
        
        # Fetch NY Fed data
        try:
            nyfed_status = self.nyfed_client.check_availability()
            self.availability_tracker.update_source_status("NYFed", nyfed_status)
        except Exception as e:
            self.logger.error(f"Error checking NY Fed: {e}")
            self.availability_tracker.update_source_status("NYFed", {"available": False, "error": str(e)})
        
        # Fetch BIS data
        try:
            bis_data = self.bis_client.fetch_multiple()
            for series_id, series in bis_data.items():
                if series is not None:
                    self.raw_data[series_id] = series
            
            bis_status = self.bis_client.check_availability()
            self.availability_tracker.update_source_status("BIS", bis_status)
            self.logger.info(f"BIS data fetched: {len([s for s in bis_data.values() if s is not None])} series")
        except Exception as e:
            self.logger.error(f"Error fetching BIS data: {e}")
            self.availability_tracker.update_source_status("BIS", {"available": False, "error": str(e)})
        
        # Check premium sources (will be unavailable in free version)
        try:
            premium_status = self.premium_adapter.check_availability()
            self.availability_tracker.update_source_status("Premium", premium_status)
        except Exception as e:
            self.logger.error(f"Error checking premium sources: {e}")
            self.availability_tracker.update_source_status("Premium", {"available": False, "error": str(e)})
        
        self.logger.info(f"Total raw data series: {len(self.raw_data)}")
        return self.availability_tracker.get_summary()
    
    def calculate_indicators(self) -> Dict[str, Any]:
        """Calculate all indicators."""
        self.logger.info("Calculating indicators...")
        
        # Load raw data into calculator
        self.calculator.load_raw_data(self.raw_data)
        
        # Calculate indicators
        self.indicators = self.calculator.calculate_all()
        
        # Calculate z-scores
        self.zscores = self.calculator.calculate_zscores()
        
        # Update availability tracker
        for ind_id in self.calculator.get_available_indicators():
            meta = self.calculator.indicator_metadata.get(ind_id, {})
            self.availability_tracker.update_indicator_status(ind_id, meta)
        
        # Run sanity checks
        sanity_results = self.calculator.run_sanity_checks()
        
        self.logger.info(f"Indicators calculated: {len(self.indicators)}")
        self.logger.info(f"Z-scores calculated: {len(self.zscores)}")
        
        return {
            "indicators_calculated": len(self.indicators),
            "zscores_calculated": len(self.zscores),
            "sanity_checks": sanity_results,
        }
    
    def build_stress_index(self) -> Dict[str, Any]:
        """Build stress index from indicators."""
        self.logger.info("Building stress index...")
        
        available_indicators = self.calculator.get_available_indicators()
        
        if not available_indicators:
            self.logger.error("No indicators available for stress index calculation")
            return {"error": "No indicators available"}
        
        # Build stress index
        self.stress_index = self.stress_builder.build_index(
            self.zscores,
            available_indicators
        )
        
        # Store contributions
        self.contributions = self.stress_builder.contributions
        
        # Run sanity checks
        sanity_results = self.stress_builder.run_sanity_checks()
        
        self.logger.info(f"Stress index built: {len(self.stress_index)} observations")
        
        return {
            "stress_index_length": len(self.stress_index),
            "current_score": self.stress_index.iloc[-1] if len(self.stress_index) > 0 else None,
            "sanity_checks": sanity_results,
        }
    
    def create_visualizations(self) -> list:
        """Create all visualizations."""
        self.logger.info("Creating visualizations...")
        
        if self.stress_index is None or len(self.stress_index) == 0:
            self.logger.warning("No stress index data for visualization")
            return []
        
        plot_paths = self.plot_manager.create_all_plots(
            self.stress_index,
            self.indicators,
            self.zscores,
            self.contributions,
            self.stress_builder.effective_weights,
            self.calculator.indicator_metadata
        )
        
        self.logger.info(f"Created {len(plot_paths)} plots")
        return plot_paths
    
    def generate_outputs(self) -> Dict[str, Any]:
        """Generate all output files."""
        self.logger.info("Generating outputs...")
        
        # Prepare latest snapshot
        latest_snapshot = self._prepare_latest_snapshot()
        
        # Prepare history
        history = self._prepare_history()
        
        # Prepare indicator status
        indicator_status = self._prepare_indicator_status()
        
        # Prepare metadata
        metadata = self._prepare_metadata()
        
        # Save JSON outputs
        self._save_json_outputs(latest_snapshot, history, indicator_status, metadata)
        
        # Generate visualizations
        plot_files = self.create_visualizations()
        
        # Generate PDF report
        critical_output_errors = []
        try:
            pdf_path = self.pdf_generator.generate(
                latest_snapshot,
                history,
                indicator_status,
                metadata,
                plot_files
            )
            self.logger.info(f"PDF report generated: {pdf_path}")
        except Exception as e:
            self.logger.error(f"Error generating PDF: {e}")
            pdf_path = None
            critical_output_errors.append(f"PDF generation failed: {e}")
        
        # Generate HTML summary
        try:
            html_content = self.html_generator.generate(
                latest_snapshot,
                indicator_status,
                metadata
            )
            self.logger.info("HTML summary generated")
        except Exception as e:
            self.logger.error(f"Error generating HTML: {e}")
            html_content = None
            critical_output_errors.append(f"HTML summary generation failed: {e}")
        
        # Send email
        mail_status = {"configured": False, "success": False, "error": None}
        if self.email_sender.is_configured():
            try:
                mail_status = self.email_sender.send_report(
                    html_content or "",
                    pdf_attachment=pdf_path,
                    latest_snapshot=latest_snapshot
                )
                self.logger.info(f"Email send status: {mail_status}")
            except Exception as e:
                self.logger.error(f"Error sending email: {e}")
                mail_status["error"] = str(e)
        else:
            self.logger.info("Email not configured, skipping send")
        
        # Update metadata with mail status
        metadata["mail_status"] = mail_status
        self._save_metadata(metadata)

        if critical_output_errors:
            raise RuntimeError("; ".join(critical_output_errors))
        
        return {
            "latest_snapshot": latest_snapshot,
            "history": history,
            "indicator_status": indicator_status,
            "metadata": metadata,
            "pdf_path": pdf_path,
            "html_generated": html_content is not None,
            "mail_status": mail_status,
        }
    
    def _prepare_latest_snapshot(self) -> Dict[str, Any]:
        """Prepare latest snapshot data."""
        if self.stress_index is None or len(self.stress_index) == 0:
            return {}
        
        current_score = self.stress_index.iloc[-1]
        current_regime = self.stress_builder.get_regime(current_score)
        changes = self.stress_builder.get_changes([5, 20])
        
        snapshot = {
            "current_score": current_score,
            "current_regime": current_regime,
            "latest_date": self.stress_index.index[-1].strftime("%Y-%m-%d"),
            "change_5d": changes.get("change_5d"),
            "change_20d": changes.get("change_20d"),
            "available_indicators": self.calculator.get_available_indicators(),
            "missing_indicators": self.calculator.get_missing_indicators(),
            "top_stress_contributors": self.stress_builder.get_top_contributors(n=3, direction="positive"),
            "top_relief_contributors": self.stress_builder.get_top_contributors(n=3, direction="negative"),
            "source_status": self.availability_tracker.source_status,
        }
        
        # Add current indicator values
        snapshot["indicator_values"] = {}
        for ind_id, series in self.indicators.items():
            if len(series) > 0:
                snapshot["indicator_values"][ind_id] = series.iloc[-1]
        
        # Add current z-scores
        snapshot["zscores"] = {}
        for ind_id, series in self.zscores.items():
            if len(series) > 0:
                snapshot["zscores"][ind_id] = series.iloc[-1]
        
        # Add current contributions
        snapshot["contributions"] = {}
        for ind_id, series in self.contributions.items():
            if len(series) > 0:
                latest_value = series.iloc[-1]
                snapshot["contributions"][ind_id] = (
                    float(latest_value) if pd.notna(latest_value) else None
                )
        
        return snapshot
    
    def _prepare_history(self) -> Dict[str, Any]:
        """Prepare historical data."""
        if self.stress_index is None:
            return {}
        
        # Convert stress index to dict
        stress_history = {
            date.strftime("%Y-%m-%d"): float(value)
            for date, value in self.stress_index.items()
        }
        
        # Convert indicators to dict
        indicator_history = {}
        for ind_id, series in self.indicators.items():
            indicator_history[ind_id] = {
                date.strftime("%Y-%m-%d"): float(value) if pd.notna(value) else None
                for date, value in series.items()
            }
        
        # Convert z-scores to dict
        zscore_history = {}
        for ind_id, series in self.zscores.items():
            zscore_history[ind_id] = {
                date.strftime("%Y-%m-%d"): float(value) if pd.notna(value) else None
                for date, value in series.items()
            }
        
        # Historical stats
        hist_stats = self.stress_builder.get_historical_stats()
        
        # Historical events validation
        event_validation = self.stress_builder.check_historical_events()
        
        return {
            "stress_index": stress_history,
            "indicators": indicator_history,
            "zscores": zscore_history,
            "historical_stats": hist_stats,
            "historical_events": event_validation,
        }
    
    def _prepare_indicator_status(self) -> Dict[str, Any]:
        """Prepare indicator status data."""
        status = {}
        
        definitions = self.config.get("indicators", {}).get("definitions", {})
        
        for ind_id, ind_def in definitions.items():
            meta = self.calculator.indicator_metadata.get(ind_id, {})
            
            status[ind_id] = {
                "indicator": ind_def.get("name", ind_id),
                "description": ind_def.get("description", ""),
                "current_value": meta.get("current_value"),
                "z_score": meta.get("current_zscore"),
                "contribution": (
                    float(self.contributions[ind_id].iloc[-1])
                    if ind_id in self.contributions
                    and len(self.contributions[ind_id]) > 0
                    and pd.notna(self.contributions[ind_id].iloc[-1])
                    else None
                ),
                "weight_raw": ind_def.get("weight", 0),
                "weight_effective": self.stress_builder.effective_weights.get(ind_id),
                "source": ind_def.get("source", ""),
                "frequency": ind_def.get("frequency", ""),
                "available": meta.get("available", False),
                "low_frequency": ind_def.get("low_frequency", False),
            }
        
        return status
    
    def _prepare_metadata(self) -> Dict[str, Any]:
        """Prepare metadata."""
        return {
            "generated_at": datetime.now().isoformat(),
            "latest_date_in_data": self.stress_index.index[-1].strftime("%Y-%m-%d") 
                                   if self.stress_index is not None and len(self.stress_index) > 0 
                                   else None,
            "source_status": self.availability_tracker.source_status,
            "missing_indicators": self.calculator.get_missing_indicators(),
            "available_indicators": self.calculator.get_available_indicators(),
            "config_summary": {
                "version": self.config.get("stress_index", {}).get("version", "1.0.0"),
                "name": self.config.get("stress_index", {}).get("name", "ESI-Lite"),
            },
            "mail_status": {"configured": False, "success": False, "error": None},
        }
    
    def _save_json_outputs(
        self,
        latest_snapshot: Dict[str, Any],
        history: Dict[str, Any],
        indicator_status: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> None:
        """Save JSON output files."""
        output_files = self.config.get("output", {}).get("files", {})
        
        # Save latest snapshot
        snapshot_path = output_files.get("latest_snapshot", "dashboard_data/latest_snapshot.json")
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(latest_snapshot, f, indent=2, default=str)
        self.logger.info(f"Saved latest snapshot: {snapshot_path}")
        
        # Save history
        history_path = output_files.get("history", "dashboard_data/history.json")
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, default=str)
        self.logger.info(f"Saved history: {history_path}")
        
        # Save indicator status
        status_path = output_files.get("indicator_status", "dashboard_data/indicator_status.json")
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump(indicator_status, f, indent=2, default=str)
        self.logger.info(f"Saved indicator status: {status_path}")
        
        # Save metadata
        self._save_metadata(metadata)
    
    def _save_metadata(self, metadata: Dict[str, Any]) -> None:
        """Save metadata file."""
        metadata_path = self.config.get("output", {}).get("files", {}).get("metadata", "outputs/metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, default=str)
        self.logger.info(f"Saved metadata: {metadata_path}")
    
    def run(self) -> Dict[str, Any]:
        """Run the complete pipeline."""
        self.logger.info("=" * 60)
        self.logger.info("Starting ESI-Lite Pipeline")
        self.logger.info("=" * 60)
        
        try:
            # Step 1: Fetch data
            fetch_summary = self.fetch_data()
            self.logger.info(f"Data fetch summary: {fetch_summary}")
            
            # Step 2: Calculate indicators
            calc_results = self.calculate_indicators()
            self.logger.info(f"Calculation results: {calc_results}")
            
            # Step 3: Build stress index
            stress_results = self.build_stress_index()
            self.logger.info(f"Stress index results: {stress_results}")
            
            # Step 4: Generate outputs
            output_results = self.generate_outputs()
            
            self.logger.info("=" * 60)
            self.logger.info("ESI-Lite Pipeline Completed Successfully")
            self.logger.info("=" * 60)
            
            return {
                "success": True,
                "fetch_summary": fetch_summary,
                "calculation_results": calc_results,
                "stress_index_results": stress_results,
                "output_results": output_results,
            }
            
        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }


def main():
    """Main entry point."""
    # Load configuration
    config_path = os.getenv("ESI_LITE_CONFIG", "config.yaml")
    config = load_config(config_path)
    
    # Setup logging
    logger = setup_logging(config)
    
    # Ensure directories exist
    ensure_directories(config)
    
    # Run pipeline
    pipeline = ESILitePipeline(config)
    results = pipeline.run()
    
    # Exit with appropriate code
    if results.get("success", False):
        logger.info("ESI-Lite completed successfully")
        sys.exit(0)
    else:
        logger.error("ESI-Lite failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
