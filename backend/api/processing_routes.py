"""
Processing & Multi-Agent Orchestration Routes.
Endpoints:
- POST /api/v1/process/run : Executes full Supervisor pipeline (Agents 1 -> 2 -> 3 -> 4 -> Audit Persistence)
"""
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.agents.supervisor import BhumiLensSupervisor

router = APIRouter(prefix="/process", tags=["processing"])
supervisor = BhumiLensSupervisor()

DEFAULT_SAMPLE_IMAGE = Path("sample_data/sample_dolil_100_anonymized.jpg")

class ProcessRequest(BaseModel):
    image_path: Optional[str] = Field(default=None, description="Path to target document image on disk")
    doc_id: Optional[str] = Field(default=None, description="Optional custom document tracking ID")
    actor_id: str = Field(default="BHUMILENS_API_USER", description="Requesting operator or service ID")

@router.post("/run")
async def run_pipeline(payload: ProcessRequest):
    """
    Executes the complete multi-agent pipeline:
    Agent 1 (Vision) -> Agent 2 (HTR) -> Agent 3 (Extraction) -> Agent 4 (Verification) -> Layer 7 (Audit DB)
    """
    target_image = Path(payload.image_path) if payload.image_path else DEFAULT_SAMPLE_IMAGE

    if not target_image.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Target image path '{target_image}' does not exist on disk."
        )

    assigned_doc_id = payload.doc_id or target_image.stem.upper()

    try:
        result = await supervisor.aprocess_document(
            image_path=str(target_image),
            doc_id=assigned_doc_id,
            actor_id=payload.actor_id
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline execution failed: {str(e)}"
        )
