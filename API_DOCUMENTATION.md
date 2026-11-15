# BhumiLens AI + BhumiGuard — REST API Reference

**Base URL**: `http://localhost:8000`  
**API Version**: `v1`  
**OpenAPI / Swagger UI**: `http://localhost:8000/docs`  
**ReDoc UI**: `http://localhost:8000/redoc`

---

## 1. System Health & Infrastructure

### `GET /health`
Returns the operational health of the BhumiLens API, system uptime, and active platform details.

**Response (200 OK)**:
```json
{
  "status": "HEALTHY",
  "app_name": "BhumiLens AI + BhumiGuard Production API",
  "version": "1.0.0",
  "platform": "Apple Silicon (macOS) - MPS Accelerated"
}
```

### `GET /api/v1/models/status`
Returns runtime loading status and device allocation (MPS/CPU) of all underlying ML models.

**Response (200 OK)**:
```json
{
  "status": "SUCCESS",
  "vision_preprocessor": "OpenCV 4.13.0 (Native C++)",
  "ocr_htr_engine": "EasyOCR (Bengali + English)",
  "extraction_model": "Qwen/Qwen3-0.6B + LoRA Adapter (Float16 on MPS/CPU)",
  "validation_engine": "Exact Decimal/Fraction Rule Engine (Active)",
  "audit_service": "SQLite Four-Eyes Ledger (Active)"
}
```

---

## 2. Document Ingestion & Storage

### `POST /api/v1/documents/upload`
Uploads a deed image file (`.jpg`, `.jpeg`, `.png`, `.tiff`, `.pdf`), saves it with SHA-256 integrity verification, and returns the assigned `doc_id`.

**Request**: Multipart form data with `file` field.

**Example `curl`**:
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@sample_data/sample_dolil_100_anonymized.jpg"
```

**Response (200 OK)**:
```json
{
  "status": "success",
  "doc_id": "DOLIL_0A1B2C3D4E5F6G7H",
  "filename": "sample_dolil_100_anonymized.jpg",
  "sha256": "5f4dcc3b5aa765d61d8327deb882cf99...",
  "size_bytes": 1048576,
  "storage_path": "outputs/uploads/DOLIL_0A1B2C3D4E5F6G7H.jpg"
}
```

### `GET /api/v1/documents/{doc_id}`
Retrieves the saved document record, audit state, and extracted fields from the persistence layer.

---

## 3. End-to-End Multi-Agent Pipeline

### `POST /api/v1/process/run`
Executes the full pipeline sequentially through all 4 agents and persists the result in the audit database.

**Request Body**:
```json
{
  "image_path": "sample_data/sample_dolil_100_anonymized.jpg",
  "doc_id": "DEED_100_SAMPLE",
  "actor_id": "OPERATOR_ALFI"
}
```

**Response (200 OK)**:
```json
{
  "status": "COMPLETED",
  "doc_id": "DEED_100_SAMPLE",
  "pipeline_state": "AI_EXTRACTED_PENDING_MAKER",
  "original_image_sha256": "5f4dcc3b5aa765d61d8327deb882cf99...",
  "record_sha256": "bb13f54fa87323afd4c89861bef9762dc362248958218cf15424ae713db1a2a2",
  "quality_assessment": {
    "status": "PASS",
    "laplacian_blur_variance": 420.5,
    "skew_angle_deg": 0.45,
    "is_acceptable": true
  },
  "layout_analysis": {
    "detected_pattern": "DEED_PROSE_LAYOUT",
    "has_official_seal": true,
    "segmented_lines_count": 25
  },
  "htr_summary": {
    "total_lines": 25,
    "average_confidence": 0.884,
    "uncertain_lines_count": 2,
    "engine_used": "HYBRID_CTC_CRNN"
  },
  "extracted_deed": {
    "deed_number": "100",
    "deed_year": 2001,
    "deed_type": "SAF_KABALA",
    "location": {
      "mouza": "বারেন্ডা",
      "upazila": "গাজীপুর সদর",
      "district": "গাজীপুর"
    }
  },
  "verification_report": {
    "is_valid": true,
    "score": 0.95,
    "flags": []
  },
  "stage_latencies_ms": {
    "stage_1_vision_ms": 320.4,
    "stage_2_htr_ms": 1420.0,
    "stage_3_extraction_ms": 13800.0,
    "stage_4_verification_ms": 15.2,
    "stage_5_audit_persistence_ms": 12.0,
    "total_pipeline_ms": 15567.6
  },
  "legal_disclaimer": "LEGAL AUTHORITY DISCLAIMER: SHA-256 cryptographic seal verifies data immutability and record integrity within BhumiLens AI. It does NOT constitute legal title, judicial deed validity, or state-sanctioned land ownership."
}
```

---

## 4. Deterministic Land Math & Verification

### `POST /api/v1/verify/convert-unit`
Converts land area between Bangladeshi land measurement units using exact `Decimal` arithmetic.

**Request Body**:
```json
{
  "value": 1.0,
  "from_unit": "KATHA",
  "to_unit": "SHOTOK"
}
```

**Response (200 OK)**:
```json
{
  "original_value": 1.0,
  "from_unit": "KATHA",
  "to_unit": "SHOTOK",
  "converted_value": 1.6529,
  "sq_feet": 720.0,
  "sq_meters": 66.8902,
  "formula_applied": "1.0 KATHA * 720.00 / 435.60"
}
```

### `POST /api/v1/verify/calculate-share`
Calculates archaic 16-Ana land shares using exact `fractions.Fraction` arithmetic.

**Request Body**:
```json
{
  "share_string": "৪ আনা ১০ গন্ডা ২ কড়া ০ ক্রান্তি"
}
```

**Response (200 OK)**:
```json
{
  "is_valid": true,
  "decimal_share": 0.282813,
  "percentage": 28.2813,
  "parsed_components": {
    "ana": 4,
    "gonda": 10,
    "kara": 2,
    "kranti": 0,
    "til": 0
  },
  "exact_fraction": "543/1920"
}
```

### `POST /api/v1/verify/validate-json`
Validates an entire deed extraction JSON payload for math consistency, stamp duty correctness, and date chronology.

---

## 5. Maker-Checker Review & Audit Workflow

### `POST /api/v1/review/{doc_id}/maker-submit`
Submits human-verified or corrected deed data by the Maker. Transitions document from `AI_EXTRACTED_PENDING_MAKER` to `MAKER_VERIFIED_PENDING_CHECKER`.

**Request Body**:
```json
{
  "maker_id": "OPERATOR_ALFI",
  "verified_data": { ... },
  "notes": "Verified deed number and mouza against high-res crop"
}
```

### `POST /api/v1/review/{doc_id}/checker-approve`
Approves and locks the document by the Checker. Enforces strict Four-Eyes security: `checker_id` must NOT equal `maker_id`. Transitions document to `CHECKER_APPROVED_LOCKED`.

**Request Body**:
```json
{
  "checker_id": "OFFICER_RAHMAN",
  "comments": "Audited math, stamps, and signatures. Approved."
}
```

**Security Violation Response (400 Bad Request)**:
```json
{
  "detail": "Maker-Checker Violation: Checker 'OPERATOR_ALFI' cannot be identical to Maker 'OPERATOR_ALFI'. Requires independent Four-Eyes verification."
}
```

---

## 6. Audit Trail & Cryptographic Verification

### `GET /api/v1/audit/{doc_id}`
Retrieves the append-only audit trail and chronological history of the document.

### `GET /api/v1/audit/{doc_id}/verify-hash`
Verifies that the document's stored JSON content matches its SHA-256 seal. Detects unauthorized database tampering.

**Response (200 OK)**:
```json
{
  "doc_id": "DEED_100_SAMPLE",
  "stored_sha256": "bb13f54fa87323afd4c89861bef9762dc362248958218cf15424ae713db1a2a2",
  "computed_sha256": "bb13f54fa87323afd4c89861bef9762dc362248958218cf15424ae713db1a2a2",
  "is_tamper_free": true,
  "status": "VERIFIED_INTACT"
}
```

---

## 7. Knowledge Base & Source-Grounded RAG Assistant (Agent 6)

### `POST /api/v1/knowledge/query`
Asks a natural language question in Bangla or English about Bangladeshi land laws, deed structures, Khatian types, or archaic 16-Ana share math. Returns source-grounded answers citing verified sections, or warns if evidence is insufficient (anti-hallucination guardrail).

**Request Body**:
```json
{
  "query": "সাফ কবলা ও বায়নাপত্রের পার্থক্য কী?",
  "top_k": 3,
  "similarity_threshold": 0.35
}
```

**Response (200 OK — In-Domain Answered)**:
```json
{
  "query": "সাফ কবলা ও বায়নাপত্রের পার্থক্য কী?",
  "status": "ANSWERED",
  "answer": "উৎস রেফারেন্স (বায়নাপত্র দলিল (Baynapatra / Agreement for Sale)) অনুসারে:\n\nবায়নাপত্র হলো সম্পত্তি বিক্রয়ের প্রাথমিক আইনি চুক্তিপত্র, যেখানে একটি নির্দিষ্ট সময়ের মধ্যে অবশিষ্ট পণমূল্য পরিশোধ সাপেক্ষে চূড়ান্ত সাফ-কবলা দলিল সম্পাদনের অঙ্গীকার থাকে। ২০০৪ সালের রেজিস্ট্রেশন (সংশোধন) আইন অনুসারে বায়নাপত্র রেজিস্ট্রি করা বাধ্যতামূলক।...\n\nসংযুক্ত কর্তৃপক্ষ ও প্রমিতি: STANDARD_LAND_LEXICON_BD (GOVERNMENT_GAZETTED)।",
  "citations": [
    {
      "doc_id": "BD_LAND_KB_002",
      "section_id": "SEC_DEED_BAYNAPATRA",
      "source_title": "বায়নাপত্র দলিল (Baynapatra / Agreement for Sale)",
      "source_authority": "STANDARD_LAND_LEXICON_BD",
      "verified_status": "GOVERNMENT_GAZETTED",
      "category": "DEED_TYPES",
      "similarity_score": 0.5742,
      "excerpt": "বায়নাপত্র হলো সম্পত্তি বিক্রয়ের প্রাথমিক আইনি চুক্তিপত্র, যেখানে একটি নির্দিষ্ট সময়ের মধ্যে অবশিষ্ট পণমূল্য পরিশোধ সাপেক্ষে চূড়ান্ত সাফ-কবলা দলিল সম্পাদনের অঙ্গীকার থাকে..."
    }
  ],
  "top_score": 0.5742,
  "model_used": "intfloat/multilingual-e5-small + TF-IDF Hybrid",
  "legal_disclaimer": "আইনি সতর্কবার্তা: BhumiLens AI এর এই ব্যাখ্যা শুধুমাত্র তথ্যগত সহায়তা ও গবেষণার উদ্দেশ্যে প্রণীত। এটি কোনো আইনি পরামর্শ বা আদালতের রায় নয়। জমির চূড়ান্ত মালিকানা নির্ধারণের এখতিয়ার সহকারী কমিশনার (ভূমি), সাব-রেজিস্ট্রার ও উপযুক্ত আদালতের।"
}
```

**Response (200 OK — Out-of-Domain Anti-Hallucination Refusal)**:
```json
{
  "query": "মঙ্গল গ্রহে জমি কেনার নিয়ম কী?",
  "status": "INSUFFICIENT_SOURCE_EVIDENCE",
  "answer": "উৎস জ্ঞানভাণ্ডারে (Corpus) এই প্রশ্নের উত্তরের স্বপক্ষে পর্যাপ্ত রেফারেন্স মেলেনি। মনগড়া বা অনুমাননির্ভর তথ্য প্রদান নিষিদ্ধ।",
  "citations": [],
  "top_score": 0.0,
  "model_used": "intfloat/multilingual-e5-small + TF-IDF Hybrid (Grounding Guardrail Active)",
  "legal_disclaimer": "আইনি সতর্কবার্তা: BhumiLens AI এর এই ব্যাখ্যা শুধুমাত্র তথ্যগত সহায়তা ও গবেষণার উদ্দেশ্যে প্রণীত..."
}
```

### `GET /api/v1/knowledge/explain-doc/{doc_id}`
Cross-references a stored deed's extracted fields (`deed_type`, `land_unit`, `sixteen_ana_share`, `khatian_numbers`, `warnings`) against authoritative land laws and compiles an executive audit & provenance summary.

**Response (200 OK)**:
```json
{
  "doc_id": "DEED_100_SAMPLE",
  "deed_number": "100",
  "deed_type": "SAF_KABALA",
  "pipeline_state": "AI_EXTRACTED_PENDING_MAKER",
  "record_sha256": "bb13f54fa87323afd4c89861bef9762dc362248958218cf15424ae713db1a2a2",
  "field_explanations": [
    {
      "field_name": "deed_type",
      "extracted_value": "SAF_KABALA",
      "knowledge_title": "সাফ-কবলা দলিল (Saf-Kabala Deed / Outright Sale Deed)",
      "explanation": "সাফ-কবলা হলো চিরস্থায়ী বিক্রয় বা হস্তান্তরের চূড়ান্ত দলিল। এই দলিলের মাধ্যমে দাতা (বিক্রেতা) তাহার সম্পত্তির সমুদয় স্বত্ব, দখল ও মালিকানা গ্রহীতার (ক্রেতার) বরাবরে চিরতরে সমর্পণ করেন...",
      "authority_reference": "STANDARD_LAND_LEXICON_BD"
    }
  ],
  "audit_summary": "দলিল নম্বর 100 (প্রকৃতি: SAF_KABALA) এর ডিজিটাল রূপান্তর ও অডিট সম্পন্ন হয়েছে। বর্তমান লাইফসাইকেল স্ট্যাটাস: AI_EXTRACTED_PENDING_MAKER...",
  "legal_disclaimer": "আইনি সতর্কবার্তা: BhumiLens AI এর এই ব্যাখ্যা শুধুমাত্র তথ্যগত সহায়তা ও গবেষণার উদ্দেশ্যে প্রণীত..."
}
```

### `GET /api/v1/knowledge/corpus-stats`
Returns the status, total indexed documents, topic categories, and embedding dimension of the offline knowledge base.

---

## 8. BhumiGuard Intelligence (Agent 5 — Anomaly & Duplicate Detection)

BhumiGuard provides defense-in-depth verification combining:
1. **Visual & Cryptographic Duplicate Matching**: Exact SHA-256 and 64-bit perceptual `dHash` (Hamming distance $\le 8$ bits for near duplicates).
2. **Deterministic Cross-Record Land Consistency Rules**:
   - `CUMULATIVE_SHARE_EXCEEDED`: Cumulative transferred ownership share $> 1.0$ (16 Ana) on same Mouza + Dag + Khatian.
   - `DUPLICATE_DEED_NUMBER_CONFLICT`: Same deed serial number registered in the same sub-registry office and year.
   - `INVALID_CONSIDERATION_AMOUNT`: Saf-Kabala deed with zero or negative declared value.
   - `SUSPICIOUS_VALUATION_OUTLIER`: Extreme valuation anomalies (e.g. 500 Shotok sold for 50 BDT).
3. **Unsupervised Tabular Anomaly Scoring**: `scikit-learn` Isolation Forest trained on seed + augmented transaction distributions to detect high-dimensional outliers without arbitrary fraud labels.

> **Ethical Governance Rule**: BhumiGuard outputs factual risk levels (`RISK_LOW`, `RISK_MEDIUM`, `RISK_HIGH_REVIEW_REQUIRED`), rule violations, and statistical outlier explanations with mandatory disclaimers. It NEVER labels any person or deed as "fraudulent".

### `POST /api/v1/verify/bhumiguard-scan`
Runs on-demand BhumiGuard multi-layered risk evaluation on a deed payload and optional image.

**Request Body**:
```json
{
  "doc_id": "DEED_SCAN_REQ_01",
  "image_path": "sample_data/sample_dolil_100_anonymized.jpg",
  "extracted_data": {
    "deed_number": "4521",
    "deed_year": 2021,
    "deed_type": "SAF_KABALA",
    "registration_office": "কালিয়াকৈর সাব-রেজিস্ট্রি",
    "location": { "mouza": "চাপাইর" },
    "land_details": {
      "dag_numbers": ["104"],
      "khatian_numbers": ["502"],
      "land_area": 12.0,
      "land_unit": "SHOTOK",
      "ownership_share": 0.50
    },
    "deed_value_bdt": 1200000.0,
    "stamp_duty_bdt": 36000.0
  }
}
```

**Response (200 OK)**:
```json
{
  "schema_version": "1.0.0",
  "doc_id": "DEED_SCAN_REQ_01",
  "risk_level": "RISK_LOW",
  "risk_score": 0.1076,
  "duplicate_matches": [],
  "rule_violations": [],
  "anomaly_score": 0.3075,
  "anomaly_explanation_bn": "লেনদেনের সংখ্যাগত মেট্রিকসমূহ সাধারণ রেফারেন্স রেঞ্জের মধ্যে স্বাভাবিক রয়েছে।",
  "feature_contributions": [
    {
      "feature_name": "land_area_shotok",
      "value": 12.0,
      "expected_range": "0.00 - 45.32",
      "is_outlier": false
    },
    {
      "feature_name": "value_per_shotok",
      "value": 100000.0,
      "expected_range": "0.00 - 245000.00",
      "is_outlier": false
    }
  ],
  "disclaimer": "আইনি সতর্কবার্তা: এই অ্যানোমালি ও রিস্ক রিপোর্ট শুধুমাত্র মানুষের পর্যালোচনার (Maker-Checker Review) জন্য প্রস্তুতকৃত স্ট্যাটিস্টিক্যাল ও লজিক্যাল সতর্কতা। এটি কোনো জালিয়াতি বা অপরাধের আইনি প্রমাণ নয়।"
}
```

### `GET /api/v1/verify/bhumiguard/{doc_id}`
Retrieves a registered document from the audit database and performs complete BhumiGuard duplicate, conflict rule, and anomaly scoring.


