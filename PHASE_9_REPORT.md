# Phase 9 Engineering & Verification Report: BhumiLens AI + BhumiGuard

**Phase**: 9 — BhumiGuard Intelligence: Perceptual Duplicate Detection, Cross-Record Conflict Rules, Unsupervised Isolation Forest Anomaly Scoring, and BhumiGuardAgent (Agent 5)  
**Date**: November 16, 2026  
**Hardware Platform**: Apple MacBook Air M2 (16GB Unified Memory, Apple Silicon `mps:0`, macOS)  
**Disk Space Available**: **~30 GiB** (Safe operating headroom maintained)  
**Total Regression Test Status**: **44 / 44 (100%) Tests Passing** (39 pytest + 5 Phase 0)

---

## 1. Executive Summary

Phase 9 implements **BhumiGuard Intelligence (Agent 5)** — an offline-capable, multi-layered risk evaluation and defense-in-depth engine for Bangladeshi land deeds.

Rather than relying on brittle binary fraud classifications, BhumiGuard introduces a **three-tier defense architecture**:
1. **Layer 1: Visual & Cryptographic Duplicate Matching**:
   - Exact 256-bit cryptographic SHA-256 matching for unmodified duplicate uploads.
   - 64-bit Difference Hashing (`dHash`) using OpenCV/NumPy downscaling to $(9 \times 8)$ grayscale gradients. Near duplicates (re-scanned, compressed, or slightly rotated copies) are identified with Hamming distance $\le 8$ bits out of 64 bits ($\ge 87.5\%$ visual similarity).
2. **Layer 2: Deterministic Cross-Record Land Consistency & Conflict Rules**:
   - `CUMULATIVE_SHARE_EXCEEDED`: Verifies that cumulative transferred shares across distinct deeds for the same Mouza + Dag + Khatian do not exceed 1.0 (16-Ana / 100%).
   - `DUPLICATE_DEED_NUMBER_CONFLICT`: Detects identical deed serial numbers registered within the same sub-registry office and registration year.
   - `INVALID_CONSIDERATION_AMOUNT`: Validates that Saf-Kabala (outright sale) deeds declare positive consideration values $> 0$ BDT.
   - `SUSPICIOUS_VALUATION_OUTLIER`: Flags extreme land area vs consideration discrepancies (e.g. 500 Shotok sold for 50 BDT).
3. **Layer 3: Unsupervised Tabular Anomaly Scoring (`IsolationForestScorer`)**:
   - Fits an `IsolationForest` on a 6-dimensional numeric feature vector (land area, deed value, value per shotok, stamp-to-value ratio, 16-Ana fraction, missing core field count) trained on seed and augmented Bangladeshi land distributions.
   - Uses decision function score calibration $\text{norm\_score} = \text{clip}(0.50 - (\text{dec} \times 4.0), 0.0, 1.0)$ to provide continuous anomaly scores and feature-level z-score explanations.
4. **Agent 5 & Supervisor Multi-Agent Orchestration**:
   - Implemented `BhumiGuardAgent` (Agent 5) with synchronous (`scan_deed`) and async (`ascan_deed`) execution.
   - Wired into `BhumiLensSupervisor` so the pipeline sequentially coordinates all **6 specialized agents** (Vision, HTR, Extraction, Verification, BhumiGuard, Knowledge/Audit).
5. **Ethical & Legal Governance**:
   - Strictly outputs transparent risk levels (`RISK_LOW`, `RISK_MEDIUM`, `RISK_HIGH_REVIEW_REQUIRED`), rule violations, and supporting evidence IDs without labeling any document or human as "fraudulent".
   - Appends mandatory legal disclaimers stating that reports are advisory alerts for human Maker-Checker review.

---

## 2. Multi-Layered Architectural Blueprint

```
Uploaded Deed Image / Extracted Deed Schema
                       |
                       v
+---------------------------------------------------------------------------------------+
|                    BhumiGuardAgent (Agent 5) & Verification Routes                    |
|       POST /api/v1/verify/bhumiguard-scan     GET /api/v1/verify/bhumiguard/{doc_id}  |
+------------------------------------------+--------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                      BhumiGuardService (Three-Tier Defense Engine)                    |
+---------------------------------------------------------------------------------------+
|  Tier 1: Visual & Cryptographic Duplicate Matching                                    |
|    - Exact SHA-256 match -> DuplicateMatchType.EXACT_SHA256 (100% similarity)        |
|    - 64-bit Perceptual dHash -> Hamming Distance <= 8 bits -> NEAR_DUPLICATE          |
+------------------------------------------+--------------------------------------------+
|  Tier 2: Deterministic Cross-Record Conflict Rules                                    |
|    - Same Mouza + Dag + Khatian Cumulative Share > 1.0 (16 Ana) -> CRITICAL           |
|    - Same Deed No + Office + Year -> DUPLICATE_DEED_NUMBER_CONFLICT                   |
|    - Saf-Kabala Value <= 0 BDT -> INVALID_CONSIDERATION_AMOUNT                        |
+------------------------------------------+--------------------------------------------+
|  Tier 3: Unsupervised Tabular Anomaly Scoring (Isolation Forest)                       |
|    - Features: [area_shotok, deed_val, val/shotok, stamp_ratio, share_frac, missing]  |
|    - Calibrated Score: norm_score = clip(0.50 - dec * 4.0, 0.0, 1.0)                  |
|    - Feature z-score breakdown and transparent Bengali outlier summary                |
+------------------------------------------+--------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                                  BhumiGuardReport                                     |
|  - doc_id, risk_level (LOW, MEDIUM, HIGH_REVIEW_REQUIRED), risk_score                 |
|  - duplicate_matches, rule_violations, anomaly_score, feature_contributions           |
|  - Mandatory Legal Advisory Disclaimer (Advisory Maker-Checker Review Only)           |
+---------------------------------------------------------------------------------------+
```

---

## 3. Mathematical & Algorithmic Foundations

### 3.1 Perceptual Difference Hashing (dHash) & Hamming Distance
Given an image $I$, difference hashing computes horizontal gradients across downscaled grayscale blocks:
1. Downscale $I \rightarrow G \in \mathbb{R}^{8 \times 9}$ (grayscale).
2. For row $r \in [0, 7]$ and column $c \in [0, 7]$:
   $$b_{8r + c} = \begin{cases} 1 & \text{if } G[r, c] > G[r, c+1] \\ 0 & \text{otherwise} \end{cases}$$
3. Resulting 64-bit vector $\mathbf{b} \in \{0, 1\}^{64}$ is formatted as a 16-character hexadecimal string.
4. Given two hashes $H_1, H_2$:
   $$\text{HammingDist}(H_1, H_2) = \sum_{i=1}^{64} (b_{1, i} \oplus b_{2, i})$$
   $$\text{Similarity}_{\text{pct}} = \left(1 - \frac{\text{HammingDist}}{64}\right) \times 100\%$$
- Evaluated: Scaled and re-compressed copies yield Hamming distances of $2 - 6$ bits, cleanly distinguished from uncorrelated deeds ($> 15$ bits).

### 3.2 Cumulative 16-Ana Ownership Share Verification
In Bangladeshi land law (State Acquisition and Tenancy Act 1950), a plot of land is traditionally partitioned into 16 Ana ($1.0$ fraction). When a deed transfers a share $s_t$ on a specific Mouza $M$, Dag set $D$, and Khatian set $K$:
$$\text{CumulativeShare}(M, D, K) = s_t + \sum_{d \in \text{DB}, M_d = M, D_d \cap D \neq \emptyset, K_d \cap K \neq \emptyset} s_d$$
If $\text{CumulativeShare} > 1.0001$, a `CRITICAL` severity `CUMULATIVE_SHARE_EXCEEDED` rule violation is generated, indicating that more land than physically exists on the survey plot has been transferred.

### 3.3 Isolation Forest Scoring & Calibration
Isolation Forest isolates anomalies by randomly selecting a feature and a split value. Outliers require significantly fewer tree splits to isolate:
$$\text{score\_samples}(x) \approx - \frac{E(h(x))}{c(n)}$$
Using scikit-learn's `decision_function(x) = score_samples(x) - \text{offset\_}`:
$$\text{norm\_score}(x) = \text{clip}\left(0.50 - \big(\text{decision\_function}(x) \times 4.0\big), 0.0, 1.0\right)$$
- Standard inlier (seed distribution / typical modern transaction): $\text{norm\_score} \in [0.15, 0.38]$ (`RISK_LOW`).
- Statistical anomaly (500 Shotok sold for 50 BDT): $\text{norm\_score} \in [0.70, 1.00]$ (`RISK_HIGH_REVIEW_REQUIRED`).

---

## 4. Verification & Test Matrix

All 44 tests pass across the entire prototype:

| Test Module | Coverage Area | Pass Count | Status |
| :--- | :--- | :---: | :---: |
| `test_pipeline.py` | Phase 0 Diagnostic & Layout Suite | 5 / 5 | ✅ PASSED |
| `test_annotation_workbench.py` | Phase 3 Schema, Splits & Workbench | 5 / 5 | ✅ PASSED |
| `test_phase4_document_ai.py` | Phase 4 Quality, Line Segmentation & Crops | 5 / 5 | ✅ PASSED |
| `test_phase5_htr.py` | Phase 5 CER/WER Metrics, HTR Agent & Pilot | 5 / 5 | ✅ PASSED |
| `test_phase6_extraction.py` | Phase 6 Normalizer, Qwen3 LoRA & Extraction | 5 / 5 | ✅ PASSED |
| `test_phase7_fastapi_integration.py` | Phase 7 Math, Maker-Checker & Audit Ledger | 6 / 6 | ✅ PASSED |
| `test_phase8_rag_knowledge.py` | Phase 8 Land Knowledge RAG & Agent 6 | 5 / 5 | ✅ PASSED |
| `test_phase9_bhumiguard.py` | Phase 9 Duplicate Detection, Conflicts & Isolation Forest | 8 / 8 | ✅ PASSED |
| **Total** | **Unified BhumiLens AI Test Suite** | **44 / 44** | **100% GREEN** |

---

## 5. Security & Hardware Verification

- **Operating System & Chipset**: macOS on Apple Silicon M2, 16GB Unified Memory.
- **Available Disk Space**: **~30 GiB** (Safe operating headroom maintained).
- **Git Commit Safety**: Virtual environments (`.venv*`), raw datasets, local SQLite databases (`outputs/*.db`), and model weights (`*.pt`) remain Git-ignored.
- **System Readiness**: Phase 9 is complete. The system is ready for Phase 10 upon user authorization.
