from fastapi import FastAPI, APIRouter, HTTPException, Query
from typing import Optional, Union

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

if load_dotenv is not None:
    from pathlib import Path

    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)

from .services.analysis_service import analyze_property
from .db.repo import Repo
from .services.broker_llm import BrokerLLM

app = FastAPI()
router = APIRouter(prefix="/api")
repo = Repo()
llm  = BrokerLLM()

@router.get("/properties")
def list_props(submarket: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=500)):
    rows = repo.list_properties(submarket=submarket, limit=limit)
    return rows

@router.get("/properties/{sys_id}")
def get_prop(sys_id: str):
    return analyze_property(sys_id)

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

app.include_router(router)
