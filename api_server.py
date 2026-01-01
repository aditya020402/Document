from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum
import tempfile
from pathlib import Path
from datetime import datetime

# Import your existing classes
from document_automation_workflow import DocumentAutomationWorkflow
from token_tracker import TokenTracker

# FastAPI app
app = FastAPI(
    title="Document Automation Analyzer API",
    description="AI-powered document analysis for automation and content quality",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Initialize (using your existing DB configs)
DB_CONFIG = {
    'dbname': 'automation_db',
    'user': 'your_username',
    'password': 'your_password',
    'host': 'localhost',
    'port': '5432'
}

AZURE_CONFIG = {
    'api_key': 'your-key',
    'api_version': '2023-05-15',
    'endpoint': 'your-endpoint',
    'embedding_deployment': 'text-embedding-ada-002'
}

workflow = DocumentAutomationWorkflow(db_config=DB_CONFIG, azure_embedding_config=AZURE_CONFIG)
tracker = TokenTracker()

# Models
class WorkflowMode(str, Enum):
    full_automation = "full_automation"
    content_improvement = "content_improvement"

class TextRequest(BaseModel):
    text_content: str = Field(..., min_length=50)
    workflow_mode: WorkflowMode = WorkflowMode.full_automation
    document_name: str = "text_doc.txt"

# Endpoints
@app.get("/")
async def root():
    return {"name": "Document Automation API", "docs": "/docs"}

@app.post("/api/v1/analyze/pdf", tags=["Analysis"])
async def analyze_pdf(file: UploadFile = File(...), workflow_mode: WorkflowMode = WorkflowMode.full_automation):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "Only PDF files allowed")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    
    try:
        results = await workflow.process_document(tmp_path, workflow_mode.value)
        Path(tmp_path).unlink()
        return results
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/v1/analyze/text", tags=["Analysis"])
async def analyze_text(request: TextRequest):
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp:
        tmp.write(request.text_content)
        tmp_path = tmp.name
    
    try:
        results = await workflow.process_text_document(tmp_path, request.workflow_mode.value)
        Path(tmp_path).unlink()
        return results
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/v1/tokens/statistics", tags=["Tokens"])
async def get_stats():
    return tracker.get_total_usage()

@app.get("/api/v1/tokens/sessions/recent", tags=["Tokens"])
async def get_sessions(limit: int = 10):
    return tracker.get_recent_sessions(limit)

@app.get("/api/v1/tokens/sessions/{session_id}/agents", tags=["Tokens"])
async def get_agents(session_id: int):
    breakdown = tracker.get_agent_breakdown(session_id)
    if not breakdown:
        raise HTTPException(404, "Session not found")
    return breakdown

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
