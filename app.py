from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uuid

app = FastAPI(title="AI Business Companion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query_text: str
    language: str = "en"
    audio_base64: Optional[str] = None

class BusinessProfile(BaseModel):
    business_id: str
    state: str
    sector: str
    turnover_inr: float
    employee_count: int
    udyam_registered: bool
    women_owned: bool

@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...)
):
    # Mocking Person A's embedding process
    return {
        "document_id": str(uuid.uuid4()),
        "status": "success",
        "chunks_processed": 12
    }

@app.post("/api/qa/ask")
async def ask_question(request: QueryRequest):
    # Mocking Person A's RAG answering logic
    mock_answer = f"Based on your documents, the answer to '{request.query_text}' is: You qualify for the MSME loan."
    
    # Normally we would call voice_module.py for TTS if requested, but for now we'll mock the response.
    return {
        "answer_text": mock_answer,
        "answer_audio_base64": "",
        "sources": ["Udyam Certificate", "GST Return"]
    }

@app.post("/api/transactions/parse")
async def parse_transactions(file: UploadFile = File(...)):
    # Mocking Person C's transaction parser
    return [
        {
            "transaction_id": "tx_10485",
            "date": "2026-07-01",
            "description": "UPI/Zomato/Oder123",
            "amount": -450.00,
            "type": "debit",
            "category": "Office Expenses",
            "flagged_anomaly": False
        }
    ]

@app.post("/api/schemes/match")
async def match_schemes(profile: BusinessProfile):
    # Mocking Person C's Scheme Matcher
    return [
        {
            "scheme_name": "Credit Guarantee Fund Trust for Micro and Small Enterprises (CGTMSE)",
            "match_score": 95,
            "eligibility_reason": "Matches turnover and manufacturing sector criteria.",
            "application_url": "https://www.cgtmse.in/"
        },
        {
            "scheme_name": "Prime Minister's Employment Generation Programme (PMEGP)",
            "match_score": 82,
            "eligibility_reason": "Matches sector, but funding limits may apply based on current loan profile.",
            "application_url": "https://www.kviconline.gov.in/"
        }
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0", port=8000)
