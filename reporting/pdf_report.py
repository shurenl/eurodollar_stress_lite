"""
PDF Report Generator Module

Generates dashboard-style PDF reports using FPDF.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fpdf import FPDF, XPos, YPos

logger = logging.getLogger(__name__)


class PDFReportGenerator:
    """Generator for ESI-Lite PDF reports."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize PDF report generator.

        Args:
            config: Configuration dictionary from config.yaml
        """
        self.config = config
        self.pdf_config = config.get("pdf", {})
        self.project_root = Path(__file__).resolve().parents[1]

        output_dir = config.get("output", {}).get("directories", {}).get("outputs", "outputs")
        output_file = config.get("output", {}).get("files", {}).get("pdf_report", "outputs/daily_summary.pdf")
        plots_dir = config.get("output", {}).get("directories", {}).get("plots", "outputs/plots")

        self.output_dir = self._resolve_path(output_dir)
        self.output_file = self._resolve_path(output_file)
        self.plots_dir = self._resolve_path(plots_dir)

        # Font settings
        self.font_family = self.pdf_config.get("font", {}).get("family", "Helvetica")
        self.title_size = self.pdf_config.get("font", {}).get("title_size", 18)
        self.heading_size = self.pdf_config.get("font", {}).get("heading_size", 14)
        self.body_size = self.pdf_config.get("font", {}).get("body_size", 10)

        # Margin settings
        self.margin_top = self.pdf_config.get("margins", {}).get("top", 20)
        self.margin_bottom = self.pdf_config.get("margins", {}).get("bottom", 20)
        self.margin_left = self.pdf_config.get("margins", {}).get("left", 15)
        self.margin_right = self.pdf_config.get("margins", {}).get("right", 15)

        # Page settings
        self.page_size = self.pdf_config.get("page_size", "A4")
        orientation = str(self.pdf_config.get("orientation", "portrait")).lower()
        self.orientation = "L" if orientation.startswith("l") else "P"

        # Palette
        self.colors = {
            "ink": (35, 39, 47),
            "muted": (92, 103, 117),
            "border": (214, 220, 229),
            "panel": (247, 249, 252),
            "accent": (42, 86, 143),
            "success": (30, 132, 73),
            "warning": (179, 89, 0),
            "danger": (180, 45, 45),
        }

        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info("PDF Report Generator initialized")

    @staticmethod
    def _status_label(is_positive: bool, positive: str, negative: str) -> str:
        """Return an ASCII-only status label safe for FPDF core fonts."""
        return positive if is_positive else negative

    @staticmethod
    def _line(
        pdf: FPDF,
        height: float,
        text: str,
        *,
        width: float = 0,
        border: int | str = 0,
        align: str = "",
    ) -> None:
        """Write a line and advance using the non-deprecated FPDF API."""
        pdf.cell(
            width,
            height,
            text,
            border=border,
            align=align,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    def _resolve_path(self, path_value: str | Path) -> Path:
        """Resolve configured paths relative to the project root."""
        path = Path(path_value)
        if path.is_absolute():
            return path
        return (self.project_root / path).resolve()

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        """Convert values to float when possible."""
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _format_number(self, value: Any, decimals: int = 2) -> str:
        """Format numeric values with fallback."""
        number = self._safe_float(value)
        if number is None:
            return "N/A"
        return f"{number:.{decimals}f}"

    def _format_signed(self, value: Any, decimals: int = 2) -> str:
        """Format signed numeric values with fallback."""
        number = self._safe_float(value)
        if number is None:
            return "N/A"
        return f"{number:+.{decimals}f}"

    def _format_percent(self, value: Any, decimals: int = 1) -> str:
        """Format percent values with fallback."""
        number = self._safe_float(value)
        if number is None:
            return "N/A"
        return f"{number:.{decimals}%}"

    def _build_pdf(self) -> FPDF:
        """Create the PDF instance with configured margins."""
        pdf = FPDF(orientation=self.orientation, format=self.page_size)
        pdf.set_auto_page_break(auto=True, margin=self.margin_bottom)
        pdf.set_margins(self.margin_left, self.margin_top, self.margin_right)
        pdf.set_title("Eurodollar Stress Index Lite")
        pdf.set_author("ESI-Lite")
        return pdf

    def _build_plot_map(self, plot_files: List[str]) -> Dict[str, str]:
        """Map plot filenames and stems to real files."""
        plot_map: Dict[str, str] = {}

        def register(path: Path) -> None:
            if not path.exists():
                return
            resolved = str(path.resolve())
            plot_map[path.name] = resolved
            plot_map[path.stem] = resolved

        for plot_file in plot_files:
            if not plot_file:
                continue

            path = Path(plot_file)
            candidates = [path]
            if not path.is_absolute():
                candidates.append((self.project_root / path).resolve())
                candidates.append((self.plots_dir / path.name).resolve())

            for candidate in candidates:
                if candidate.exists():
                    register(candidate)
                    break

        if self.plots_dir.exists():
            for candidate in self.plots_dir.glob("*.png"):
                if candidate.name not in plot_map and candidate.stem not in plot_map:
                    register(candidate)

        return plot_map

    @staticmethod
    def _lookup_plot(plot_map: Dict[str, str], *candidates: str) -> Optional[str]:
        """Find a registered plot by name or stem."""
        for candidate in candidates:
            if not candidate:
                continue
            for key in (candidate, Path(candidate).name, Path(candidate).stem):
                if key in plot_map:
                    return plot_map[key]
        return None

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        """Truncate text for narrow table cells."""
        if len(text) <= limit:
            return text
        return f"{text[: limit - 3]}..."

    def _set_text_color(self, pdf: FPDF, color_key: str) -> None:
        """Apply a named text color."""
        pdf.set_text_color(*self.colors[color_key])

    def _draw_page_header(self, pdf: FPDF, title: str, subtitle: str, latest_date: str) -> None:
        """Draw a dashboard-style page header."""
        pdf.add_page()

        start_y = pdf.get_y()
        panel_h = 18
        pdf.set_fill_color(*self.colors["panel"])
        pdf.set_draw_color(*self.colors["border"])
        pdf.rect(pdf.l_margin, start_y, pdf.epw, panel_h, style="DF")

        pdf.set_xy(pdf.l_margin + 4, start_y + 3)
        self._set_text_color(pdf, "ink")
        pdf.set_font(self.font_family, "B", self.heading_size + 2)
        pdf.cell(pdf.epw * 0.62, 6, title, new_x=XPos.RIGHT, new_y=YPos.TOP)

        self._set_text_color(pdf, "muted")
        pdf.set_font(self.font_family, "", self.body_size - 1)
        pdf.cell(pdf.epw * 0.38 - 8, 6, f"Data through {latest_date}", align="R")

        pdf.set_xy(pdf.l_margin + 4, start_y + 10)
        pdf.set_font(self.font_family, "", self.body_size - 1)
        pdf.multi_cell(pdf.epw - 8, 4.2, subtitle)
        self._set_text_color(pdf, "ink")
        pdf.ln(4)

    def _draw_metric_card(
        self,
        pdf: FPDF,
        x: float,
        y: float,
        w: float,
        h: float,
        label: str,
        value: str,
        detail: Optional[str] = None,
    ) -> None:
        """Render a compact metric card."""
        pdf.set_fill_color(*self.colors["panel"])
        pdf.set_draw_color(*self.colors["border"])
        pdf.rect(x, y, w, h, style="DF")

        pdf.set_xy(x + 3, y + 3)
        self._set_text_color(pdf, "muted")
        pdf.set_font(self.font_family, "", self.body_size - 2)
        pdf.cell(w - 6, 4, label, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_xy(x + 3, y + 8)
        self._set_text_color(pdf, "ink")
        pdf.set_font(self.font_family, "B", self.body_size + 3)
        pdf.cell(w - 6, 7, value, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if detail:
            pdf.set_xy(x + 3, y + h - 7)
            self._set_text_color(pdf, "muted")
            pdf.set_font(self.font_family, "", self.body_size - 2)
            pdf.cell(w - 6, 4, detail)

        self._set_text_color(pdf, "ink")

    def _draw_panel_title(self, pdf: FPDF, x: float, y: float, w: float, title: str) -> None:
        """Render a small section label inside a panel."""
        pdf.set_xy(x, y)
        self._set_text_color(pdf, "accent")
        pdf.set_font(self.font_family, "B", self.body_size)
        pdf.cell(w, 5, title)
        self._set_text_color(pdf, "ink")

    def _draw_text_panel(
        self,
        pdf: FPDF,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        lines: List[str],
        *,
        body_size: Optional[int] = None,
    ) -> None:
        """Render a bordered text panel."""
        pdf.set_fill_color(*self.colors["panel"])
        pdf.set_draw_color(*self.colors["border"])
        pdf.rect(x, y, w, h, style="DF")
        self._draw_panel_title(pdf, x + 3, y + 3, w - 6, title)

        pdf.set_xy(x + 3, y + 10)
        pdf.set_font(self.font_family, "", body_size or self.body_size - 1)
        self._set_text_color(pdf, "ink")

        for line in lines:
            pdf.multi_cell(w - 6, 4.3, line)
            if pdf.get_y() > y + h - 6:
                break
            pdf.set_x(x + 3)

    def _draw_image_panel(
        self,
        pdf: FPDF,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        image_path: Optional[str],
        caption: str,
        *,
        placeholder: str,
    ) -> None:
        """Render an image box with caption."""
        pdf.set_fill_color(*self.colors["panel"])
        pdf.set_draw_color(*self.colors["border"])
        pdf.rect(x, y, w, h, style="DF")
        self._draw_panel_title(pdf, x + 3, y + 3, w - 6, title)

        caption_h = 14
        image_y = y + 11
        image_h = max(18, h - 11 - caption_h - 3)

        if image_path and Path(image_path).exists():
            pdf.image(
                image_path,
                x=x + 2,
                y=image_y,
                w=w - 4,
                h=image_h,
                keep_aspect_ratio=True,
            )
        else:
            pdf.set_xy(x + 5, image_y + (image_h / 2) - 3)
            self._set_text_color(pdf, "muted")
            pdf.set_font(self.font_family, "I", self.body_size - 1)
            pdf.multi_cell(w - 10, 5, placeholder, align="C")

        pdf.set_xy(x + 3, y + h - caption_h + 1)
        self._set_text_color(pdf, "muted")
        pdf.set_font(self.font_family, "", self.body_size - 2)
        pdf.multi_cell(w - 6, 4, caption)
        self._set_text_color(pdf, "ink")

    def _draw_bullet_list(
        self,
        pdf: FPDF,
        x: float,
        y: float,
        w: float,
        title: str,
        items: List[Dict[str, Any]],
        positive: bool,
    ) -> None:
        """Render contributor bullets."""
        box_h = 31
        pdf.set_fill_color(*self.colors["panel"])
        pdf.set_draw_color(*self.colors["border"])
        pdf.rect(x, y, w, box_h, style="DF")
        self._draw_panel_title(pdf, x + 3, y + 3, w - 6, title)

        pdf.set_xy(x + 3, y + 10)
        pdf.set_font(self.font_family, "", self.body_size - 1)

        for index, item in enumerate(items[:3], start=1):
            contribution = self._format_signed(item.get("contribution"), 3)
            weight = self._format_percent(item.get("weight"), 1)
            name = item.get("name", "Unknown")
            line = f"{index}. {self._truncate(name, 22)} {contribution} | wt {weight}"
            if positive:
                self._set_text_color(pdf, "warning")
            else:
                self._set_text_color(pdf, "success")
            pdf.cell(w - 6, 5.2, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_x(x + 3)

        self._set_text_color(pdf, "ink")

    def _add_overview_page(
        self,
        pdf: FPDF,
        snapshot: Dict[str, Any],
        history: Dict[str, Any],
        plot_map: Dict[str, str],
    ) -> None:
        """Add overview dashboard page."""
        latest_date = snapshot.get("latest_date", datetime.now().strftime("%Y-%m-%d"))
        subtitle = (
            "Overview metrics, regime context, and the full stress-index history. "
            "This page aligns the PDF with the same core dashboard view used locally."
        )
        self._draw_page_header(pdf, "Daily Dashboard", subtitle, latest_date)

        card_gap = 4
        card_h = 23
        card_w = (pdf.epw - (4 * card_gap)) / 5
        y0 = pdf.get_y()
        cards = [
            ("ESI-Lite", self._format_number(snapshot.get("current_score"), 1), None),
            ("Risk Regime", snapshot.get("current_regime", {}).get("label", "Unknown"), None),
            ("5D Change", self._format_signed(snapshot.get("change_5d"), 2), "Delta vs 5 trading days"),
            ("20D Change", self._format_signed(snapshot.get("change_20d"), 2), "Delta vs 20 trading days"),
            (
                "Coverage",
                f"{len(snapshot.get('available_indicators', []))}",
                f"Missing {len(snapshot.get('missing_indicators', []))}",
            ),
        ]

        for index, (label, value, detail) in enumerate(cards):
            x = pdf.l_margin + index * (card_w + card_gap)
            self._draw_metric_card(pdf, x, y0, card_w, card_h, label, value, detail)

        plot_y = y0 + card_h + 6
        plot_h = 102
        main_plot = self._lookup_plot(plot_map, "stress_index.png", "stress_index")
        self._draw_image_panel(
            pdf,
            pdf.l_margin,
            plot_y,
            pdf.epw,
            plot_h,
            "Main Index",
            main_plot,
            "Caption: Regime bands show the scoring ranges; dashed event markers highlight validation episodes. "
            "Higher readings indicate tighter USD funding conditions.",
            placeholder="Stress index plot not found in plot_files.",
        )

        regime = snapshot.get("current_regime", {})
        hist_stats = history.get("historical_stats", {})
        left_lines = [
            f"Current regime: {regime.get('label', 'Unknown')}",
            regime.get("description", "No regime description available."),
            f"Latest date: {latest_date}",
            f"Current score: {self._format_number(snapshot.get('current_score'), 2)}",
        ]
        right_lines = []
        for regime_config in self.config.get("stress_index", {}).get("regimes", {}).values():
            right_lines.append(
                f"{regime_config.get('label', 'Unknown')}: "
                f"{regime_config.get('min', 0)}-{regime_config.get('max', 100)}"
            )
        if hist_stats:
            right_lines.extend(
                [
                    f"Mean: {self._format_number(hist_stats.get('mean'), 2)}",
                    f"Std Dev: {self._format_number(hist_stats.get('std'), 2)}",
                    f"Range: {self._format_number(hist_stats.get('min'), 1)} to {self._format_number(hist_stats.get('max'), 1)}",
                ]
            )

        panel_y = plot_y + plot_h + 6
        panel_h = 38
        gap = 5
        panel_w = (pdf.epw - gap) / 2
        self._draw_text_panel(pdf, pdf.l_margin, panel_y, panel_w, panel_h, "Interpretation", left_lines)
        self._draw_text_panel(
            pdf,
            pdf.l_margin + panel_w + gap,
            panel_y,
            panel_w,
            panel_h,
            "Regime Scale",
            right_lines or ["No regime ranges configured."],
        )

    def _add_contributions_page(
        self,
        pdf: FPDF,
        snapshot: Dict[str, Any],
        indicator_status: Dict[str, Any],
        plot_map: Dict[str, str],
    ) -> None:
        """Add contribution dashboard page."""
        latest_date = snapshot.get("latest_date", datetime.now().strftime("%Y-%m-%d"))
        subtitle = (
            "Contribution view showing which indicators are adding stress and which are providing relief "
            "to the current composite score."
        )
        self._draw_page_header(pdf, "Contribution Dashboard", subtitle, latest_date)

        gap = 5
        plot_w = pdf.epw * 0.62
        side_w = pdf.epw - plot_w - gap
        top_y = pdf.get_y()
        plot_h = 95
        contribution_plot = self._lookup_plot(plot_map, "contribution.png", "contribution")

        self._draw_image_panel(
            pdf,
            pdf.l_margin,
            top_y,
            plot_w,
            plot_h,
            "Contribution History",
            contribution_plot,
            "Caption: Positive contributions push ESI-Lite higher; negative contributions offset stress. "
            "Read the latest edge of the chart together with the contributor lists on the right.",
            placeholder="Contribution plot not found in plot_files.",
        )

        side_x = pdf.l_margin + plot_w + gap
        self._draw_bullet_list(
            pdf,
            side_x,
            top_y,
            side_w,
            "Top Stress Contributors",
            snapshot.get("top_stress_contributors", []),
            True,
        )
        self._draw_bullet_list(
            pdf,
            side_x,
            top_y + 35,
            side_w,
            "Top Relief Contributors",
            snapshot.get("top_relief_contributors", []),
            False,
        )

        coverage_lines = [
            f"Available indicators: {len([status for status in indicator_status.values() if status.get('available', False)])}",
            f"Unavailable indicators: {len([status for status in indicator_status.values() if not status.get('available', False)])}",
            f"Active contributors: {len([status for status in indicator_status.values() if status.get('contribution') is not None])}",
            "Indicators with null contribution are available for reference but not currently driving the composite.",
        ]
        self._draw_text_panel(
            pdf,
            side_x,
            top_y + 70,
            side_w,
            25,
            "Coverage Note",
            coverage_lines,
            body_size=self.body_size - 2,
        )

        ranked = sorted(
            indicator_status.items(),
            key=lambda item: abs(self._safe_float(item[1].get("contribution")) or 0),
            reverse=True,
        )
        rows = []
        for ind_id, status in ranked[:6]:
            rows.append(
                f"{status.get('indicator', ind_id)} | contrib {self._format_signed(status.get('contribution'), 3)} "
                f"| z {self._format_number(status.get('z_score'), 2)}"
            )

        bottom_y = top_y + plot_h + 6
        self._draw_text_panel(
            pdf,
            pdf.l_margin,
            bottom_y,
            pdf.epw,
            44,
            "Current Contribution Snapshot",
            rows or ["No contribution data available."],
        )

    def _indicator_sort_key(self, item: tuple[str, Dict[str, Any]]) -> tuple[int, float, str]:
        """Sort indicators by availability and contribution magnitude."""
        ind_id, status = item
        contribution = abs(self._safe_float(status.get("contribution")) or 0.0)
        available = 0 if status.get("available", False) else 1
        return available, -contribution, status.get("indicator", ind_id)

    def _draw_indicator_card(
        self,
        pdf: FPDF,
        x: float,
        y: float,
        w: float,
        h: float,
        indicator_id: str,
        status: Dict[str, Any],
        plot_map: Dict[str, str],
    ) -> None:
        """Render an individual indicator card."""
        pdf.set_fill_color(*self.colors["panel"])
        pdf.set_draw_color(*self.colors["border"])
        pdf.rect(x, y, w, h, style="DF")

        title = status.get("indicator", indicator_id)
        image_path = self._lookup_plot(
            plot_map,
            f"{indicator_id}.png",
            indicator_id,
            f"{indicator_id}_zscore.png",
            f"{indicator_id}_zscore",
        )
        source = status.get("source", "N/A")
        frequency = status.get("frequency", "N/A")
        availability = self._status_label(status.get("available", False), "Available", "Missing")

        self._draw_panel_title(pdf, x + 3, y + 3, w - 6, self._truncate(title, 26))
        pdf.set_xy(x + 3, y + 9)
        self._set_text_color(pdf, "muted")
        pdf.set_font(self.font_family, "", self.body_size - 2)
        pdf.cell(w - 6, 4, self._truncate(f"{source} | {frequency} | {availability}", 34))

        image_y = y + 15
        image_h = h - 44
        if image_path and Path(image_path).exists():
            pdf.image(
                image_path,
                x=x + 2,
                y=image_y,
                w=w - 4,
                h=image_h,
                keep_aspect_ratio=True,
            )
        else:
            pdf.set_xy(x + 5, image_y + (image_h / 2) - 3)
            pdf.set_font(self.font_family, "I", self.body_size - 1)
            pdf.multi_cell(w - 10, 5, "Indicator plot not found in plot_files.", align="C")

        stats_y = y + h - 24
        self._set_text_color(pdf, "ink")
        pdf.set_xy(x + 3, stats_y)
        pdf.set_font(self.font_family, "", self.body_size - 2)
        stats_line_1 = (
            f"Value {self._format_number(status.get('current_value'), 4)} | "
            f"Z {self._format_number(status.get('z_score'), 2)}"
        )
        stats_line_2 = (
            f"Contrib {self._format_signed(status.get('contribution'), 3)} | "
            f"Wt {self._format_percent(status.get('weight_effective'), 1)}"
        )
        pdf.cell(w - 6, 4, self._truncate(stats_line_1, 40), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_x(x + 3)
        pdf.cell(w - 6, 4, self._truncate(stats_line_2, 40), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_xy(x + 3, y + h - 8)
        self._set_text_color(pdf, "muted")
        pdf.set_font(self.font_family, "", self.body_size - 3)
        pdf.cell(w - 6, 3.5, "Caption: Raw trend chart. Compare pressure using Z-score and contribution.")
        self._set_text_color(pdf, "ink")

    def _add_indicator_cards_pages(
        self,
        pdf: FPDF,
        indicator_status: Dict[str, Any],
        plot_map: Dict[str, str],
        latest_date: str,
    ) -> None:
        """Add one or more indicator-card pages."""
        items = sorted(indicator_status.items(), key=self._indicator_sort_key)
        if not items:
            self._draw_page_header(
                pdf,
                "Indicator Cards",
                "Indicator cards and plot thumbnails were requested, but no indicator metadata was available.",
                latest_date,
            )
            return

        items_per_page = 4
        gap_x = 5
        gap_y = 6

        for start in range(0, len(items), items_per_page):
            chunk = items[start : start + items_per_page]
            self._draw_page_header(
                pdf,
                "Indicator Cards",
                "Each card pairs the latest reading with the local plot image generated for the dashboard.",
                latest_date,
            )

            top_y = pdf.get_y()
            card_w = (pdf.epw - gap_x) / 2
            card_h = 101

            for index, (indicator_id, status) in enumerate(chunk):
                row = index // 2
                col = index % 2
                x = pdf.l_margin + col * (card_w + gap_x)
                y = top_y + row * (card_h + gap_y)
                self._draw_indicator_card(pdf, x, y, card_w, card_h, indicator_id, status, plot_map)

    def _draw_status_table_header(self, pdf: FPDF, widths: List[float], columns: List[str]) -> None:
        """Draw the status table header row."""
        pdf.set_fill_color(231, 236, 244)
        pdf.set_draw_color(*self.colors["border"])
        pdf.set_font(self.font_family, "B", self.body_size - 2)
        self._set_text_color(pdf, "ink")

        for width, label in zip(widths, columns):
            pdf.cell(width, 6.5, label, border=1, fill=True, align="C")
        pdf.ln()

    def _add_status_table_pages(
        self,
        pdf: FPDF,
        indicator_status: Dict[str, Any],
        latest_date: str,
    ) -> None:
        """Add paginated indicator status tables."""
        subtitle = (
            "Tabular audit view of the same indicator set used in the dashboard: latest reading, normalized score, "
            "contribution, weight, and availability state."
        )
        self._draw_page_header(pdf, "Indicator Status Table", subtitle, latest_date)

        columns = ["Indicator", "Source/Freq", "Value", "Z", "Contrib", "Weight", "Status"]
        widths = [46, 29, 24, 16, 23, 18, 20]
        line_h = 6

        self._draw_status_table_header(pdf, widths, columns)
        pdf.set_font(self.font_family, "", self.body_size - 3)

        for indicator_id, status in sorted(indicator_status.items(), key=lambda item: item[1].get("indicator", item[0])):
            if pdf.get_y() > pdf.h - pdf.b_margin - 12:
                self._draw_page_header(pdf, "Indicator Status Table", subtitle, latest_date)
                self._draw_status_table_header(pdf, widths, columns)
                pdf.set_font(self.font_family, "", self.body_size - 3)

            source_freq = f"{status.get('source', 'N/A')}/{status.get('frequency', 'N/A')}"
            row = [
                self._truncate(status.get("indicator", indicator_id), 22),
                self._truncate(source_freq, 14),
                self._format_number(status.get("current_value"), 4),
                self._format_number(status.get("z_score"), 2),
                self._format_signed(status.get("contribution"), 3),
                self._format_percent(status.get("weight_effective"), 1),
                self._status_label(status.get("available", False), "Available", "Missing"),
            ]

            for width, value in zip(widths, row):
                pdf.cell(width, line_h, value, border=1)
            pdf.ln()

    def _add_notes_page(
        self,
        pdf: FPDF,
        history: Dict[str, Any],
        metadata: Dict[str, Any],
        indicator_status: Dict[str, Any],
        plot_map: Dict[str, str],
        latest_date: str,
    ) -> None:
        """Add data source and event explanation page."""
        subtitle = (
            "Operational notes covering source availability, low-frequency handling, and historical event checks. "
            "This page explains what the charts should and should not be interpreted as."
        )
        self._draw_page_header(pdf, "Source and Event Notes", subtitle, latest_date)

        gap = 5
        left_w = (pdf.epw - gap) / 2
        right_w = left_w
        top_y = pdf.get_y()

        low_freq = [
            status.get("indicator", indicator_id)
            for indicator_id, status in indicator_status.items()
            if status.get("low_frequency", False) and status.get("available", False)
        ]
        source_lines = [
            f"Generated at: {metadata.get('generated_at', 'N/A')}",
            f"Latest data date: {metadata.get('latest_date_in_data', 'N/A')}",
            f"Available indicators: {len(metadata.get('available_indicators', []))}",
            f"Missing indicators: {len(metadata.get('missing_indicators', []))}",
        ]
        for source, status in metadata.get("source_status", {}).items():
            label = self._status_label(status.get("available", False), "OK", "Unavailable")
            source_lines.append(f"{source}: {label}")
            error = status.get("error")
            if error:
                source_lines.append(f"  Note: {self._truncate(str(error), 45)}")

        if low_freq:
            source_lines.append("Low-frequency indicators are forward-filled between official releases.")
            for name in low_freq[:3]:
                source_lines.append(f"  - {name}")

        self._draw_text_panel(pdf, pdf.l_margin, top_y, left_w, 74, "Data Source Notes", source_lines)

        events = history.get("historical_events", {})
        event_lines = [
            "Validation events are sanity checks, not forecasting signals.",
            f"Validated events: {events.get('validated_events', 0)}/{events.get('total_events', 0)}",
        ]
        for event in events.get("events", [])[:4]:
            status_label = self._status_label(event.get("validated", False), "PASS", "FAIL")
            event_lines.append(
                f"{event.get('name', 'Unknown')} | {event.get('date', 'N/A')} | "
                f"score {self._format_number(event.get('score'), 1)} | {status_label}"
            )

        self._draw_text_panel(
            pdf,
            pdf.l_margin + left_w + gap,
            top_y,
            right_w,
            74,
            "Event Notes",
            event_lines or ["No historical event checks available."],
        )

        event_images: List[str] = []
        for event in events.get("events", [])[:3]:
            date = str(event.get("date", ""))
            key = f"event_{date.replace('-', '')}.png"
            plot_path = self._lookup_plot(plot_map, key, key.replace(".png", ""))
            if plot_path:
                event_images.append(plot_path)

        image_y = top_y + 80
        image_gap = 4
        image_w = (pdf.epw - (2 * image_gap)) / 3
        image_h = 49

        if event_images:
            for index, image_path in enumerate(event_images[:3]):
                x = pdf.l_margin + index * (image_w + image_gap)
                self._draw_image_panel(
                    pdf,
                    x,
                    image_y,
                    image_w,
                    image_h,
                    f"Event Window {index + 1}",
                    image_path,
                    "Caption: 30-day window around the event date; the red marker is the event itself.",
                    placeholder="Event window plot missing.",
                )
        else:
            self._draw_text_panel(
                pdf,
                pdf.l_margin,
                image_y,
                pdf.epw,
                34,
                "Event Window Note",
                [
                    "No event window plots were found in plot_files.",
                    "If event PNGs are generated later, this section will render them automatically.",
                ],
            )

    def generate(
        self,
        latest_snapshot: Dict[str, Any],
        history: Dict[str, Any],
        indicator_status: Dict[str, Any],
        metadata: Dict[str, Any],
        plot_files: List[str],
    ) -> str:
        """
        Generate PDF report.

        Args:
            latest_snapshot: Latest snapshot data
            history: Historical data
            indicator_status: Indicator status data
            metadata: Metadata
            plot_files: List of plot file paths

        Returns:
            Path to generated PDF file
        """
        pdf = self._build_pdf()
        plot_map = self._build_plot_map(plot_files)
        latest_date = latest_snapshot.get("latest_date", datetime.now().strftime("%Y-%m-%d"))

        self._add_overview_page(pdf, latest_snapshot, history, plot_map)
        self._add_contributions_page(pdf, latest_snapshot, indicator_status, plot_map)
        self._add_indicator_cards_pages(pdf, indicator_status, plot_map, latest_date)
        self._add_status_table_pages(pdf, indicator_status, latest_date)
        self._add_notes_page(pdf, history, metadata, indicator_status, plot_map, latest_date)

        pdf.output(str(self.output_file))
        if not self.output_file.exists() or self.output_file.stat().st_size == 0:
            raise RuntimeError(f"PDF output was not written: {self.output_file}")
        logger.info("PDF report generated: %s", self.output_file)

        return str(self.output_file)
