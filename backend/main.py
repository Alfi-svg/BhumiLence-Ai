"""
BhumiLens AI + BhumiGuard — Unified Production FastAPI Application.
Offline-capable, AI-driven Bangladeshi Land Document Intelligence & Verification System.

Exposes REST APIs across all 7 layers:
- Layer 1, 2, 3: Vision Quality, Layout & Evidence Cropping
- Layer 4: Bengali Handwritten Text Recognition (HTR)
- Layer 5: Bangla Land Normalization & Qwen3-0.6B Structured Extraction
- Layer 6: Deterministic Land-Math, 16-Ana Share, Stamp Duty & Chronology Verification
- Layer 7: SQLite-backed Audit Persistence, Four-Eyes Maker-Checker & SHA-256 Tamper Detection
"""
import os
import shutil
import time
from pathlib import Path
from typing import Dict, Any

import torch
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse

from backend.api import (
    document_router,
    processing_router,
    verification_router,
    review_router,
    audit_router,
    knowledge_router
)

START_TIME = time.time()
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="BhumiLens AI + BhumiGuard Production API",
    version="1.0.0",
    description=(
        "Offline-capable AI Land Document Intelligence & Verification System "
        "tailored for Bangladeshi Land Deeds (Dolil) and Khatians."
    ),
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for local frontend & dev tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount outputs/ directory for static access to evidence crops & images
outputs_dir = WORKSPACE_ROOT / "outputs"
outputs_dir.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(outputs_dir)), name="outputs")

# Mount frontend/ directory for UI assets
frontend_dir = WORKSPACE_ROOT / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

# Mount API v1 Routers
app.include_router(document_router, prefix="/api/v1")
app.include_router(processing_router, prefix="/api/v1")
app.include_router(verification_router, prefix="/api/v1")
app.include_router(review_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")

@app.get("/")
@app.get("/workbench")
async def root(request: Request):
    """
    Serves the Human-in-the-Loop Workbench UI when requested via browser/HTML,
    or returns system API metadata when JSON is requested.
    """
    accept = request.headers.get("accept", "")
    index_path = WORKSPACE_ROOT / "frontend" / "index.html"
    
    # Return HTML UI if browser or not explicitly requesting JSON
    if "text/html" in accept or "application/json" not in accept:
        if index_path.exists():
            return FileResponse(str(index_path))

    return {
        "system": "BhumiLens AI + BhumiGuard",
        "version": "1.0.0",
        "status": "OPERATIONAL",
        "workbench_ui": "/workbench",
        "documentation": "/docs",
        "endpoints": {
            "health": "/health",
            "models_status": "/api/v1/models/status",
            "documents": "/api/v1/documents",
            "process": "/api/v1/process/run",
            "verify": "/api/v1/verify/validate-json",
            "bhumiguard": "/api/v1/verify/bhumiguard-scan",
            "review": "/api/v1/review",
            "audit": "/api/v1/audit",
            "knowledge": "/api/v1/knowledge/gazetteer"
        },
        "legal_disclaimer": (
            "LEGAL AUTHORITY DISCLAIMER: SHA-256 cryptographic seal verifies data immutability "
            "and record integrity within BhumiLens AI. It does NOT constitute legal title, "
            "judicial deed validity, or state-sanctioned land ownership."
        )
    }

@app.get("/health")
async def health_check():
    """System health check reporting uptime, storage, memory, and compute status."""
    disk_stat = shutil.disk_usage(WORKSPACE_ROOT)
    free_gib = disk_stat.free / (1024 ** 3)
    total_gib = disk_stat.total / (1024 ** 3)
    uptime_seconds = round(time.time() - START_TIME, 2)

    mps_available = torch.backends.mps.is_available()

    return {
        "status": "healthy",
        "uptime_seconds": uptime_seconds,
        "disk": {
            "free_gib": round(free_gib, 2),
            "total_gib": round(total_gib, 2),
            "safe_headroom": free_gib > 25.0
        },
        "compute": {
            "apple_silicon_mps": mps_available,
            "torch_version": torch.__version__
        },
        "active_layers": [
            "Layer 1: Document Image Quality Assessment",
            "Layer 2: Layout & Line Segmentation",
            "Layer 3: Visual Evidence Cropping & SHA-256",
            "Layer 4: Bengali Handwritten Text Recognition (HTR)",
            "Layer 5: Bangla Land Normalization & SLM Extraction",
            "Layer 6: Deterministic Land Math & Chronology Verification",
            "Layer 7: Maker-Checker Audit Persistence & Cryptographic Ledger",
            "Layer 8: Local-First Source-Grounded Knowledge Assistant (RAG & Agent 6)",
            "Layer 9: BhumiGuard Perceptual Duplicate & Tabular Anomaly Intelligence (Agent 5)"
        ]
    }

@app.get("/api/v1/models/status")
async def models_status():
    """Detailed status report of all AI models, neural weights, and deterministic services."""
    mps_available = torch.backends.mps.is_available()

    # Check local model paths
    htr_baseline_dir = WORKSPACE_ROOT / "models" / "htr" / "pretrained_baseline"
    htr_pilot_weights = WORKSPACE_ROOT / "models" / "htr" / "bhumilens_htr_v1_pilot.pt"
    qwen_base_dir = WORKSPACE_ROOT / "models" / "extractor" / "qwen3-0.6b-base"
    qwen_lora_dir = WORKSPACE_ROOT / "models" / "extractor" / "qwen3-0.6b-deed-lora"

    return {
        "system": "BhumiLens AI Model & Service Registry",
        "device": "mps" if mps_available else "cpu",
        "mps_support": mps_available,
        "models": {
            "vision_quality_engine": {
                "type": "OpenCV Deterministic",
                "status": "LOADED",
                "capabilities": ["Blur (Laplacian)", "Contrast (RMS)", "Skew (Hough Lines)", "Resolution"]
            },
            "htr_pretrained_baseline": {
                "type": "EasyOCR CRAFT + ResNet-BiLSTM (bn)",
                "status": "CACHED_OFFLINE" if htr_baseline_dir.exists() else "DOWNLOAD_ON_DEMAND",
                "local_path": str(htr_baseline_dir)
            },
            "htr_custom_pilot": {
                "type": "BhumiLens-HTR-v1-pilot (CRNN-CTC)",
                "status": "LOADED" if htr_pilot_weights.exists() else "NOT_TRAINED",
                "local_path": str(htr_pilot_weights),
                "parameters": "~1.14M (4.6 MB)"
            },
            "qwen3_0_6b_extractor": {
                "base_model": "Qwen/Qwen3-0.6B (597M Causal LM)",
                "status": "CACHED_OFFLINE" if qwen_base_dir.exists() else "AVAILABLE_ON_DEMAND",
                "lora_adapter": "BhumiLens-Qwen3-0.6B-Deed-LoRA",
                "lora_status": "LOADED" if qwen_lora_dir.exists() else "NOT_FOUND",
                "lora_parameters": "1,146,880 (0.19% trainable, 4.4 MB)",
                "lora_path": str(qwen_lora_dir)
            },
            "land_validation_service": {
                "type": "Deterministic Python Decimal/Fraction Rule Engine",
                "status": "ACTIVE",
                "zero_hallucination_guarantee": True
            },
            "audit_persistence_service": {
                "type": "SQLite + Canonical SHA-256 Audit Trail",
                "status": "ACTIVE",
                "database_path": "outputs/bhumilens_records.db",
                "four_eyes_enforced": True
            },
            "rag_knowledge_service": {
                "type": "Hybrid Dense (multilingual-e5-small) + TF-IDF Lexical RAG",
                "status": "OFFLINE_ACTIVE",
                "embedding_path": "models/embeddings/multilingual-e5-small",
                "corpus_path": "research/rag_corpus/land_knowledge_base.json",
                "anti_hallucination_guardrail": True
            },
            "knowledge_audit_agent": {
                "agent_id": "Agent 6",
                "type": "Source-Grounded Land Knowledge & Document Auditor",
                "status": "READY"
            },
            "bhumiguard_intelligence": {
                "agent_id": "Agent 5",
                "type": "Perceptual dHash (64-bit) + Cross-Record Rules + Isolation Forest",
                "status": "ACTIVE",
                "features": ["Exact SHA-256", "Hamming Perceptual dHash", "Over-transfer >16 Ana", "Isolation Forest Outlier Scoring"]
            }
        }
    }
