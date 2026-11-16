"""
Document Ingestion & Management Routes.
Endpoints:
- POST /api/v1/documents/upload : Uploads deed image, computes SHA-256, and stores in outputs/uploads/
- GET /api/v1/documents/{doc_id} : Retrieves document record and lifecycle state
- GET /api/v1/documents : Lists registered documents with optional state filter
"""
import os
import shutil
import hashlib
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status

from backend.services.audit_service import AuditPersistenceService
from backend.services.security_service import SecurityGuardService

router = APIRouter(prefix="/documents", tags=["documents"])
audit_service = AuditPersistenceService()
security_service = SecurityGuardService()

UPLOAD_DIR = Path("outputs/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    doc_id: Optional[str] = Form(None)
):
    """
    Uploads a document image, verifies magic bytes, enforces path safety, computes cryptographic SHA-256 hash, and stages for pipeline processing.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")

    # 1. Path-traversal sanitization
    clean_filename = security_service.sanitize_filename(file.filename)
    assigned_doc_id = doc_id or Path(clean_filename).stem.upper()
    dest_path = UPLOAD_DIR / f"{assigned_doc_id}_{clean_filename}"

    # 2. Read bytes and validate size & magic byte signature
    file_bytes = await file.read()
    detected_mime = security_service.validate_file_content(file_bytes, clean_filename)

    # 3. Cryptographic SHA-256 hash calculation
    hasher = hashlib.sha256()
    hasher.update(file_bytes)
    file_sha256 = hasher.hexdigest()

    with open(dest_path, "wb") as f:
        f.write(file_bytes)

    return {
        "status": "success",
        "doc_id": assigned_doc_id,
        "filename": clean_filename,
        "file_name": clean_filename,
        "file_path": str(dest_path),
        "file_size_bytes": len(file_bytes),
        "detected_mime": detected_mime,
        "mime_type": detected_mime,
        "sha256": file_sha256
    }

@router.get("/{doc_id}")
async def get_document_details(doc_id: str):
    """
    Retrieves full document record, lifecycle state, and audit trail.
    """
    doc = audit_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")
    return doc.model_dump()

@router.get("")
@router.get("/")
async def list_documents(state: Optional[str] = None, limit: int = 50):
    """
    Lists registered documents with optional pipeline state filtering.
    """
    records = audit_service.list_documents(state=state, limit=limit)
    return {
        "status": "success",
        "total_records": len(records),
        "filter_state": state,
        "documents": records
    }
