"""
BhumiLens AI - API Routes Package
"""
from backend.api.document_routes import router as document_router
from backend.api.processing_routes import router as processing_router
from backend.api.verification_routes import router as verification_router
from backend.api.review_routes import router as review_router
from backend.api.audit_routes import router as audit_router
from backend.api.knowledge_routes import router as knowledge_router

__all__ = [
    "document_router",
    "processing_router",
    "verification_router",
    "review_router",
    "audit_router",
    "knowledge_router"
]
