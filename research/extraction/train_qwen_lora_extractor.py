"""
BhumiLens AI — Controlled LoRA Fine-Tuning Experiment for Qwen3-0.6B on Land Deed Extraction.

This script:
1. Loads Qwen3-0.6B base model.
2. Applies parameter-efficient fine-tuning (PEFT / LoRA) on target attention projections (q_proj, v_proj).
3. Trains on the seed training split (20 deed extraction instances) using Apple Silicon MPS.
4. Saves the trained LoRA adapter to models/extractor/qwen3-0.6b-deed-lora/.
5. Evaluates the fine-tuned model on the 10 held-out test instances.
6. Exports comparative evaluation metrics to research/extraction/qwen3_lora_evaluation_results.json.
"""
import os
import sys
import time
import json
import re
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any

import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model, TaskType, PeftModel

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
BASE_MODEL_DIR = WORKSPACE_ROOT / "models" / "extractor" / "qwen3-0.6b-base"
LORA_ADAPTER_DIR = WORKSPACE_ROOT / "models" / "extractor" / "qwen3-0.6b-deed-lora"
SEED_DATA_PATH = WORKSPACE_ROOT / "research" / "datasets" / "annotations" / "deed_extraction_seed.jsonl"
EVAL_RESULTS_PATH = WORKSPACE_ROOT / "research" / "extraction" / "qwen3_lora_evaluation_results.json"

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

def extract_target_json(sample: dict) -> dict:
    """Constructs the canonical ground-truth JSON for the given seed sample."""
    loc = sample.get("location", {})
    land = sample.get("land_details", {})
    return {
        "deed_number": sample.get("deed_number"),
        "deed_type": sample.get("deed_type"),
        "registration_date": sample.get("registration_date"),
        "deed_value_bdt": sample.get("deed_value_bdt"),
        "mouza": loc.get("mouza"),
        "upazila": loc.get("upazila"),
        "district": loc.get("district"),
        "dag_numbers": land.get("dag_numbers", []),
        "khatian_numbers": land.get("khatian_numbers", []),
        "land_area": land.get("land_area"),
        "land_unit": land.get("land_unit")
    }

def extract_json_from_response(text: str) -> Optional[dict]:
    """Robustly extracts JSON from model output."""
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
    """Checks whether non-null string or numerical values were invented."""
    hallucination_count = 0
    en_to_bn = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
    bn_to_en = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

    for field in ["deed_number", "mouza", "upazila", "district"]:
        val = pred_json.get(field)
        if val and isinstance(val, str) and val.lower() != "null":
            val_en = val.translate(bn_to_en)
            val_bn = val.translate(en_to_bn)
            if (val not in input_text) and (val_en not in input_text) and (val_bn not in input_text):
                hallucination_count += 1

    dags = pred_json.get("dag_numbers", [])
    if isinstance(dags, list):
        for d in dags:
            d_str = str(d)
            d_en = d_str.translate(bn_to_en)
            d_bn = d_str.translate(en_to_bn)
            if (d_str not in input_text) and (d_en not in input_text) and (d_bn not in input_text):
                hallucination_count += 1

    return hallucination_count

def train_and_evaluate():
    print("=" * 75)
    print("  BHUMILENS AI — QWEN3-0.6B CONTROLLED LoRA FINE-TUNING & EVALUATION")
    print("=" * 75)

    stat = shutil.disk_usage(WORKSPACE_ROOT)
    free_gib = stat.free / (1024 ** 3)
    print(f"Free disk space: {free_gib:.2f} GiB")

    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Compute Device: {device}")

    # 1. Load Seed Data
    with open(SEED_DATA_PATH, "r", encoding="utf-8") as f:
        all_samples = [json.loads(line) for line in f if line.strip()]

    train_samples = all_samples[:20]
    test_samples = all_samples[20:30]
    print(f"Loaded {len(all_samples)} total instances: {len(train_samples)} Train, {len(test_samples)} Held-out Test.")

    # 2. Load Base Model and Tokenizer
    model_name = "Qwen/Qwen3-0.6B"
    print(f"Loading Tokenizer & Base Model '{model_name}' from local cache: {BASE_MODEL_DIR}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=str(BASE_MODEL_DIR), local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load in float32 for training stability on MPS
    base_model = AutoModelForCausalLM.from_pretrained(
        model_name,
        cache_dir=str(BASE_MODEL_DIR),
        local_files_only=True,
        torch_dtype=torch.float32
    ).to(device)

    # 3. Setup LoRA
    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM
    )
    model = get_peft_model(base_model, lora_config)
    trainable_params, all_params = model.get_nb_trainable_parameters()
    trainable_pct = 100 * trainable_params / all_params
    print(f"PEFT LoRA Configured: {trainable_params:,} trainable params / {all_params:,} total ({trainable_pct:.2f}% trainable)")

    # 4. Prepare Training Tensors
    training_data = []
    for sample in train_samples:
        ocr_text = sample["provenance"].get("normalized_ocr_text") or sample["provenance"].get("raw_ocr_text")
        target_dict = extract_target_json(sample)
        target_json_str = json.dumps(target_dict, ensure_ascii=False, indent=2)

        prompt_messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"দলিলের টেক্সট:\n{ocr_text}\n\nউপরে উল্লিখিত দলিলের টেক্সট থেকে নির্ধারিত স্কিমা অনুযায়ী তথ্য এক্সট্র্যাক্ট করে JSON ফরম্যাটে আউটপুট দাও:"}
        ]
        prompt_str = tokenizer.apply_chat_template(prompt_messages, tokenize=False, add_generation_prompt=True)
        # Append target JSON and EOS token
        full_str = prompt_str + target_json_str + tokenizer.eos_token

        prompt_ids = tokenizer.encode(prompt_str, add_special_tokens=False)
        full_ids = tokenizer.encode(full_str, add_special_tokens=False)

        input_ids = torch.tensor(full_ids, dtype=torch.long)
        # Mask out prompt tokens so loss is only computed on target JSON tokens
        labels = torch.tensor(full_ids, dtype=torch.long)
        labels[:len(prompt_ids)] = -100

        training_data.append({"input_ids": input_ids, "labels": labels})

    print(f"Prepared {len(training_data)} training prompt-target token pairs.")

    # 5. Training Loop
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=0.01)
    num_epochs = 3
    grad_accum_steps = 2
    model.train()

    print(f"\nStarting LoRA Fine-Tuning ({num_epochs} Epochs, Grad Accum: {grad_accum_steps}, LR: 2e-4)...", flush=True)
    t_start = time.perf_counter()

    for epoch in range(1, num_epochs + 1):
        epoch_loss = 0.0
        optimizer.zero_grad()

        for step_idx, item in enumerate(training_data):
            inp = item["input_ids"].unsqueeze(0).to(device)
            lbl = item["labels"].unsqueeze(0).to(device)

            outputs = model(input_ids=inp, labels=lbl)
            loss = outputs.loss / grad_accum_steps
            loss.backward()

            epoch_loss += outputs.loss.item()

            if (step_idx + 1) % grad_accum_steps == 0 or (step_idx + 1) == len(training_data):
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                optimizer.zero_grad()

        avg_epoch_loss = epoch_loss / len(training_data)
        print(f"  [Epoch {epoch}/{num_epochs}] Training Loss: {avg_epoch_loss:.4f}", flush=True)

    total_train_time = time.perf_counter() - t_start
    print(f"LoRA fine-tuning completed in {total_train_time:.2f} seconds.", flush=True)

    # Clean MPS cache
    if device.type == "mps":
        torch.mps.empty_cache()

    # 6. Save LoRA Adapter
    LORA_ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Saving fine-tuned LoRA adapter to: {LORA_ADAPTER_DIR}...", flush=True)
    model.save_pretrained(str(LORA_ADAPTER_DIR))
    tokenizer.save_pretrained(str(LORA_ADAPTER_DIR))
    print("Adapter successfully saved.", flush=True)

    # 7. Evaluate Fine-Tuned Model on Held-Out Test Split
    print(f"\nEvaluating fine-tuned LoRA model on {len(test_samples)} held-out test instances...", flush=True)
    model.eval()

    valid_json_count = 0
    total_field_checks = 0
    correct_field_checks = 0
    total_null_ground_truths = 0
    correct_null_outputs = 0
    total_hallucinations = 0
    latencies = []
    test_eval_records = []

    for idx, sample in enumerate(test_samples, start=1):
        doc_id = sample.get("doc_id", f"SEED_DOLIL_{idx+20:03d}")
        input_ocr = sample["provenance"].get("normalized_ocr_text") or sample["provenance"].get("raw_ocr_text")

        gt_deed_no = sample.get("deed_number")
        gt_type = sample.get("deed_type")
        gt_mouza = sample["location"].get("mouza")
        gt_area = sample["land_details"].get("land_area")

        user_content = f"দলিলের টেক্সট:\n{input_ocr}\n\nউপরে উল্লিখিত দলিলের টেক্সট থেকে নির্ধারিত স্কিমা অনুযায়ী তথ্য এক্সট্র্যাক্ট করে JSON ফরম্যাটে আউটপুট দাও:"
        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]
        prompt_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt_text, return_tensors="pt").to(device)

        t0 = time.perf_counter()
        with torch.inference_mode():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id
            )
        elapsed_s = time.perf_counter() - t0
        latencies.append(elapsed_s)

        response_text = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
        parsed_json = extract_json_from_response(response_text)
        is_valid_json = parsed_json is not None

        h_count = 0
        if is_valid_json:
            valid_json_count += 1
            h_count = check_hallucinations(parsed_json, input_ocr)
            total_hallucinations += h_count

            # Field check: deed_type
            total_field_checks += 1
            if parsed_json.get("deed_type") == gt_type:
                correct_field_checks += 1

            # Field check: mouza
            total_field_checks += 1
            if parsed_json.get("mouza") == gt_mouza:
                correct_field_checks += 1

            # Field check: land_area
            total_field_checks += 1
            p_area = parsed_json.get("land_area")
            if (p_area is None and gt_area is None) or (p_area is not None and gt_area is not None and abs(float(p_area) - float(gt_area)) < 1e-3):
                correct_field_checks += 1

            # Null check: fields not in input text (e.g. upazila, district if null in prompt)
            for null_field in ["upazila", "district", "registration_date"]:
                gt_val = sample.get("location", {}).get(null_field) if null_field in ["upazila", "district"] else sample.get(null_field)
                if null_field not in input_ocr:
                    total_null_ground_truths += 1
                    if parsed_json.get(null_field) is None:
                        correct_null_outputs += 1

        print(f"[{idx:02d}] {doc_id:<16} | Latency: {elapsed_s:.2f}s | Valid JSON: {is_valid_json} | Hallucinations: {h_count}", flush=True)
        test_eval_records.append({
            "doc_id": doc_id,
            "latency_seconds": round(elapsed_s, 2),
            "is_valid_json": is_valid_json,
            "hallucination_count": h_count,
            "raw_response": response_text[:250],
            "parsed_json": parsed_json
        })

    # 8. Summary Metrics
    json_valid_rate = 100.0 * valid_json_count / len(test_samples) if test_samples else 0.0
    field_acc = 100.0 * correct_field_checks / total_field_checks if total_field_checks else 0.0
    null_prec = 100.0 * correct_null_outputs / total_null_ground_truths if total_null_ground_truths else 0.0
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

    print("-" * 75)
    print("FINE-TUNED LoRA QWEN3-0.6B EVALUATION SUMMARY:")
    print(f"  -> JSON Validity Rate:           {json_valid_rate:.1f}%")
    print(f"  -> Exact Field Accuracy:         {field_acc:.1f}%")
    print(f"  -> Null / Missing-Field Prec.:   {null_prec:.1f}%")
    print(f"  -> Hallucination Metric:         {total_hallucinations} invented value(s)")
    print(f"  -> Average Inference Latency:    {avg_lat:.2f} seconds per document")
    print("-" * 75)

    # Save results
    eval_results = {
        "model": "Qwen/Qwen3-0.6B + LoRA (r=8, alpha=16)",
        "base_model": "Qwen/Qwen3-0.6B",
        "adapter_dir": str(LORA_ADAPTER_DIR),
        "device": str(device),
        "training_epochs": num_epochs,
        "trainable_parameters": trainable_params,
        "trainable_parameters_pct": trainable_pct,
        "training_time_seconds": round(total_train_time, 2),
        "samples_evaluated": len(test_samples),
        "json_validity_rate_pct": json_valid_rate,
        "exact_field_accuracy_pct": field_acc,
        "null_precision_pct": null_prec,
        "total_hallucinations": total_hallucinations,
        "average_latency_seconds": round(avg_lat, 2),
        "sample_records": test_eval_records
    }

    with open(EVAL_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(eval_results, f, indent=2, ensure_ascii=False)
    print(f"Results written to: {EVAL_RESULTS_PATH}")
    print("=" * 75)

if __name__ == "__main__":
    train_and_evaluate()
