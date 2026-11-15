"""
Evaluation and Benchmarking of Qwen3-0.6B for Structured Land Document Extraction.
Measures:
1. JSON Validity Rate (%)
2. Exact Field Extraction Accuracy (%)
3. Null / Missing-Field Precision (%)
4. Hallucination Rate (%)
5. Inference Latency per document (seconds) on Apple Silicon M2 MPS.
"""
import os
import sys
import time
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
import shutil
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_NAME = "Qwen/Qwen3-0.6B"
LOCAL_MODEL_DIR = WORKSPACE_ROOT / "models" / "extractor" / "qwen3-0.6b-base"

EXTRACTION_SYSTEM_PROMPT = """You are an expert GovTech Land Document Extraction Assistant for Bangladeshi Land Deeds.
Given raw or normalized Bangla OCR text from a deed, extract the structured information in pure JSON format matching this schema:
{
  "deed_number": string or null,
  "deed_type": "SAF_KABALA" | "BAYNAPATRA" | "BONTONAMA" | "HEBA" | "KHATIAN" | null,
  "registration_date": string or null,
  "deed_value_bdt": number or null,
  "mouza": string or null,
  "upazila": string or null,
  "district": string or null,
  "dag_numbers": list of strings,
  "khatian_numbers": list of strings,
  "land_area": number or null,
  "land_unit": "SHOTOK" | "KATHA" | "BIGHA" | "ACRE" | null
}

STRICT GROUNDING RULES:
1. Only extract information explicitly mentioned in the input text.
2. If any field is missing, not mentioned, or unreadable, you MUST set it to null.
3. NEVER hallucinate or invent deed numbers, mouzas, dag numbers, or land areas.
4. Output ONLY the JSON object. Do not include markdown commentary."""

def extract_json_from_response(text: str) -> Optional[dict]:
    """Robustly extracts JSON from LLM response text."""
    # Look for code block or first '{' to last '}'
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    return None

def check_hallucinations(pred_json: dict, input_text: str) -> int:
    """Checks whether non-null string or numerical values were invented out of thin air."""
    hallucination_count = 0
    en_to_bn = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
    bn_to_en = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

    # Check key text fields
    for field in ["deed_number", "mouza", "upazila", "district"]:
        val = pred_json.get(field)
        if val and isinstance(val, str) and val.lower() != "null":
            # Check if any part of val appears in input
            val_en = val.translate(bn_to_en)
            val_bn = val.translate(en_to_bn)
            if (val not in input_text) and (val_en not in input_text) and (val_bn not in input_text):
                hallucination_count += 1

    # Check dag numbers
    dags = pred_json.get("dag_numbers", [])
    if isinstance(dags, list):
        for d in dags:
            d_str = str(d)
            d_en = d_str.translate(bn_to_en)
            d_bn = d_str.translate(en_to_bn)
            if (d_str not in input_text) and (d_en not in input_text) and (d_bn not in input_text):
                hallucination_count += 1

    return hallucination_count

def run_evaluation():
    print("=" * 75)
    print("  BHUMILENS AI — QWEN3-0.6B LAND INFORMATION EXTRACTOR BENCHMARK")
    print("=" * 75)

    # Check disk space
    stat = shutil.disk_usage(WORKSPACE_ROOT)
    free_gib_before = stat.free / (1024 ** 3)
    print(f"Free disk space before loading: {free_gib_before:.2f} GiB")

    LOCAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Compute Device: {device} | Target Model: {MODEL_NAME}")

    print(f"Loading/Caching model locally at: {LOCAL_MODEL_DIR}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, cache_dir=str(LOCAL_MODEL_DIR))
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float16 if device.type == "mps" else torch.float32,
        cache_dir=str(LOCAL_MODEL_DIR)
    ).to(device)
    model.eval()

    stat_after = shutil.disk_usage(WORKSPACE_ROOT)
    free_gib_after = stat_after.free / (1024 ** 3)
    print(f"Free disk space after loading:  {free_gib_after:.2f} GiB (Delta: -{free_gib_before - free_gib_after:.2f} GiB)\n")

    # Load held-out test samples from seed dataset (last 10 samples)
    seed_file = WORKSPACE_ROOT / "research" / "datasets" / "annotations" / "deed_extraction_seed.jsonl"
    all_seeds = []
    with open(seed_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                all_seeds.append(json.loads(line))

    test_samples = all_seeds[20:30]
    print(f"Benchmarking on {len(test_samples)} held-out deed extraction instances...")

    valid_json_count = 0
    total_field_checks = 0
    correct_field_checks = 0
    total_null_ground_truths = 0
    correct_null_outputs = 0
    total_hallucinations = 0
    latencies = []
    sample_outputs = []

    for idx, sample in enumerate(test_samples, start=1):
        doc_id = sample.get("doc_id", f"SAMPLE_{idx}")
        input_ocr = sample["provenance"].get("normalized_ocr_text") or sample["provenance"].get("raw_ocr_text")

        # Ground truth values
        gt_deed_no = sample.get("deed_number")
        gt_type = sample.get("deed_type")
        gt_mouza = sample["location"].get("mouza")
        gt_upazila = sample["location"].get("upazila")
        gt_area = sample["land_details"].get("land_area")
        gt_dags = sample["land_details"].get("dag_numbers", [])

        user_content = f"দলিলের টেক্সট:\n{input_ocr}\n\nউপরে উল্লিখিত দলিলের টেক্সট থেকে নির্ধারিত স্কিমা অনুযায়ী তথ্য এক্সট্র্যাক্ট করে JSON ফরম্যাটে আউটপুট দাও:"
        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

        prompt_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt_text, return_tensors="pt").to(device)

        t0 = time.perf_counter()
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=350,
                temperature=0.1,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id
            )
        elapsed_s = time.perf_counter() - t0
        latencies.append(elapsed_s)

        response_text = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
        parsed_json = extract_json_from_response(response_text)

        is_valid_json = parsed_json is not None
        if is_valid_json:
            valid_json_count += 1
            h_count = check_hallucinations(parsed_json, input_ocr)
            total_hallucinations += h_count

            # Field checks
            # 1. Deed Type
            total_field_checks += 1
            if parsed_json.get("deed_type") == gt_type:
                correct_field_checks += 1

            # 2. Mouza
            total_field_checks += 1
            if parsed_json.get("mouza") == gt_mouza:
                correct_field_checks += 1

            # 3. Land Area
            total_field_checks += 1
            p_area = parsed_json.get("land_area")
            if (p_area is None and gt_area is None) or (p_area is not None and gt_area is not None and abs(float(p_area) - float(gt_area)) < 1e-3):
                correct_field_checks += 1

            # Check null precision for intentionally missing fields (e.g. dag numbers)
            total_null_ground_truths += 1
            if (not gt_dags) and (not parsed_json.get("dag_numbers")):
                correct_null_outputs += 1
        else:
            total_field_checks += 4
            total_null_ground_truths += 1

        print(f"[{idx:02d}] {doc_id:<16} | Latency: {elapsed_s:.2f}s | Valid JSON: {is_valid_json} | Hallucinations: {h_count if is_valid_json else 'N/A'}")

        sample_outputs.append({
            "doc_id": doc_id,
            "latency_seconds": round(elapsed_s, 2),
            "is_valid_json": is_valid_json,
            "raw_response": response_text[:200],
            "parsed_json": parsed_json
        })

    # Summary Metrics
    json_validity_rate = (valid_json_count / len(test_samples)) * 100
    field_acc_rate = (correct_field_checks / max(1, total_field_checks)) * 100
    null_precision = (correct_null_outputs / max(1, total_null_ground_truths)) * 100
    hallucination_rate = (total_hallucinations / max(1, len(test_samples))) * 100
    avg_latency_s = float(sum(latencies) / len(latencies)) if latencies else 0.0

    print("-" * 75)
    print("EVALUATION METRICS SUMMARY (Base Qwen3-0.6B on Apple M2 MPS):")
    print(f"  -> JSON Validity Rate:           {json_validity_rate:.1f}%")
    print(f"  -> Exact Field Accuracy:         {field_acc_rate:.1f}%")
    print(f"  -> Null / Missing-Field Prec.:   {null_precision:.1f}%")
    print(f"  -> Hallucination Metric:         {total_hallucinations} invented value(s) across {len(test_samples)} docs")
    print(f"  -> Average Inference Latency:    {avg_latency_s:.2f} seconds per document")
    print("-" * 75)

    # Save results
    out_json = WORKSPACE_ROOT / "research" / "extraction" / "qwen3_evaluation_results.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "model": MODEL_NAME,
            "device": str(device),
            "dtype": "float16",
            "samples_evaluated": len(test_samples),
            "json_validity_rate_pct": round(json_validity_rate, 2),
            "exact_field_accuracy_pct": round(field_acc_rate, 2),
            "null_precision_pct": round(null_precision, 2),
            "total_hallucinations": total_hallucinations,
            "average_latency_seconds": round(avg_latency_s, 2),
            "free_disk_space_after_gib": round(free_gib_after, 2),
            "sample_records": sample_outputs
        }, f, indent=2, ensure_ascii=False)

    print(f"Results written to: {out_json}")
    print("=" * 75)

if __name__ == "__main__":
    run_evaluation()
