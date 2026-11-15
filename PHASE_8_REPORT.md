# Phase 8 Engineering & Verification Report: BhumiLens AI + BhumiGuard

**Phase**: 8 — Local-First, Source-Grounded Land Document Knowledge Assistant (RAG) & Knowledge/Audit Agent (Agent 6)  
**Date**: November 16, 2026  
**Hardware Platform**: Apple MacBook Air M2 (16GB Unified Memory, Apple Silicon `mps:0`, macOS)  
**Disk Space Available**: **~31 GiB** (Safe operating headroom maintained)  
**Total Regression Test Status**: **36 / 36 (100%) Tests Passing** (31 pytest + 5 Phase 0)

---

## 1. Executive Summary

Phase 8 implements an offline-first, source-grounded **Retrieval-Augmented Generation (RAG)** assistant and integrates **Agent 6 (`KnowledgeAuditAgent`)** into BhumiLens AI + BhumiGuard.

To comply with land administration standards and prevent hallucinations:
1. **Curated, Authoritative Land Knowledge Corpus**: Built a versioned 12-section knowledge base (`research/rag_corpus/land_knowledge_base.json`) covering Bangladeshi deed types, Khatian hierarchies (CS, SA, RS, BS), archaic 16-Ana share calculations, and Maker-Checker security governance.
2. **Offline Local Embeddings**: Deployed `intfloat/multilingual-e5-small` (~466 MB) locally under `models/embeddings/` (Git-ignored) with cached vector indices in `outputs/rag_index/`, eliminating external network dependencies.
3. **Calibrated Hybrid Retrieval (Dense + Lexical TF-IDF)**: Combined dense multilingual sentence embeddings with Bengali-tokenized TF-IDF lexical retrieval, utilizing stopword suppression and dense baseline calibration:
   $$\text{Dense}_{\text{calib}} = \max\left(0, \frac{\text{CosineSim} - 0.72}{0.28}\right)$$
   $$S_{\text{hybrid}} = 0.50 \cdot \text{Dense}_{\text{calib}} + 0.50 \cdot S_{\text{lexical}}$$
4. **Anti-Hallucination Guardrail**: Queries scoring below the relevance threshold ($S_{\text{hybrid}} < 0.35$) trigger an explicit `INSUFFICIENT_SOURCE_EVIDENCE` refusal without fabricating non-existent laws or facts.
5. **Mandatory Citation & Disclaimer Separation**: Every response isolates: (a) Source Citations with authority metadata, (b) AI-synthesized explanation, and (c) Mandatory Legal Disclaimer.

---

## 2. Architectural Blueprint

```
User Query (Bangla/English) / Extracted Deed Cross-Reference
                                |
                                v
+-----------------------------------------------------------------------------------+
|               KnowledgeAuditAgent (Agent 6) & Knowledge Routes                    |
|   POST /api/v1/knowledge/query        GET /api/v1/knowledge/explain-doc/{id}     |
+---------------------------------------+-------------------------------------------+
                                        |
                                        v
+-----------------------------------------------------------------------------------+
|                    LandKnowledgeRAGService (Hybrid Retrieval)                     |
+-----------------------------------------------------------------------------------+
|  1. Dense Retriever: intfloat/multilingual-e5-small (M2 Apple Silicon / CPU)      |
|  2. Lexical Retriever: Bengali-aware TfidfVectorizer (Stopword-Suppressed)        |
|  3. Calibrated Score Fusion: 0.50 * DenseCalib + 0.50 * Lexical                   |
+---------------------------------------+-------------------------------------------+
                                        |
               +------------------------+------------------------+
               | Score >= 0.35                                   | Score < 0.35
               v                                                 v
+-------------------------------+               +-----------------------------------+
|      Grounding Synthesizer    |               | Anti-Hallucination Guardrail      |
| - Top-k passages cited        |               | Status: INSUFFICIENT_EVIDENCE     |
| - Authority & status verified |               | Honest refusal without invention  |
| - Mandatory Legal Disclaimer  |               | Empty citations list              |
+-------------------------------+               +-----------------------------------+
```

---

## 3. Curated Corpus Architecture (`research/rag_corpus/`)

| Document ID | Section ID | Title | Authority | Category |
| :--- | :--- | :--- | :--- | :--- |
| `BD_LAND_KB_001` | `SEC_DEED_SAF_KABALA` | সাফ-কবলা দলিল (Saf-Kabala Deed) | `STANDARD_LAND_LEXICON_BD` | `DEED_TYPES` |
| `BD_LAND_KB_002` | `SEC_DEED_BAYNAPATRA` | বায়নাপত্র দলিল (Baynapatra) | `STANDARD_LAND_LEXICON_BD` | `DEED_TYPES` |
| `BD_LAND_KB_003` | `SEC_DEED_BONTONAMA` | বণ্টননামা দলিল (Partition Deed) | `STANDARD_LAND_LEXICON_BD` | `DEED_TYPES` |
| `BD_LAND_KB_004` | `SEC_DEED_HEBA` | হেবা ও হেবা-বিল-এওয়াজ (Gift Deeds) | `STANDARD_LAND_LEXICON_BD` | `DEED_TYPES` |
| `BD_LAND_KB_005` | `SEC_DEED_EWAZ` | এওয়াজ বদল দলিল (Exchange Deed) | `STANDARD_LAND_LEXICON_BD` | `DEED_TYPES` |
| `BD_LAND_KB_006` | `SEC_KHATIAN_TYPES` | খতিয়ান বা পর্চার শ্রেণিবিভাগ (CS, SA, RS, BS) | `MINISTRY_OF_LAND_CIRCULAR` | `LAND_TERMINOLOGY` |
| `BD_LAND_KB_007` | `SEC_DAG_CHOUHADDI` | মৌজা, জে.এল. নম্বর, দাগ নম্বর ও চৌহদ্দি | `STANDARD_LAND_LEXICON_BD` | `LAND_TERMINOLOGY` |
| `BD_LAND_KB_008` | `SEC_SIXTEEN_ANA` | ১৬-আনা প্রাচীন হিস্যা পদ্ধতি (16-Ana System) | `STANDARD_LAND_LEXICON_BD` | `ARCHAIC_UNITS` |
| `BD_LAND_KB_009` | `SEC_LAND_UNITS` | ভূমি পরিমাপের একক ও রূপান্তর (Units & Math) | `MINISTRY_OF_LAND_CIRCULAR` | `ARCHAIC_UNITS` |
| `BD_LAND_KB_010` | `SEC_VERIFICATION_RED_FLAGS`| দলিল যাচাই ও রেড-ফ্ল্যাগ গাইডলাইন | `SYSTEM_GOVERNANCE_POLICY` | `VERIFICATION_GUIDELINES`|
| `BD_LAND_KB_011` | `SEC_GOVERNANCE_SECURITY` | মেকার-চেকার গভর্ন্যান্স ও SHA-256 সিল | `SYSTEM_GOVERNANCE_POLICY` | `GOVERNANCE_SECURITY` |
| `BD_LAND_KB_012` | `SEC_TAFSIL_SCHEDULE` | দলিলের তফসিল ও বায়ে-রেজিস্ট্রি বিবরণ | `STANDARD_LAND_LEXICON_BD` | `LAND_TERMINOLOGY` |

---

## 4. Benchmark & Anti-Hallucination Results

| Test Query | Target Category | Dense Raw | Lexical Max | Hybrid Score | Classification / Outcome |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `"সাফ কবলা ও বায়নাপত্রের পার্থক্য কী?"` | `DEED_TYPES` | 0.8803 | 0.6033 | **0.5879** | **ANSWERED** (Cites `BD_LAND_KB_002`, `001`) |
| `"১৬ আনা হিস্যা ও গন্ডা কীভাবে হিসাব করে?"`| `ARCHAIC_UNITS`| 0.9011 | 0.5495 | **0.5981** | **ANSWERED** (Cites `BD_LAND_KB_008`) |
| `"সিএস এবং বিএস খতিয়ান কী?"` | `LAND_TERMINOLOGY`| 0.8937 | 0.3578 | **0.4890** | **ANSWERED** (Cites `BD_LAND_KB_006`) |
| `"মৌজা ও জে.এল. নম্বর কী?"` | `LAND_TERMINOLOGY`| 0.8811 | 0.4257 | **0.5005** | **ANSWERED** (Cites `BD_LAND_KB_007`) |
| `"মঙ্গল গ্রহে জমি কেনার নিয়ম কী?"` | Out-of-Domain | 0.8092 | 0.3312 | **0.3248** | **INSUFFICIENT_EVIDENCE** (Refusal) |
| `"ক্রিকেট খেলার বিশ্বকাপ ফাইনাল কবে?"` | Out-of-Domain | 0.7499 | 0.3438 | **0.2252** | **INSUFFICIENT_EVIDENCE** (Refusal) |
| `"আইফেল টাওয়ার কোন দেশে অবস্থিত?"` | Out-of-Domain | 0.7604 | 0.2593 | **0.2018** | **INSUFFICIENT_EVIDENCE** (Refusal) |

---

## 5. Automated Test Suite Status

```
=======================================================================================================
Suite / Module                      Tests Passed   Result   Coverage Highlights
-------------------------------------------------------------------------------------------------------
tests/test_annotation_workbench.py  5 / 5          PASS     Pydantic Schema & Workbench
tests/test_phase4_document_ai.py    5 / 5          PASS     Quality Gate, Layout & Evidence Cropping
tests/test_phase5_htr.py            5 / 5          PASS     EasyOCR, CRNN & Uncertainty Flags
tests/test_phase6_extraction.py     5 / 5          PASS     Bangla Normalizer & Qwen3 LoRA Extractor
tests/test_phase7_fastapi_integration.py 6 / 6     PASS     FastAPI, Deterministic Math & Four-Eyes
tests/test_phase8_rag_knowledge.py  5 / 5          PASS     RAG Assistant, Citations & Guardrails
test_pipeline.py (Phase 0 Suite)    5 / 5          PASS     Original 5 Diagnostic Scientific Modules
=======================================================================================================
TOTAL VERIFIED TESTS                36 / 36        100%     Zero Regressions Across All Phases
=======================================================================================================
```
