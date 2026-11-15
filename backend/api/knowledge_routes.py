"""
Land Gazetteers, Legal Knowledge Base & Source-Grounded RAG Routes (Phase 8).
Endpoints:
- POST /api/v1/knowledge/query : Natural language RAG assistant with cited sources & anti-hallucination guardrail
- GET /api/v1/knowledge/explain-doc/{doc_id} : Executive cited explanation and cross-referencing for a stored deed
- GET /api/v1/knowledge/corpus-stats : Verified land knowledge corpus statistics and embedding model status
- GET /api/v1/knowledge/health : Health and offline readiness status
- GET /api/v1/knowledge/gazetteer : Built-in Gazipur/Dhaka revenue hierarchy gazetteer lookup
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends

from backend.agents.knowledge_audit_agent import KnowledgeAuditAgent
from backend.schemas.rag_schema import (
    RAGQueryRequest,
    RAGQueryResponse,
    RAGCorpusStats,
    DeedExplanationResponse
)
from backend.services.extraction_service import MOUZA_LIST, UPAZILA_LIST, DISTRICT_LIST

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# Initialize Agent 6 as a singleton for the router
knowledge_agent = KnowledgeAuditAgent()

@router.get("/health")
async def knowledge_health():
    """
    Readiness and operational health status for Phase 8 Retrieval-Augmented Generation (RAG).
    """
    stats = knowledge_agent.get_stats()
    return {
        "status": "ACTIVE",
        "phase": "PHASE 8 (Local-First Land Knowledge Assistant RAG)",
        "embedding_model": stats.embedding_model,
        "is_offline_ready": stats.is_offline_ready,
        "total_knowledge_chunks": stats.total_documents,
        "cached_gazetteer_entries": len(MOUZA_LIST) + len(UPAZILA_LIST) + len(DISTRICT_LIST)
    }

@router.post("/query", response_model=RAGQueryResponse)
async def query_land_knowledge(payload: RAGQueryRequest):
    """
    Asks a natural language question about Bangladeshi land records, deed types, or 16-Ana math.
    Returns source-grounded answers citing verified sections, or warns if evidence is insufficient.
    """
    try:
        response = await knowledge_agent.aask_land_knowledge(
            query=payload.query,
            top_k=payload.top_k,
            similarity_threshold=payload.similarity_threshold
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Knowledge retrieval failed: {str(e)}"
        )

@router.get("/explain-doc/{doc_id}", response_model=DeedExplanationResponse)
async def explain_document(doc_id: str):
    """
    Cross-references an extracted deed's fields against the verified land knowledge corpus,
    providing citations and an executive audit trail summary.
    """
    try:
        response = await knowledge_agent.aexplain_extracted_deed(doc_id)
        if response.pipeline_state == "NOT_FOUND":
            raise HTTPException(
                status_code=404,
                detail=f"Document '{doc_id}' not found in the persistence store."
            )
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Deed explanation generation failed: {str(e)}"
        )

@router.get("/corpus-stats", response_model=RAGCorpusStats)
async def get_corpus_statistics():
    """
    Returns verified document counts, topic categories, and embedding configuration.
    """
    try:
        return knowledge_agent.get_stats()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve corpus statistics: {str(e)}"
        )

@router.get("/gazetteer")
async def query_gazetteer(query: str = ""):
    """
    Searches built-in administrative geography gazetteer for Mouzas, Upazilas, and Districts.
    """
    clean_q = query.strip()
    matched_mouzas = [m for m in MOUZA_LIST if clean_q in m] if clean_q else MOUZA_LIST
    matched_upazilas = [u for u in UPAZILA_LIST if clean_q in u] if clean_q else UPAZILA_LIST
    matched_districts = [d for d in DISTRICT_LIST if clean_q in d] if clean_q else DISTRICT_LIST

    return {
        "query": query,
        "mouzas": matched_mouzas,
        "upazilas": matched_upazilas,
        "districts": matched_districts
    }
