"""FastAPI application exposing property analytics endpoints."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .db.repo import get_repository
from .models.analysis import (
    Analysis,
    AnalyzeRequest,
    BrokerRequest,
    BrokerResponse,
    ExportResponse,
)
from .models.property import PropertyListResponse
from .services.analysis_service import AnalysisService
from .services.broker_llm import BrokerLLM
from .services.comps_service import CompsService
from .services.forecast_service import ForecastService
from .services.pdf_service import PDFService
from .utils.logging import get_logger

LOGGER = get_logger("api")

app = FastAPI(title="AI Real Estate Broker (DC)", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_repository = get_repository()
_forecast_service = ForecastService(_repository)
_comps_service = CompsService(_repository)
_analysis_service = AnalysisService(_repository, _forecast_service, _comps_service)
_broker = BrokerLLM()
_pdf_service = PDFService()


@app.on_event("startup")
async def _startup() -> None:
    LOGGER.info("API startup complete")


@app.get("/api/properties", response_model=PropertyListResponse)
def list_properties(zip: Optional[str] = Query(None, min_length=5, max_length=5), limit: int = Query(20, ge=1, le=50)) -> PropertyListResponse:
    all_properties = _repository.list_properties(zipcode=zip, limit=None)
    items = all_properties[:limit]
    return PropertyListResponse(items=items, total=len(all_properties))


@app.get("/api/properties/{property_id}", response_model=Analysis)
def get_property_analysis(property_id: str) -> Analysis:
    try:
        return _analysis_service.analyze_property(property_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/analyze", response_model=Analysis)
def analyze(body: AnalyzeRequest = Body(...)) -> Analysis:
    property_id = body.id
    if not property_id and body.address:
        match = next((p for p in _repository.list_properties(limit=None) if p.address.lower() == body.address.lower()), None)
        if match:
            property_id = match.id
    if not property_id:
        raise HTTPException(status_code=400, detail="Must provide property id or address")
    return get_property_analysis(property_id)


@app.post("/api/broker", response_model=BrokerResponse)
def broker(body: BrokerRequest = Body(...)) -> BrokerResponse:
    messages = _broker.invoke(body.analysis_json, body.question)
    return BrokerResponse(messages=messages)


@app.post("/api/export/{property_id}", response_model=ExportResponse)
def export_pdf(property_id: str) -> Response:
    analysis = get_property_analysis(property_id)
    pdf_bytes = _pdf_service.render(analysis)
    filename = f"{property_id}_investor_brief.pdf"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})

