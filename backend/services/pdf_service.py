"""PDF export service for investor reports."""

from __future__ import annotations

import io
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from ..models.analysis import Analysis, ZipTrendPoint


class PDFService:
    def render(self, analysis: Analysis) -> bytes:
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        margin = 0.6 * inch

        self._draw_header(c, analysis, width, height, margin)
        self._draw_metrics(c, analysis, width, height, margin)
        self._draw_charts(c, analysis, width, height, margin)
        self._draw_summary(c, analysis, width, height, margin)

        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(colors.grey)
        c.drawString(
            margin,
            margin / 2,
            "This is an MVP using public/demo data for Washington, DC. Estimates and recommendations are informational only and not financial advice.",
        )

        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer.read()

    def _draw_header(self, c: canvas.Canvas, analysis: Analysis, width: float, height: float, margin: float) -> None:
        c.setFillColor(colors.HexColor("#0A2342"))
        c.rect(margin, height - margin - 60, width - 2 * margin, 60, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(margin + 12, height - margin - 24, analysis.address)
        c.setFont("Helvetica", 12)
        c.drawString(margin + 12, height - margin - 44, f"Decision: {analysis.decision}  |  Score: {analysis.score}")

    def _draw_metrics(self, c: canvas.Canvas, analysis: Analysis, width: float, height: float, margin: float) -> None:
        top = height - margin - 100
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, top, "Key Metrics")
        c.setFont("Helvetica", 11)
        metrics = analysis.metrics
        rows = [
            ("Current Value", f"${metrics.current_est_value:,.0f}"),
            ("Appreciation (5y)", f"{metrics.appreciation_5y:.1%}" if metrics.appreciation_5y is not None else "Insufficient data"),
            ("Cap Rate", f"{metrics.cap_rate_est:.1%}" if metrics.cap_rate_est is not None else "Insufficient data"),
            ("Rent Growth (3y)", f"{metrics.rent_growth_3y:.1%}" if metrics.rent_growth_3y is not None else "Insufficient data"),
            ("Market Strength", f"{metrics.market_strength:+.2f}" if metrics.market_strength is not None else "Insufficient data"),
        ]
        y = top - 18
        for label, value in rows:
            c.drawString(margin, y, label)
            c.drawRightString(width - margin, y, value)
            y -= 16

    def _draw_charts(self, c: canvas.Canvas, analysis: Analysis, width: float, height: float, margin: float) -> None:
        chart_width = (width - 3 * margin) / 2
        chart_height = 2.2 * inch
        bottom = height / 2 - chart_height / 2
        left = margin
        self._line_chart(c, analysis.zip_trends.price_history, analysis.zip_trends.price_forecast, left, bottom, chart_width, chart_height, "Median Price ($)")
        right = left + chart_width + margin
        self._line_chart(c, analysis.zip_trends.rent_history, analysis.zip_trends.rent_forecast, right, bottom, chart_width, chart_height, "Median Rent ($)")

    def _line_chart(
        self,
        c: canvas.Canvas,
        history: List[ZipTrendPoint],
        forecast: List[ZipTrendPoint],
        x: float,
        y: float,
        width: float,
        height: float,
        title: str,
    ) -> None:
        if not history:
            return
        c.setStrokeColor(colors.black)
        c.setLineWidth(1)
        c.rect(x, y, width, height, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x + 6, y + height - 16, title)

        all_points = history + forecast
        values = [pt.value for pt in all_points]
        min_val, max_val = min(values), max(values)
        if min_val == max_val:
            max_val = min_val + 1
        def scale(point: ZipTrendPoint, idx: int, total: int) -> tuple[float, float]:
            px = x + 12 + (idx / max(total - 1, 1)) * (width - 24)
            norm = (point.value - min_val) / (max_val - min_val)
            py = y + 12 + norm * (height - 24)
            return px, py

        history_points = list(history)
        forecast_points = list(forecast)
        c.setStrokeColor(colors.HexColor("#1565C0"))
        for i in range(1, len(history_points)):
            x1, y1 = scale(history_points[i - 1], i - 1, len(history_points) + len(forecast_points))
            x2, y2 = scale(history_points[i], i, len(history_points) + len(forecast_points))
            c.line(x1, y1, x2, y2)
        if forecast_points:
            c.setStrokeColor(colors.HexColor("#42A5F5"))
            offset = len(history_points) - 1
            for j in range(1, len(forecast_points)):
                idx1 = offset + j
                idx0 = offset + j - 1
                x1, y1 = scale(forecast_points[j - 1], idx0, len(history_points) + len(forecast_points))
                x2, y2 = scale(forecast_points[j], idx1, len(history_points) + len(forecast_points))
                c.line(x1, y1, x2, y2)

    def _draw_summary(self, c: canvas.Canvas, analysis: Analysis, width: float, height: float, margin: float) -> None:
        top = height / 2 - 36
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, top, "Broker Summary")
        c.setFont("Helvetica", 11)
        body = (
            f"{analysis.decision} recommendation with score {analysis.score}. "
            f"Current estimated value ${analysis.metrics.current_est_value:,.0f}. "
            "See charts for historic and projected trends."
        )
        text_obj = c.beginText(margin, top - 18)
        text_obj.textLines(body)
        c.drawText(text_obj)

