"""
Phase 8 Automated Test Suite: Local-First Land Document Knowledge Assistant (RAG) & Agent 6.
Tests:
1. Knowledge Base Corpus Integrity & Metadata Verification
2. Hybrid Dense + Lexical Retrieval Relevance on Bangla Land Queries
3. Anti-Hallucination Guardrail & Insufficient Source Evidence Refusal
4. FastAPI POST /api/v1/knowledge/query Endpoint Integration
5. FastAPI GET /api/v1/knowledge/corpus-stats and explain-doc/{doc_id} Integration
"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.rag_service import LandKnowledgeRAGService
from backend.agents.knowledge_audit_agent import KnowledgeAuditAgent
from backend.services.audit_service import AuditPersistenceService
from backend.schemas.audit_schema import WorkflowState

client = TestClient(app)

CORPUS_PATH = Path("research/rag_corpus/land_knowledge_base.json")
EMBEDDING_DIR = Path("models/embeddings/multilingual-e5-small")

def test_rag_corpus_integrity():
    """Verifies that the offline curated land knowledge base is structurally valid."""
    assert CORPUS_PATH.exists(), "Corpus JSON file must exist on disk"
    
    rag = LandKnowledgeRAGService(corpus_path=CORPUS_PATH, model_dir=EMBEDDING_DIR)
    assert len(rag.documents) >= 10, "Corpus must contain at least 10 authoritative land knowledge chunks"
    
    # Check schema compliance of every document
    required_keys = {"doc_id", "section_id", "title", "category", "source_authority", "verified_status", "content", "key_terms"}
    for doc in rag.documents:
        for k in required_keys:
            assert k in doc, f"Document {doc.get('doc_id')} missing required key '{k}'"
        assert len(doc["content"]) > 100, f"Document {doc['doc_id']} content too short"
        assert len(doc["key_terms"]) >= 2, f"Document {doc['doc_id']} must have key terms"

def test_hybrid_retrieval_in_domain_relevance():
    """Tests that in-domain Bangla queries retrieve the exact target documents with citations."""
    rag = LandKnowledgeRAGService(corpus_path=CORPUS_PATH, model_dir=EMBEDDING_DIR)
    
    # 1. Deed Types Query
    res1 = rag.answer_query("সাফ কবলা ও বায়নাপত্রের পার্থক্য কী?", top_k=2)
    assert res1.status == "ANSWERED"
    assert res1.top_score >= 0.35
    assert len(res1.citations) >= 1
    cited_ids = [c.doc_id for c in res1.citations]
    assert any(target in cited_ids for target in ["BD_LAND_KB_001", "BD_LAND_KB_002"])
    assert "আইনি সতর্ক" in res1.legal_disclaimer

    # 2. 16-Ana Share Query
    res2 = rag.answer_query("১৬ আনা হিস্যা ও গন্ডা কীভাবে হিসাব করে?", top_k=2)
    assert res2.status == "ANSWERED"
    assert res2.top_score >= 0.35
    cited_ids_2 = [c.doc_id for c in res2.citations]
    assert "BD_LAND_KB_008" in cited_ids_2

    # 3. Khatian Survey Query
    res3 = rag.answer_query("সিএস এবং বিএস খতিয়ান কী?", top_k=2)
    assert res3.status == "ANSWERED"
    assert res3.top_score >= 0.35
    cited_ids_3 = [c.doc_id for c in res3.citations]
    assert "BD_LAND_KB_006" in cited_ids_3

def test_anti_hallucination_out_of_domain_guardrail():
    """Tests that out-of-domain queries are rejected with INSUFFICIENT_SOURCE_EVIDENCE."""
    rag = LandKnowledgeRAGService(corpus_path=CORPUS_PATH, model_dir=EMBEDDING_DIR)
    
    # Out of domain query: Mars Real Estate
    res_mars = rag.answer_query("মঙ্গল গ্রহে জমি কেনার নিয়ম কী?", similarity_threshold=0.35)
    assert res_mars.status == "INSUFFICIENT_SOURCE_EVIDENCE"
    assert len(res_mars.citations) == 0
    assert "মনগড়া বা অনুমাননির্ভর তথ্য প্রদান নিষিদ্ধ" in res_mars.answer
    assert res_mars.top_score == 0.0

    # Completely unrelated query: Cricket World Cup
    res_cricket = rag.answer_query("ক্রিকেট খেলার বিশ্বকাপ ফাইনাল কবে?", similarity_threshold=0.35)
    assert res_cricket.status == "INSUFFICIENT_SOURCE_EVIDENCE"
    assert len(res_cricket.citations) == 0

def test_fastapi_knowledge_query_endpoint():
    """Tests POST /api/v1/knowledge/query with valid and out-of-domain payloads."""
    # 1. Valid Query
    payload_valid = {
        "query": "বণ্টননামা দলিল কীভাবে করা হয়?",
        "top_k": 3,
        "similarity_threshold": 0.35
    }
    res_valid = client.post("/api/v1/knowledge/query", json=payload_valid)
    assert res_valid.status_code == 200
    data_valid = res_valid.json()
    assert data_valid["status"] == "ANSWERED"
    assert len(data_valid["citations"]) >= 1
    assert data_valid["citations"][0]["doc_id"] == "BD_LAND_KB_003"
    assert "legal_disclaimer" in data_valid

    # 2. Out-of-domain Query
    payload_ood = {
        "query": "আইফেল টাওয়ার কোন শহরে অবস্থিত?",
        "top_k": 2,
        "similarity_threshold": 0.35
    }
    res_ood = client.post("/api/v1/knowledge/query", json=payload_ood)
    assert res_ood.status_code == 200
    data_ood = res_ood.json()
    assert data_ood["status"] == "INSUFFICIENT_SOURCE_EVIDENCE"
    assert len(data_ood["citations"]) == 0

def test_fastapi_corpus_stats_and_explain_doc_endpoints():
    """Tests GET /api/v1/knowledge/corpus-stats and explain-doc/{doc_id}."""
    # 1. Corpus stats
    res_stats = client.get("/api/v1/knowledge/corpus-stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["total_documents"] >= 10
    assert "DEED_TYPES" in stats["categories"]
    assert stats["is_offline_ready"] is True

    # 2. Setup document in Audit DB to test explanation
    audit_service = AuditPersistenceService()
    test_doc_id = "RAG_EXPLAIN_TEST_DOC_99"
    sample_extracted = {
        "deed_number": "9999",
        "deed_type": "SAF_KABALA",
        "land_details": {
            "land_unit": "SHOTOK",
            "sixteen_ana_share": "৪ আনা ১০ গন্ডা ২ কড়া ০ ক্রান্তি",
            "khatian_numbers": ["১২৩৪"]
        },
        "provenance": {
            "warnings": ["MISSING_TAFSIL_SCHEDULE_PAGE"]
        }
    }
    audit_service.create_initial_record(
        doc_id=test_doc_id,
        original_image_sha256="9999999999999999999999999999999999999999999999999999999999999999",
        extracted_data=sample_extracted,
        verification_report={"is_valid": True, "score": 1.0},
        actor_id="PHASE8_TESTER"
    )

    # 3. Call explain-doc endpoint
    res_explain = client.get(f"/api/v1/knowledge/explain-doc/{test_doc_id}")
    assert res_explain.status_code == 200
    explain_data = res_explain.json()
    assert explain_data["doc_id"] == test_doc_id
    assert explain_data["deed_type"] == "SAF_KABALA"
    assert len(explain_data["field_explanations"]) >= 3
    assert "আইনি সতর্কবার্তা" in explain_data["legal_disclaimer"]
    assert "ডিজিটাল রূপান্তর ও অডিট সম্পন্ন হয়েছে" in explain_data["audit_summary"]

    # 4. Non-existent doc explanation returns 404
    res_404 = client.get("/api/v1/knowledge/explain-doc/NON_EXISTENT_DOC_XYZ")
    assert res_404.status_code == 404
