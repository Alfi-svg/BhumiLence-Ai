"""
Pydantic v2 schemas for BhumiLens Knowledge RAG Assistant (Agent 6).
Defines typed request/response models, citation provenance, and corpus statistics.
"""
from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0.0"

class AuthorityLevel(str, Enum):
    GOVERNMENT_GAZETTED = "GOVERNMENT_GAZETTED"
    LEXICON_STANDARD = "LEXICON_STANDARD"
    INTERNAL_SECURITY_POLICY = "INTERNAL_SECURITY_POLICY"
    REFERENCE_TEMPLATE = "REFERENCE_TEMPLATE"

class RAGCitation(BaseModel):
    """Citation provenance for verified land knowledge chunks."""
    doc_id: str = Field(..., description="Unique document ID in knowledge corpus")
    section_id: str = Field(..., description="Section identifier (e.g. SEC_DEED_SAF_KABALA)")
    source_title: str = Field(..., description="Title of cited section in Bangla/English")
    source_authority: str = Field(..., description="Authoritative publisher or gazette reference")
    verified_status: str = Field(..., description="Verification classification level")
    category: str = Field(..., description="Topic category (DEED_TYPES, ARCHAIC_UNITS, etc.)")
    similarity_score: float = Field(..., description="Hybrid retrieval similarity score (0.0 to 1.0)")
    excerpt: str = Field(..., description="Exact textual excerpt from the source chunk")

class RAGQueryRequest(BaseModel):
    """User knowledge question payload."""
    query: str = Field(..., min_length=2, max_length=500, description="Natural language question in Bangla or English")
    top_k: int = Field(default=3, ge=1, le=10, description="Maximum number of cited passages to return")
    similarity_threshold: float = Field(default=0.35, ge=0.0, le=1.0, description="Minimum hybrid score required")

class RAGQueryResponse(BaseModel):
    """Source-grounded RAG answer payload with strict separation of AI text and verified citation."""
    query: str
    status: str = Field(..., description="ANSWERED or INSUFFICIENT_SOURCE_EVIDENCE")
    answer: str = Field(..., description="Source-grounded explanation or refusal message")
    citations: List[RAGCitation] = Field(default_factory=list, description="List of verified cited sources")
    top_score: float = Field(default=0.0, description="Highest similarity score observed")
    model_used: str = Field(default="intfloat/multilingual-e5-small + TF-IDF Hybrid", description="Embedding and retrieval engine")
    legal_disclaimer: str = Field(
      default="আইনি সতর্কতা: এই উত্তর শুধুমাত্র তথ্য ও গবেষণার উদ্দেশ্যে প্রণীত। এটি কোনো আইনি পরামর্শ বা জমি স্বত্বের সরকারি সনদ নয়।",
      description="Mandatory legal disclaimer"
    )

class RAGCorpusStats(BaseModel):
    """Metadata regarding the indexed knowledge corpus."""
    corpus_version: str = SCHEMA_VERSION
    total_documents: int
    categories: Dict[str, int]
    authorities: Dict[str, int]
    embedding_model: str
    embedding_dimension: int
    is_offline_ready: bool = True
    index_storage_path: str

class DeedFieldExplanation(BaseModel):
    """Cross-referenced knowledge explanation for an extracted deed field."""
    field_name: str
    extracted_value: Any
    knowledge_title: Optional[str] = None
    explanation: str
    authority_reference: Optional[str] = None

class DeedExplanationResponse(BaseModel):
    """Executive audit and cross-referenced explanation for a stored deed document."""
    doc_id: str
    deed_number: Optional[str] = None
    deed_type: Optional[str] = None
    pipeline_state: Optional[str] = None
    record_sha256: Optional[str] = None
    field_explanations: List[DeedFieldExplanation] = Field(default_factory=list)
    audit_summary: str
    legal_disclaimer: str
