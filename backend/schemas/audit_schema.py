"""
BhumiLens AI — Audit, Governance & Maker-Checker Workflow Schema.
Pydantic v2 data models for:
- State machine lifecycle (AI_EXTRACTED_PENDING_MAKER -> MAKER_VERIFIED_PENDING_CHECKER -> CHECKER_APPROVED_LOCKED)
- Cryptographic SHA-256 seal & tamper detection
- Maker-Checker separation enforcement
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class WorkflowState(str, Enum):
    AI_EXTRACTED_PENDING_MAKER = "AI_EXTRACTED_PENDING_MAKER"
    MAKER_VERIFIED_PENDING_CHECKER = "MAKER_VERIFIED_PENDING_CHECKER"
    CHECKER_APPROVED_LOCKED = "CHECKER_APPROVED_LOCKED"
    REJECTED_REVISION_REQUESTED = "REJECTED_REVISION_REQUESTED"

class AuditRole(str, Enum):
    AI_SYSTEM = "AI_SYSTEM"
    MAKER = "MAKER"
    CHECKER = "CHECKER"
    AUDITOR = "AUDITOR"

class AuditAction(str, Enum):
    AI_EXTRACTED = "AI_EXTRACTED"
    MAKER_SUBMITTED = "MAKER_SUBMITTED"
    CHECKER_APPROVED = "CHECKER_APPROVED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    RECORD_EXPORTED = "RECORD_EXPORTED"
    INTEGRITY_CHECKED = "INTEGRITY_CHECKED"

class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    event_id: str
    doc_id: str
    actor_id: str
    role: AuditRole
    action: AuditAction
    timestamp_utc: str
    previous_hash: Optional[str] = None
    record_sha256: str
    details: Dict[str, Any] = Field(default_factory=dict)

class DocumentRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    doc_id: str
    original_image_sha256: str
    pipeline_state: WorkflowState
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    human_corrected_data: Optional[Dict[str, Any]] = None
    verification_report: Optional[Dict[str, Any]] = None
    evidence_manifest: Optional[Dict[str, Any]] = None
    current_record_sha256: str
    created_at_utc: str
    updated_at_utc: str
    maker_id: Optional[str] = None
    checker_id: Optional[str] = None
    audit_trail: List[AuditEvent] = Field(default_factory=list)
    legal_disclaimer: str = (
        "LEGAL AUTHORITY DISCLAIMER: SHA-256 cryptographic seal verifies data immutability "
        "and record integrity within BhumiLens AI. It does NOT constitute legal title, "
        "judicial deed validity, or state-sanctioned land ownership."
    )
