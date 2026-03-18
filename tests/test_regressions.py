"""
Regression tests for reviewed failure modes.
"""

from __future__ import annotations

import base64
import os
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_sources.nyfed_client import NYFedClient
from indicators.stress_index import StressIndexBuilder
from reporting.email_report import EmailSender
from reporting.html_summary import HTMLSummaryGenerator
from reporting.pdf_report import PDFReportGenerator


class TestReviewRegressions(unittest.TestCase):
    """Targeted regression coverage for review findings."""

    def test_email_sender_falls_back_when_smtp_port_env_is_missing(self) -> None:
        """SMTP placeholder config should not crash initialization."""
        config = {
            "email": {
                "smtp": {
                    "host": "${SMTP_HOST}",
                    "port": "${SMTP_PORT}",
                    "user": "${SMTP_USER}",
                    "password": "${SMTP_PASSWORD}",
                },
                "addresses": {
                    "from": "${MAIL_FROM}",
                    "to": "${MAIL_TO}",
                },
            }
        }

        with patch.dict(os.environ, {}, clear=False):
            sender = EmailSender(config)

        self.assertEqual(sender.smtp_port, 587)
        self.assertFalse(sender.is_configured())

    def test_stress_index_renormalizes_per_day_and_ignores_zero_weight_only_dates(self) -> None:
        """Missing indicators should renormalize remaining weights on each date."""
        builder = StressIndexBuilder(
            {
                "indicators": {
                    "start_date": "2024-01-01",
                    "definitions": {
                        "a": {"name": "A", "weight": 0.6},
                        "b": {"name": "B", "weight": 0.4},
                        "zero": {"name": "Zero", "weight": 0.0},
                    },
                },
                "stress_index": {
                    "formula": {
                        "base_score": 50,
                        "multiplier": 15,
                        "min_score": 0,
                        "max_score": 100,
                    }
                },
                "historical_events": [],
                "sanity_checks": {"checks": {}},
            }
        )

        zscores = {
            "a": pd.Series(
                [1.0, 2.0],
                index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
            ),
            "b": pd.Series(
                [3.0],
                index=pd.to_datetime(["2024-01-01"]),
            ),
            "zero": pd.Series(
                [100.0, 200.0, 300.0],
                index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            ),
        }

        result = builder.build_index(zscores, ["a", "b", "zero"])

        self.assertEqual(list(result.index.strftime("%Y-%m-%d")), ["2024-01-01", "2024-01-02"])
        self.assertAlmostEqual(float(result.loc[pd.Timestamp("2024-01-01")]), 77.0)
        self.assertAlmostEqual(float(result.loc[pd.Timestamp("2024-01-02")]), 80.0)
        self.assertAlmostEqual(
            float(builder.contributions["a"].loc[pd.Timestamp("2024-01-02")]),
            2.0,
        )
        self.assertAlmostEqual(builder.effective_weights["a"], 1.0)
        self.assertNotIn("zero", builder.weights)

    @patch("data_sources.nyfed_client.requests.get")
    def test_nyfed_client_uses_live_effr_search_endpoint(self, mock_get: Mock) -> None:
        """Legacy config should be normalized to the live JSON search endpoint."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "refRates": [
                {"effectiveDate": "2026-03-11", "type": "EFFR", "percentRate": "3.63"},
                {"effectiveDate": "2026-03-12", "type": "EFFR", "percentRate": "3.64"},
                {"effectiveDate": "2026-03-12", "type": "SOFR", "percentRate": "3.65"},
            ]
        }
        mock_get.return_value = mock_response

        client = NYFedClient(
            {
                "base_url": "https://markets.newyorkfed.org/api",
                "retry_attempts": 1,
                "series": {"effective_fed_funds": "rates/all/fed-funds"},
            }
        )

        result = client.fetch_effective_fed_funds("2026-03-01", "2026-03-14")

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "EFFR")
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(float(result.iloc[-1]), 3.64)
        called_url = mock_get.call_args.args[0]
        self.assertTrue(called_url.endswith("/rates/unsecured/effr/search.json"))

    def test_pdf_generator_writes_file_with_ascii_status_labels(self) -> None:
        """PDF generation should succeed without FPDF deprecation warnings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "outputs" / "daily_summary.pdf"
            generator = PDFReportGenerator(
                {
                    "output": {
                        "directories": {"outputs": str(output_path.parent)},
                        "files": {"pdf_report": str(output_path)},
                    },
                    "pdf": {},
                    "stress_index": {
                        "regimes": {
                            "neutral": {"min": 45, "max": 60, "label": "Neutral"}
                        }
                    },
                }
            )

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                pdf_path = generator.generate(
                    latest_snapshot={
                        "latest_date": "2026-03-12",
                        "current_score": 52.5,
                        "current_regime": {"label": "Neutral", "description": "Balanced"},
                        "change_5d": 1.2,
                        "change_20d": -0.8,
                        "top_stress_contributors": [{"name": "SOFR", "contribution": 0.25}],
                        "top_relief_contributors": [{"name": "OBFR", "contribution": -0.15}],
                    },
                    history={
                        "historical_stats": {"mean": 50.0, "std": 5.0, "min": 35.0, "max": 70.0},
                        "historical_events": {
                            "events": [
                                {
                                    "name": "Repo Spike",
                                    "date": "2019-09-17",
                                    "nearest_date": "2019-09-17",
                                    "score": 82.0,
                                    "regime": "Stress",
                                    "expected_regime": "stress",
                                    "validated": True,
                                }
                            ],
                            "total_events": 1,
                            "validated_events": 1,
                        },
                    },
                    indicator_status={
                        "sofr": {
                            "indicator": "SOFR",
                            "description": "Secured Overnight Financing Rate",
                            "current_value": 3.64,
                            "z_score": -1.7,
                            "weight_effective": 0.5,
                            "available": True,
                            "source": "fred",
                            "low_frequency": False,
                        },
                        "obfr": {
                            "indicator": "OBFR",
                            "description": "Overnight Bank Funding Rate",
                            "current_value": 3.63,
                            "z_score": -1.5,
                            "weight_effective": 0.5,
                            "available": False,
                            "source": "fred",
                            "low_frequency": False,
                        },
                    },
                    metadata={
                        "available_indicators": ["sofr"],
                        "missing_indicators": ["obfr"],
                        "source_status": {
                            "FRED": {"available": True},
                            "NYFed": {"available": False},
                        },
                        "generated_at": "2026-03-12T00:00:00",
                        "latest_date_in_data": "2026-03-12",
                    },
                    plot_files=[],
                )

            self.assertEqual(Path(pdf_path), output_path)
            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)
            pdf_warnings = [
                warning
                for warning in caught
                if issubclass(warning.category, DeprecationWarning)
            ]
            self.assertEqual(pdf_warnings, [])

    def test_pdf_generator_embeds_registered_plot_files(self) -> None:
        """Registered plot_files should be rendered into the dashboard PDF."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            output_path = tmp_path / "outputs" / "daily_summary.pdf"
            plots_path = tmp_path / "plots"
            plots_path.mkdir(parents=True, exist_ok=True)

            stress_plot = plots_path / "stress_index.png"
            stress_plot.write_bytes(
                base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5X2uoAAAAASUVORK5CYII="
                )
            )

            generator = PDFReportGenerator(
                {
                    "output": {
                        "directories": {
                            "outputs": str(output_path.parent),
                            "plots": str(plots_path),
                        },
                        "files": {"pdf_report": str(output_path)},
                    },
                    "pdf": {},
                    "stress_index": {
                        "regimes": {
                            "neutral": {"min": 45, "max": 60, "label": "Neutral"}
                        }
                    },
                }
            )

            pdf_path = generator.generate(
                latest_snapshot={
                    "latest_date": "2026-03-12",
                    "current_score": 52.5,
                    "current_regime": {"label": "Neutral", "description": "Balanced"},
                    "change_5d": 1.2,
                    "change_20d": -0.8,
                    "available_indicators": [],
                    "missing_indicators": [],
                    "top_stress_contributors": [],
                    "top_relief_contributors": [],
                },
                history={"historical_events": {"events": [], "total_events": 0, "validated_events": 0}},
                indicator_status={},
                metadata={
                    "available_indicators": [],
                    "missing_indicators": [],
                    "source_status": {},
                    "generated_at": "2026-03-12T00:00:00",
                    "latest_date_in_data": "2026-03-12",
                },
                plot_files=[str(stress_plot)],
            )

            self.assertEqual(Path(pdf_path), output_path)
            self.assertTrue(output_path.exists())
            self.assertIn(b"/Subtype /Image", output_path.read_bytes())

    def test_html_summary_includes_indicator_descriptions(self) -> None:
        """Indicator descriptions should be rendered into the HTML summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "outputs" / "email_summary.html"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            generator = HTMLSummaryGenerator(
                {"output": {"files": {"email_html": str(output_path)}}}
            )

            html = generator.generate(
                latest_snapshot={
                    "current_score": 52.5,
                    "current_regime": {"label": "Neutral", "color": "#888888"},
                    "top_stress_contributors": [],
                },
                indicator_status={
                    "sofr": {
                        "indicator": "SOFR",
                        "description": "Secured Overnight Financing Rate",
                        "current_value": 3.64,
                        "z_score": -1.7,
                        "available": True,
                    }
                },
                metadata={"generated_at": "2026-03-12T00:00:00", "missing_indicators": []},
            )

            self.assertIn("Secured Overnight Financing Rate", html)
            self.assertIn("Available", html)


if __name__ == "__main__":
    unittest.main()
