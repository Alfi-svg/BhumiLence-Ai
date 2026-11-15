"""
BhumiLens AI — BhumiGuard Intelligence Agent (Agent 5 - Layer 6 / Defense in Depth).
Executes:
1. Visual & Cryptographic Duplicate Matching (exact SHA-256 + 64-bit Perceptual dHash)
2. Deterministic Cross-Record Consistency & Conflict Rules (>16-Ana Over-transfer, Deed ID Collision)
3. Unsupervised Tabular Anomaly Scoring (Isolation Forest on Land Distributions)

Ethical & Legal Governance:
Never labels any document or person as 'fraud' or 'forgery'.
Produces factual risk indicators (RISK_LOW, RISK_MEDIUM, RISK_HIGH_REVIEW_REQUIRED),
exact rule triggers, supporting evidence IDs, and human-readable Bangla explanations.
"""
import asyncio
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union, List

from backend.schemas.deed_schema import DeedExtractionSchema
from backend.schemas.bhumiguard_schema import (
    BhumiGuardReport,
    RiskLevel,
    DuplicateMatch,
    RuleViolation,
    FeatureContribution,
    SCHEMA_VERSION
)
from backend.services.anomaly_service import BhumiGuardService

logger = logging.getLogger("bhumilens.bhumiguard_agent")

DISCLAIMER_TEXT = (
    "আইনি সতর্কবার্তা: এই অ্যানোমালি ও রিস্ক রিপোর্ট শুধুমাত্র মানুষের পর্যালোচনার "
    "(Maker-Checker Review) জন্য প্রস্তুতকৃত স্ট্যাটিস্টিক্যাল ও লজিক্যাল সতর্কতা। "
    "এটি কোনো জালিয়াতি বা অপরাধের আইনি প্রমাণ নয়।"
)

class BhumiGuardAgent:
    def __init__(
        self,
        bhumiguard_service: Optional[BhumiGuardService] = None,
        db_path: Optional[str] = None,
        seed_path: Optional[Path] = None
    ):
        self.agent_name = "BhumiGuardAgent"
        self.service = bhumiguard_service or BhumiGuardService(
            db_path=db_path,
            seed_path=seed_path
        )
        self.events_log: List[Dict[str, Any]] = []

    def _log_event(self, event_type: str, details: Dict[str, Any]):
        event = {
            "agent": self.agent_name,
            "event": event_type,
            "timestamp": time.time(),
            "details": details
        }
        self.events_log.append(event)
        logger.info("[%s] %s: %s", self.agent_name, event_type, details)

    def scan_deed(
        self,
        deed_input: Union[DeedExtractionSchema, Dict[str, Any]],
        image_path: Optional[str] = None,
        target_sha256: Optional[str] = None,
        doc_id: Optional[str] = None
    ) -> BhumiGuardReport:
        """
        Synchronously runs multi-layered BhumiGuard Intelligence on a deed record.
        """
        t0 = time.perf_counter()
        if isinstance(deed_input, DeedExtractionSchema):
            extracted_dict = deed_input.to_canonical_dict()
            resolved_doc_id = doc_id or deed_input.doc_id
        elif isinstance(deed_input, dict):
            extracted_dict = deed_input
            resolved_doc_id = doc_id or deed_input.get("doc_id") or "UNKNOWN_DOC"
        else:
            raise ValueError(f"Unsupported deed_input type: {type(deed_input)}")

        self._log_event("SCAN_STARTED", {
            "doc_id": resolved_doc_id,
            "has_image": bool(image_path),
            "target_sha256": target_sha256
        })

        report = self.service.scan_document(
            extracted_data=extracted_dict,
            image_path=image_path,
            target_sha256=target_sha256,
            doc_id=resolved_doc_id
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self._log_event("SCAN_COMPLETED", {
            "doc_id": resolved_doc_id,
            "risk_level": report.risk_level.value,
            "risk_score": report.risk_score,
            "duplicate_matches_count": len(report.duplicate_matches),
            "rule_violations_count": len(report.rule_violations),
            "anomaly_score": report.anomaly_score,
            "elapsed_ms": round(elapsed_ms, 2)
        })

        return report

    async def ascan_deed(
        self,
        deed_input: Union[DeedExtractionSchema, Dict[str, Any]],
        image_path: Optional[str] = None,
        target_sha256: Optional[str] = None,
        doc_id: Optional[str] = None
    ) -> BhumiGuardReport:
        """
        Asynchronous non-blocking wrapper for FastAPI.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self.scan_deed,
            deed_input,
            image_path,
            target_sha256,
            doc_id
        )

    # Backward-compatible endpoints
    def scan(self, *args, **kwargs) -> BhumiGuardReport:
        """Alias for scan_deed."""
        return self.scan_deed(*args, **kwargs)

    async def run_fraud_checks(self, document_record: dict) -> Dict[str, Any]:
        """
        Backward-compatible async endpoint returning dictionary format.
        Note: Per ethical guidelines, does not return 'fraud' labels, but risk indicators.
        """
        report = await self.ascan_deed(document_record)
        return {
            "status": "COMPLETED",
            "doc_id": report.doc_id,
            "risk_level": report.risk_level.value,
            "risk_score": report.risk_score,
            "anomaly_score": report.anomaly_score,
            "duplicate_matches": [m.model_dump() for m in report.duplicate_matches],
            "rule_violations": [v.model_dump() for v in report.rule_violations],
            "disclaimer": report.disclaimer,
            "report": report.model_dump()
        }
