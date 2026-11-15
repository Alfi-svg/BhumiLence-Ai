"""
BhumiLens AI — Verification Agent (Agent 4 - Layer 6).
Executes deterministic mathematical and domain consistency verification:
1. Exact unit conversion (Shotok ↔ Katha ↔ Bigha ↔ Acre ↔ Ajutangsho)
2. 16-Ana archaic share fraction verification
3. Stamp duty arithmetic verification
4. Date chronology & mandatory field consistency checks
5. Emits strict VerificationReport schema
"""
import asyncio
import time
import logging
from typing import Optional, Dict, Any, Union

from backend.schemas.deed_schema import DeedExtractionSchema
from backend.schemas.verification_schema import VerificationReport
from backend.services.land_validation_service import LandValidationService

logger = logging.getLogger("bhumilens.verification_agent")

class VerificationAgent:
    def __init__(self, validation_service: Optional[LandValidationService] = None):
        self.agent_name = "VerificationAgent"
        self.validation_service = validation_service or LandValidationService()
        self.events_log = []

    def _log_event(self, event_type: str, details: Dict[str, Any]):
        event = {
            "agent": self.agent_name,
            "event": event_type,
            "timestamp": time.time(),
            "details": details
        }
        self.events_log.append(event)
        logger.info("[%s] %s: %s", self.agent_name, event_type, details)

    def verify_deed(self, deed_input: Union[DeedExtractionSchema, Dict[str, Any]]) -> VerificationReport:
        """
        Synchronously runs deterministic verification against a deed schema or dictionary.
        """
        t0 = time.perf_counter()
        if isinstance(deed_input, dict):
            deed_schema = DeedExtractionSchema.model_validate(deed_input)
        else:
            deed_schema = deed_input

        doc_id = deed_schema.doc_id
        self._log_event("VERIFICATION_STARTED", {"doc_id": doc_id})

        report = self.validation_service.validate_deed(deed_schema)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self._log_event("VERIFICATION_COMPLETED", {
            "doc_id": doc_id,
            "is_valid": report.is_valid,
            "score": report.score,
            "flags_count": len(report.flags),
            "elapsed_ms": round(elapsed_ms, 2)
        })

        return report

    async def averify_deed(self, deed_input: Union[DeedExtractionSchema, Dict[str, Any]]) -> VerificationReport:
        """
        Asynchronously runs deterministic verification (non-blocking for FastAPI).
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.verify_deed, deed_input)

    async def verify(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Backward-compatible async endpoint returning report dictionary."""
        report = await self.averify_deed(extracted_data)
        return {
            "status": "success",
            "doc_id": report.doc_id,
            "valid": report.is_valid,
            "score": report.score,
            "flags": [f.model_dump() for f in report.flags],
            "report": report.model_dump()
        }
