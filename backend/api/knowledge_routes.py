"""
Land Gazetteers, Mouza Registries & Legal Knowledge Base Routes.
Provides:
- GET /api/v1/knowledge/health : Health and readiness check for legal RAG integration (Phase 8)
- GET /api/v1/knowledge/gazetteer : Built-in Gazipur/Dhaka revenue hierarchy gazetteer lookup
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter

from backend.services.extraction_service import MOUZA_LIST, UPAZILA_LIST, DISTRICT_LIST

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

@router.get("/health")
async def knowledge_health():
    """
    Readiness status endpoint for Phase 8 Retrieval-Augmented Generation (RAG) and Land Law indexing.
    """
    return {
        "status": "ready",
        "phase": "Phase 8 Pre-conditioned",
        "rag_support": "Local Vector Indexing (Planned Phase 8)",
        "cached_gazetteer_entries": len(MOUZA_LIST) + len(UPAZILA_LIST) + len(DISTRICT_LIST)
    }

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
