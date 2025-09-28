from fastapi import FastAPI, APIRouter, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from typing import Any, Optional, Union
app = FastAPI()
router = APIRouter(prefix="/api")
import math

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

if load_dotenv is not None:
    from pathlib import Path

    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)




def _sanitize(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value

from .services.analysis_service import analyze_property
from .db.repo import Repo
from .services.broker_llm import BrokerLLM
from .services.pdf_service import PDFService
from .models.analysis import AnalysisResponse

app = FastAPI()
router = APIRouter(prefix="/api")
repo = Repo()
llm  = BrokerLLM()
pdf_service = PDFService()

@router.get("/properties")
def list_props(submarket: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=500)):
    rows = repo.list_properties(submarket=submarket, limit=limit)
    payload = {"items": [_sanitize(row) for row in rows], "total": len(rows)}
    return jsonable_encoder(payload)

@router.get("/properties/{sys_id}")
def get_prop(sys_id: str):
    analysis = analyze_property(sys_id)
    return jsonable_encoder(_sanitize(analysis.dict()))


@router.post("/export/{sys_id}")
def export_property(sys_id: str):
    analysis = analyze_property(sys_id)
    sanitized = _sanitize(analysis.dict())
    score_payload = llm.score_and_explain(sanitized)
    analysis_model = AnalysisResponse.parse_obj(sanitized)
    pdf_bytes = pdf_service.render(analysis_model, score_payload)  # pragma: no cover
    return Response(content=pdf_bytes, media_type="application/pdf")

from pydantic import BaseModel
class BrokerReq(BaseModel):
    mode: str
    analysis_json: dict
    question: Optional[str] = None

@router.post("/broker")
def broker_route(req: BrokerReq):
    if req.mode == "thesis":
        return llm.score_and_explain(req.analysis_json)  # JSON with score/decision/rationale
    if req.mode == "qa":
        if not req.question:
            raise HTTPException(400, detail="question required for qa mode")
        return {"text": llm.qa(req.analysis_json, req.question)}
    raise HTTPException(400, detail="invalid mode")

@router.get("/health")
def health(): return {"status":"ok"}

@router.get("/llm_probe")
def llm_probe():
    from .services.broker_llm import BrokerLLM
    b = BrokerLLM()
    if not b._model:
        return {"ok": False, "why": "no_model"}
    try:
        t = b._model.generate_content("ping").text
        return {"ok": True, "model": b.model_name, "sample": (t or "")[:40]}
    except Exception as e:
        return {"ok": False, "model": b.model_name, "error": str(e)}

app.include_router(router)
