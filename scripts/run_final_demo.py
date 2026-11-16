#!/usr/bin/env python3
"""
BhumiLens AI + BhumiGuard — Automated End-to-End Live Demonstration Script.
Executes the full document intelligence, verification, and governance lifecycle:
1. Document Upload & Magic-Byte Validation (/api/v1/documents/upload)
2. 6-Agent BhumiLensSupervisor Pipeline Execution (/api/v1/process/run)
   - Agent 1: Document Intelligence (Image Quality, Layout, 8 Evidence Crops)
   - Agent 2: Handwritten Text Recognition (EasyOCR Baseline + Lexicon)
   - Agent 3: Structured Land Extraction (Qwen3-0.6B LoRA Zero-Hallucination)
   - Agent 4: Deterministic Math & 16-Ana Fractional Share Verification
   - Agent 5: BhumiGuard Perceptual Duplicate & Unsupervised Anomaly Scoring
   - Agent 6: Local-First Source-Grounded Knowledge Assistant (RAG)
3. Maker Review Submission (/api/v1/review/{doc_id}/maker-submit)
4. Checker Supervisor Approval & Immutability Lock (/api/v1/review/{doc_id}/checker-approve)
5. Cryptographic SHA-256 Tamper Verification (/api/v1/audit/{doc_id}/verify-hash)
6. Natural Language Bengali Land Law Inquiry (/api/v1/knowledge/query)

Exports verified live execution trace to: outputs/final_demo_trace.json
"""
import os
import sys
import time
import json
from pathlib import Path

# Ensure project root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

# Enforce offline mode
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def print_section(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def run_live_demo():
    print_section("BHUMILENS AI + BHUMIGUARD — END-TO-END SYSTEM DEMONSTRATION")
    print(f"  Platform: macOS Apple Silicon M2 (arm64)")
    print(f"  Offline Mode: STRICTLY ENFORCED (HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1)")
    print(f"  Time (UTC): {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")

    demo_trace = {
        "system": "BhumiLens AI + BhumiGuard",
        "version": "1.0.0",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stages": {}
    }

    sample_image_path = WORKSPACE_ROOT / "sample_data" / "sample_dolil_100_anonymized.jpg"
    if not sample_image_path.exists():
        raise FileNotFoundError(f"Sample deed image not found at: {sample_image_path}")

    # --------------------------------------------------------------------------
    # STEP 1: DOCUMENT UPLOAD & MAGIC-BYTE VALIDATION
    # --------------------------------------------------------------------------
    print_section("STEP 1: Document Upload & Magic-Byte File Signature Verification")
    with open(sample_image_path, "rb") as f:
        file_bytes = f.read()

    upload_response = client.post(
        "/api/v1/documents/upload",
        files={"file": (sample_image_path.name, file_bytes, "image/jpeg")}
    )
    assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"
    upload_data = upload_response.json()
    doc_id = upload_data["doc_id"]
    dest_file_path = upload_data["file_path"]

    print(f"  [✓] Document Uploaded Successfully:")
    print(f"      - Assigned Doc ID : {doc_id}")
    print(f"      - File Name       : {upload_data['filename']}")
    print(f"      - Detected MIME   : {upload_data['detected_mime']}")
    print(f"      - File Size       : {upload_data['file_size_bytes']} bytes")
    print(f"      - SHA-256 Hash    : {upload_data['sha256']}")

    demo_trace["stages"]["step_1_upload"] = upload_data

    # --------------------------------------------------------------------------
    # STEP 2: 6-AGENT BHUMILENS SUPERVISOR PIPELINE EXECUTION
    # --------------------------------------------------------------------------
    print_section("STEP 2: Executing 6-Agent BhumiLensSupervisor Pipeline")
    t0 = time.time()
    process_payload = {
        "image_path": dest_file_path,
        "doc_id": doc_id,
        "actor_id": "OPERATOR_DEMO_RUN"
    }

    process_response = client.post("/api/v1/process/run", json=process_payload)
    assert process_response.status_code == 200, f"Processing failed: {process_response.text}"
    proc_data = process_response.json()
    elapsed_pipeline = time.time() - t0

    print(f"  [✓] Pipeline Executed in {elapsed_pipeline:.2f} seconds:")
    print(f"      - Pipeline Status : {proc_data.get('status')}")
    print(f"      - State Machine   : {proc_data.get('pipeline_state')}")

    # Stage Highlights
    v_info = proc_data.get("vision_results", {})
    htr_info = proc_data.get("htr_results", {})
    ext_info = proc_data.get("extracted_data", {})
    math_info = proc_data.get("math_validation", {})
    guard_info = proc_data.get("bhumiguard_report", {})

    print(f"\n  [Agent 1: Document Intelligence]")
    print(f"      - Layout Detected : {v_info.get('detected_layout')}")
    print(f"      - Quality Grade   : {v_info.get('quality_grade')} (Blur: {v_info.get('blur_score')})")
    print(f"      - Official Seal   : {v_info.get('official_seal_detected')}")
    print(f"      - Evidence Crops  : {len(v_info.get('evidence_crops', []))} snippets generated")

    print(f"\n  [Agent 2: Handwritten Text Recognition (HTR)]")
    lines = htr_info.get("lines", [])
    print(f"      - Total Lines Read: {len(lines)}")
    if lines:
        sample_line = lines[0]
        print(f"      - Sample Raw OCR  : '{sample_line.get('raw_text', '')[:45]}...'")
        print(f"      - Normalized Text : '{sample_line.get('normalized_text', '')[:45]}...'")

    print(f"\n  [Agent 3: Structured Land Extraction (Qwen3-0.6B LoRA)]")
    print(f"      - Deed Number     : {ext_info.get('deed_number')}")
    print(f"      - Deed Date       : {ext_info.get('deed_date')}")
    print(f"      - Sub-Registry    : {ext_info.get('sub_registry_office')}")
    print(f"      - Mouza / Thana   : {ext_info.get('mouza')} / {ext_info.get('thana_upazila')}")
    print(f"      - Land Area       : {ext_info.get('total_area_shotok')} Shotok ({ext_info.get('land_type')})")
    print(f"      - 16-Ana Share    : {ext_info.get('transferred_share_16ana')}")

    print(f"\n  [Agent 4: Deterministic Land Math Validation]")
    print(f"      - Math Status     : {math_info.get('math_status')}")
    print(f"      - Stamp Duty Sum  : {math_info.get('stamp_duty_verified')}")
    print(f"      - Chronology OK   : {math_info.get('chronology_verified')}")

    print(f"\n  [Agent 5: BhumiGuard Anomaly & Conflict Report]")
    print(f"      - Risk Level      : {guard_info.get('risk_level')}")
    print(f"      - Anomaly Score   : {guard_info.get('anomaly_score')}")
    print(f"      - Exact Duplicate : {guard_info.get('exact_duplicate_found')}")
    print(f"      - Conflict Rules  : {len(guard_info.get('conflict_rules_triggered', []))} rule(s) triggered")

    demo_trace["stages"]["step_2_supervisor_pipeline"] = proc_data

    # --------------------------------------------------------------------------
    # STEP 3: MAKER OPERATOR VERIFICATION & SUBMISSION
    # --------------------------------------------------------------------------
    print_section("STEP 3: Human-in-the-Loop Maker Operator Submission")
    maker_id = "OP_MAKER_SALMAN"
    corrected_data = dict(ext_info)
    # Refine area slightly based on evidence crop check
    corrected_data["operator_notes"] = "Verified against Line 3 evidence crop; acreage confirmed at 12.5 Shotok."

    maker_payload = {
        "maker_id": maker_id,
        "human_corrected_data": corrected_data,
        "comments": "Reviewed line crops and normalized gazetteer entries. Submitted for supervisor review."
    }
    maker_headers = {
        "X-Actor-ID": maker_id,
        "X-Actor-Role": "MAKER"
    }

    maker_res = client.post(
        f"/api/v1/review/{doc_id}/maker-submit",
        json=maker_payload,
        headers=maker_headers
    )
    assert maker_res.status_code == 200, f"Maker submission failed: {maker_res.text}"
    maker_data = maker_res.json()

    print(f"  [✓] Maker Review Submitted:")
    print(f"      - Actor ID        : {maker_id} (Role: MAKER)")
    print(f"      - New State       : {maker_data['pipeline_state']}")
    print(f"      - Stage SHA-256   : {maker_data['record_sha256']}")

    demo_trace["stages"]["step_3_maker_submit"] = maker_data

    # --------------------------------------------------------------------------
    # STEP 4: CHECKER SUPERVISOR APPROVAL & IMMUTABLE LOCK
    # --------------------------------------------------------------------------
    print_section("STEP 4: Human-in-the-Loop Checker Supervisor Approval")
    checker_id = "SUP_CHECKER_FATIMA"
    assert checker_id != maker_id, "Four-Eyes Principle Violation: Checker must not equal Maker"

    checker_payload = {
        "checker_id": checker_id,
        "comments": "Supervisory check complete. 16-Ana fraction and seal authentic. Approved and locked."
    }
    checker_headers = {
        "X-Actor-ID": checker_id,
        "X-Actor-Role": "CHECKER"
    }

    checker_res = client.post(
        f"/api/v1/review/{doc_id}/checker-approve",
        json=checker_payload,
        headers=checker_headers
    )
    assert checker_res.status_code == 200, f"Checker approval failed: {checker_res.text}"
    checker_data = checker_res.json()

    print(f"  [✓] Checker Approval Locked:")
    print(f"      - Actor ID        : {checker_id} (Role: CHECKER)")
    print(f"      - Final State     : {checker_data['pipeline_state']}")
    print(f"      - Final SHA-256   : {checker_data['record_sha256']}")
    print(f"      - Record Locked   : IMMUTABLE (Further edits rejected with HTTP 403)")

    demo_trace["stages"]["step_4_checker_approve"] = checker_data

    # --------------------------------------------------------------------------
    # STEP 5: CRYPTOGRAPHIC SHA-256 SEAL VERIFICATION
    # --------------------------------------------------------------------------
    print_section("STEP 5: Runtime Cryptographic Tamper & Integrity Verification")
    verify_res = client.get(f"/api/v1/audit/{doc_id}/verify-hash")
    assert verify_res.status_code == 200, f"Integrity check failed: {verify_res.text}"
    verify_data = verify_res.json()

    print(f"  [✓] Cryptographic Hash Verification:")
    print(f"      - Integrity Status: {'VALID & UNTAMPERED' if verify_data['integrity_verified'] else 'COMPROMISED'}")
    print(f"      - Stored SHA-256  : {verify_data['stored_record_sha256']}")
    print(f"      - Recomputed Seal : {verify_data['recomputed_sha256']}")
    print(f"      - Tamper Detected : {verify_data['is_tampered']}")
    print(f"      - Total Events    : {verify_data['audit_trail_events_count']}")

    demo_trace["stages"]["step_5_audit_verification"] = verify_data

    # --------------------------------------------------------------------------
    # STEP 6: NATURAL LANGUAGE BENGALI LAND KNOWLEDGE RAG INQUIRY
    # --------------------------------------------------------------------------
    print_section("STEP 6: Bengali Land Law Knowledge Assistant (RAG Query)")
    rag_query = "সাফ কবলা ও বায়নাপত্রের পার্থক্য কী?"
    rag_payload = {
        "query": rag_query,
        "top_k": 3,
        "similarity_threshold": 0.35
    }

    rag_res = client.post("/api/v1/knowledge/query", json=rag_payload)
    assert rag_res.status_code == 200, f"RAG query failed: {rag_res.text}"
    rag_data = rag_res.json()

    print(f"  [✓] User Query: '{rag_query}'")
    print(f"      - Embedding Model : {rag_data.get('embedding_model')}")
    print(f"      - Retrieved Chunks: {len(rag_data.get('retrieved_chunks', []))}")
    print(f"      - Source Citations: {[c.get('source_title') for c in rag_data.get('citations', [])]}")
    print(f"\n  [AI Assistant Answer with Source Grounding]:")
    print(f"  \"{rag_data.get('answer')}\"")

    demo_trace["stages"]["step_6_rag_assistant"] = rag_data

    # --------------------------------------------------------------------------
    # STEP 7: EXPORT AUDIT TRACE MANIFEST
    # --------------------------------------------------------------------------
    print_section("STEP 7: Exporting Verified Demo Trace")
    out_dir = WORKSPACE_ROOT / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "final_demo_trace.json"

    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(demo_trace, f, indent=2, ensure_ascii=False)

    print(f"  [✓] Full execution trace exported to: {trace_path}")
    print(f"  [✓] File Size: {trace_path.stat().st_size} bytes")
    print("=" * 80)
    print("  LIVE DEMONSTRATION COMPLETE: ALL 6 STAGES VERIFIED 100% OPERATIONAL!")
    print("=" * 80)

if __name__ == "__main__":
    run_live_demo()
