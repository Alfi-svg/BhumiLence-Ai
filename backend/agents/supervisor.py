"""
BhumiLens AI — Supervisor Orchestrator (Multi-Agent System Coordinator).
Sequentially orchestrates the end-to-end BhumiLens AI pipeline across Layers 1 to 7:
1. Agent 1: DocumentIntelligenceAgent (Quality Gate, Layout, Seal, Line Segmentation & Evidence Crops)
2. Agent 2: HTRAgent (Bengali Handwritten Text Recognition with Confidence & Uncertainty Flagging)
3. Agent 3: LandInformationExtractionAgent (Normalization, Qwen3-0.6B LoRA, Zero-Hallucination Grounding)
4. Agent 4: VerificationAgent (Deterministic Math, 16-Ana Share, Stamp Duty & Chronology Validator)
5. Layer 7: AuditPersistenceService (Cryptographic SHA-256 Seal, AI_EXTRACTED_PENDING_MAKER State)

Enforces sequential, memory-safe execution tailored for Apple Silicon M2 (16GB RAM budget).
"""
import asyncio
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from backend.agents.document_agent import DocumentIntelligenceAgent
from backend.agents.htr_agent import HTRAgent
from backend.agents.extraction_agent import LandInformationExtractionAgent
from backend.agents.verification_agent import VerificationAgent
from backend.agents.bhumiguard_agent import BhumiGuardAgent
from backend.services.audit_service import AuditPersistenceService
from backend.schemas.htr_schema import HTREngineType

logger = logging.getLogger("bhumilens.supervisor")

LEGAL_DISCLAIMER = (
    "LEGAL AUTHORITY DISCLAIMER: SHA-256 cryptographic seal verifies data immutability "
    "and record integrity within BhumiLens AI. It does NOT constitute legal title, "
    "judicial deed validity, or state-sanctioned land ownership."
)

class BhumiLensSupervisor:
    def __init__(
        self,
        evidence_dir: str = "outputs/evidence",
        db_path: Optional[str] = None,
        htr_engine: HTREngineType = HTREngineType.HYBRID,
        extraction_mode: str = "hybrid"
    ):
        self.supervisor_name = "BhumiLensSupervisor"
        self.evidence_dir = evidence_dir
        self.audit_service = AuditPersistenceService(db_path=db_path)

        # Lazy/sequential agent initialization
        self.agent_1_vision = DocumentIntelligenceAgent(output_base_dir=evidence_dir)
        self.agent_2_htr = HTRAgent(default_engine=htr_engine)
        self.agent_3_extraction = LandInformationExtractionAgent(model_mode=extraction_mode)
        self.agent_4_verification = VerificationAgent()
        self.agent_5_bhumiguard = BhumiGuardAgent(db_path=db_path)

    def process_document(
        self,
        image_path: str,
        doc_id: Optional[str] = None,
        actor_id: str = "BHUMILENS_AI_PIPELINE"
    ) -> Dict[str, Any]:
        """
        Synchronously runs the complete end-to-end multi-agent pipeline on a deed image.
        """
        t_total_start = time.perf_counter()
        latencies_ms: Dict[str, float] = {}
        target_doc_id = doc_id or Path(image_path).stem.upper()

        logger.info("[Supervisor] Starting pipeline execution for %s (Image: %s)", target_doc_id, image_path)

        # ---------------------------------------------------------------------
        # Stage 1: Vision, Quality Assessment & Evidence Cropping (Agent 1)
        # ---------------------------------------------------------------------
        t0 = time.perf_counter()
        vision_result = self.agent_1_vision.process_document(image_path, doc_id=target_doc_id)
        latencies_ms["stage_1_vision_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        logger.info("[Supervisor] Stage 1 Vision completed in %.2f ms", latencies_ms["stage_1_vision_ms"])

        # ---------------------------------------------------------------------
        # Stage 2: Bengali Handwritten Text Recognition (Agent 2)
        # ---------------------------------------------------------------------
        t0 = time.perf_counter()
        htr_result = self.agent_2_htr.process_document(vision_result)
        latencies_ms["stage_2_htr_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        logger.info("[Supervisor] Stage 2 HTR completed in %.2f ms (Total Lines: %d, Uncertain: %d)",
                    latencies_ms["stage_2_htr_ms"], htr_result.total_lines, htr_result.uncertain_lines_count)

        # ---------------------------------------------------------------------
        # Stage 3: Normalization & Structured Extraction (Agent 3)
        # ---------------------------------------------------------------------
        t0 = time.perf_counter()
        extraction_schema = self.agent_3_extraction.process_document(htr_result, doc_id=target_doc_id)
        latencies_ms["stage_3_extraction_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        logger.info("[Supervisor] Stage 3 Extraction completed in %.2f ms (Deed No: %s, Mouza: %s)",
                    latencies_ms["stage_3_extraction_ms"], extraction_schema.deed_number, extraction_schema.location.mouza)

        # ---------------------------------------------------------------------
        # Stage 4: Deterministic Land Math & Consistency Verification (Agent 4)
        # ---------------------------------------------------------------------
        t0 = time.perf_counter()
        verification_report = self.agent_4_verification.verify_deed(extraction_schema)
        latencies_ms["stage_4_verification_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        logger.info("[Supervisor] Stage 4 Verification completed in %.2f ms (Valid: %s, Score: %.2f)",
                    latencies_ms["stage_4_verification_ms"], verification_report.is_valid, verification_report.score)

        # ---------------------------------------------------------------------
        # Stage 5: BhumiGuard Intelligence Anomaly & Duplicate Detection (Agent 5)
        # ---------------------------------------------------------------------
        t0 = time.perf_counter()
        bhumiguard_report = self.agent_5_bhumiguard.scan_deed(
            deed_input=extraction_schema,
            image_path=str(image_path),
            target_sha256=vision_result.image_sha256,
            doc_id=target_doc_id
        )
        latencies_ms["stage_5_bhumiguard_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        logger.info("[Supervisor] Stage 5 BhumiGuard completed in %.2f ms (Risk Level: %s, Score: %.2f)",
                    latencies_ms["stage_5_bhumiguard_ms"], bhumiguard_report.risk_level.value, bhumiguard_report.risk_score)

        # ---------------------------------------------------------------------
        # Stage 6: Layer 7 Audit Persistence & Cryptographic SHA-256 Hashing
        # ---------------------------------------------------------------------
        t0 = time.perf_counter()
        evidence_manifest = {
            "image_path": str(image_path),
            "image_sha256": vision_result.image_sha256,
            "dimensions": vision_result.quality.dimensions.model_dump(),
            "crops_count": len(vision_result.evidence_crops),
            "line_crops_count": len(vision_result.layout.line_crops),
            "field_crops": extraction_schema.provenance.evidence_crops,
            "bhumiguard_risk_level": bhumiguard_report.risk_level.value,
            "bhumiguard_risk_score": bhumiguard_report.risk_score
        }

        doc_record = self.audit_service.create_initial_record(
            doc_id=target_doc_id,
            original_image_sha256=vision_result.image_sha256,
            extracted_data=extraction_schema.to_canonical_dict(),
            verification_report=verification_report.model_dump(),
            evidence_manifest=evidence_manifest,
            actor_id=actor_id
        )
        latencies_ms["stage_6_audit_persistence_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        latencies_ms["total_pipeline_ms"] = round((time.perf_counter() - t_total_start) * 1000.0, 2)

        pipeline_output = {
            "status": "COMPLETED",
            "doc_id": target_doc_id,
            "pipeline_state": doc_record.pipeline_state.value,
            "original_image_sha256": doc_record.original_image_sha256,
            "record_sha256": doc_record.current_record_sha256,
            "quality_assessment": vision_result.quality.model_dump(),
            "layout_analysis": {
                "detected_pattern": vision_result.layout.pattern.value,
                "has_official_seal": vision_result.layout.official_seal_detected,
                "segmented_lines_count": len(vision_result.layout.line_crops)
            },
            "htr_summary": {
                "total_lines": htr_result.total_lines,
                "average_confidence": round(htr_result.average_confidence, 4),
                "uncertain_lines_count": htr_result.uncertain_lines_count,
                "engine_used": htr_result.engine_used.value
            },
            "extracted_deed": extraction_schema.to_canonical_dict(),
            "verification_report": verification_report.model_dump(),
            "bhumiguard_report": bhumiguard_report.model_dump(),
            "evidence_manifest": evidence_manifest,
            "stage_latencies_ms": latencies_ms,
            "legal_disclaimer": LEGAL_DISCLAIMER
        }

        logger.info("[Supervisor] Pipeline complete for %s in %.2f ms (Record SHA-256: %s)",
                    target_doc_id, latencies_ms["total_pipeline_ms"], doc_record.current_record_sha256)

        return pipeline_output

    async def aprocess_document(
        self,
        image_path: str,
        doc_id: Optional[str] = None,
        actor_id: str = "BHUMILENS_AI_PIPELINE"
    ) -> Dict[str, Any]:
        """
        Asynchronously runs the complete supervisor pipeline (FastAPI friendly).
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.process_document, image_path, doc_id, actor_id
        )

# Backward-compatible alias
SupervisorAgent = BhumiLensSupervisor
