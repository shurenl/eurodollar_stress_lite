"""
Read-only Streamlit dashboard for ESI-Lite.

The dashboard reads pre-generated local files only. It does not fetch market
data or run the pipeline.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="ESI-Lite Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent


@st.cache_data
def load_config() -> Dict[str, Any]:
    """Load local config.yaml."""
    config_path = ROOT / "config.yaml"
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@st.cache_data
def load_json(path: str) -> Optional[Dict[str, Any]]:
    """Load a local JSON artifact."""
    file_path = ROOT / path
    if not file_path.exists():
        return None

    try:
        with file_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        logger.error("Failed to load %s: %s", file_path, exc)
        return None


def plot_path(filename: str) -> Path:
    """Build a local plot path."""
    return ROOT / "outputs" / "plots" / filename


def format_change(value: Optional[float]) -> str:
    """Format change values."""
    if value is None:
        return "N/A"
    return f"{value:+.2f}"


def render_metric_cards(snapshot: Dict[str, Any]) -> None:
    """Render top metric cards."""
    regime = snapshot.get("current_regime", {})
    columns = st.columns(5)
    columns[0].metric("ESI-Lite", f"{snapshot.get('current_score', 0):.1f}")
    columns[1].metric("Risk Regime", regime.get("label", "Unknown"))
    columns[2].metric("5-Day Change", format_change(snapshot.get("change_5d")))
    columns[3].metric("20-Day Change", format_change(snapshot.get("change_20d")))
    columns[4].metric("Latest Date", snapshot.get("latest_date", "N/A"))


def render_stress_history(history: Dict[str, Any], config: Dict[str, Any]) -> None:
    """Render main index chart and regime legend."""
    st.subheader("Stress Index History")

    main_plot = plot_path("stress_index.png")
    if main_plot.exists():
        st.image(str(main_plot), use_container_width=True)
    else:
        stress_index = history.get("stress_index", {})
        if stress_index:
            frame = pd.DataFrame(
                [(pd.to_datetime(date), value) for date, value in stress_index.items()],
                columns=["date", "score"],
            ).sort_values("date")
            frame = frame.set_index("date")
            st.line_chart(frame["score"])
        else:
            st.info("No stress index history available.")

    regimes = config.get("stress_index", {}).get("regimes", {})
    if regimes:
        st.markdown("**Risk Regimes**")
        columns = st.columns(len(regimes))
        for index, (_, regime) in enumerate(regimes.items()):
            columns[index].markdown(
                f"**{regime.get('label', 'Unknown')}**  \n"
                f"{regime.get('min', 0)} - {regime.get('max', 100)}"
            )

    events = history.get("historical_events", {}).get("events", [])
    if events:
        st.markdown("**Historical Regime Checks**")
        event_rows = [
            {
                "Event": event.get("name"),
                "Date": event.get("date"),
                "Nearest": event.get("nearest_date"),
                "Score": event.get("score"),
                "Regime": event.get("regime"),
                "Validated": event.get("validated"),
            }
            for event in events
        ]
        st.dataframe(pd.DataFrame(event_rows), use_container_width=True)


def render_indicator_cards(indicator_status: Dict[str, Any]) -> None:
    """Render indicator cards and local PNGs."""
    st.subheader("Indicators")
    columns = st.columns(3)

    for index, (indicator_id, status) in enumerate(indicator_status.items()):
        with columns[index % 3]:
            st.markdown(f"**{status.get('indicator', indicator_id)}**")
            description = status.get("description")
            if description:
                st.caption(description)
            st.caption(
                f"Source: {status.get('source', 'N/A')} | Frequency: {status.get('frequency', 'N/A')}"
            )
            st.write(f"Value: {status.get('current_value', 'N/A')}")
            st.write(f"Z-Score: {status.get('z_score', 'N/A')}")
            st.write(f"Available: {'Yes' if status.get('available', False) else 'No'}")

            image_path = plot_path(f"{indicator_id}.png")
            if image_path.exists():
                st.image(str(image_path), use_container_width=True)


def render_contributions(snapshot: Dict[str, Any]) -> None:
    """Render contribution plot and contributor lists."""
    st.subheader("Contributions")
    columns = st.columns(2)

    contribution_image = plot_path("contribution.png")
    with columns[0]:
        if contribution_image.exists():
            st.image(str(contribution_image), use_container_width=True)
        else:
            st.info("Contribution plot not found.")

    with columns[1]:
        st.markdown("**Top Stress Contributors**")
        for item in snapshot.get("top_stress_contributors", [])[:5]:
            st.write(f"{item.get('name', 'Unknown')}: {item.get('contribution', 0):+.3f}")

        st.markdown("**Top Relief Contributors**")
        for item in snapshot.get("top_relief_contributors", [])[:5]:
            st.write(f"{item.get('name', 'Unknown')}: {item.get('contribution', 0):+.3f}")


def render_status_table(indicator_status: Dict[str, Any]) -> None:
    """Render the indicator status table."""
    st.subheader("Indicator Status")
    rows = []
    for indicator_id, status in indicator_status.items():
        rows.append(
            {
                "Indicator": status.get("indicator", indicator_id),
                "Description": status.get("description", ""),
                "Value": status.get("current_value"),
                "Z-Score": status.get("z_score"),
                "Contribution": status.get("contribution"),
                "Weight": status.get("weight_effective"),
                "Available": "Yes" if status.get("available", False) else "No",
                "Source": status.get("source", ""),
                "Frequency": status.get("frequency", ""),
            }
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True)


def render_sidebar(metadata: Dict[str, Any]) -> None:
    """Render sidebar metadata."""
    with st.sidebar:
        st.title("ESI-Lite")
        st.caption("Read-only local dashboard")

        st.subheader("Source Status")
        for source, status in metadata.get("source_status", {}).items():
            label = "OK" if status.get("available", False) else "Unavailable"
            st.write(f"{source}: {label}")

        st.subheader("Available Indicators")
        for indicator in metadata.get("available_indicators", []):
            st.write(f"- {indicator}")

        missing = metadata.get("missing_indicators", [])
        if missing:
            st.subheader("Missing Indicators")
            for indicator in missing:
                st.write(f"- {indicator}")

        st.subheader("Config Summary")
        config_summary = metadata.get("config_summary", {})
        st.write(f"Name: {config_summary.get('name', 'N/A')}")
        st.write(f"Version: {config_summary.get('version', 'N/A')}")

        st.subheader("Mail Status")
        mail_status = metadata.get("mail_status", {})
        if mail_status.get("configured", False):
            status_text = "Success" if mail_status.get("success", False) else "Failed"
            st.write(f"Status: {status_text}")
            if mail_status.get("error"):
                st.write(f"Error: {mail_status.get('error')}")
        else:
            st.write("Status: Not configured")

        st.subheader("Metadata")
        st.write(f"Generated: {metadata.get('generated_at', 'N/A')}")
        st.write(f"Latest data date: {metadata.get('latest_date_in_data', 'N/A')}")


def main() -> None:
    """Render the dashboard."""
    config = load_config()
    latest_snapshot = load_json("dashboard_data/latest_snapshot.json")
    history = load_json("dashboard_data/history.json")
    indicator_status = load_json("dashboard_data/indicator_status.json")
    metadata = load_json("outputs/metadata.json")

    if not latest_snapshot or not history or not indicator_status or not metadata:
        st.error(
            "No dashboard artifacts found. Run `python main.py` in this directory first."
        )
        st.stop()

    render_sidebar(metadata)
    st.title("Eurodollar Stress Index Lite (ESI-Lite)")
    render_metric_cards(latest_snapshot)
    st.divider()
    render_stress_history(history, config)
    st.divider()
    render_indicator_cards(indicator_status)
    st.divider()
    render_contributions(latest_snapshot)
    st.divider()
    render_status_table(indicator_status)


if __name__ == "__main__":
    main()
