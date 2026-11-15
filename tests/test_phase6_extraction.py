"""
BhumiLens AI — Phase 6 Automated Test Suite: Normalization, Extraction & Agent Verification.
Verifies:
1. BanglaLandNormalizer (NFC, Digits, Terminology).
2. Noisy OCR Normalization (cleaning real Phase 5 OCR artifacts).
3. LandExtractionService Schema Compliance (DeedExtractionSchema validation).
4. Zero-Hallucination & Null Preservation (Unstated fields remain null).
5. LandInformationExtractionAgent HTR Evidence Linking (Provenance & Crop Tracking).
"""
import pytest
from backend.services.normalization_service import BanglaLandNormalizer, default_normalizer
from backend.services.extraction_service import LandExtractionService
from backend.agents.extraction_agent import LandInformationExtractionAgent
from backend.schemas.deed_schema import DeedExtractionSchema, DeedType, LandUnit
from backend.schemas.htr_schema import DocumentHTRResult, LineRecognitionResult, HTREngineType

def test_bangla_land_normalizer():
    """Tests NFC normalization, digit canonicalization, and land unit standardization."""
    normalizer = BanglaLandNormalizer()

    # 1. Digit Conversion
    bn_digits = "১২৩৪৫৬৭৮৯০"
    en_digits = normalizer.to_english_digits(bn_digits)
    assert en_digits == "1234567890", f"Expected 1234567890, got {en_digits}"
    back_to_bn = normalizer.to_bangla_digits(en_digits)
    assert back_to_bn == bn_digits, f"Expected {bn_digits}, got {back_to_bn}"

    # 2. Number Extraction
    mixed_text = "দলিল নং ১২৩৪/১৯৯৬ জমি ২৫.৫০ শতক"
    extracted_nums = normalizer.extract_numbers(mixed_text)
    numeric_values = [n.numeric_value for n in extracted_nums]
    assert 1234.0 in numeric_values
    assert 1996.0 in numeric_values
    assert 25.5 in numeric_values

    # 3. Terminology Standardization
    norm_res = normalizer.normalize("জমির পরিমাণ ৫.০ শতক সাফ-কবলা")
    norm_text = norm_res["normalized_text"]
    assert "শতাংশ" in norm_text or "শতক" in norm_text
    assert "সাফ কবলা" in norm_text

def test_noisy_ocr_text_normalization():
    """Tests normalization of realistic noisy OCR output from Phase 5."""
    normalizer = BanglaLandNormalizer()
    noisy_ocr = "গণখ্রজাতন্গ্রী নাংলাদেন সরকার । নমা ৩৭১০/১৯৮৩ সাব-রেজিস্ট্রার আফিস"
    result = normalizer.normalize(noisy_ocr)
    normalized = result["normalized_text"]

    # Check that known OCR mistakes are corrected
    assert "গণপ্রজাতন্ত্রী" in normalized
    assert "বাংলাদেশ" in normalized
    assert "সরকার" in normalized
    assert "সাব-রেজিস্ট্রি" in normalized or "সাব-রেজিস্ট্রার" in normalized

def test_land_extraction_service_schema_compliance():
    """Tests that LandExtractionService outputs a valid DeedExtractionSchema."""
    service = LandExtractionService(model_mode="deterministic")
    sample_text = "দলিল নং 1548/1992 সাফ কবলা মৌজা পাইস্কা জমি 15.0 শতাংশ দাগ নং 312, 313"

    extracted: DeedExtractionSchema = service.extract_from_text(sample_text, doc_id="DOC_TEST_001")

    assert isinstance(extracted, DeedExtractionSchema)
    assert extracted.doc_id == "DOC_TEST_001"
    assert extracted.deed_number == "1548"
    assert extracted.deed_year == 1992
    assert extracted.deed_type == DeedType.SAF_KABALA
    assert extracted.location.mouza == "পাইস্কা"
    assert extracted.land_details.land_area == 15.0
    assert extracted.land_details.land_unit == LandUnit.SHOTOK
    assert "312" in extracted.land_details.dag_numbers
    assert "313" in extracted.land_details.dag_numbers

def test_zero_hallucination_null_preservation():
    """
    CRITICAL SAFETY TEST:
    Verifies that when input text omits fields (no upazila, no khatian, no date, no seller),
    those fields strictly remain None or empty list, and are NEVER hallucinated.
    """
    service = LandExtractionService(model_mode="deterministic")
    sparse_text = "দলিল নং 9999 সাফ কবলা মৌজা মৌচাক"

    extracted = service.extract_from_text(sparse_text, doc_id="SPARSE_TEST_001")

    # Present fields
    assert extracted.deed_number == "9999"
    assert extracted.deed_type == DeedType.SAF_KABALA
    assert extracted.location.mouza == "মৌচাক"

    # Absent fields MUST be None (null)
    assert extracted.registration_date is None, "registration_date must be None"
    assert extracted.deed_value_bdt is None, "deed_value_bdt must be None"
    assert extracted.location.upazila is None, "upazila must be None"
    assert extracted.location.district is None, "district must be None"
    assert extracted.land_details.land_area is None, "land_area must be None"
    assert extracted.land_details.dag_numbers == [], "dag_numbers must be empty list"
    assert extracted.land_details.khatian_numbers == [], "khatian_numbers must be empty list"
    assert extracted.sellers == [], "sellers must be empty list"
    assert extracted.buyers == [], "buyers must be empty list"

def test_extraction_agent_htr_evidence_linking():
    """Tests end-to-end LandInformationExtractionAgent processing of DocumentHTRResult with crop linking."""
    agent = LandInformationExtractionAgent(model_mode="deterministic")

    # Construct mock DocumentHTRResult matching Phase 5 output
    mock_htr = DocumentHTRResult(
        doc_id="HTR_MOCK_101",
        image_sha256="abc123sha256hash",
        total_lines=3,
        recognized_lines=[
            LineRecognitionResult(
                line_id="line_001",
                line_index=0,
                bbox=[50, 100, 400, 35],
                evidence_crop_path="outputs/evidence/HTR_MOCK_101/crops/line_001.png",
                raw_text="দলিল নং 2370/2010 SAF_KABALA",
                confidence=0.92,
                uncertain_flag=False,
                engine_used=HTREngineType.PRETRAINED_BASELINE,
                model_version="EasyOCR-bn"
            ),
            LineRecognitionResult(
                line_id="line_002",
                line_index=1,
                bbox=[50, 150, 380, 35],
                evidence_crop_path="outputs/evidence/HTR_MOCK_101/crops/line_002.png",
                raw_text="মৌজা বারেন্ডা",
                confidence=0.95,
                uncertain_flag=False,
                engine_used=HTREngineType.PRETRAINED_BASELINE,
                model_version="EasyOCR-bn"
            ),
            LineRecognitionResult(
                line_id="line_003",
                line_index=2,
                bbox=[50, 200, 420, 35],
                evidence_crop_path="outputs/evidence/HTR_MOCK_101/crops/line_003.png",
                raw_text="জমির পরিমাণ 30.0 শতাংশ",
                confidence=0.89,
                uncertain_flag=False,
                engine_used=HTREngineType.PRETRAINED_BASELINE,
                model_version="EasyOCR-bn"
            )
        ],
        full_raw_text="দলিল নং 2370/2010 SAF_KABALA\nমৌজা বারেন্ডা\nজমির পরিমাণ 30.0 শতাংশ",
        average_confidence=0.92,
        uncertain_lines_count=0,
        engine_used=HTREngineType.PRETRAINED_BASELINE,
        total_recognition_time_ms=180.5,
        timestamp="2026-11-15T23:00:00"
    )

    result = agent.process_document(mock_htr)

    assert result.doc_id == "HTR_MOCK_101"
    assert result.deed_number == "2370"
    assert result.deed_year == 2010
    assert result.deed_type == DeedType.SAF_KABALA
    assert result.location.mouza == "বারেন্ডা"
    assert result.land_details.land_area == 30.0

    # Verify evidence crop linkage
    crops = result.provenance.evidence_crops
    assert "deed_number" in crops
    assert crops["deed_number"]["line_id"] == "line_001"
    assert crops["deed_number"]["crop_path"] == "outputs/evidence/HTR_MOCK_101/crops/line_001.png"

    assert "mouza" in crops
    assert crops["mouza"]["line_id"] == "line_002"

    assert "land_area" in crops
    assert crops["land_area"]["line_id"] == "line_003"

    # Verify events were logged
    assert len(agent.events_log) >= 3
    events = [e["event"] for e in agent.events_log]
    assert "EXTRACTION_STARTED" in events
    assert "NORMALIZATION_COMPLETED" in events
    assert "EXTRACTION_COMPLETED" in events
