"""
BhumiLens AI — Knowledge & Audit Agent (Agent 6).
Provides local-first, source-grounded land knowledge assistant (RAG) and automated document explanation.
Cross-references extracted deed fields against authoritative land laws, archaic 16-Ana lexicons,
and system audit trails with strict anti-hallucination guardrails and source citations.
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

from backend.services.rag_service import LandKnowledgeRAGService
from backend.services.audit_service import AuditPersistenceService
from backend.schemas.rag_schema import (
    RAGQueryRequest,
    RAGQueryResponse,
    RAGCorpusStats,
    DeedFieldExplanation,
    DeedExplanationResponse
)

logger = logging.getLogger("bhumilens.agent.knowledge")

LEGAL_DISCLAIMER_TEXT = (
    "আইনি সতর্কবার্তা: BhumiLens AI এর এই ব্যাখ্যা শুধুমাত্র তথ্যগত সহায়তা ও গবেষণার উদ্দেশ্যে প্রণীত। "
    "এটি কোনো আইনি পরামর্শ বা আদালতের রায় নয়। জমির চূড়ান্ত মালিকানা নির্ধারণের এখতিয়ার সহকারী কমিশনার (ভূমি), "
    "সাব-রেজিস্ট্রার ও উপযুক্ত আদালতের।"
)

class KnowledgeAuditAgent:
    def __init__(
        self,
        rag_service: Optional[LandKnowledgeRAGService] = None,
        audit_service: Optional[AuditPersistenceService] = None
    ):
        self.agent_name = "KnowledgeAuditAgent"
        self.rag_service = rag_service or LandKnowledgeRAGService()
        self.audit_service = audit_service or AuditPersistenceService()

    def ask_land_knowledge(
        self,
        query: str,
        top_k: int = 3,
        similarity_threshold: float = 0.35
    ) -> RAGQueryResponse:
        """
        Answers natural language queries about Bangladeshi land documents,
        revenue terms, archaic 16-Ana math, and registration rules with citations.
        """
        logger.info("[KnowledgeAuditAgent] Answering query: '%s' (top_k=%d)", query, top_k)
        return self.rag_service.answer_query(
            query=query,
            top_k=top_k,
            similarity_threshold=similarity_threshold
        )

    async def aask_land_knowledge(
        self,
        query: str,
        top_k: int = 3,
        similarity_threshold: float = 0.35
    ) -> RAGQueryResponse:
        """Asynchronous wrapper for FastAPI non-blocking execution."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.ask_land_knowledge, query, top_k, similarity_threshold
        )

    def explain_extracted_deed(self, doc_id: str) -> DeedExplanationResponse:
        """
        Retrieves a processed document from persistence and cross-references its extracted fields
        against the verified knowledge base, compiling an executive audit summary.
        """
        logger.info("[KnowledgeAuditAgent] Generating executive explanation for doc_id: %s", doc_id)
        doc = self.audit_service.get_document(doc_id)

        if not doc:
            return DeedExplanationResponse(
                doc_id=doc_id,
                deed_number=None,
                deed_type=None,
                pipeline_state="NOT_FOUND",
                record_sha256=None,
                field_explanations=[],
                audit_summary=f"দলিল আইডি '{doc_id}' ডাটাবেজে খুঁজে পাওয়া যায়নি। অনুগ্রহ করে প্রথমে দলিল প্রসেস করুন।",
                legal_disclaimer=LEGAL_DISCLAIMER_TEXT
            )

        extracted_data = doc.extracted_data or {}
        deed_number = extracted_data.get("deed_number")
        deed_type = extracted_data.get("deed_type", "UNKNOWN")

        # Cross-reference fields with RAG knowledge corpus
        field_explanations = self.rag_service.explain_deed_fields(extracted_data)

        # Compile executive audit summary
        verified_notes = []
        if doc.maker_id:
            verified_notes.append(f"মেকার (এন্ট্রি ও ড্রাফট): {doc.maker_id}")
        if doc.checker_id:
            verified_notes.append(f"চেকার (অনুমোদন ও সিল): {doc.checker_id}")
        
        audit_trail_text = " | ".join(verified_notes) if verified_notes else "এআই প্রক্রিয়াজাতকরণ সম্পন্ন (মেকার পর্যালোচনার অপেক্ষায়)"

        exec_summary = (
            f"দলিল নম্বর {deed_number or 'অজ্ঞাত'} (প্রকৃতি: {deed_type}) এর ডিজিটাল রূপান্তর ও অডিট সম্পন্ন হয়েছে। "
            f"বর্তমান লাইফসাইকেল স্ট্যাটাস: {doc.pipeline_state.value}। "
            f"ডিজিটাল সিল: {doc.current_record_sha256[:16]}...। "
            f"অডিট বিবরণী: {audit_trail_text}। "
            f"মোট {len(field_explanations)}টি গুরুত্বপূর্ণ ফিল্ডকে প্রমিত ভূমি জ্ঞানভাণ্ডারের সাথে ক্রস-রেফারেন্স করা হয়েছে।"
        )

        return DeedExplanationResponse(
            doc_id=doc_id,
            deed_number=deed_number,
            deed_type=deed_type,
            pipeline_state=doc.pipeline_state.value,
            record_sha256=doc.current_record_sha256,
            field_explanations=field_explanations,
            audit_summary=exec_summary,
            legal_disclaimer=LEGAL_DISCLAIMER_TEXT
        )

    async def aexplain_extracted_deed(self, doc_id: str) -> DeedExplanationResponse:
        """Asynchronous wrapper for FastAPI non-blocking execution."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.explain_extracted_deed, doc_id)

    def get_stats(self) -> RAGCorpusStats:
        """Returns metadata and health of the knowledge corpus."""
        return self.rag_service.get_corpus_stats()
