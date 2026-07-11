"""FastAPI surface. Deliberately thin.

All logic lives in `app.pipeline`. This module only does HTTP concerns: parse the
multipart body, spill the upload to a temp file, translate exceptions into status
codes. Previously the analysis logic was copy-pasted in here alongside
`intelligence_layer.py`; that duplication is gone.
"""
from __future__ import annotations

import json
import os
import tempfile
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from .categorizer import SemanticCategorizer, build_groq_llm_fn
from .embeddings import HashingEmbedder, SentenceTransformerEmbedder
from .parser import StatementParseError, parse_bank_statement
from .pipeline import analyze
from .scheme_matcher import SchemeMatcher


def _build_embedder():
    """Real embeddings if the model loads; hashing fallback otherwise.

    A missing torch install should degrade the semantic tier, not 500 the API.
    """
    embedder = SentenceTransformerEmbedder()
    try:
        embedder.encode(["warmup"])
        return embedder
    except Exception:
        return HashingEmbedder()


def build_state() -> dict:
    embedder = _build_embedder()
    llm = build_groq_llm_fn() if os.environ.get("GROQ_API_KEY") else None
    return {
        "embedder": embedder,
        "categorizer": SemanticCategorizer(embedder=embedder, llm_fn=llm),
        "matcher": SchemeMatcher(embedder=embedder),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the model once at boot, not on the first user's request.

    Anything already placed on `app.state` is left alone, which is what lets a
    test inject a fake categorizer without the startup hook clobbering it.
    """
    if not getattr(app.state, "configured", False):
        for key, value in build_state().items():
            setattr(app.state, key, value)
        app.state.configured = True
    yield


app = FastAPI(title="MSME AI Advisor API", lifespan=lifespan)


def get_categorizer(request: Request) -> SemanticCategorizer:
    return request.app.state.categorizer


def get_matcher(request: Request) -> SchemeMatcher:
    return request.app.state.matcher


@app.get("/health")
def health(request: Request):
    embedder = getattr(request.app.state, "embedder", None)
    return {
        "status": "ok",
        "embedder": type(embedder).__name__ if embedder else "uninitialized",
        "llm_tier_enabled": getattr(request.app.state.categorizer, "llm_fn", None) is not None,
    }


@app.post("/api/analyze")
async def analyze_business(
    file: UploadFile = File(...),
    profile_data: str = Form(...),
    need_text: str = Form(""),
    categorizer: SemanticCategorizer = Depends(get_categorizer),
    matcher: SchemeMatcher = Depends(get_matcher),
):
    try:
        base_profile = json.loads(profile_data)
    except json.JSONDecodeError as exc:
        return JSONResponse(status_code=400, content={"error": f"profile_data is not valid JSON: {exc}"})

    current_balance = base_profile.get("current_bank_balance_inr", 50_000)

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        transactions = parse_bank_statement(tmp_path, categorizer)
        return analyze(transactions, base_profile, current_balance, need_text, matcher)

    except StatementParseError as exc:
        # User-facing, user-fixable. Their file, not our bug.
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Internal Server Error: {exc}"})
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)  # runs even on the error paths above

