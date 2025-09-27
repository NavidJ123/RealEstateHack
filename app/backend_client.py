"""Helper client used by the Streamlit app to talk to the API or fall back to local services."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

import requests

from backend.db.repo import get_repository
from backend.models.analysis import Analysis
from backend.services.analysis_service import AnalysisService
from backend.services.broker_llm import BrokerLLM
from backend.services.comps_service import CompsService
from backend.services.forecast_service import ForecastService
from backend.services.pdf_service import PDFService


class BackendClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        self.session = requests.Session()
        self.use_api = self._ping_api()
        self._analysis_cache: Dict[str, Dict[str, object]] = {}
        if not self.use_api:
            self.repository = get_repository()
            self.forecast_service = ForecastService(self.repository)
            self.comps_service = CompsService(self.repository)
            self.analysis_service = AnalysisService(self.repository, self.forecast_service, self.comps_service)
            self.broker = BrokerLLM()
            self.pdf_service = PDFService()

    def _ping_api(self) -> bool:
        try:
            resp = self.session.get(f"{self.base_url}/health", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def list_properties(self, zipcode: Optional[str] = None, limit: int = 24) -> List[Dict]:
        if self.use_api:
            params = {"limit": limit}
            if zipcode:
                params["zip"] = zipcode
            resp = self.session.get(f"{self.base_url}/api/properties", params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()["items"]
        properties = self.repository.list_properties(zipcode=zipcode, limit=None)
        return [prop.dict() for prop in properties][:limit]

    def get_analysis(self, property_id: str) -> Dict:
        if self.use_api:
            resp = self.session.get(f"{self.base_url}/api/properties/{property_id}", timeout=10)
            if resp.status_code == 404:
                raise ValueError("Property not found")
            resp.raise_for_status()
            data = resp.json()
            self._analysis_cache[property_id] = {"json": data}
            return data
        analysis = self.analysis_service.analyze_property(property_id)
        data = json.loads(analysis.json())
        self._analysis_cache[property_id] = {"json": data, "model": analysis}
        return data

    def ask_broker(self, property_id: str, analysis: Dict, question: str) -> str:
        if self.use_api:
            payload = {"analysis_json": analysis, "question": question}
            resp = self.session.post(f"{self.base_url}/api/broker", json=payload, timeout=20)
            resp.raise_for_status()
            messages = resp.json()["messages"]
            return messages[-1]["content"]
        cache = self._analysis_cache.get(property_id)
        model: Analysis
        if cache and "model" in cache:
            model = cache["model"]  # type: ignore[assignment]
        else:
            model = self.analysis_service.analyze_property(property_id)
            self._analysis_cache[property_id] = {"json": json.loads(model.json()), "model": model}
        reply = self.broker.invoke(model, question)
        return reply[-1].content if reply else "No response available."

    def export_pdf(self, property_id: str) -> bytes:
        if self.use_api:
            resp = self.session.post(f"{self.base_url}/api/export/{property_id}", timeout=30)
            resp.raise_for_status()
            return resp.content
        cache = self._analysis_cache.get(property_id)
        model: Analysis
        if cache and "model" in cache:
            model = cache["model"]  # type: ignore[assignment]
        else:
            model = self.analysis_service.analyze_property(property_id)
            self._analysis_cache[property_id] = {"json": json.loads(model.json()), "model": model}
        return self.pdf_service.render(model)

