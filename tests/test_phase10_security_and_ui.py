"""
BhumiLens AI + BhumiGuard — Phase 10 Automated Test Suite:
1. Security Guard: Magic-byte inspection & rejection of disguised executables/scripts
2. Path traversal filename sanitization & null byte defense
3. Upload size ceiling enforcement (HTTP 413)
4. Maker-Checker role authorization & PII masking
5. FastAPI upload & review route security enforcement
6. Zero-bloat, offline full-stack Workbench UI serving (GET /, /workbench, /static)
7. Offline environment execution verification
8. Atomic SQLite database backup, cryptographic SHA-256 manifest & verified restore
"""
import os
import io
import json
import tempfile
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from fastapi import HTTPException

from backend.main import app
from backend.services.security_service import (
    SecurityGuardService,
    default_security_service,
    MAX_UPLOAD_SIZE_BYTES
)
from backend.services.audit_service import AuditPersistenceService
from backend.schemas.audit_schema import (
    DocumentRecord,
    WorkflowState
)
from scripts.backup_restore_db import (
    backup_database,
    restore_database,
    compute_file_sha256
)

client = TestClient(app)


# ==============================================================================
# 1. SECURITY SERVICE: MAGIC-BYTE REJECTION & SIGNATURE VALIDATION
# ==============================================================================

def test_security_magic_bytes_detection_and_rejection():
    """Verifies that disguised executables, scripts, and archives are rejected via magic bytes."""
    service = default_security_service

    # A. Disguised Windows PE Executable (.exe disguised as .png)
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"\x00" * 100
    with pytest.raises(HTTPException) as exc_info:
        service.validate_file_content(fake_exe, "malicious_scan.png")
    assert exc_info.value.status_code == 400
    assert "Disguised executable" in exc_info.value.detail or "Windows DOS/PE" in exc_info.value.detail

    # B. Disguised Linux ELF binary disguised as .jpg
    fake_elf = b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00" + b"\x00" * 100
    with pytest.raises(HTTPException) as exc_info:
        service.validate_file_content(fake_elf, "khatian.jpg")
    assert exc_info.value.status_code == 400
    assert "Linux ELF" in exc_info.value.detail

    # C. Disguised Shell script (shebang) disguised as .png
    fake_sh = b"#!/bin/bash\nrm -rf /tmp/data\n"
    with pytest.raises(HTTPException) as exc_info:
        service.validate_file_content(fake_sh, "porcha.png")
    assert exc_info.value.status_code == 400
    assert "Executable Shell Script" in exc_info.value.detail

    # D. Disguised PHP script
    fake_php = b"<?php system($_GET['cmd']); ?>"
    with pytest.raises(HTTPException) as exc_info:
        service.validate_file_content(fake_php, "deed_photo.jpg")
    assert exc_info.value.status_code == 400
    assert "PHP Server Script" in exc_info.value.detail

    # E. Disguised HTML/JavaScript script
    fake_html = b"<script>alert('XSS')</script>"
    with pytest.raises(HTTPException) as exc_info:
        service.validate_file_content(fake_html, "deed.png")
    assert exc_info.value.status_code == 400
    assert "Client-side HTML/JavaScript" in exc_info.value.detail

    # F. Empty file
    with pytest.raises(HTTPException) as exc_info:
        service.validate_file_content(b"", "empty.png")
    assert exc_info.value.status_code == 400
    assert "0 bytes" in exc_info.value.detail


def test_security_valid_documents_acceptance():
    """Verifies that legitimate PNG, JPEG, PDF, and TIFF signatures are accepted."""
    service = default_security_service

    # Valid PNG header
    valid_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50
    mime = service.validate_file_content(valid_png, "sample_dolil.png")
    assert mime == "image/png"

    # Valid JPEG header
    valid_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01" + b"\x00" * 50
    mime = service.validate_file_content(valid_jpeg, "sample_khatian.jpg")
    assert mime == "image/jpeg"

    # Valid PDF header
    valid_pdf = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n" + b"\x00" * 50
    mime = service.validate_file_content(valid_pdf, "land_deed.pdf")
    assert mime == "application/pdf"

    # Valid TIFF (Little-Endian)
    valid_tiff = b"II*\x00\x08\x00\x00\x00" + b"\x00" * 50
    mime = service.validate_file_content(valid_tiff, "deed_scan.tiff")
    assert mime == "image/tiff"


# ==============================================================================
# 2. PATH TRAVERSAL SANITIZATION & SIZE CEILING
# ==============================================================================

def test_security_filename_sanitization():
    """Tests defense against path traversal, null-bytes, and control characters."""
    service = default_security_service

    # Directory traversal
    assert service.sanitize_filename("../../../etc/passwd.png") == "passwd.png"
    assert service.sanitize_filename("..\\..\\Windows\\System32\\cmd.exe.png") == "cmd.exe.png"

    # Null byte injection
    assert service.sanitize_filename("valid_deed\x00.exe.png") == "valid_deed.exe.png"

    # Bengali characters preserved
    cleaned_bn = service.sanitize_filename("দলিল_গাজীপুর_২০০১.png")
    assert "দলিল" in cleaned_bn
    assert "গাজীপুর" in cleaned_bn
    assert cleaned_bn.endswith(".png")

    # Empty or blank fallback
    assert service.sanitize_filename("") == "unnamed_document.png"
    assert service.sanitize_filename("   ") == "unnamed_document.png"


def test_security_file_size_limit():
    """Verifies that payloads exceeding MAX_UPLOAD_SIZE_BYTES are rejected with 413."""
    service = default_security_service

    # Test with custom small max_size to avoid allocating 26 MB in test
    fake_content = b"\x89PNG\r\n\x1a\n" + b"A" * 1024
    with pytest.raises(HTTPException) as exc_info:
        service.validate_file_content(fake_content, "large.png", max_size=512)
    assert exc_info.value.status_code == 413
    assert "File size exceeds" in exc_info.value.detail


# ==============================================================================
# 3. MAKER-CHECKER ROLE AUTHORIZATION & PII MASKING
# ==============================================================================

def test_security_maker_checker_role_authorization():
    """Tests role validation rules for GovTech Four-Eyes governance."""
    service = default_security_service

    # Valid roles
    assert service.verify_maker_checker_roles("OPERATOR_01", "MAKER", required_role="MAKER") is True
    assert service.verify_maker_checker_roles("OFFICER_02", "CHECKER", required_role="CHECKER") is True
    # ADMIN has override access
    assert service.verify_maker_checker_roles("ADMIN_SUPER", "ADMIN", required_role="MAKER") is True
    assert service.verify_maker_checker_roles("ADMIN_SUPER", "ADMIN", required_role="CHECKER") is True

    # Invalid actor ID
    with pytest.raises(HTTPException) as exc_info:
        service.verify_maker_checker_roles(" ", "MAKER")
    assert exc_info.value.status_code == 400

    # Invalid role name
    with pytest.raises(HTTPException) as exc_info:
        service.verify_maker_checker_roles("USER_01", "HACKER")
    assert exc_info.value.status_code == 400

    # Role mismatch (MAKER attempting CHECKER approval)
    with pytest.raises(HTTPException) as exc_info:
        service.verify_maker_checker_roles("OPERATOR_01", "MAKER", required_role="CHECKER")
    assert exc_info.value.status_code == 403


def test_security_pii_masking():
    """Tests recursive masking of Bangladeshi NID and mobile phone numbers."""
    service = default_security_service

    # 1. NID masking (10-digit, 13-digit, 17-digit)
    text_nid = "National ID of owner is 19851234567890123 and old NID 1234567890."
    masked_nid = service.mask_pii(text_nid)
    assert "19851234567890123" not in masked_nid
    assert "1234567890" not in masked_nid
    assert "0123" in masked_nid  # last 4 digits visible
    assert "7890" in masked_nid

    # 2. Bangladeshi mobile number masking (017..., 018..., 019...)
    text_phone = "Contact number is 01712345678 or 01898765432."
    masked_phone = service.mask_pii(text_phone)
    assert "01712345678" not in masked_phone
    assert "017****5678" in masked_phone
    assert "018****5432" in masked_phone

    # 3. Nested dictionary & list masking
    payload = {
        "deed_no": "1002/2001",
        "seller": {
            "name": "Md. Rafiqul Islam",
            "nid": "1972123456789",
            "phone": "01911223344"
        },
        "witnesses": [
            {"name": "Witness 1", "phone": "01600112233"}
        ]
    }
    masked_dict = service.mask_pii(payload)
    assert masked_dict["seller"]["nid"] == "******6789"
    assert masked_dict["seller"]["phone"] == "019****3344"
    assert masked_dict["witnesses"][0]["phone"] == "016****2233"


# ==============================================================================
# 4. FASTAPI ROUTE SECURITY ENFORCEMENT
# ==============================================================================

def test_fastapi_upload_disguised_file_rejected():
    """POST /api/v1/documents/upload rejects disguised executable with HTTP 400."""
    fake_exe = b"MZ\x90\x00\x03\x00" + b"\x00" * 200
    files = {"file": ("malicious_deed.png", io.BytesIO(fake_exe), "image/png")}
    response = client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert "Security Violation" in data["detail"] or "Disguised executable" in data["detail"]


def test_fastapi_upload_valid_document_accepted():
    """POST /api/v1/documents/upload accepts valid PNG and returns metadata."""
    valid_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4" + b"\x00" * 50
    files = {"file": ("clean_deed.png", io.BytesIO(valid_png), "image/png")}
    response = client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["file_name"] == "clean_deed.png"
    assert data["mime_type"] == "image/png"
    assert "sha256" in data
    assert len(data["sha256"]) == 64


def test_fastapi_review_routes_role_validation():
    """Verifies that review endpoints validate X-Actor-Role headers and Four-Eyes rules."""
    audit = AuditPersistenceService()
    test_doc_id = "PHASE10_FOUR_EYES_SEC_001"

    audit.create_initial_record(
        doc_id=test_doc_id,
        original_image_sha256="abc123phase10imagehash",
        extracted_data={"deed_number": "9999", "mouza": "বারেন্ডা", "land_area": 12.0}
    )

    # 1. Maker submit with invalid role header -> 400
    payload = {
        "maker_id": "OP_MAKER_A",
        "human_corrected_data": {"deed_number": "9999", "mouza": "বারেন্ডা", "land_area": 12.0},
        "comments": "Testing invalid role"
    }
    headers_invalid = {"X-Actor-ID": "OP_MAKER_A", "X-Actor-Role": "INVALID_ROLE"}
    res_bad_role = client.post(f"/api/v1/review/{test_doc_id}/maker-submit", json=payload, headers=headers_invalid)
    assert res_bad_role.status_code == 400

    # 2. Maker submit with valid MAKER role header -> 200
    headers_maker = {"X-Actor-ID": "OP_MAKER_A", "X-Actor-Role": "MAKER"}
    res_maker_ok = client.post(f"/api/v1/review/{test_doc_id}/maker-submit", json=payload, headers=headers_maker)
    assert res_maker_ok.status_code == 200
    assert res_maker_ok.json()["pipeline_state"] == "MAKER_VERIFIED_PENDING_CHECKER"

    # 3. Checker decision with MAKER role header -> 403 Forbidden
    checker_payload = {
        "checker_id": "SUP_CHECKER_B",
        "comments": "Should be rejected because header role is MAKER"
    }
    headers_checker_bad = {"X-Actor-ID": "SUP_CHECKER_B", "X-Actor-Role": "MAKER"}
    res_checker_forbidden = client.post(f"/api/v1/review/{test_doc_id}/checker-approve", json=checker_payload, headers=headers_checker_bad)
    assert res_checker_forbidden.status_code == 403

    # 4. Checker decision with same actor ID -> 400 Four-Eyes violation
    violating_payload = {
        "checker_id": "OP_MAKER_A",
        "comments": "Self-approving"
    }
    headers_checker_same = {"X-Actor-ID": "OP_MAKER_A", "X-Actor-Role": "CHECKER"}
    res_violation = client.post(f"/api/v1/review/{test_doc_id}/checker-approve", json=violating_payload, headers=headers_checker_same)
    assert res_violation.status_code == 400
    assert "Four-Eyes" in res_violation.json()["detail"] or "maker" in res_violation.json()["detail"].lower()

    # 5. Checker decision with valid CHECKER role and distinct ID -> 200
    valid_checker_payload = {
        "checker_id": "SUP_CHECKER_B",
        "comments": "Approved and locked."
    }
    headers_checker_ok = {"X-Actor-ID": "SUP_CHECKER_B", "X-Actor-Role": "CHECKER"}
    res_checker_ok = client.post(f"/api/v1/review/{test_doc_id}/checker-approve", json=valid_checker_payload, headers=headers_checker_ok)
    assert res_checker_ok.status_code == 200
    assert res_checker_ok.json()["pipeline_state"] == "CHECKER_APPROVED_LOCKED"


# ==============================================================================
# 5. FULL-STACK WORKBENCH UI SERVING
# ==============================================================================

def test_frontend_workbench_serving():
    """Verifies that FastAPI serves the zero-bloat HTML5/CSS3/ES6 UI at /, /workbench, and /static."""
    # 1. GET / returns HTML
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "text/html" in res_root.headers.get("content-type", "")
    assert "BhumiLens AI" in res_root.text
    assert "BhumiGuard" in res_root.text

    # 2. GET /workbench returns HTML
    res_wb = client.get("/workbench")
    assert res_wb.status_code == 200
    assert "text/html" in res_wb.headers.get("content-type", "")
    assert "Human-in-the-Loop" in res_wb.text or "Maker-Checker" in res_wb.text

    # 3. GET /static/styles.css returns CSS
    res_css = client.get("/static/styles.css")
    assert res_css.status_code == 200
    assert "css" in res_css.headers.get("content-type", "")
    assert "--bg-primary" in res_css.text

    # 4. GET /static/app.js returns JavaScript
    res_js = client.get("/static/app.js")
    assert res_js.status_code == 200
    assert "javascript" in res_js.headers.get("content-type", "")
    assert "activeDocId" in res_js.text

    # 5. GET / with Accept: application/json returns system info
    res_json = client.get("/", headers={"Accept": "application/json"})
    assert res_json.status_code == 200
    data = res_json.json()
    assert data["system"] == "BhumiLens AI + BhumiGuard"
    assert data["status"].lower() == "operational"


# ==============================================================================
# 6. OFFLINE ENVIRONMENT EXECUTION VERIFICATION
# ==============================================================================

def test_offline_environment_execution():
    """Verifies that the system functions with offline environment variables enforced."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    # Health check works offline
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    # Math unit conversion works offline
    conv_payload = {"area": 5.0, "unit": "SHOTOK"}
    res_conv = client.post("/api/v1/verify/convert-unit", json=conv_payload)
    assert res_conv.status_code == 200
    assert res_conv.json()["conversions"]["shotok"] == 5.0


# ==============================================================================
# 7. DATABASE BACKUP, MANIFEST & RESTORE INTEGRITY
# ==============================================================================

def test_database_backup_and_restore_cycle():
    """Tests atomic backup creation, SHA-256 manifest export, and verified restore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "test_records.db"
        backup_dir = tmp_path / "backups"
        restore_path = tmp_path / "restored_records.db"

        # 1. Initialize AuditPersistenceService with test records
        audit_service = AuditPersistenceService(db_path=str(db_path))
        audit_service.create_initial_record(
            doc_id="TEST_PHASE10_DOC_001",
            original_image_sha256="aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899",
            extracted_data={
                "deed_number": "1234/2001",
                "district": "গাজীপুর",
                "thana_upazila": "কালিয়াকৈর",
                "mouza": "বারেন্ডা",
                "total_area_shotok": 15.5
            }
        )

        # 2. Execute backup
        manifest = backup_database(db_path=str(db_path), backup_dir=str(backup_dir))
        assert manifest["status"] == "SUCCESS"
        assert manifest["document_count"] >= 1
        assert "backup_sha256" in manifest
        assert len(manifest["backup_sha256"]) == 64

        backup_file = manifest["backup_file"]
        assert Path(backup_file).exists()

        # 3. Execute restore with SHA-256 verification
        restore_result = restore_database(
            backup_file=backup_file,
            target_db_path=str(restore_path),
            expected_sha256=manifest["backup_sha256"]
        )
        assert restore_result["status"] == "SUCCESS"
        assert restore_result["total_documents_restored"] >= 1
        assert restore_result["all_records_intact"] is True

        # 4. Verify tampering detection: modify 1 byte in backup file
        with open(backup_file, "r+b") as f:
            f.seek(100)
            f.write(b"\xff")

        with pytest.raises(ValueError) as exc_info:
            restore_database(
                backup_file=backup_file,
                target_db_path=str(tmp_path / "corrupt.db"),
                expected_sha256=manifest["backup_sha256"]
            )
        assert "checksum mismatch" in str(exc_info.value).lower()
