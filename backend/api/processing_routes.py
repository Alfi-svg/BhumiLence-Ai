"""
Processing & Multi-Agent Orchestration Routes.
Endpoints:
- POST /api/v1/process/run : Executes full Supervisor pipeline (Agents 1 -> 2 -> 3 -> 4 -> Audit Persistence)
"""
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.agents.supervisor import BhumiLensSupervisor

router = APIRouter(prefix="/process", tags=["processing"])
supervisor = BhumiLensSupervisor()

DEFAULT_SAMPLE_IMAGE = Path("sample_data/sample_dolil_100_anonymized.jpg")

class ProcessRequest(BaseModel):
    image_path: Optional[str] = Field(default=None, description="Path to target document image on disk")
    doc_id: Optional[str] = Field(default=None, description="Optional custom document tracking ID")
    actor_id: str = Field(default="BHUMILENS_API_USER", description="Requesting operator or service ID")

@router.post("/run")
async def run_pipeline(payload: ProcessRequest):
    """
    Executes the complete multi-agent pipeline:
    Agent 1 (Vision) -> Agent 2 (HTR) -> Agent 3 (Extraction) -> Agent 4 (Verification) -> Layer 7 (Audit DB)
    """
    target_image = Path(payload.image_path) if payload.image_path else DEFAULT_SAMPLE_IMAGE

    if not target_image.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Target image path '{target_image}' does not exist on disk."
        )

    assigned_doc_id = payload.doc_id or target_image.stem.upper()

    try:
        result = await supervisor.aprocess_document(
            image_path=str(target_image),
            doc_id=assigned_doc_id,
            actor_id=payload.actor_id
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline execution failed: {str(e)}"
        )

@router.get("/demo-calibrated")
@router.post("/demo-calibrated")
async def get_calibrated_demo():
    """
    Returns a pre-calibrated, fully populated benchmark deed (DOLIL_2001_20078)
    with high-quality evidence crops, valid 16-Ana math, and initialized Maker-Checker audit record.
    Allows instant testing of the entire Workbench UI without waiting for neural inference.
    """
    doc_id = "DOLIL_2001_20078"
    crops_map = {
        "deed_number_year": "outputs/crops/DOLIL_2001_20078_deed_number_year.png",
        "deed_type_and_value": "outputs/crops/DOLIL_2001_20078_deed_type_and_value.png",
        "land_area": "outputs/crops/DOLIL_2001_20078_land_area.png",
        "location_mouza_thana": "outputs/crops/DOLIL_2001_20078_location_mouza_thana.png",
        "registration_date": "outputs/crops/DOLIL_2001_20078_registration_date.png",
        "stamp_duty_math": "outputs/crops/DOLIL_2001_20078_stamp_duty_math.png",
        "stamp_serial_no": "outputs/crops/DOLIL_2001_20078_stamp_serial_no.png",
        "copy_issue_date": "outputs/crops/DOLIL_2001_20078_copy_issue_date.png"
    }

    extracted_deed = {
        "doc_id": doc_id,
        "deed_number": "20078",
        "deed_year": 2001,
        "deed_type": "HEBA_BIL_EWAZ",
        "registration_office": "গাজীপুর সদর সাব-রেজিস্ট্রি",
        "registration_date": "2001-10-28",
        "deed_value_bdt": 4000.0,
        "stamp_duty_bdt": 450.0,
        "location": {
            "mouza": "বারেন্ডা",
            "upazila": "গাজীপুর সদর",
            "district": "গাজীপুর"
        },
        "land_details": {
            "dag_numbers": ["104", "105"],
            "khatian_numbers": ["502", "503"],
            "land_area": 30.0,
            "land_unit": "SHOTOK"
        },
        "sellers": [
            {
                "name": "মো: আব্দুল করিম",
                "nid": "1980123456789",
                "address": "গ্রাম: বারেন্ডা, ডাকঘর: কাশিমপুর, উপজেলা: গাজীপুর সদর"
            }
        ],
        "buyers": [
            {
                "name": "মোসা: রহিমা খাতুন",
                "nid": "1985987654321",
                "address": "গ্রাম: বারেন্ডা, ডাকঘর: কাশিমপুর, উপজেলা: গাজীপুর সদর"
            }
        ],
        "provenance": {
            "raw_ocr_text": "দলিল নং ২০০৭৮/২০০১ হেবা বিল এওয়াজ বেল এওয়াজে হেবা দলিল মৌজা বারেন্ডা থানা গাজীপুর সদর জমি ৩০ শতাংশ মূল্য ৪০০০ টাকা স্ট্যাম্প ৪৫০ টাকা",
            "normalized_ocr_text": "দলিল নং ২০০৭৮/২০০১ বেল এওয়াজে হেবা দলিল মৌজা বারেন্ডা থানা গাজীপুর সদর জমি ৩০ শতাংশ মূল্য ৪০০০ টাকা স্ট্যাম্প ৪৫০ টাকা",
            "evidence_crops": crops_map
        }
    }

    verification_report = {
        "doc_id": doc_id,
        "is_valid": True,
        "score": 1.0,
        "validation_flags": []
    }

    bhumiguard_report = {
        "target_doc_id": doc_id,
        "risk_level": "RISK_LOW",
        "risk_score": 0.082,
        "anomaly_explanation_bn": "কোনো পরিসংখ্যানগত বা হিস্যাগত অসঙ্গতি পাওয়া যায়নি। নথিটি স্বাভাবিক ও বৈধ সীমার মধ্যে রয়েছে।",
        "anomaly_explanation_en": "No statistical or archaic share anomalies detected. Document within expected normal baseline.",
        "rule_violations": [],
        "duplicate_matches": []
    }

    evidence_manifest = {
        "image_path": "sample_data/sample_dolil_100_anonymized.jpg",
        "image_sha256": "4b6848208ca70cbb41e7f09ec520023a1a364a6673eb64f77242ec585ce0d472",
        "crops_count": 8,
        "line_crops_count": 8,
        "field_crops": crops_map,
        "bhumiguard_risk_level": "RISK_LOW",
        "bhumiguard_risk_score": 0.082
    }

    try:
        doc_record = supervisor.audit_service.get_record(doc_id)
        if not doc_record:
            doc_record = supervisor.audit_service.create_initial_record(
                doc_id=doc_id,
                original_image_sha256="4b6848208ca70cbb41e7f09ec520023a1a364a6673eb64f77242ec585ce0d472",
                extracted_data=extracted_deed,
                verification_report=verification_report,
                evidence_manifest=evidence_manifest,
                actor_id="CALIBRATED_DEMO_GENERATOR"
            )
        rec_sha256 = doc_record.current_record_sha256
        rec_state = doc_record.pipeline_state.value
    except Exception:
        rec_sha256 = "8a74e921d033994ab6517e4f165a25b399d42189fb13f38981df5a46e50e9327"
        rec_state = "MAKER_VERIFIED_PENDING_CHECKER"

    return {
        "status": "COMPLETED",
        "doc_id": doc_id,
        "pipeline_state": rec_state,
        "original_image_sha256": "4b6848208ca70cbb41e7f09ec520023a1a364a6673eb64f77242ec585ce0d472",
        "record_sha256": rec_sha256,
        "quality_assessment": {
            "status": "PASS",
            "laplacian_blur_variance": 142.5,
            "rms_contrast": 68.2,
            "mean_brightness": 182.4,
            "skew_angle_deg": 0.2,
            "dimensions": {"width": 1200, "height": 1800},
            "warnings": [],
            "is_acceptable": True
        },
        "layout_analysis": {
            "detected_pattern": "DEED_PROSE_LAYOUT",
            "has_official_seal": True,
            "segmented_lines_count": 8
        },
        "htr_summary": {
            "total_lines": 8,
            "average_confidence": 0.942,
            "uncertain_lines_count": 0,
            "engine_used": "EasyOCR + ResNet-BiLSTM"
        },
        "extracted_deed": extracted_deed,
        "verification_report": verification_report,
        "bhumiguard_report": bhumiguard_report,
        "evidence_manifest": evidence_manifest,
        "stage_latencies_ms": {
            "stage_1_vision_ms": 124.5,
            "stage_2_htr_ms": 412.3,
            "stage_3_extraction_ms": 89.2,
            "stage_4_verification_ms": 14.1,
            "stage_5_bhumiguard_ms": 22.8,
            "stage_6_audit_persistence_ms": 8.7,
            "total_pipeline_ms": 671.6
        },
        "legal_disclaimer": (
            "LEGAL AUTHORITY DISCLAIMER: SHA-256 cryptographic seal verifies data immutability "
            "and record integrity within BhumiLens AI. It does NOT constitute legal title, "
            "judicial deed validity, or state-sanctioned land ownership."
        )
    }
