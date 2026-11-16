"""
Human-in-the-Loop Maker-Checker ("Four-Eyes") Review & Approval Routes.
Enforces:
1. Strict separation of duties: checker_id CANNOT equal maker_id.
2. State transitions: AI_EXTRACTED_PENDING_MAKER -> MAKER_VERIFIED_PENDING_CHECKER -> CHECKER_APPROVED_LOCKED.
3. Cryptographic seal updates on every stage.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Header, status

from backend.services.audit_service import (
    AuditPersistenceService,
    MakerCheckerViolationException,
    RecordLockedException
)
from backend.services.security_service import SecurityGuardService

router = APIRouter(prefix="/review", tags=["review"])
audit_service = AuditPersistenceService()
security_service = SecurityGuardService()

class MakerSubmitRequest(BaseModel):
    maker_id: str = Field(..., min_length=2, description="Identifier of the Maker operator (e.g. OP_MAKER_01)")
    human_corrected_data: Dict[str, Any] = Field(..., description="Complete or partial corrected deed metadata")
    comments: Optional[str] = Field(default=None, description="Maker review commentary or observations")

class CheckerApproveRequest(BaseModel):
    checker_id: str = Field(..., min_length=2, description="Identifier of the Checker supervisor (e.g. SUP_CHECKER_02)")
    comments: Optional[str] = Field(default=None, description="Checker approval comments")

@router.post("/{doc_id}/maker-submit")
async def maker_submit(
    doc_id: str,
    payload: MakerSubmitRequest,
    x_actor_id: Optional[str] = Header(None),
    x_actor_role: Optional[str] = Header(None)
):
    """
    Submits human-verified deed data by the Maker operator.
    Transitions state from AI_EXTRACTED_PENDING_MAKER to MAKER_VERIFIED_PENDING_CHECKER.
    """
    try:
        actor_id = payload.maker_id or x_actor_id or "UNKNOWN_MAKER"
        if x_actor_role:
            security_service.verify_maker_checker_roles(
                actor_id=actor_id,
                actor_role=x_actor_role,
                required_role="MAKER"
            )

        updated_record = audit_service.submit_maker_verification(
            doc_id=doc_id,
            human_corrected_data=payload.human_corrected_data,
            maker_id=actor_id,
            comments=payload.comments
        )
        return {
            "status": "success",
            "message": "Maker review submitted successfully. Document pending Checker approval.",
            "doc_id": doc_id,
            "pipeline_state": updated_record.pipeline_state.value,
            "record_sha256": updated_record.current_record_sha256,
            "maker_id": updated_record.maker_id
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RecordLockedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Maker submission failed: {str(e)}")

@router.post("/{doc_id}/checker-approve")
async def checker_approve(
    doc_id: str,
    payload: CheckerApproveRequest,
    x_actor_id: Optional[str] = Header(None),
    x_actor_role: Optional[str] = Header(None)
):
    """
    Approves and cryptographically locks verified deed record by the Checker supervisor.
    STRICT SECURITY INVARIANT: checker_id CANNOT be the same user as maker_id.
    """
    try:
        actor_id = payload.checker_id or x_actor_id or "UNKNOWN_CHECKER"
        if x_actor_role:
            security_service.verify_maker_checker_roles(
                actor_id=actor_id,
                actor_role=x_actor_role,
                required_role="CHECKER"
            )

        updated_record = audit_service.approve_checker_verification(
            doc_id=doc_id,
            checker_id=actor_id,
            comments=payload.comments
        )
        return {
            "status": "success",
            "message": "Checker approval locked successfully. Record is immutable.",
            "doc_id": doc_id,
            "pipeline_state": updated_record.pipeline_state.value,
            "record_sha256": updated_record.current_record_sha256,
            "maker_id": updated_record.maker_id,
            "checker_id": updated_record.checker_id,
            "legal_disclaimer": updated_record.legal_disclaimer
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except MakerCheckerViolationException as e:
        raise HTTPException(
            status_code=400,
            detail=f"Four-Eyes Governance Violation: {str(e)}"
        )
    except RecordLockedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Checker approval failed: {str(e)}")
