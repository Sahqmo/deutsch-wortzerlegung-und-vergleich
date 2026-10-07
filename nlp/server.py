"""분석 서비스. `python -m uvicorn server:app --port 8000` (nlp 폴더에서) 로 실행."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from pipeline import analyze
from translator import GtxTranslator

log = logging.getLogger("nlp")
app = FastAPI(title="German compound analyzer")
translator = GtxTranslator()


class Req(BaseModel):
    word: str


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/analyze")
def analyze_endpoint(req: Req) -> dict:
    try:
        return analyze(req.word, translator)
    except RuntimeError as e:  # 번역기 호출 실패
        log.warning("translator error: %s", e)
        raise HTTPException(status_code=502, detail="번역 서비스에 연결하지 못했어요.") from e
