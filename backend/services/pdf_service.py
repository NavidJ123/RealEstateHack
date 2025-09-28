"""PDF export service for investor reports."""

from __future__ import annotations

import io
from typing import Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from ..models.analysis import AnalysisResponse, TrendPoint

DISCLAIMER = (
    "Demo using public/synthetic data for Washington, DC. Informational only; not financial advice."
)


class PDFService:
    def render(self, analysis: AnalysisResponse, scoring: Dict[str, object]) -> bytes:
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        margin = 0.6 * inch

        header_bottom = self._draw_header(c, analysis, scoring, width, height, margin)
        summary_bottom = self._draw_executive_summary(c, scoring, width, header_bottom - 20, margin)
        metrics_bottom = self._draw_metrics(c, analysis, width, summary_bottom - 20, margin)
        charts_bottom = self._draw_charts(c, analysis, width, metrics_bottom - 30, margin)
        comps_bottom = self._draw_comps(c, analysis, width, charts_bottom - 20, margin)
        factors_bottom = self._draw_scoring_factors(c, analysis, width, comps_bottom - 20, margin)
        self._draw_risks(c, analysis, min(factors_bottom - 20, margin + 160), margin)

        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(colors.grey)
        c.drawString(margin, margin / 2, DISCLAIMER)

        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer.read()

    def _draw_header(
        self,
        c: canvas.Canvas,
        analysis: AnalysisResponse,
        scoring: Dict[str, object],
        width: float,
        height: float,
        margin: float,
    ) -> float:
        header_height = 70
        top = height - margin
        c.setFillColor(colors.HexColor("#0A2342"))
        c.rect(margin, top - header_height, width - 2 * margin, header_height, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(margin + 16, top - 26, analysis.address)
        c.setFont("Helvetica", 12)
        decision = scoring.get("decision", "Hold")
        score = scoring.get("score", "–")
        c.drawString(margin + 16, top - 48, f"Zip {analysis.zip} · Decision: {decision} · Score: {score}")
        return top - header_height

    def _draw_executive_summary(
        self,
        c: canvas.Canvas,
        scoring: Dict[str, object],
        width: float,
        top: float,
        margin: float,
    ) -> float:
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor("#0A2342"))
        c.drawString(margin, top - 14, "Executive Summary")
        c.setFont("Helvetica", 10.5)
        c.setFillColor(colors.black)
        text = scoring.get("rationale") or "Gemini scoring unavailable; displaying fallback summary."
        wrapped = self._wrap_text(str(text), width - 2 * margin)
        y = top - 30
        for line in wrapped:
            c.drawString(margin, y, line)
            y -= 13
        return y

    def _draw_metrics(
        self,
        c: canvas.Canvas,
        analysis: AnalysisResponse,
        width: float,
        top: float,
        margin: float,
    ) -> float:
        metrics = analysis.metrics
        rows = [
            ("Current Value", self._fmt_currency(metrics.current_est_value)),
            ("Cap Rate (Market)", self._fmt_percent(metrics.cap_rate_market_now)),
            ("Projected Rent Growth (12m)", self._fmt_percent(metrics.rent_growth_proj_12m)),
            ("Median Income", self._fmt_currency(metrics.income_median_now)),
            ("Income Growth (3y)", self._fmt_percent(metrics.income_growth_3y)),
            ("Vacancy Rate", self._fmt_percent(metrics.vacancy_rate_now)),
            ("Days on Market", self._fmt_number(metrics.dom_now)),
            ("Affordability Index", self._fmt_percent(metrics.affordability_index)),
            ("Rent-to-Income", self._fmt_percent(metrics.rent_to_income_ratio)),
            ("Market Strength Index", self._fmt_number(metrics.market_strength_index, precision=2)),
            ("Appreciation (5y)", self._fmt_percent(metrics.appreciation_5y)),
        ]
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor("#0A2342"))
        c.drawString(margin, top - 14, "Key Metrics")
        c.setFont("Helvetica", 10.5)
        c.setFillColor(colors.black)
        row_height = 12
        y = top - 30
        for idx, (label, value) in enumerate(rows):
            self._draw_row_stripe(c, idx, margin, width, y, row_height, x_padding=6)
            c.drawString(margin + 6, y, label)
            c.drawRightString(width - margin - 6, y, value)
            y -= row_height
        return y

    def _draw_charts(
        self,
        c: canvas.Canvas,
        analysis: AnalysisResponse,
        width: float,
        top: float,
        margin: float,
    ) -> float:
        chart_width = (width - 3 * margin) / 2
        chart_height = 1.8 * inch
        y = top - chart_height
        left = margin
        self._line_chart(
            c,
            analysis.zip_trends.rent_history,
            analysis.zip_trends.rent_forecast,
            left,
            y,
            chart_width,
            chart_height,
            "Median Rent History & Forecast",
        )
        right = left + chart_width + margin
        self._line_chart(
            c,
            analysis.zip_trends.price_history,
            analysis.zip_trends.price_forecast,
            right,
            y,
            chart_width,
            chart_height,
            "Median Price History & Forecast",
        )
        return y - 10

    def _line_chart(
        self,
        c: canvas.Canvas,
        history: List[TrendPoint],
        forecast: List[TrendPoint],
        x: float,
        y: float,
        width: float,
        height: float,
        title: str,
    ) -> None:
        if not history:
            return
        c.setStrokeColor(colors.black)
        c.rect(x, y, width, height, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(x + 6, y + height - 14, title)
        series = history + forecast
        values = [pt.value for pt in series]
        min_val = min(values)
        max_val = max(values)
        if min_val == max_val:
            max_val = min_val + 1
        total_points = len(series)

        def scale(pt: TrendPoint, idx: int) -> tuple[float, float]:
            px = x + 12 + (idx / max(total_points - 1, 1)) * (width - 24)
            norm = (pt.value - min_val) / (max_val - min_val)
            py = y + 18 + norm * (height - 36)
            return px, py

        c.setStrokeColor(colors.HexColor("#1565C0"))
        for idx in range(1, len(history)):
            x1, y1 = scale(history[idx - 1], idx - 1)
            x2, y2 = scale(history[idx], idx)
            c.line(x1, y1, x2, y2)
        if forecast:
            c.setStrokeColor(colors.HexColor("#42A5F5"))
            offset = len(history) - 1
            for idx in range(1, len(forecast)):
                x1, y1 = scale(forecast[idx - 1], offset + idx - 1)
                x2, y2 = scale(forecast[idx], offset + idx)
                c.line(x1, y1, x2, y2)

    def _draw_comps(
        self,
        c: canvas.Canvas,
        analysis: AnalysisResponse,
        width: float,
        top: float,
        margin: float,
    ) -> float:
        comps = analysis.comps[:5]
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor("#0A2342"))
        c.drawString(margin, top - 14, "Comparable Sales")
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.black)
        y = top - 30
        if not comps:
            c.drawString(margin, y, "No comparable sales available.")
            return y - 10
        row_height = 12
        for idx, comp in enumerate(comps):
            row = (
                f"{comp.address} · {comp.sale_date} · {self._fmt_currency(comp.sale_price)} · "
                f"{self._fmt_number(comp.sqft, suffix=' sqft')}"
            )
            self._draw_row_stripe(c, idx, margin, width, y, row_height, x_padding=6)
            c.drawString(margin + 6, y, row)
            y -= row_height
        return y

    def _draw_scoring_factors(
        self,
        c: canvas.Canvas,
        analysis: AnalysisResponse,
        width: float,
        top: float,
        margin: float,
    ) -> float:
        factors = analysis.explanations.factors
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor("#0A2342"))
        c.drawString(margin, top - 14, "How We Scored This")
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.black)
        row_height = 12
        y = top - 30
        for idx, factor in enumerate(factors):
            effect = "+" if factor.contrib >= 0 else "-"
            label = f"{factor.name}: {effect}{abs(factor.contrib):.1f} pts (weight {factor.weight:.2f})"
            self._draw_row_stripe(c, idx, margin, width, y, row_height, x_padding=6)
            c.drawString(margin + 6, y, label)
            y -= row_height
        return y

    def _draw_row_stripe(
        self,
        c: canvas.Canvas,
        row_index: int,
        margin: float,
        width: float,
        baseline: float,
        row_height: float,
        *,
        x_padding: float = 0.0,
        y_padding: float = 2.0,
    ) -> None:
        """Shade every other row to create alternating horizontal stripes."""
        if row_index % 2 != 0:
            return
        stripe_y = baseline - row_height + y_padding
        stripe_width = width - 2 * margin - 2 * x_padding
        if stripe_width <= 0:
            return
        c.saveState()
        c.setFillColor(colors.HexColor("#F2F4F7"))
        c.rect(margin + x_padding, stripe_y, stripe_width, row_height, stroke=0, fill=1)
        c.restoreState()

    def _draw_risks(self, c: canvas.Canvas, analysis: AnalysisResponse, top: float, margin: float) -> None:
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor("#0A2342"))
        c.drawString(margin, top - 14, "Risks & Assumptions")
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.black)
        provenance = analysis.provenance
        risks = [
            "Market assumptions derived from synthetic datasets; replace with live feeds before production.",
            f"Data sources: {', '.join(provenance.sources) if provenance.sources else 'CSV demo datasets'}.",
            "Cap rate proxy uses median rent and price when explicit market data is unavailable.",
        ]
        y = top - 30
        for item in risks:
            c.drawString(margin, y, f"- {item}")
            y -= 12

    def _fmt_currency(self, value: Optional[float]) -> str:
        if value is None:
            return "—"
        return f"${value:,.0f}"

    def _fmt_percent(self, value: Optional[float]) -> str:
        if value is None:
            return "—"
        return f"{value:.1%}"

    def _fmt_number(self, value: Optional[float], precision: int = 0, suffix: str = "") -> str:
        if value is None:
            return "—"
        fmt = f"{value:.{precision}f}"
        return f"{fmt}{suffix}"

    def _wrap_text(self, text: str, width: float, char_width: float = 6.0) -> List[str]:
        max_chars = max(20, int(width / char_width))
        words = text.split()
        lines: List[str] = []
        current: List[str] = []
        for word in words:
            tentative = " ".join(current + [word])
            if len(tentative) > max_chars and current:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            lines.append(" ".join(current))
        return lines
