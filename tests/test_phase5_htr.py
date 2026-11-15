"""
Automated Pytest Suite for Phase 5: Bengali HTR Baseline, Custom Pilot Model, and HTR Agent (Layer 4).
"""
import os
import sys
import asyncio
from pathlib import Path
import jiwer
import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from backend.schemas.htr_schema import (
    HTREngineType,
    LineRecognitionResult,
    DocumentHTRResult
)
from backend.services.htr_service import HTRService
from backend.agents.document_agent import DocumentIntelligenceAgent
from backend.agents.htr_agent import HTRAgent

@pytest.fixture
def htr_service():
    return HTRService(default_engine=HTREngineType.HYBRID, confidence_threshold=0.65)

@pytest.fixture
def htr_agent():
    return HTRAgent(default_engine=HTREngineType.HYBRID, confidence_threshold=0.65)

@pytest.fixture
def sample_line_crop():
    crop_path = WORKSPACE_ROOT / "outputs" / "evidence" / "DOLIL_SAMPLE" / "crops" / "line_001.png"
    if not crop_path.exists():
        # Fallback to authentic dolil crop or create dummy
        candidates = list((WORKSPACE_ROOT / "outputs" / "evidence").glob("**/crops/line_*.png"))
        if candidates:
            return str(candidates[0])
    return str(crop_path)

# -----------------------------------------------------------------------------
# TEST 1: CER & WER Metric Calculation
# -----------------------------------------------------------------------------
def test_cer_wer_evaluation_metric():
    ref = "গণপ্রজাতন্ত্রী বাংলাদেশ সরকার"
    hyp_identical = "গণপ্রজাতন্ত্রী বাংলাদেশ সরকার"
    assert jiwer.cer(ref, hyp_identical) == 0.0
    assert jiwer.wer(ref, hyp_identical) == 0.0

    hyp_perturbed = "গণখ্রজাতন্গ্রী নাংলাদেন সরকার"
    cer_val = jiwer.cer(ref, hyp_perturbed)
    wer_val = jiwer.wer(ref, hyp_perturbed)
    assert 0.0 < cer_val < 0.5, f"Expected moderate CER, got {cer_val}"
    assert wer_val > 0.0

# -----------------------------------------------------------------------------
# TEST 2: Real HTR Inference on Line Crop (Pretrained & Custom Pilot)
# -----------------------------------------------------------------------------
def test_real_htr_inference_on_line_crop(htr_service, sample_line_crop):
    if not os.path.exists(sample_line_crop):
        pytest.skip(f"Sample line crop not found at {sample_line_crop}")

    # 1. Pretrained baseline inference
    res_base = htr_service.recognize_line(
        crop_path=sample_line_crop,
        line_index=1,
        bbox=[10, 10, 200, 30],
        engine=HTREngineType.PRETRAINED_BASELINE
    )
    assert isinstance(res_base, LineRecognitionResult)
    assert res_base.line_id == "line_001"
    assert res_base.engine_used == HTREngineType.PRETRAINED_BASELINE
    assert res_base.latency_ms > 0
    assert isinstance(res_base.raw_text, str)

    # 2. Custom pilot model inference
    res_custom = htr_service.recognize_line(
        crop_path=sample_line_crop,
        line_index=1,
        bbox=[10, 10, 200, 30],
        engine=HTREngineType.CUSTOM_PILOT
    )
    assert isinstance(res_custom, LineRecognitionResult)
    assert res_custom.line_id == "line_001"
    assert res_custom.engine_used == HTREngineType.CUSTOM_PILOT
    assert res_custom.latency_ms > 0
    assert isinstance(res_custom.raw_text, str)

# -----------------------------------------------------------------------------
# TEST 3: Low-Confidence Uncertain Flag Triggering
# -----------------------------------------------------------------------------
def test_uncertain_flag_triggering(htr_service, tmp_path):
    # Test on a nonexistent or zero-sized crop
    empty_crop = str(tmp_path / "empty_crop.png")
    Path(empty_crop).touch()

    res = htr_service.recognize_line(
        crop_path=empty_crop,
        line_index=99,
        bbox=[0, 0, 50, 50],
        engine=HTREngineType.HYBRID
    )
    assert res.uncertain_flag is True
    assert res.confidence < 0.65

# -----------------------------------------------------------------------------
# TEST 4: HTRAgent End-to-End Integration with DocumentIntelligenceAgent
# -----------------------------------------------------------------------------
def test_htr_agent_end_to_end_integration(htr_agent, tmp_path):
    sample_img = WORKSPACE_ROOT / "sample_data" / "sample_dolil_100_anonymized.jpg"
    doc_agent = DocumentIntelligenceAgent(output_base_dir=str(tmp_path / "evidence"))
    doc_analysis = doc_agent.process_document(str(sample_img), doc_id="TEST_HTR_INTEG")

    # Run HTR Agent on the DocumentAnalysisResult (limit to first 3 lines for quick test)
    doc_analysis.layout.line_crops = doc_analysis.layout.line_crops[:3]
    htr_result = htr_agent.process_document(doc_analysis, engine=HTREngineType.HYBRID)

    assert isinstance(htr_result, DocumentHTRResult)
    assert htr_result.doc_id == "TEST_HTR_INTEG"
    assert htr_result.image_sha256 == doc_analysis.image_sha256
    assert htr_result.total_lines == len(doc_analysis.layout.line_crops)
    assert len(htr_result.recognized_lines) == htr_result.total_lines
    assert htr_result.total_recognition_time_ms > 0

# -----------------------------------------------------------------------------
# TEST 5: HTRAgent Async Execution
# -----------------------------------------------------------------------------
def test_htr_agent_async_execution(htr_agent, tmp_path):
    sample_img = WORKSPACE_ROOT / "sample_data" / "sample_dolil_100_anonymized.jpg"
    doc_agent = DocumentIntelligenceAgent(output_base_dir=str(tmp_path / "evidence"))
    doc_analysis = doc_agent.process_document(str(sample_img), doc_id="TEST_HTR_ASYNC")
    doc_analysis.layout.line_crops = doc_analysis.layout.line_crops[:2]

    htr_result = asyncio.run(htr_agent.aprocess_document(doc_analysis, engine=HTREngineType.HYBRID))
    assert isinstance(htr_result, DocumentHTRResult)
    assert htr_result.doc_id == "TEST_HTR_ASYNC"
    assert htr_result.total_lines == 2
