# BhumiLens AI + BhumiGuard — System Architecture & Technical Specifications
**Offline-Capable Multi-Agent Land Document Intelligence & Verification System**
**Version:** 1.0.0 (Production Release) | **Hardware Target:** Apple Silicon M2 (arm64, 16 GB Unified Memory)

---

## 1. High-Level Architectural Overview

BhumiLens AI + BhumiGuard is an air-gapped, on-premise artificial intelligence and verification system engineered for sub-registry offices, land revenue collectors, and district land administration in Bangladesh. It bridges the gap between century-old handwritten deeds (*Dolil*), tabular land records (*Khatian / Porcha*), and modern tamper-evident digital ledgers.

```
+---------------------------------------------------------------------------------------------------+
|                                      SYSTEM RUNTIME TOPOLOGY                                      |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [GovTech Operator / Citizen Browser]                                                             |
|       │                                                                                           |
|       ▼ HTTP (127.0.0.1:8000)                                                                     |
|  [FastAPI Unified Application Gateway] ◄── SecurityGuardService (Magic Bytes, Size, Traversal)    |
|       │                                                                                           |
|       ├─► Static Web Router ─────────► [Zero-Bloat Workbench UI (HTML5/CSS3/ES6)]                 |
|       │                                                                                           |
|       └─► API Router (v1)                                                                         |
|            │                                                                                      |
|            ▼                                                                                      |
|  [BhumiLensSupervisor] (Central Orchestrator & Memory Manager)                                     |
|       │                                                                                           |
|       ├─► Agent 1: DocumentIntelligenceAgent    (OpenCV, Morphological Filters, Hough Transform) |
|       ├─► Agent 2: HTRExtractionAgent           (EasyOCR CRAFT+ResNet, Bengali Lexicon Matcher)   |
|       ├─► Agent 3: LandInformationExtractionAgent (Qwen3-0.6B LoRA SLM, Zero-Hallucination JSON)  |
|       ├─► Agent 4: LandMathValidationAgent      (Python Decimal/Fraction, 16-Ana & Stamp Logic)  |
|       ├─► Agent 5: BhumiGuardAgent              (64-bit dHash, Isolation Forest, Conflict Rules) |
|       ├─► Agent 6: KnowledgeAuditAgent          (Multilingual-E5 RAG, Hybrid TF-IDF, Grounding)   |
|       │                                                                                           |
|       ▼                                                                                           |
|  [AuditPersistenceService & Cryptographic State Machine]                                          |
|       │                                                                                           |
|       ▼ SQLite (WAL Mode, Hot Atomic Backup via sqlite3.backup)                                   |
|  [bhumilens_records.db] (Documents, Immutable Events, SHA-256 State Seals)                       |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. The 7 Processing Layers

### Layer 1: Document Image Quality Assessment & Preprocessing
- **Module:** `src/vision_pipeline.py` & `backend/services/quality_service.py`
- **Key Metrics:**
  - **Blur Detection:** Modified Laplacian Variance ($\sigma^2 \ge 100.0$ for acceptable focus).
  - **Contrast Assessment:** Dynamic range ratio of grayscale histogram ($> 0.35$).
  - **Skew Correction:** Minimum area bounding box rotation via Hough line transforms.
  - **Morphological Binarization:** OpenCV CLAHE + morphological background division to eliminate uneven camera lighting and shadows.

### Layer 2: Document Layout Classification & Seal Detection
- **Module:** `src/vision_pipeline.py`
- **Classifier:** Morphological grid intersection counter vs spatial stamp deed layout.
  - **Stamp Deed (Dolil):** Top header zone reserved for British/Pakistani/Bangladeshi revenue stamps; bottom body contains continuous flowing handwriting.
  - **Tabular Khatian (Porcha):** High density of orthogonal grid intersections ($> 15$ crossings).
- **HSV Official Seal Detection:** HSV color thresholding (Hue: 140–180, Sat: 40–255, Val: 40–255) + Hough Circle Transform isolating circular sub-registry seals.

### Layer 3: Visual Evidence Cropping & Cryptographic Hashing
- **Module:** `src/vision_pipeline.py` & `backend/services/evidence_service.py`
- **Mechanism:** Isolates 8 high-value bounding boxes:
  1. Header Stamps
  2. Sub-Registry Office Seal
  3. Deed Identification Number
  4. Registration & Scribe Dates
  5. Donor / Seller Information
  6. Receiver / Buyer Information
  7. Schedule of Land (Mouza, Khatian, Dag)
  8. Consideration / Stamp Duty Sum
- **Evidence Integrity:** Each crop is saved as a discrete PNG snippet with its SHA-256 checksum recorded in the document's `evidence_manifest`.

### Layer 4: Bengali Handwritten Text Recognition (HTR)
- **Module:** `src/ocr_engine.py` & `backend/agents/htr_agent.py`
- **Engines:**
  - **Baseline:** EasyOCR (CRAFT + ResNet-BiLSTM) operating on individual line crops.
  - **Experimental Pilot:** BhumiLens-HTR-v1-pilot (ConvNet-BiLSTM-CTC, 4.6 MB).
- **Lexicon Normalization (`BangladeshLandGazetteer`):**
  - Weighted Levenshtein distance with custom Bengali grapheme confusion matrix resolving visual OCR confusions (e.g. `ম` $\leftrightarrow$ `স`, `ড়` $\leftrightarrow$ `ড`, `ণ` $\leftrightarrow$ `ন`).
  - Matches against official gazetteer of 64 districts, upazilas, and mouzas.

### Layer 5: Structured Land Information Extraction (SLM)
- **Module:** `backend/services/extraction_service.py` & `backend/agents/extraction_agent.py`
- **Model:** `Qwen/Qwen3-0.6B` + LoRA adapter fine-tuned on Apple Silicon MPS.
- **Zero-Hallucination Policy:** Prompt enforced schema constraints requiring unreadable or absent fields to be emitted strictly as `null` (`None`). Never hallucinates deed numbers, party names, or acreages.
- **JSON Schema:** Validated against Pydantic v2 `DeedExtractionSchema` (Schema Version `1.0.0`).

### Layer 6: Deterministic Land Math & Legal Chronology Validation
- **Module:** `src/land_math_validator.py` & `backend/agents/validation_agent.py`
- **Zero-LLM Math Policy:** Never permits a language model to perform arithmetic.
- **Components:**
  - **Exact Decimal Area Conversion:** Python `Decimal` conversion between Shotok, Katha, Bigha, and Acre ($1\text{ Acre} = 100\text{ Shotok} = 60.5\text{ Katha} = 3.025\text{ Bigha}$).
  - **Archaic 16-Ana Share Calculator:** Exact fractional decomposition:
    $$\text{Fraction} = \frac{\text{Ana}}{16} + \frac{\text{Gonda}}{320} + \frac{\text{Kara}}{1280} + \frac{\text{Kranti}}{3840} + \frac{\text{Til}}{76800}$$
  - **Stamp Duty Sum Validator:** Verifies whether stamped impressions equal the recorded total fee.
  - **Date Chronology:** Ensures $\text{Deed Registration Date} \le \text{Certified Copy Issue Date}$.

### Layer 7: Audit Persistence, Maker-Checker Governance & SHA-256 Seals
- **Module:** `backend/services/audit_service.py` & `src/database_audit.py`
- **Database:** SQLite in WAL (Write-Ahead Logging) mode.
- **Four-Eyes Governance:** State transitions enforce operator separation:
  $$\text{AI\_EXTRACTED} \xrightarrow{\text{maker\_id}} \text{MAKER\_VERIFIED} \xrightarrow{\text{checker\_id} \ne \text{maker\_id}} \text{CHECKER\_APPROVED\_LOCKED}$$
- **Cryptographic Seal:** Canonical JSON SHA-256 hash updated on every state transition. Locked records reject modification with `RecordLockedException` (HTTP 403).

---

## 3. The 6 Specialized Agents

```
+----------------------------------------------------------------------------------------------------+
|                                    BHUMILENS MULTI-AGENT ROSTER                                    |
+----------------------------------------------------------------------------------------------------+
| Agent Name                     | Target Layer   | Underlying Engine       | Output Artifact        |
|--------------------------------|----------------|-------------------------|------------------------|
| 1. DocumentIntelligenceAgent   | Layers 1, 2, 3 | OpenCV, Hough, Binarize | Quality report & crops |
| 2. HTRExtractionAgent          | Layer 4        | EasyOCR + Gazetteer     | Normalized line texts  |
| 3. LandInformationExtractAgent | Layer 5        | Qwen3-0.6B LoRA SLM     | Structured deed JSON   |
| 4. LandMathValidationAgent     | Layer 6        | Python Decimal/Fraction | Mathematical audit     |
| 5. BhumiGuardAgent             | Layer 7 + Guard| dHash + IsolationForest | Anomaly & conflict rep |
| 6. KnowledgeAuditAgent         | Knowledge RAG  | Multilingual-E5 + TFIDF | Grounded legal advice  |
+----------------------------------------------------------------------------------------------------+
```

---

## 4. BhumiGuard Intelligence: 3-Tier Anomaly & Conflict Architecture

1. **Visual & Cryptographic Duplicate Matching:**
   - Exact binary match via SHA-256.
   - Perceptual near-duplicate detection via 64-bit difference hash (`dHash`) with Hamming distance $\le 8$ bits.
2. **Cross-Record Conflict Rules:**
   - Cumulative 16-Ana share check: flags when $\sum \text{Share} > 1.0$ (16 Ana) across deeds on the same Dag/Khatian.
   - Deed collision check: flags duplicate deed numbers issued in the same sub-registry office in the same year.
   - Consideration check: flags Saf-Kabala deeds with zero or negative price.
3. **Unsupervised Anomaly Scoring (Isolation Forest):**
   - Evaluates a 6-dimensional feature vector without requiring biased or synthetic fraud labels.
   - Calculates calibrated anomaly score ($0.0 \dots 1.0$) and identifies outlier dimensions via Z-score analysis.

---

## 5. Security & Boundary Hardening

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|                                    SECURITY BOUNDARY DEFENSE                                     |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|  Incoming File Stream                                                                            |
|       │                                                                                          |
|       ├─► 1. Magic-Byte Inspection (Blocks MZ, \x7fELF, PK\x03\x04, #!/, <?php, <script)         |
|       │                                                                                          |
|       ├─► 2. Path-Traversal Neutralization (Strips ../, ..\, null-bytes; preserves Bengali text) |
|       │                                                                                          |
|       ├─► 3. Size Ceiling Enforcement (Rejects files > 25 MB with HTTP 413)                      |
|       │                                                                                          |
|       ├─► 4. Four-Eyes Header Verification (Enforces X-Actor-Role & X-Actor-ID separation)       |
|       │                                                                                          |
|       └─► 5. PII Masking Filter (Redacts NID & mobile numbers in logs and exported JSON)         |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
```

---

## 6. Disaster Recovery & Hot Backup Protocol

The database utility (`scripts/backup_restore_db.py`) safeguards against unexpected power failures or hardware faults:
1. **Online Atomic Backup:** Uses `sqlite3.backup` to take consistent hot snapshots without pausing running queries.
2. **Cryptographic Manifest:** Every backup includes a `.json` manifest containing document count, audit event count, and a 256-bit SHA-256 checksum.
3. **Tamper-Verified Restoration:** The restore routine recalculates the target file's hash against the manifest before copying into production; any byte modification aborts the restore immediately.
