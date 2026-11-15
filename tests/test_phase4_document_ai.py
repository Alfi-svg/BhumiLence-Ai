"""
Automated Pytest Suite for Phase 4: Document AI, Quality Gate, Layout Segmentation, and Evidence Cropping.
"""
import os
import sys
import asyncio
from pathlib import Path
import cv2
import numpy as np
import pytest

# Ensure project root is in python module search path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from backend.schemas.document_schema import (
    QualityStatus,
    LayoutPattern,
    DocumentAnalysisResult
)
from backend.services.document_vision_service import DocumentVisionService
from backend.agents.document_agent import DocumentIntelligenceAgent

@pytest.fixture
def vision_service(tmp_path):
    return DocumentVisionService(output_base_dir=str(tmp_path / "evidence"))

@pytest.fixture
def document_agent(tmp_path):
    return DocumentIntelligenceAgent(output_base_dir=str(tmp_path / "evidence"))

# -----------------------------------------------------------------------------
# TEST 1: Quality Gate on Sharp vs Degraded Images
# -----------------------------------------------------------------------------
def test_quality_assessment_sharp_vs_degraded(vision_service, tmp_path):
    # 1. Create a sharp synthetic document with black text on white background
    sharp_img = np.ones((800, 800, 3), dtype=np.uint8) * 255
    for y in range(80, 750, 40):
        cv2.putText(sharp_img, "Bangla Land Deed Saf-Kabala Verification 2026",
                    (50, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    
    quality_sharp = vision_service.assess_image_quality(sharp_img)
    assert quality_sharp.status == QualityStatus.PASS
    assert quality_sharp.is_acceptable is True
    assert quality_sharp.laplacian_blur_variance > 100.0

    # 2. Blur the image heavily
    blurry_img = cv2.GaussianBlur(sharp_img, (35, 35), 0)
    quality_blurry = vision_service.assess_image_quality(blurry_img)
    assert quality_blurry.status == QualityStatus.WARN_BLURRY
    assert quality_blurry.laplacian_blur_variance < 80.0
    assert any("blurry" in w.lower() for w in quality_blurry.warnings)

    # 3. Low contrast / washed out image
    washed_out = np.ones((800, 800, 3), dtype=np.uint8) * 128
    cv2.putText(washed_out, "Low Contrast Faint Text", (50, 400),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (120, 120, 120), 1)
    quality_low_contrast = vision_service.assess_image_quality(washed_out)
    assert quality_low_contrast.status in [QualityStatus.WARN_LOW_CONTRAST, QualityStatus.WARN_BLURRY]
    assert quality_low_contrast.rms_contrast < 18.0

# -----------------------------------------------------------------------------
# TEST 2: Seal/Stamp & Tabular Grid Detection
# -----------------------------------------------------------------------------
def test_seal_and_tabular_detection(vision_service):
    khatian_path = WORKSPACE_ROOT / "sample_data" / "sample_khatian_synthetic.png"
    assert khatian_path.exists(), "Khatian sample image must exist"
    
    khatian_res = vision_service.process_document(str(khatian_path), doc_id="TEST_KHATIAN")
    assert khatian_res.layout.pattern == LayoutPattern.KHATIAN_TABULAR_LAYOUT
    assert khatian_res.layout.has_tabular_grid is True
    assert khatian_res.layout.grid_intersections >= 12

    dolil_path = WORKSPACE_ROOT / "sample_data" / "sample_dolil_100_anonymized.jpg"
    assert dolil_path.exists(), "Dolil sample image must exist"

    dolil_res = vision_service.process_document(str(dolil_path), doc_id="TEST_DOLIL")
    assert dolil_res.layout.pattern == LayoutPattern.DEED_PROSE_LAYOUT
    assert dolil_res.layout.official_seal_detected is True

# -----------------------------------------------------------------------------
# TEST 3: Handwritten Line Segmentation & Top-to-Bottom Ordering
# -----------------------------------------------------------------------------
def test_handwritten_line_segmentation_ordering(vision_service):
    dolil_path = WORKSPACE_ROOT / "sample_data" / "sample_dolil_100_anonymized.jpg"
    img_bgr = cv2.imread(str(dolil_path))
    norm_gray, bin_clean = vision_service.preprocess_image(img_bgr)
    layout = vision_service.analyze_layout(img_bgr, norm_gray, bin_clean)

    assert layout.detected_lines_count >= 10, f"Expected at least 10 lines, got {layout.detected_lines_count}"
    assert len(layout.line_crops) == layout.detected_lines_count

    # Check strict vertical ordering: y_{i} <= y_{i+1}
    for i in range(len(layout.line_crops) - 1):
        curr_y = layout.line_crops[i].bbox[1]
        next_y = layout.line_crops[i + 1].bbox[1]
        assert curr_y <= next_y, f"Line {i} y={curr_y} should be <= Line {i+1} y={next_y}"

    # Check valid bounding boxes
    for lc in layout.line_crops:
        x, y, w, h = lc.bbox
        assert w > 0 and h > 0, "Line bounding box dimensions must be positive"

# -----------------------------------------------------------------------------
# TEST 4: Evidence Crop Generation & Provenance Hash
# -----------------------------------------------------------------------------
def test_evidence_crops_generation_and_integrity(vision_service):
    dolil_path = WORKSPACE_ROOT / "sample_data" / "sample_dolil_100_anonymized.jpg"
    res = vision_service.process_document(str(dolil_path), doc_id="TEST_EVIDENCE_PROV")

    # 1. SHA-256 Provenance Check
    assert len(res.image_sha256) == 64
    assert res.doc_id == "TEST_EVIDENCE_PROV"

    # 2. Preprocessed Image Paths
    assert os.path.exists(res.normalized_image_path)
    assert os.path.exists(res.binarized_image_path)

    # 3. Core Evidence Crops
    assert "header_zone" in res.evidence_crops
    assert "stamp_duty_math" in res.evidence_crops
    assert "deed_number_year" in res.evidence_crops
    assert "land_area" in res.evidence_crops

    # 4. Check files on disk
    for crop_id, crop in res.evidence_crops.items():
        assert os.path.exists(crop.crop_path), f"Crop path missing for {crop_id}"
        assert os.path.getsize(crop.crop_path) > 0, f"Crop file empty for {crop_id}"

# -----------------------------------------------------------------------------
# TEST 5: DocumentIntelligenceAgent End-to-End Execution
# -----------------------------------------------------------------------------
def test_document_intelligence_agent_orchestration(document_agent):
    dolil_path = str(WORKSPACE_ROOT / "sample_data" / "sample_dolil_100_anonymized.jpg")
    
    # Synchronous process
    res_sync = document_agent.process_document(dolil_path, doc_id="AGENT_SYNC_TEST")
    assert isinstance(res_sync, DocumentAnalysisResult)
    assert res_sync.doc_id == "AGENT_SYNC_TEST"
    assert res_sync.processing_time_ms > 0

    # Asynchronous process
    res_async = asyncio.run(document_agent.aprocess_document(dolil_path, doc_id="AGENT_ASYNC_TEST"))
    assert isinstance(res_async, DocumentAnalysisResult)
    assert res_async.doc_id == "AGENT_ASYNC_TEST"
    assert res_async.image_sha256 == res_sync.image_sha256
