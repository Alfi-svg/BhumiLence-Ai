"""
Document Ingestion & Management Routes (Upload, Download, Status)
"""
from fastapi import APIRouter

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get("/")
async def list_documents():
    return {"status": "placeholder", "documents": []}
