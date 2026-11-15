"""
Bengali Handwritten Text Recognition (HTR) Agent (Agent 2 - Layer 4).
Orchestrates HTRService to:
1. Ingest DocumentAnalysisResult produced by DocumentIntelligenceAgent (Agent 1).
2. Execute real neural HTR across every segmented handwritten line.
3. Track confidence metrics, flag uncertain lines (< 0.65), and preserve SHA-256 provenance.
"""
import asyncio
from typing import Optional
from backend.schemas.document_schema import DocumentAnalysisResult
from backend.schemas.htr_schema import DocumentHTRResult, HTREngineType
from backend.services.htr_service import HTRService

class HTRAgent:
    def __init__(
        self,
        default_engine: HTREngineType = HTREngineType.HYBRID,
        confidence_threshold: float = 0.65,
        models_base_dir: Optional[str] = None
    ):
        self.agent_name = "HTRAgent"
        self.htr_service = HTRService(
            default_engine=default_engine,
            confidence_threshold=confidence_threshold,
            models_base_dir=models_base_dir
        )

    def process_document(
        self,
        doc_analysis: DocumentAnalysisResult,
        engine: Optional[HTREngineType] = None
    ) -> DocumentHTRResult:
        """
        Synchronously runs HTR on all segmented line crops from DocumentAnalysisResult.
        """
        return self.htr_service.recognize_document(doc_analysis, engine=engine)

    async def aprocess_document(
        self,
        doc_analysis: DocumentAnalysisResult,
        engine: Optional[HTREngineType] = None
    ) -> DocumentHTRResult:
        """
        Asynchronously runs HTR (non-blocking for FastAPI routers).
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.htr_service.recognize_document, doc_analysis, engine
        )
