"""
Automated Pytest for Human Annotation Workbench & DeedExtractionSchema
Tests:
1. Pydantic v2 DeedExtractionSchema validation & null safety
2. JSONL serialization, persistence, and retrieval
3. Curation queue loading and metadata integrity
"""
import os
import sys
import json
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.schemas.deed_schema import (
    DeedExtractionSchema,
    DeedType,
    LandUnit,
    Party,
    LocationDetails,
    LandDetails,
    SCHEMA_VERSION
)
from tools.annotation_workbench import load_queue_index, get_annotated_doc_ids

def test_deed_schema_null_safety():
    """Verify missing fields default to None rather than being hallucinated."""
    schema = DeedExtractionSchema(doc_id="TEST_DOC_999")
    d = schema.to_canonical_dict()
    
    assert d["schema_version"] == SCHEMA_VERSION
    assert d["doc_id"] == "TEST_DOC_999"
    assert d["deed_number"] is None
    assert d["deed_year"] is None
    assert d["deed_type"] == "UNKNOWN"
    assert d["deed_value_bdt"] is None
    assert d["sellers"] == []
    assert d["buyers"] == []
    assert d["location"]["mouza"] is None
    assert d["land_details"]["dag_numbers"] == []
    assert d["land_details"]["land_area"] is None

def test_deed_schema_complete_valid():
    """Verify complete realistic record passes validation."""
    schema = DeedExtractionSchema(
        doc_id="TEST_DOC_001",
        deed_number="২০৭৮",
        deed_year=2001,
        deed_type=DeedType.SAF_KABALA,
        deed_value_bdt=450000.0,
        stamp_duty_bdt=1500.0,
        registration_date="28/10/2001",
        location=LocationDetails(
            mouza="বারেন্ডা",
            jl_number="১০৫",
            union="কাশিমপুর",
            upazila="গাজীপুর সদর",
            district="গাজীপুর"
        ),
        land_details=LandDetails(
            dag_numbers=["১২৪", "১২৫"],
            khatian_numbers=["৭৮"],
            land_area=33.5,
            land_unit=LandUnit.SHOTOK,
            ownership_share=1.0,
            sixteen_ana_share="১৬ আনা"
        ),
        sellers=[Party(name="মোসাঃ সালেহা খাতুন", father_or_husband="মৃত হাজী আবদুল গণি")],
        buyers=[Party(name="মোসাঃ মাজেদা বেগম", father_or_husband="মোঃ ইউনুস আলী")]
    )
    d = schema.to_canonical_dict()
    assert d["deed_number"] == "২০৭৮"
    assert d["location"]["mouza"] == "বারেন্ডা"
    assert len(d["land_details"]["dag_numbers"]) == 2
    assert d["land_details"]["land_area"] == 33.5

def test_curation_queue_loaded():
    """Verify the curated queue has at least 20 prepared deeds."""
    docs = load_queue_index()
    assert len(docs) >= 20, f"Expected >= 20 docs in queue, found {len(docs)}"
    first_doc = docs[0]
    assert "doc_id" in first_doc
    assert "preview_path" in first_doc
    assert "crop_fields" in first_doc
    assert len(first_doc["crop_fields"]) == 8

def test_annotation_persistence(tmp_path):
    """Test writing and reading from a jsonl file."""
    test_jsonl = tmp_path / "test_annotations.jsonl"
    record = {
        "doc_id": "TEST_ANNOTATE_DOC",
        "annotator_id": "TESTER",
        "verified": True,
        "deed_number": "১২৩৪"
    }
    with open(test_jsonl, "w", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        
    with open(test_jsonl, "r", encoding="utf-8") as f:
        loaded = json.loads(f.readline())
        
    assert loaded["doc_id"] == "TEST_ANNOTATE_DOC"
    assert loaded["verified"] is True
    assert loaded["deed_number"] == "১২৩৪"

def test_seed_dataset_integrity():
    """Verify seed dataset has exactly 30 records, all tagged as synthetic."""
    seed_file = BASE_DIR / "research" / "datasets" / "annotations" / "deed_extraction_seed.jsonl"
    assert seed_file.exists(), f"Seed file not found: {seed_file}"
    
    count = 0
    with open(seed_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                assert item["source_type"] == "synthetic_bangla_deed_template"
                assert "doc_id" in item
                assert "schema_version" in item
                count += 1
    assert count == 30, f"Expected 30 seed records, found {count}"
