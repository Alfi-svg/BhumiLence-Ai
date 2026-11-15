"""
Audit Trail, SHA-256 Ledger & Compliance Verification Routes.
Endpoints:
- GET /api/v1/audit/{doc_id} : Retrieves full cryptographic audit trail of events
- GET /api/v1/audit/{doc_id}/verify-hash : Performs runtime tamper detection by recomputing SHA-256
"""
from fastapi import APIRouter, HTTPException

from backend.services.audit_service import AuditPersistenceService

router = APIRouter(prefix="/audit", tags=["audit"])
audit_service = AuditPersistenceService()

@router.get("/{doc_id}")
async def get_audit_trail(doc_id: str):
    """
    Retrieves the complete immutable audit trail of events for a document.
    """
    doc = audit_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")

    return {
        "status": "success",
        "doc_id": doc_id,
        "current_state": doc.pipeline_state.value,
        "current_sha256": doc.current_record_sha256,
        "total_events": len(doc.audit_trail),
        "audit_trail": [event.model_dump() for event in doc.audit_trail],
        "legal_disclaimer": doc.legal_disclaimer
    }

@router.get("/{doc_id}/verify-hash")
async def verify_record_hash(doc_id: str):
    """
    Cryptographic verification endpoint.
    Recomputes the canonical SHA-256 hash over stored document data and compares
    against current_record_sha256 to detect any unauthorized database tampering.
    """
    try:
        integrity_status = audit_service.verify_record_integrity(doc_id)
        return integrity_status
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Integrity check failed: {str(e)}")
