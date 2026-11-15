"""
BhumiLens AI — Phase 7 Automated FastAPI Integration & Governance Test Suite.
Verifies:
1. /health and /api/v1/models/status API endpoints.
2. Deterministic land math: Decimal unit conversion & 16-Ana share parsing.
3. Standalone deed validation endpoint (/api/v1/verify/validate-json).
4. Maker-Checker Four-Eyes workflow, security violation rejection & SHA-256 tamper verification.
5. End-to-end Supervisor process execution (/api/v1/process/run).
6. Document upload & retrieval (/api/v1/documents/upload).
"""
import io
import json
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.audit_service import AuditPersistenceService
from backend.schemas.audit_schema import WorkflowState

client = TestClient(app)

def test_health_and_models_status():
    """Tests /health and /api/v1/models/status endpoints."""
    # 1. Health
    res_health = client.get("/health")
    assert res_health.status_code == 200
    data_health = res_health.json()
    assert data_health["status"] == "healthy"
    assert "disk" in data_health
    assert data_health["disk"]["safe_headroom"] is True
    assert len(data_health["active_layers"]) >= 7

    # 2. Models Status
    res_models = client.get("/api/v1/models/status")
    assert res_models.status_code == 200
    data_models = res_models.json()
    assert "models" in data_models
    assert "vision_quality_engine" in data_models["models"]
    assert "qwen3_0_6b_extractor" in data_models["models"]
    assert "audit_persistence_service" in data_models["models"]

def test_deterministic_land_math_endpoints():
    """Tests exact Decimal unit conversion and 16-Ana share calculation endpoints."""
    # 1. Unit conversion: 1 Acre = 100 Shotok = 3.0303 Bigha
    conv_payload = {"area": 1.0, "unit": "ACRE"}
    res_conv = client.post("/api/v1/verify/convert-unit", json=conv_payload)
    assert res_conv.status_code == 200
    conv_data = res_conv.json()
    assert conv_data["original_area"] == 1.0
    assert conv_data["conversions"]["shotok"] == 100.0
    assert conv_data["conversions"]["sq_ft"] == 43560.0

    # 2. 16-Ana traditional share: 4 আনা = 25%, 8 আনা = 50%
    share_payload = {"share_notation": "4 আনা 0 গন্ডা 0 কড়া 0 ক্রান্তি"}
    res_share = client.post("/api/v1/verify/calculate-share", json=share_payload)
    assert res_share.status_code == 200
    share_data = res_share.json()
    assert share_data["decimal_share"] == 0.25
    assert share_data["percentage_share"] == 25.0
    assert share_data["is_valid"] is True

    # 3. Excess share (> 16 Ana) triggers validation error
    excess_payload = {"share_notation": "20 আনা 0 গন্ডা"}
    res_excess = client.post("/api/v1/verify/calculate-share", json=excess_payload)
    assert res_excess.status_code == 200
    assert res_excess.json()["is_valid"] is False

def test_deed_validation_endpoint():
    """Tests /api/v1/verify/validate-json endpoint on sample structured deed."""
    sample_deed = {
        "doc_id": "TEST_DEED_VALIDATE_01",
        "deed_number": "1234",
        "deed_year": 1995,
        "deed_type": "SAF_KABALA",
        "registration_date": "10/05/1995",
        "copy_issue_date": "15/06/2000",
        "location": {
            "mouza": "বারেন্ডা",
            "upazila": "গাজীপুর সদর",
            "district": "গাজীপুর"
        },
        "land_details": {
            "dag_numbers": ["101", "102"],
            "khatian_numbers": ["45"],
            "land_area": 12.5,
            "land_unit": "SHOTOK"
        },
        "provenance": {
            "raw_ocr_text": "১০০+১০০+১০০+১০০+৫০=৪৫০/-"
        },
        "stamp_duty_bdt": 450.0
    }
    res = client.post("/api/v1/verify/validate-json", json=sample_deed)
    assert res.status_code == 200
    report = res.json()
    assert report["doc_id"] == "TEST_DEED_VALIDATE_01"
    assert report["is_valid"] is True
    assert report["score"] >= 0.85
    assert report["unit_conversions"]["conversions"]["shotok"] == 12.5
    assert report["stamp_validation"]["is_valid"] is True

def test_maker_checker_workflow_and_security_invariants():
    """
    SECURITY TEST:
    Verifies Four-Eyes principle, rejection when maker_id == checker_id,
    and cryptographic SHA-256 integrity verification.
    """
    audit = AuditPersistenceService()
    test_doc_id = "FOUR_EYES_GOV_TEST_001"

    # 1. Create initial record
    audit.create_initial_record(
        doc_id=test_doc_id,
        original_image_sha256="abc000imagehash",
        extracted_data={"deed_number": "5555", "mouza": "মৌচাক", "land_area": 10.0}
    )

    doc_init = audit.get_document(test_doc_id)
    assert doc_init.pipeline_state == WorkflowState.AI_EXTRACTED_PENDING_MAKER

    # 2. Maker Operator submits review
    maker_payload = {
        "maker_id": "OP_MAKER_SALMAN",
        "human_corrected_data": {"deed_number": "5555", "mouza": "মৌচাক", "land_area": 10.5},
        "comments": "Corrected land area from 10.0 to 10.5 Shotok after visually checking Line 3 crop."
    }
    res_maker = client.post(f"/api/v1/review/{test_doc_id}/maker-submit", json=maker_payload)
    assert res_maker.status_code == 200
    maker_data = res_maker.json()
    assert maker_data["pipeline_state"] == "MAKER_VERIFIED_PENDING_CHECKER"
    assert maker_data["maker_id"] == "OP_MAKER_SALMAN"

    # 3. Security Violation: Same user attempts Checker Approval
    violating_checker_payload = {
        "checker_id": "OP_MAKER_SALMAN",  # Same ID!
        "comments": "Self-approving my own review."
    }
    res_violation = client.post(f"/api/v1/review/{test_doc_id}/checker-approve", json=violating_checker_payload)
    assert res_violation.status_code == 400
    assert "Four-Eyes" in res_violation.json()["detail"] or "maker" in res_violation.json()["detail"].lower()

    # 4. Valid Checker Supervisor Approval (Distinct Individual)
    valid_checker_payload = {
        "checker_id": "SUP_CHECKER_FATIMA",  # Distinct ID!
        "comments": "Verified against deed scan. Approved and locked."
    }
    res_valid_checker = client.post(f"/api/v1/review/{test_doc_id}/checker-approve", json=valid_checker_payload)
    assert res_valid_checker.status_code == 200
    checker_data = res_valid_checker.json()
    assert checker_data["pipeline_state"] == "CHECKER_APPROVED_LOCKED"
    assert checker_data["checker_id"] == "SUP_CHECKER_FATIMA"

    # 5. Subsequent edit attempts on locked record MUST be rejected (HTTP 403)
    res_locked_edit = client.post(f"/api/v1/review/{test_doc_id}/maker-submit", json=maker_payload)
    assert res_locked_edit.status_code == 403

    # 6. Verify SHA-256 seal integrity via API
    res_hash = client.get(f"/api/v1/audit/{test_doc_id}/verify-hash")
    assert res_hash.status_code == 200
    hash_data = res_hash.json()
    assert hash_data["integrity_verified"] is True
    assert hash_data["is_tampered"] is False

def test_document_upload_and_retrieval():
    """Tests file upload via multipart/form-data and retrieval."""
    test_file_content = b"Mock image byte content for BhumiLens testing"
    test_filename = "mock_test_deed.png"

    res_upload = client.post(
        "/api/v1/documents/upload",
        files={"file": (test_filename, io.BytesIO(test_file_content), "image/png")},
        data={"doc_id": "UPLOAD_TEST_DOC_88"}
    )
    assert res_upload.status_code == 200
    upload_data = res_upload.json()
    assert upload_data["status"] == "success"
    assert upload_data["doc_id"] == "UPLOAD_TEST_DOC_88"
    assert len(upload_data["sha256"]) == 64

def test_supervisor_pipeline_run_endpoint():
    """Tests /api/v1/process/run invoking BhumiLensSupervisor on sample deed."""
    process_payload = {
        "image_path": "sample_data/sample_dolil_100_anonymized.jpg",
        "doc_id": "SUPERVISOR_TEST_RUN_01",
        "actor_id": "TEST_RUNNER"
    }
    res_run = client.post("/api/v1/process/run", json=process_payload)
    assert res_run.status_code == 200
    pipeline_res = res_run.json()

    assert pipeline_res["status"] == "COMPLETED"
    assert pipeline_res["doc_id"] == "SUPERVISOR_TEST_RUN_01"
    assert pipeline_res["pipeline_state"] == "AI_EXTRACTED_PENDING_MAKER"
    assert "stage_latencies_ms" in pipeline_res
    assert "verification_report" in pipeline_res
    assert "legal_disclaimer" in pipeline_res

    # Check database persistence was triggered
    res_doc = client.get("/api/v1/documents/SUPERVISOR_TEST_RUN_01")
    assert res_doc.status_code == 200
    saved_doc = res_doc.json()
    assert saved_doc["doc_id"] == "SUPERVISOR_TEST_RUN_01"
    assert saved_doc["pipeline_state"] == "AI_EXTRACTED_PENDING_MAKER"
