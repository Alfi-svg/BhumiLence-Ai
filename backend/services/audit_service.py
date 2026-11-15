"""
BhumiLens AI — Audit Persistence & Maker-Checker Service (Layer 7).
Implements:
1. SQLite-backed persistence in outputs/bhumilens_records.db.
2. Complete document lifecycle state machine:
   AI_EXTRACTED_PENDING_MAKER -> MAKER_VERIFIED_PENDING_CHECKER -> CHECKER_APPROVED_LOCKED
3. Strict Maker-Checker separation (checker_id != maker_id) enforcing Four-Eyes principle.
4. Cryptographic SHA-256 canonical seals and tamper-detection verification.
5. Append-only immutable audit trail recording every state change and user action.
"""
import sqlite3
import json
import hashlib
import uuid
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from backend.schemas.audit_schema import (
    WorkflowState,
    AuditRole,
    AuditAction,
    AuditEvent,
    DocumentRecord
)

DEFAULT_DB_PATH = Path("outputs/bhumilens_records.db")

LEGAL_DISCLAIMER = (
    "LEGAL AUTHORITY DISCLAIMER: SHA-256 cryptographic seal verifies data immutability "
    "and record integrity within BhumiLens AI. It does NOT constitute legal title, "
    "judicial deed validity, or state-sanctioned land ownership."
)

class MakerCheckerViolationException(ValueError):
    """Raised when the same individual attempts both Maker and Checker roles."""
    pass

class RecordLockedException(PermissionError):
    """Raised when an edit is attempted on a locked/approved record."""
    pass

class AuditPersistenceService:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    original_image_sha256 TEXT NOT NULL,
                    pipeline_state TEXT NOT NULL,
                    extracted_json TEXT NOT NULL,
                    human_corrected_json TEXT,
                    verification_report_json TEXT,
                    evidence_manifest_json TEXT,
                    current_record_sha256 TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    maker_id TEXT,
                    checker_id TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    action TEXT NOT NULL,
                    timestamp_utc TEXT NOT NULL,
                    previous_hash TEXT,
                    record_sha256 TEXT NOT NULL,
                    details_json TEXT,
                    FOREIGN KEY (doc_id) REFERENCES documents (doc_id)
                )
            """)
            conn.commit()

    @staticmethod
    def compute_canonical_hash(
        doc_id: str,
        image_sha256: str,
        state: str,
        extracted_data: Dict[str, Any],
        human_corrected: Optional[Dict[str, Any]],
        maker_id: Optional[str],
        checker_id: Optional[str]
    ) -> str:
        canonical_dict = {
            "doc_id": doc_id,
            "original_image_sha256": image_sha256,
            "pipeline_state": state,
            "extracted_data": extracted_data,
            "human_corrected_data": human_corrected or {},
            "maker_id": maker_id or "",
            "checker_id": checker_id or ""
        }
        canonical_str = json.dumps(canonical_dict, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def create_initial_record(
        self,
        doc_id: str,
        original_image_sha256: str,
        extracted_data: Dict[str, Any],
        verification_report: Optional[Dict[str, Any]] = None,
        evidence_manifest: Optional[Dict[str, Any]] = None,
        actor_id: str = "BHUMILENS_AI_PIPELINE"
    ) -> DocumentRecord:
        """
        Saves initial AI extraction with state AI_EXTRACTED_PENDING_MAKER.
        """
        state = WorkflowState.AI_EXTRACTED_PENDING_MAKER.value
        record_hash = self.compute_canonical_hash(
            doc_id=doc_id,
            image_sha256=original_image_sha256,
            state=state,
            extracted_data=extracted_data,
            human_corrected=None,
            maker_id=None,
            checker_id=None
        )
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO documents (
                    doc_id, original_image_sha256, pipeline_state,
                    extracted_json, human_corrected_json, verification_report_json,
                    evidence_manifest_json, current_record_sha256, created_at_utc,
                    updated_at_utc, maker_id, checker_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_id,
                original_image_sha256,
                state,
                json.dumps(extracted_data, ensure_ascii=False),
                None,
                json.dumps(verification_report, ensure_ascii=False) if verification_report else None,
                json.dumps(evidence_manifest, ensure_ascii=False) if evidence_manifest else None,
                record_hash,
                now_iso,
                now_iso,
                None,
                None
            ))

            event_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO audit_events (
                    event_id, doc_id, actor_id, role, action,
                    timestamp_utc, previous_hash, record_sha256, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                doc_id,
                actor_id,
                AuditRole.AI_SYSTEM.value,
                AuditAction.AI_EXTRACTED.value,
                now_iso,
                None,
                record_hash,
                json.dumps({"stage": "Supervisor Orchestration", "state": state})
            ))
            conn.commit()

        return self.get_document(doc_id)

    def submit_maker_verification(
        self,
        doc_id: str,
        human_corrected_data: Dict[str, Any],
        maker_id: str,
        comments: Optional[str] = None
    ) -> DocumentRecord:
        """
        Maker operator reviews and submits corrected deed data.
        Transitions state to MAKER_VERIFIED_PENDING_CHECKER.
        """
        existing = self.get_document(doc_id)
        if not existing:
            raise KeyError(f"Document {doc_id} not found.")

        if existing.pipeline_state == WorkflowState.CHECKER_APPROVED_LOCKED:
            raise RecordLockedException(f"Document {doc_id} is locked following Checker approval. Modifications are forbidden.")

        new_state = WorkflowState.MAKER_VERIFIED_PENDING_CHECKER.value
        prev_hash = existing.current_record_sha256
        new_hash = self.compute_canonical_hash(
            doc_id=doc_id,
            image_sha256=existing.original_image_sha256,
            state=new_state,
            extracted_data=existing.extracted_data,
            human_corrected=human_corrected_data,
            maker_id=maker_id,
            checker_id=existing.checker_id
        )
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE documents SET
                    pipeline_state = ?,
                    human_corrected_json = ?,
                    current_record_sha256 = ?,
                    updated_at_utc = ?,
                    maker_id = ?
                WHERE doc_id = ?
            """, (
                new_state,
                json.dumps(human_corrected_data, ensure_ascii=False),
                new_hash,
                now_iso,
                maker_id,
                doc_id
            ))

            event_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO audit_events (
                    event_id, doc_id, actor_id, role, action,
                    timestamp_utc, previous_hash, record_sha256, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                doc_id,
                maker_id,
                AuditRole.MAKER.value,
                AuditAction.MAKER_SUBMITTED.value,
                now_iso,
                prev_hash,
                new_hash,
                json.dumps({"comments": comments or "Maker verification submitted."})
            ))
            conn.commit()

        return self.get_document(doc_id)

    def approve_checker_verification(
        self,
        doc_id: str,
        checker_id: str,
        comments: Optional[str] = None
    ) -> DocumentRecord:
        """
        Checker supervisor approves verified record.
        STRICT RULE: checker_id CANNOT equal maker_id.
        Transitions state to CHECKER_APPROVED_LOCKED.
        """
        existing = self.get_document(doc_id)
        if not existing:
            raise KeyError(f"Document {doc_id} not found.")

        if existing.pipeline_state == WorkflowState.CHECKER_APPROVED_LOCKED:
            raise RecordLockedException(f"Document {doc_id} is already approved and locked.")

        # Four-Eyes principle enforcement
        if existing.maker_id and existing.maker_id.strip().lower() == checker_id.strip().lower():
            raise MakerCheckerViolationException(
                f"Maker-Checker conflict: checker_id '{checker_id}' cannot equal maker_id '{existing.maker_id}'. "
                "The Four-Eyes Principle strictly requires two distinct individuals."
            )

        new_state = WorkflowState.CHECKER_APPROVED_LOCKED.value
        prev_hash = existing.current_record_sha256
        new_hash = self.compute_canonical_hash(
            doc_id=doc_id,
            image_sha256=existing.original_image_sha256,
            state=new_state,
            extracted_data=existing.extracted_data,
            human_corrected=existing.human_corrected_data,
            maker_id=existing.maker_id,
            checker_id=checker_id
        )
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE documents SET
                    pipeline_state = ?,
                    current_record_sha256 = ?,
                    updated_at_utc = ?,
                    checker_id = ?
                WHERE doc_id = ?
            """, (
                new_state,
                new_hash,
                now_iso,
                checker_id,
                doc_id
            ))

            event_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO audit_events (
                    event_id, doc_id, actor_id, role, action,
                    timestamp_utc, previous_hash, record_sha256, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                doc_id,
                checker_id,
                AuditRole.CHECKER.value,
                AuditAction.CHECKER_APPROVED.value,
                now_iso,
                prev_hash,
                new_hash,
                json.dumps({"comments": comments or "Checker approval locked."})
            ))
            conn.commit()

        return self.get_document(doc_id)

    def get_document(self, doc_id: str) -> Optional[DocumentRecord]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
            row = cur.fetchone()
            if not row:
                return None

            # Fetch audit events
            cur.execute("SELECT * FROM audit_events WHERE doc_id = ? ORDER BY timestamp_utc ASC", (doc_id,))
            event_rows = cur.fetchall()

            events: List[AuditEvent] = []
            for er in event_rows:
                events.append(AuditEvent(
                    event_id=er["event_id"],
                    doc_id=er["doc_id"],
                    actor_id=er["actor_id"],
                    role=AuditRole(er["role"]),
                    action=AuditAction(er["action"]),
                    timestamp_utc=er["timestamp_utc"],
                    previous_hash=er["previous_hash"],
                    record_sha256=er["record_sha256"],
                    details=json.loads(er["details_json"]) if er["details_json"] else {}
                ))

            return DocumentRecord(
                doc_id=row["doc_id"],
                original_image_sha256=row["original_image_sha256"],
                pipeline_state=WorkflowState(row["pipeline_state"]),
                extracted_data=json.loads(row["extracted_json"]),
                human_corrected_data=json.loads(row["human_corrected_json"]) if row["human_corrected_json"] else None,
                verification_report=json.loads(row["verification_report_json"]) if row["verification_report_json"] else None,
                evidence_manifest=json.loads(row["evidence_manifest_json"]) if row["evidence_manifest_json"] else None,
                current_record_sha256=row["current_record_sha256"],
                created_at_utc=row["created_at_utc"],
                updated_at_utc=row["updated_at_utc"],
                maker_id=row["maker_id"],
                checker_id=row["checker_id"],
                audit_trail=events,
                legal_disclaimer=LEGAL_DISCLAIMER
            )

    def verify_record_integrity(self, doc_id: str) -> Dict[str, Any]:
        """
        Recomputes SHA-256 seal from database state and verifies against stored seal.
        Returns tamper detection status.
        """
        doc = self.get_document(doc_id)
        if not doc:
            raise KeyError(f"Document {doc_id} not found.")

        recomputed_hash = self.compute_canonical_hash(
            doc_id=doc.doc_id,
            image_sha256=doc.original_image_sha256,
            state=doc.pipeline_state.value,
            extracted_data=doc.extracted_data,
            human_corrected=doc.human_corrected_data,
            maker_id=doc.maker_id,
            checker_id=doc.checker_id
        )

        is_tampered = (recomputed_hash != doc.current_record_sha256)

        return {
            "doc_id": doc_id,
            "pipeline_state": doc.pipeline_state.value,
            "stored_record_sha256": doc.current_record_sha256,
            "recomputed_sha256": recomputed_hash,
            "integrity_verified": not is_tampered,
            "is_tampered": is_tampered,
            "audit_trail_events_count": len(doc.audit_trail),
            "legal_disclaimer": LEGAL_DISCLAIMER
        }

    def list_documents(self, state: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            if state:
                cur.execute("SELECT doc_id, pipeline_state, current_record_sha256, maker_id, checker_id, updated_at_utc FROM documents WHERE pipeline_state = ? ORDER BY updated_at_utc DESC LIMIT ?", (state, limit))
            else:
                cur.execute("SELECT doc_id, pipeline_state, current_record_sha256, maker_id, checker_id, updated_at_utc FROM documents ORDER BY updated_at_utc DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def get_all_documents(self, limit: int = 200) -> List[DocumentRecord]:
        """
        Retrieves full DocumentRecord instances for all registered documents.
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM documents ORDER BY updated_at_utc DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
            results: List[DocumentRecord] = []
            for row in rows:
                results.append(DocumentRecord(
                    doc_id=row["doc_id"],
                    original_image_sha256=row["original_image_sha256"],
                    pipeline_state=WorkflowState(row["pipeline_state"]),
                    extracted_data=json.loads(row["extracted_json"]),
                    human_corrected_data=json.loads(row["human_corrected_json"]) if row["human_corrected_json"] else None,
                    verification_report=json.loads(row["verification_report_json"]) if row["verification_report_json"] else None,
                    evidence_manifest=json.loads(row["evidence_manifest_json"]) if row["evidence_manifest_json"] else None,
                    current_record_sha256=row["current_record_sha256"],
                    created_at_utc=row["created_at_utc"],
                    updated_at_utc=row["updated_at_utc"],
                    maker_id=row["maker_id"],
                    checker_id=row["checker_id"],
                    audit_trail=[],
                    legal_disclaimer=LEGAL_DISCLAIMER
                ))
            return results
