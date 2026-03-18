"""
HTML Summary Generator Module

Generates HTML email summaries.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class HTMLSummaryGenerator:
    """Generator for HTML email summaries."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize HTML summary generator.
        
        Args:
            config: Configuration dictionary from config.yaml
        """
        self.config = config
        self.output_file = config.get("output", {}).get("files", {}).get("email_html", "outputs/email_summary.html")
        
        logger.info("HTML Summary Generator initialized")
    
    def generate(
        self,
        latest_snapshot: Dict[str, Any],
        indicator_status: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> str:
        """
        Generate HTML summary.
        
        Args:
            latest_snapshot: Latest snapshot data
            indicator_status: Indicator status data
            metadata: Metadata
            
        Returns:
            HTML content as string
        """
        html = self._build_html(latest_snapshot, indicator_status, metadata)
        
        # Save to file
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(html)
        
        logger.info(f"HTML summary generated: {self.output_file}")
        return html
    
    def _build_html(
        self,
        snapshot: Dict[str, Any],
        indicator_status: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> str:
        """
        Build HTML content.
        
        Args:
            snapshot: Latest snapshot data
            indicator_status: Indicator status data
            metadata: Metadata
            
        Returns:
            HTML content
        """
        # Get color for current score
        score = snapshot.get("current_score", 0)
        score_color = self._get_score_color(score)
        
        # Build sections
        header = self._build_header()
        score_section = self._build_score_section(snapshot, score_color)
        changes_section = self._build_changes_section(snapshot)
        contributors_section = self._build_contributors_section(snapshot)
        indicators_section = self._build_indicators_section(indicator_status)
        missing_section = self._build_missing_section(metadata)
        footer = self._build_footer(metadata)
        
        # Combine all sections
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ESI-Lite Daily Summary</title>
    <style>
        {self._get_css()}
    </style>
</head>
<body>
    <div class="container">
        {header}
        {score_section}
        {changes_section}
        {contributors_section}
        {indicators_section}
        {missing_section}
        {footer}
    </div>
</body>
</html>"""
        
        return html
    
    def _get_css(self) -> str:
        """Get CSS styles."""
        return """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 28px;
            font-weight: 600;
        }
        .header p {
            margin: 10px 0 0 0;
            opacity: 0.9;
        }
        .score-section {
            padding: 30px;
            text-align: center;
            border-bottom: 1px solid #eee;
        }
        .score-value {
            font-size: 64px;
            font-weight: 700;
            margin: 0;
        }
        .score-label {
            font-size: 14px;
            color: #666;
            margin-top: 5px;
        }
        .regime-badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
            margin-top: 15px;
            color: white;
        }
        .section {
            padding: 20px 30px;
            border-bottom: 1px solid #eee;
        }
        .section-title {
            font-size: 16px;
            font-weight: 600;
            color: #333;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .changes-grid {
            display: flex;
            justify-content: space-around;
            text-align: center;
        }
        .change-item {
            flex: 1;
        }
        .change-value {
            font-size: 24px;
            font-weight: 600;
        }
        .change-value.up {
            color: #e74c3c;
        }
        .change-value.down {
            color: #27ae60;
        }
        .change-value.neutral {
            color: #7f8c8d;
        }
        .change-label {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        .contributor-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        .contributor-item {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #f0f0f0;
        }
        .contributor-item:last-child {
            border-bottom: none;
        }
        .contributor-name {
            font-weight: 500;
        }
        .contributor-value {
            font-family: monospace;
        }
        .contributor-value.positive {
            color: #e74c3c;
        }
        .contributor-value.negative {
            color: #27ae60;
        }
        .indicator-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        .indicator-table th {
            text-align: left;
            padding: 10px 5px;
            border-bottom: 2px solid #ddd;
            font-weight: 600;
            color: #666;
        }
        .indicator-table td {
            padding: 10px 5px;
            border-bottom: 1px solid #eee;
        }
        .indicator-table tr:last-child td {
            border-bottom: none;
        }
        .indicator-name {
            font-weight: 600;
        }
        .indicator-description {
            color: #666;
            font-size: 12px;
            margin-top: 2px;
        }
        .status-available {
            color: #27ae60;
        }
        .status-unavailable {
            color: #e74c3c;
        }
        .missing-section {
            background-color: #fff3cd;
            padding: 15px 30px;
        }
        .missing-list {
            margin: 0;
            padding-left: 20px;
        }
        .missing-list li {
            margin-bottom: 5px;
        }
        .footer {
            background-color: #f8f9fa;
            padding: 20px 30px;
            text-align: center;
            font-size: 12px;
            color: #666;
        }
        .footer a {
            color: #667eea;
            text-decoration: none;
        }
    """
    
    def _build_header(self) -> str:
        """Build HTML header section."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return f"""
        <div class="header">
            <h1>ESI-Lite</h1>
            <p>Eurodollar Stress Index Lite - Daily Summary</p>
            <p>{date_str}</p>
        </div>
        """
    
    def _build_score_section(self, snapshot: Dict[str, Any], score_color: str) -> str:
        """Build score section."""
        score = snapshot.get("current_score", 0)
        regime = snapshot.get("current_regime", {})
        regime_label = regime.get("label", "Unknown")
        regime_color = regime.get("color", "#808080")
        
        return f"""
        <div class="score-section">
            <div class="score-value" style="color: {score_color};">{score:.1f}</div>
            <div class="score-label">Current Stress Score (0-100)</div>
            <span class="regime-badge" style="background-color: {regime_color};">
                {regime_label}
            </span>
        </div>
        """
    
    def _build_changes_section(self, snapshot: Dict[str, Any]) -> str:
        """Build changes section."""
        change_5d = snapshot.get("change_5d")
        change_20d = snapshot.get("change_20d")
        
        change_5d_class = "up" if change_5d and change_5d > 0 else "down" if change_5d and change_5d < 0 else "neutral"
        change_20d_class = "up" if change_20d and change_20d > 0 else "down" if change_20d and change_20d < 0 else "neutral"
        
        change_5d_str = f"{change_5d:+.2f}" if change_5d is not None else "N/A"
        change_20d_str = f"{change_20d:+.2f}" if change_20d is not None else "N/A"
        
        return f"""
        <div class="section">
            <div class="section-title">Recent Changes</div>
            <div class="changes-grid">
                <div class="change-item">
                    <div class="change-value {change_5d_class}">{change_5d_str}</div>
                    <div class="change-label">5-Day Change</div>
                </div>
                <div class="change-item">
                    <div class="change-value {change_20d_class}">{change_20d_str}</div>
                    <div class="change-label">20-Day Change</div>
                </div>
            </div>
        </div>
        """
    
    def _build_contributors_section(self, snapshot: Dict[str, Any]) -> str:
        """Build contributors section."""
        top_stress = snapshot.get("top_stress_contributors", [])
        
        contributors_html = ""
        for contrib in top_stress[:3]:
            name = contrib.get("name", "Unknown")
            value = contrib.get("contribution", 0)
            value_class = "positive" if value > 0 else "negative"
            value_str = f"{value:+.3f}"
            contributors_html += f"""
                <li class="contributor-item">
                    <span class="contributor-name">{name}</span>
                    <span class="contributor-value {value_class}">{value_str}</span>
                </li>
            """
        
        return f"""
        <div class="section">
            <div class="section-title">Top Stress Contributors</div>
            <ul class="contributor-list">
                {contributors_html}
            </ul>
        </div>
        """
    
    def _build_indicators_section(self, indicator_status: Dict[str, Any]) -> str:
        """Build indicators table section."""
        rows = ""
        for ind_id, status in indicator_status.items():
            name = status.get("indicator", ind_id)
            description = status.get("description", "")
            value = status.get("current_value")
            zscore = status.get("z_score")
            available = status.get("available", False)
            
            value_str = f"{value:.4f}" if value is not None else "N/A"
            zscore_str = f"{zscore:.2f}" if zscore is not None else "N/A"
            status_class = "status-available" if available else "status-unavailable"
            status_str = "Available" if available else "Unavailable"
            description_html = (
                f'<div class="indicator-description">{description}</div>'
                if description
                else ""
            )
            
            rows += f"""
                <tr>
                    <td>
                        <div class="indicator-name">{name}</div>
                        {description_html}
                    </td>
                    <td>{value_str}</td>
                    <td>{zscore_str}</td>
                    <td class="{status_class}">{status_str}</td>
                </tr>
            """
        
        return f"""
        <div class="section">
            <div class="section-title">Indicator Status</div>
            <table class="indicator-table">
                <thead>
                    <tr>
                        <th>Indicator</th>
                        <th>Value</th>
                        <th>Z-Score</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        """
    
    def _build_missing_section(self, metadata: Dict[str, Any]) -> str:
        """Build missing indicators section."""
        missing = metadata.get("missing_indicators", [])
        
        if not missing:
            return ""
        
        missing_list = "".join([f"<li>{ind}</li>" for ind in missing])
        
        return f"""
        <div class="missing-section">
            <div class="section-title">Missing Indicators</div>
            <p>The following indicators are currently unavailable:</p>
            <ul class="missing-list">
                {missing_list}
            </ul>
        </div>
        """
    
    def _build_footer(self, metadata: Dict[str, Any]) -> str:
        """Build footer section."""
        generated_at = metadata.get("generated_at", datetime.now().isoformat())
        
        return f"""
        <div class="footer">
            <p>Generated: {generated_at}</p>
            <p>ESI-Lite | Eurodollar Stress Index Lite</p>
            <p>Free data sources: FRED, NY Fed, BIS</p>
        </div>
        """
    
    def _get_score_color(self, score: float) -> str:
        """Get color based on stress score."""
        if score < 30:
            return "#27ae60"
        elif score < 45:
            return "#2ecc71"
        elif score < 60:
            return "#f39c12"
        elif score < 75:
            return "#e67e22"
        else:
            return "#e74c3c"
