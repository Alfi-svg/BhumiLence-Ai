# Phase 7 Engineering & Verification Report: BhumiLens AI + BhumiGuard

**Phase**: 7 — Deterministic Land Validation (Agent 4), Maker-Checker Audit Persistence (Layer 7), Supervisor Orchestrator & Production FastAPI Backend  
**Date**: November 15, 2026  
**Hardware Target**: Apple MacBook Air M2 (16GB Unified Memory, Apple Silicon `mps:0`, macOS)  
**Disk Status**: ~32 GiB Available  
**Regression Test Status**: **31 / 31 (100%) Tests Passing** (26 pytest + 5 Phase 0)

---

## 1. Executive Summary

Phase 7 integrates all individual AI/ML modules and document intelligence layers built during Phases 1–6 into a unified, production-grade **FastAPI Backend** governed by the **BhumiLensSupervisor** multi-agent coordinator.

In adherence to GovTech Bangladesh and Land Administration compliance rules:
1. **Deterministic Rule Engines Over LLMs**: Land unit conversions, 16-Ana archaic fractional shares, stamp duty additions, and chronological deed sequencing are calculated strictly with Python's exact `decimal.Decimal` and `fractions.Fraction` primitives—guaranteeing zero floating-point drift and zero hallucination.
2. **Four-Eyes Maker-Checker Audit Architecture**: Implemented a state machine (`AI_EXTRACTED_PENDING_MAKER` -> `MAKER_VERIFIED_PENDING_CHECKER` -> `CHECKER_APPROVED_LOCKED`) backed by SQLite persistence (`outputs/bhumilens_records.db`, Git-ignored). Programmatic security invariants prevent a Maker from approving their own records (`maker_id != checker_id`), and locked records cannot be modified.
3. **Cryptographic SHA-256 Immutability**: Every document version is canonicalized and sealed with a 64-character SHA-256 hash. Real-time `/audit/{doc_id}/verify-hash` endpoints detect unauthorized tampering.
4. **Legal Authority Demarcation**: All API outputs and audit trails carry an explicit legal disclaimer confirming that the cryptographic seal certifies digital data immutability, **not** legal ownership or judicial title validity.

---

## 2. Architectural Blueprint

```
                      +---------------------------------------+
                      |       Client / Frontend (Phase 8)     |
                      +-------------------+-------------------+
                                          | HTTP REST (FastAPI)
                                          v
+-----------------------------------------------------------------------------------+
|                        BhumiLens Production FastAPI Backend                       |
|                                                                                   |
|  /api/v1/documents     /api/v1/process       /api/v1/verify       /api/v1/review  |
|  - Upload Image        - Run Supervisor      - Land Math          - Maker Submit  |
|  - Retrieve Records    - Status & Telemetry  - 16-Ana Shares      - Checker Lock  |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                   BhumiLensSupervisor (Multi-Agent Coordinator)                    |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [Stage 1] Agent 1: DocumentIntelligenceAgent (Vision, Quality Gate & Layout)     |
|            -> Generates OpenCV shadow removal, seal suppression, evidence crops   |
|                                                                                   |
|  [Stage 2] Agent 2: HTRAgent (Bengali Handwritten Text Recognition)               |
|            -> Executes EasyOCR baseline + CTC CRNN, computes CER & confidence     |
|                                                                                   |
|  [Stage 3] Agent 3: LandInformationExtractionAgent (Grapheme & LLM Extraction)   |
|            -> Normalizes Bangla text, runs Qwen3-0.6B LoRA, enforces grounding   |
|                                                                                   |
|  [Stage 4] Agent 4: VerificationAgent (Deterministic Math & Consistency Engine)   |
|            -> Exact Decimal conversion (Shotok/Katha/Bigha/Acre), 16-Ana Fraction |
|                                                                                   |
|  [Stage 5] Layer 7: AuditPersistenceService (SQLite + Canonical SHA-256)          |
|            -> Four-Eyes State Machine, Tamper-Evident SHA-256 Seal                |
+-----------------------------------------------------------------------------------+
```

---

## 3. Implemented Components

### 3.1 Deterministic Land Math Service (`backend/services/land_validation_service.py`)
- **`LandUnitConverter`**: Implements exact conversion rates using `decimal.Decimal`:
  - 1 Shotok (শতাংশ) = 435.60 sq ft
  - 1 Katha (কাঠা) = 720.00 sq ft (1.65289 Shotok)
  - 1 Bigha (বিঘা) = 20 Katha = 14,400 sq ft (33.0578 Shotok)
  - 1 Acre (একর) = 100 Shotok = 43,560 sq ft
  - 1 Ajutangsho (অযুতাংশ) = 0.01 Shotok = 4.356 sq ft
- **`SixteenAnaValidator`**: Archaic Bengali fractional share arithmetic computed via `fractions.Fraction`:
  $$\text{Total Share} = \frac{\text{Ana}}{16} + \frac{\text{Gonda}}{320} + \frac{\text{Kara}}{1280} + \frac{\text{Kranti}}{3840} + \frac{\text{Til}}{76800}$$
  Matches exactly $1.0$ (16 Ana) and parses text expressions like `"৪ আনা ১০ গন্ডা ২ কড়া ০ ক্রান্তি"` with $100\%$ precision.
- **`validate_stamp_duty`**: Verifies physical adhesive stamps against declared deed stamp duty.
- **`validate_chronology`**: Enforces historical validity (e.g., deed year $\ge 1885$, registration date $\le$ certified copy issue date).

### 3.2 Four-Eyes Maker-Checker Audit Persistence (`backend/services/audit_service.py`)
- **SQLite Database**: `outputs/bhumilens_records.db` with two relational tables:
  - `document_records`: Holds document ID, SHA-256 hashes, workflow states, and full JSON payloads.
  - `audit_events`: Append-only immutable log recording actor ID, role, action, timestamp, and SHA-256 digest.
- **Enforced Security Invariants**:
  - `maker_id != checker_id`: An operator cannot check their own drafted/extracted record (`MakerCheckerViolationException`).
  - `RecordLockedException`: Disallows modifications once in `CHECKER_APPROVED_LOCKED` state.
  - Cryptographic verification via canonical JSON hashing (`hashlib.sha256(json_str.encode('utf-8')).hexdigest()`).

### 3.3 Multi-Agent Supervisor Orchestrator (`backend/agents/supervisor.py`)
- Coordinates the 4 agents sequentially to prevent RAM spikes on 16GB Apple M2 hardware.
- Tracks per-stage latency telemetry (`stage_1_vision_ms`, `stage_2_htr_ms`, `stage_3_extraction_ms`, `stage_4_verification_ms`, `stage_5_audit_persistence_ms`).
- Automatically produces evidence manifests linking cropped bounding boxes to extracted fields.

### 3.4 Production FastAPI Application (`backend/main.py` & `backend/api/`)
- Modular APIRouters:
  - `/api/v1/documents`: File upload (`/upload`) and record fetching (`/{doc_id}`).
  - `/api/v1/process`: Pipeline execution (`/run`).
  - `/api/v1/verify`: Land unit conversion, 16-Ana share math, and full deed validation.
  - `/api/v1/review`: Human Maker submission (`/maker-submit`) and Checker approval (`/checker-approve`).
  - `/api/v1/audit`: Audit trail retrieval and cryptographic tamper-check (`/verify-hash`).
  - `/api/v1/knowledge`: Health check and administrative gazetteer queries.
- CORS middleware configured for React/Vite development (`localhost:5173`, `localhost:3000`).
- Static mount for visual evidence crops under `/outputs`.

---

## 4. Verification & Test Results

### 4.1 Phase 7 Test Suite (`tests/test_phase7_fastapi_integration.py`)
| Test Case | Description | Result | Latency |
| :--- | :--- | :---: | :---: |
| `test_health_and_models_status` | Verifies FastAPI `/health` and model loading status | **PASS** | 12 ms |
| `test_deterministic_land_math_endpoints` | Unit conversion & 16-Ana exact fraction arithmetic | **PASS** | 8 ms |
| `test_deed_validation_endpoint` | Verifies stamp duty, chronology, and scoring | **PASS** | 15 ms |
| `test_maker_checker_workflow_and_security_invariants` | Enforces state machine, Four-Eyes separation, and tamper detection | **PASS** | 35 ms |
| `test_document_upload_and_retrieval` | Multipart image upload and metadata extraction | **PASS** | 22 ms |
| `test_supervisor_pipeline_run_endpoint` | Full end-to-end multi-agent execution on real deed | **PASS** | 41.2 s |

### 4.2 Full Repository Regression Summary
- **Phase 3**: 5 / 5 passed
- **Phase 4**: 5 / 5 passed
- **Phase 5**: 5 / 5 passed
- **Phase 6**: 5 / 5 passed
- **Phase 7**: 6 / 6 passed
- **Phase 0** (`test_pipeline.py`): 5 / 5 passed
- **Total Passing Tests**: **31 / 31 (100% Success Rate)**

---

## 5. Next Steps
Phase 7 is complete and verified. The backend is fully operational and ready to serve the interactive React + Vite frontend workbench in **Phase 8**.
