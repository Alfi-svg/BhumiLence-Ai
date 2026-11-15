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
