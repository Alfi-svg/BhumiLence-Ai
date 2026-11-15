"""
Pydantic Data Models & Schemas Package
"""
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

class DocumentResponse(BaseModel):
    doc_id: str
    detected_layout: str
    workflow_state: str
    fields: Dict[str, Any]
    sha256_audit_hash: str
