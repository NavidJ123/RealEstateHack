"""Helper client used by the Streamlit app to talk to the API or fall back to local services."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

import requests
from requests import Response

from backend.db.repo import get_repository
from backend.models.analysis import AnalysisResponse
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
        self.repository: Optional[object] = None
        self.forecast_service: Optional[ForecastService] = None
        self.comps_service: Optional[CompsService] = None
        self.analysis_service: Optional[AnalysisService] = None
        self.broker: Optional[BrokerLLM] = None
        self.pdf_service: Optional[PDFService] = None
        if not self.use_api:
            self._enable_local_mode()

    def _ping_api(self) -> bool:
        try:
            resp = self.session.get(f"{self.base_url}/api/health", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def list_properties(self, submarket: Optional[str] = None, limit: int = 24) -> List[Dict]:
        if self.use_api:
            params = {"limit": limit}
            if submarket:
                params["submarket"] = submarket
            try:
                resp = self.session.get(f"{self.base_url}/api/properties", params=params, timeout=10)
                self._raise_for_status(resp)
                return resp.json()["items"]
            except requests.RequestException:
                pass
            self._enable_local_mode()
        properties = self.repository.list_properties(submarket=submarket, limit=limit)
        return [dict(prop) for prop in properties]

    def get_analysis(self, property_id: str) -> Dict:
        if self.use_api:
            try:
                resp = self.session.get(f"{self.base_url}/api/properties/{property_id}", timeout=10)
                if resp.status_code == 404:
                    raise ValueError("Property not found")
                self._raise_for_status(resp)
                data = resp.json()
                cache = self._analysis_cache.setdefault(property_id, {})
                cache["json"] = data
                return data
            except requests.RequestException:
                self._enable_local_mode()
        analysis = self.analysis_service.analyze_property(property_id)
        data = json.loads(analysis.json())
        cache = self._analysis_cache.setdefault(property_id, {})
        cache["json"] = data
        cache["model"] = analysis
        return data

    def score_analysis(self, analysis: Dict) -> Dict:
        property_id = analysis.get("property_id")
        cache = self._analysis_cache.setdefault(property_id, {}) if property_id else {}
        if "score" in cache:
            return cache["score"]  # type: ignore[return-value]
        if self.use_api:
            payload = {"mode": "thesis", "analysis_json": analysis}
            try:
                resp = self.session.post(f"{self.base_url}/api/broker", json=payload, timeout=20)
                self._raise_for_status(resp)
                result = resp.json()
            except requests.RequestException:
                self._enable_local_mode()
                model = cache.get("model")
                if model is None:
                    model = AnalysisResponse.parse_obj(analysis)
                    cache["model"] = model
                result = self.broker.score_and_explain(model)  # type: ignore[attr-defined]
        else:
            model = cache.get("model")
            if model is None:
                model = AnalysisResponse.parse_obj(analysis)
                cache["model"] = model
            result = self.broker.score_and_explain(model)  # type: ignore[attr-defined]
        cache["score"] = result
        return result

    def ask_broker(self, property_id: str, analysis: Dict, question: str) -> str:
        score = self.score_analysis(analysis)
        if self.use_api:
            payload = {"mode": "qa", "analysis_json": analysis, "question": question}
            try:
                resp = self.session.post(f"{self.base_url}/api/broker", json=payload, timeout=20)
                self._raise_for_status(resp)
                return resp.json()["text"]
            except requests.RequestException:
                self._enable_local_mode()
        model = self._analysis_cache.get(property_id, {}).get("model")
        if model is None:
            model = AnalysisResponse.parse_obj(analysis)
            self._analysis_cache.setdefault(property_id, {})["model"] = model
        reply = self.broker.qa(model, question, score)  # type: ignore[attr-defined]
        return reply

    def export_pdf(self, property_id: str) -> bytes:
        analysis = self.get_analysis(property_id)
        score = self.score_analysis(analysis)
        if self.use_api:
            try:
                resp = self.session.post(f"{self.base_url}/api/export/{property_id}", timeout=30)
                self._raise_for_status(resp)
                return resp.content
            except requests.RequestException:
                self._enable_local_mode()
        model = self._analysis_cache.get(property_id, {}).get("model")
        if model is None:
            model = self.analysis_service.analyze_property(property_id)
            self._analysis_cache.setdefault(property_id, {})["model"] = model
        return self.pdf_service.render(model, score)  # type: ignore[attr-defined]
    def _enable_local_mode(self) -> None:
        if self.repository is None:
            self.repository = get_repository()
            self.forecast_service = ForecastService(self.repository)
            self.comps_service = CompsService(self.repository)
            self.analysis_service = AnalysisService(self.repository, self.forecast_service, self.comps_service)
            self.broker = BrokerLLM()
            self.pdf_service = PDFService()
        self.use_api = False

    def _handle_api_failure(self, exc: Exception) -> None:
        self._enable_local_mode()

    def _raise_for_status(self, response: Response) -> None:
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            self._handle_api_failure(exc)
            raise
