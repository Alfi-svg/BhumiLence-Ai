"""
BhumiLens AI — Land Information Extraction Agent (Agent 3 - Layer 5).
Orchestrates LandExtractionService to:
1. Ingest DocumentHTRResult from HTRAgent (Agent 2) or raw transcribed text.
2. Normalize domain text through BanglaLandNormalizer.
3. Extract standardized deed metadata using Qwen3-0.6B LoRA + Deterministic Fallback.
4. Enforce zero hallucination: unstated fields remain null (None).
5. Map extracted entities directly to visual line evidence crops and SHA-256 signatures.
6. Emit audit events: EXTRACTION_STARTED, NORMALIZATION_COMPLETED, EXTRACTION_COMPLETED.
"""
import asyncio
import time
import logging
from typing import Optional, Dict, Any, List, Union

from backend.schemas.deed_schema import DeedExtractionSchema
from backend.schemas.htr_schema import DocumentHTRResult
from backend.services.extraction_service import LandExtractionService
from backend.services.normalization_service import BanglaLandNormalizer

logger = logging.getLogger("bhumilens.extraction_agent")

class LandInformationExtractionAgent:
    def __init__(
        self,
        model_mode: str = "hybrid",
        normalizer: Optional[BanglaLandNormalizer] = None,
        lora_adapter_dir: Optional[str] = None
    ):
        self.agent_name = "LandInformationExtractionAgent"
        self.extraction_service = LandExtractionService(
            normalizer=normalizer,
            model_mode=model_mode,
            lora_adapter_dir=lora_adapter_dir
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

    def process_document(
        self,
        document_input: Union[DocumentHTRResult, str],
        doc_id: Optional[str] = None
    ) -> DeedExtractionSchema:
        """
        Synchronously extracts structured land entities from DocumentHTRResult or raw string.
        """
        t0 = time.perf_counter()
        target_doc_id = doc_id or (document_input.doc_id if isinstance(document_input, DocumentHTRResult) else "DEED_DOC")

        self._log_event("EXTRACTION_STARTED", {"doc_id": target_doc_id})

        if isinstance(document_input, DocumentHTRResult):
            result = self.extraction_service.extract_from_htr_result(document_input)
        else:
            result = self.extraction_service.extract_from_text(document_input, doc_id=target_doc_id)

        self._log_event("NORMALIZATION_COMPLETED", {
            "doc_id": target_doc_id,
            "raw_len": len(result.provenance.raw_ocr_text or ""),
            "norm_len": len(result.provenance.normalized_ocr_text or "")
        })

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self._log_event("EXTRACTION_COMPLETED", {
            "doc_id": target_doc_id,
            "deed_number": result.deed_number,
            "deed_type": result.deed_type.value,
            "mouza": result.location.mouza,
            "land_area": result.land_details.land_area,
            "elapsed_ms": round(elapsed_ms, 2)
        })

        return result

    async def aprocess_document(
        self,
        document_input: Union[DocumentHTRResult, str],
        doc_id: Optional[str] = None
    ) -> DeedExtractionSchema:
        """
        Asynchronously extracts structured land entities (non-blocking for FastAPI).
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.process_document, document_input, doc_id
        )

    async def extract_entities(self, raw_text: str, doc_id: str = "DEED_DOC") -> Dict[str, Any]:
        """Backward-compatible async endpoint returning canonical dictionary."""
        schema = await self.aprocess_document(raw_text, doc_id=doc_id)
        return {
            "status": "success",
            "doc_id": schema.doc_id,
            "structured_entities": schema.to_canonical_dict(),
            "provenance": schema.provenance.model_dump()
        }

# Backward-compatible alias
ExtractionAgent = LandInformationExtractionAgent
