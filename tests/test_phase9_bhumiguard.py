"""
Phase 9 Automated Test Suite: BhumiGuard Intelligence (Layer 6 & Agent 5).
Tests:
1. Perceptual dHash & Hamming Distance Computation
2. Exact SHA-256 and Perceptual Near-Duplicate Matching
3. Cross-Record Land Consistency & Conflict Rules (>16-Ana Over-transfer, Deed ID Collision, Zero Consideration)
4. Unsupervised Tabular Isolation Forest Anomaly Scoring on GovTech Outliers
5. BhumiGuardAgent (Agent 5) Execution & Event Logging
6. FastAPI Endpoints (/api/v1/verify/bhumiguard-scan, /api/v1/verify/bhumiguard/{doc_id})
7. End-to-End BhumiLensSupervisor Orchestration with BhumiGuard
"""
import os
import cv2
import numpy as np
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.anomaly_service import (
    BhumiGuardService,
    compute_dhash,
    compute_hamming_distance,
    IsolationForestScorer
)
from backend.services.audit_service import AuditPersistenceService
from backend.agents.bhumiguard_agent import BhumiGuardAgent
from backend.agents.supervisor import BhumiLensSupervisor
from backend.schemas.bhumiguard_schema import (
    RiskLevel,
    DuplicateMatchType,
    ConflictRuleType,
    BhumiGuardReport
)
from backend.schemas.deed_schema import DeedExtractionSchema

client = TestClient(app)
SAMPLE_IMAGE = "sample_data/sample_dolil_100_anonymized.jpg"

def test_dhash_and_hamming_distance(tmp_path):
    """
    Verifies 64-bit difference hashing (dHash) and Hamming distance metrics.
    A re-scaled/compressed duplicate should have small Hamming distance (<= 8),
    while an inverted or noise image should have large Hamming distance (> 15).
    """
    assert os.path.exists(SAMPLE_IMAGE), f"Sample image {SAMPLE_IMAGE} must exist"

    # 1. Compute dHash of original
    hash_orig = compute_dhash(SAMPLE_IMAGE)
    assert len(hash_orig) == 16, "64-bit hex hash must be 16 characters"
    assert compute_hamming_distance(hash_orig, hash_orig) == 0

    # 2. Create slightly scaled duplicate
    img = cv2.imread(SAMPLE_IMAGE)
    h, w = img.shape[:2]
    scaled_img = cv2.resize(img, (int(w * 0.8), int(h * 0.8)))
    scaled_path = str(tmp_path / "scaled_copy.jpg")
    cv2.imwrite(scaled_path, scaled_img, [cv2.IMWRITE_JPEG_QUALITY, 80])

    hash_scaled = compute_dhash(scaled_path)
    dist_scaled = compute_hamming_distance(hash_orig, hash_scaled)
    assert dist_scaled <= 6, f"Scaled copy Hamming distance ({dist_scaled}) should be <= 6"

    # 3. Create inverted noise image (completely different)
    noise_img = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
    hash_noise = compute_dhash(noise_img)
    dist_noise = compute_hamming_distance(hash_orig, hash_noise)
    assert dist_noise > 12, f"Noise image Hamming distance ({dist_noise}) should be > 12"

def test_exact_and_perceptual_duplicate_detection(tmp_path):
    """
    Verifies duplicate detection against database:
    - Exact SHA-256 match -> DuplicateMatchType.EXACT_SHA256 & RISK_HIGH_REVIEW_REQUIRED
    - Perceptual dHash near duplicate -> DuplicateMatchType.PERCEPTUAL_NEAR_DUPLICATE
    """
    db_file = str(tmp_path / "test_dup_audit.db")
    audit = AuditPersistenceService(db_path=db_file)
    guard = BhumiGuardService(db_path=db_file)

    # Pre-seed document in DB
    existing_sha256 = "1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff"
    orig_dhash = compute_dhash(SAMPLE_IMAGE)
    audit.create_initial_record(
        doc_id="SEED_DEED_DUP_01",
        original_image_sha256=existing_sha256,
        extracted_data={"deed_number": "9001", "location": {"mouza": "মির্জাপুর"}},
        evidence_manifest={"dhash_hex": orig_dhash, "image_path": SAMPLE_IMAGE}
    )

    # Case A: Exact SHA-256 match
    report_exact = guard.scan_document(
        extracted_data={"deed_number": "NEW_DEED_01", "location": {"mouza": "মির্জাপুর"}},
        target_sha256=existing_sha256,
        doc_id="TEST_EXACT_SCAN"
    )
    assert len(report_exact.duplicate_matches) >= 1
    assert any(m.match_type == DuplicateMatchType.EXACT_SHA256 for m in report_exact.duplicate_matches)
    assert report_exact.risk_level == RiskLevel.RISK_HIGH_REVIEW_REQUIRED

    # Case B: Perceptual near duplicate (different SHA, but same image content)
    report_perceptual = guard.scan_document(
        extracted_data={"deed_number": "NEW_DEED_02", "location": {"mouza": "মির্জাপুর"}},
        image_path=SAMPLE_IMAGE,
        target_sha256="different_sha256_hash_here_1234567890",
        doc_id="TEST_PERCEPTUAL_SCAN"
    )
    assert len(report_perceptual.duplicate_matches) >= 1
    near_dups = [m for m in report_perceptual.duplicate_matches if m.match_type == DuplicateMatchType.PERCEPTUAL_NEAR_DUPLICATE]
    assert len(near_dups) >= 1
    assert near_dups[0].hamming_distance <= 4

def test_cross_record_cumulative_share_conflict(tmp_path):
    """
    CRITICAL LAND LAW TEST:
    Verifies that transferring more than 16-Ana (1.0 / 100%) total share
    across deeds for the same Mouza + Dag + Khatian triggers a CRITICAL violation.
    """
    db_file = str(tmp_path / "test_share_conflict.db")
    audit = AuditPersistenceService(db_path=db_file)
    guard = BhumiGuardService(db_path=db_file)

    # Prior deed already transferred 10-Ana (0.625) of plot
    audit.create_initial_record(
        doc_id="PRIOR_DEED_SHARE_01",
        original_image_sha256="prior_share_hash_01",
        extracted_data={
            "deed_number": "1001",
            "location": {"mouza": "বড়চর"},
            "plot_numbers": {"dag_numbers": ["104"], "khatian_numbers": ["502"]},
            "sixteen_ana_share": 0.625  # 10 Ana
        }
    )

    # New deed attempts to transfer 8-Ana (0.50) of the SAME plot
    # Cumulative = 0.625 + 0.50 = 1.125 (18 Ana) -> Over-transfer!
    new_deed_data = {
        "doc_id": "NEW_DEED_OVERTRANSFER",
        "deed_number": "2002",
        "location": {"mouza": "বড়চর"},
        "plot_numbers": {"dag_numbers": ["104"], "khatian_numbers": ["502"]},
        "sixteen_ana_share": 0.50  # 8 Ana
    }

    report = guard.scan_document(
        extracted_data=new_deed_data,
        doc_id="NEW_DEED_OVERTRANSFER"
    )

    share_violations = [v for v in report.rule_violations if v.rule_type == ConflictRuleType.CUMULATIVE_SHARE_EXCEEDED]
    assert len(share_violations) == 1, "Must flag CUMULATIVE_SHARE_EXCEEDED"
    assert share_violations[0].severity == "CRITICAL"
    assert "PRIOR_DEED_SHARE_01" in share_violations[0].conflicting_doc_ids
    assert "১৬ আনা" in share_violations[0].description_bn
    assert report.risk_level == RiskLevel.RISK_HIGH_REVIEW_REQUIRED

def test_cross_record_deed_collision_and_consideration(tmp_path):
    """
    Verifies deed number collision in same sub-registry office and zero consideration on Saf-Kabala.
    """
    db_file = str(tmp_path / "test_collision.db")
    audit = AuditPersistenceService(db_path=db_file)
    guard = BhumiGuardService(db_path=db_file)

    # Prior deed registered in Kaliakair in 2022
    audit.create_initial_record(
        doc_id="PRIOR_DEED_KALIAKAIR_2022",
        original_image_sha256="prior_kaliakair_hash",
        extracted_data={
            "deed_number": "7788",
            "registration_office": "কালিয়াকৈর সাব-রেজিস্ট্রি",
            "date": "2022-03-15",
            "location": {"mouza": "চাপাইর"}
        }
    )

    # New deed with duplicate deed number in same office and year, PLUS invalid 0 BDT consideration on Saf-Kabala
    violating_deed = {
        "doc_id": "COLLISION_DEED_01",
        "deed_number": "7788",
        "registration_office": "কালিয়াকৈর সাব-রেজিস্ট্রি",
        "date": "2022-11-20",
        "deed_type": "SAF_KABALA",
        "financials": {"consideration_bdt": 0.0},
        "location": {"mouza": "চাপাইর"}
    }

    report = guard.scan_document(extracted_data=violating_deed, doc_id="COLLISION_DEED_01")
    rule_types = {v.rule_type for v in report.rule_violations}

    assert ConflictRuleType.DUPLICATE_DEED_NUMBER_CONFLICT in rule_types
    assert ConflictRuleType.INVALID_CONSIDERATION_AMOUNT in rule_types
    assert report.risk_level == RiskLevel.RISK_HIGH_REVIEW_REQUIRED

def test_tabular_isolation_forest_anomaly_scoring():
    """
    Tests unsupervised Isolation Forest:
    1. Normal realistic deed record has low anomaly score (< 0.50).
    2. Outlier deed (500 Shotok sold for 50 BDT) receives high anomaly score (> 0.50)
       and flags the consideration per shotok feature.
    """
    scorer = IsolationForestScorer()

    # Normal typical record
    normal_record = {
        "land_schedule": {"area_shotok": 12.0},
        "financials": {
            "consideration_bdt": 1_200_000.0,  # ~100k / shotok
            "stamp_duty_bdt": 36_000.0
        },
        "sixteen_ana_share": 1.0,
        "date": "2021-05-10"
    }
    score_normal, contribs_normal, bn_normal = scorer.score(normal_record)
    assert score_normal < 0.50, f"Normal record score ({score_normal}) should be < 0.50"

    # Extreme Outlier record (500 Shotok sold for 50 BDT, valuation = 0.1 BDT / shotok)
    outlier_record = {
        "land_schedule": {"area_shotok": 500.0},
        "financials": {
            "consideration_bdt": 50.0,
            "stamp_duty_bdt": 1.0
        },
        "sixteen_ana_share": 0.001,
        "date": "2023-01-01"
    }
    score_outlier, contribs_outlier, bn_outlier = scorer.score(outlier_record)
    assert score_outlier > 0.50, f"Outlier record score ({score_outlier}) should be > 0.50"
    assert any(c.is_outlier for c in contribs_outlier)
    assert "অস্বাভাবিক" in bn_outlier

def test_bhumiguard_agent_execution_and_events():
    """
    Tests BhumiGuardAgent (Agent 5) API wrapper, async execution, and event logs.
    """
    agent = BhumiGuardAgent()
    deed_data = {
        "doc_id": "AGENT5_TEST_DEED",
        "deed_number": "3344",
        "location": {"mouza": "ধামরাই"},
        "land_schedule": {"area_shotok": 15.0},
        "financials": {"consideration_bdt": 500_000.0, "stamp_duty_bdt": 15_000.0}
    }

    report = agent.scan_deed(deed_data, doc_id="AGENT5_TEST_DEED")
    assert isinstance(report, BhumiGuardReport)
    assert report.doc_id == "AGENT5_TEST_DEED"
    assert report.risk_level in [RiskLevel.RISK_LOW, RiskLevel.RISK_MEDIUM, RiskLevel.RISK_HIGH_REVIEW_REQUIRED]
    assert len(agent.events_log) >= 2
    assert agent.events_log[-1]["event"] == "SCAN_COMPLETED"

    # Test backward-compatible run_fraud_checks
    compat_res = pytest.importorskip("asyncio").run(agent.run_fraud_checks(deed_data))
    assert compat_res["status"] == "COMPLETED"
    assert "risk_level" in compat_res
    assert "আইনি সতর্কবার্তা" in compat_res["disclaimer"]

def test_fastapi_bhumiguard_endpoints():
    """
    Tests FastAPI endpoints:
    - POST /api/v1/verify/bhumiguard-scan
    - GET /api/v1/verify/bhumiguard/{doc_id}
    """
    # 1. On-demand scan via POST
    scan_payload = {
        "doc_id": "API_SCAN_DOC_01",
        "extracted_data": {
            "deed_number": "8899",
            "location": {"mouza": "সাভার"},
            "land_schedule": {"area_shotok": 8.0},
            "financials": {"consideration_bdt": 400_000.0, "stamp_duty_bdt": 12_000.0}
        }
    }
    res_post = client.post("/api/v1/verify/bhumiguard-scan", json=scan_payload)
    assert res_post.status_code == 200
    report_post = res_post.json()
    assert report_post["doc_id"] == "API_SCAN_DOC_01"
    assert "risk_level" in report_post
    assert "anomaly_score" in report_post
    assert "আইনি সতর্কবার্তা" in report_post["disclaimer"]

    # 2. Non-existent document via GET
    res_404 = client.get("/api/v1/verify/bhumiguard/NON_EXISTENT_DOC_XYZ")
    assert res_404.status_code == 404

    # 3. Create document in DB and query via GET
    audit = AuditPersistenceService()
    test_db_doc_id = "API_PERSISTED_DOC_99"
    audit.create_initial_record(
        doc_id=test_db_doc_id,
        original_image_sha256="api_persisted_hash_99",
        extracted_data={
            "deed_number": "1234",
            "location": {"mouza": "গাজীপুর"},
            "land_schedule": {"area_shotok": 10.0},
            "financials": {"consideration_bdt": 500_000.0}
        }
    )
    res_get = client.get(f"/api/v1/verify/bhumiguard/{test_db_doc_id}")
    assert res_get.status_code == 200
    report_get = res_get.json()
    assert report_get["doc_id"] == test_db_doc_id
    assert report_get["risk_level"] in ["RISK_LOW", "RISK_MEDIUM", "RISK_HIGH_REVIEW_REQUIRED"]

def test_supervisor_end_to_end_with_bhumiguard():
    """
    INTEGRATION TEST:
    Verifies that BhumiLensSupervisor orchestrates all agents (1 through 5)
    and returns bhumiguard_report inside pipeline_output.
    """
    supervisor = BhumiLensSupervisor()
    result = supervisor.process_document(
        image_path=SAMPLE_IMAGE,
        doc_id="SUPERVISOR_PHASE9_INTEGRATION_TEST"
    )

    assert result["status"] == "COMPLETED"
    assert result["doc_id"] == "SUPERVISOR_PHASE9_INTEGRATION_TEST"
    assert "bhumiguard_report" in result, "Supervisor output must include bhumiguard_report"

    guard_report = result["bhumiguard_report"]
    assert "risk_level" in guard_report
    assert "risk_score" in guard_report
    assert "anomaly_score" in guard_report
    assert "rule_violations" in guard_report
    assert "duplicate_matches" in guard_report

    # Check that stage 5 bhumiguard latency was captured
    latencies = result["stage_latencies_ms"]
    assert "stage_5_bhumiguard_ms" in latencies
    assert latencies["stage_5_bhumiguard_ms"] >= 0.0
