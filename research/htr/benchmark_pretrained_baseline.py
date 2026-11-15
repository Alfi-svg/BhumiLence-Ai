"""
Benchmark Real Pretrained Bengali OCR/HTR Baseline on BN-HTRd Test Split and Real Dolil Line Crops.
Uses:
- EasyOCR Bengali model (cached locally in models/htr/pretrained_baseline/)
- jiwer for exact Character Error Rate (CER) and Word Error Rate (WER) computation.
"""
import os
import sys
import time
import json
from pathlib import Path
import jiwer
import easyocr
import cv2

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = str(WORKSPACE_ROOT / "models" / "htr" / "pretrained_baseline")
USER_NET_DIR = str(WORKSPACE_ROOT / "models" / "htr" / "pretrained_baseline" / "user_network")

def load_easyocr_reader():
    print(f"Loading EasyOCR reader from local model directory: {MODEL_DIR}")
    reader = easyocr.Reader(
        ["bn", "en"],
        model_storage_directory=MODEL_DIR,
        user_network_directory=USER_NET_DIR,
        download_enabled=False,
        gpu=False
    )
    return reader

def run_benchmark():
    print("=" * 75)
    print("  BHUMILENS AI — PRETRAINED BENGALI OCR/HTR BASELINE BENCHMARK")
    print("=" * 75)

    reader = load_easyocr_reader()

    # 1. Benchmark on 50 held-out samples from test.jsonl
    test_split_path = WORKSPACE_ROOT / "research" / "datasets" / "splits" / "bn_htrd" / "test.jsonl"
    if not test_split_path.exists():
        print(f"Error: {test_split_path} not found.")
        return

    test_samples = []
    with open(test_split_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                test_samples.append(json.loads(line))

    # Select 50 test samples (prefer LINE level, fallback to WORD level)
    line_samples = [s for s in test_samples if s.get("level") == "LINE"]
    word_samples = [s for s in test_samples if s.get("level") == "WORD"]
    eval_samples = (line_samples + word_samples)[:50]

    print(f"\nEvaluating on {len(eval_samples)} held-out BN-HTRd test samples...")

    references = []
    hypotheses = []
    sample_records = []
    latencies = []

    for i, s in enumerate(eval_samples, start=1):
        rel_img_path = s["image_path"]
        full_img_p = WORKSPACE_ROOT / rel_img_path
        gt_text = s["ground_truth_text"].strip()

        if not full_img_p.exists():
            continue

        t0 = time.perf_counter()
        # Run recognition
        results = reader.readtext(str(full_img_p), detail=1)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)

        pred_tokens = [r[1] for r in results]
        confidences = [float(r[2]) for r in results]
        pred_text = " ".join(pred_tokens).strip()
        avg_conf = float(sum(confidences) / len(confidences)) if confidences else 0.0

        # jiwer needs non-empty strings
        ref_clean = gt_text if gt_text else "empty"
        hyp_clean = pred_text if pred_text else "empty"

        references.append(ref_clean)
        hypotheses.append(hyp_clean)

        sample_cer = float(jiwer.cer(ref_clean, hyp_clean))
        sample_wer = float(jiwer.wer(ref_clean, hyp_clean))

        sample_records.append({
            "sample_id": s.get("sample_id"),
            "level": s.get("level"),
            "ground_truth": ref_clean,
            "prediction": pred_text,
            "confidence": round(avg_conf, 3),
            "cer": round(sample_cer, 4),
            "wer": round(sample_wer, 4),
            "latency_ms": round(elapsed_ms, 2)
        })

        if i <= 8:
            print(f"[{i:02d}] GT:   {ref_clean[:45]}")
            print(f"     PRED: {pred_text[:45]} | Conf: {avg_conf:.2f} | CER: {sample_cer:.2f} | {elapsed_ms:.1f}ms\n")

    overall_cer = float(jiwer.cer(references, hypotheses))
    overall_wer = float(jiwer.wer(references, hypotheses))
    avg_latency = float(sum(latencies) / len(latencies)) if latencies else 0.0

    print("-" * 75)
    print(f"Overall Evaluation Metrics across {len(references)} Test Samples:")
    print(f"  -> Character Error Rate (CER): {overall_cer * 100:.2f}% (CER = {overall_cer:.4f})")
    print(f"  -> Word Error Rate (WER):      {overall_wer * 100:.2f}% (WER = {overall_wer:.4f})")
    print(f"  -> Average Latency:            {avg_latency:.2f} ms per crop")
    print("-" * 75)

    # 2. Qualitative evaluation on Real Dolil Line Crops (Phase 4 outputs)
    dolil_crop_dir = WORKSPACE_ROOT / "outputs" / "evidence" / "DOLIL_AUTHENTIC_1" / "crops"
    if not dolil_crop_dir.exists():
        dolil_crop_dir = WORKSPACE_ROOT / "outputs" / "evidence" / "DOLIL_SAMPLE" / "crops"

    dolil_results = []
    if dolil_crop_dir.exists():
        dolil_lines = sorted(list(dolil_crop_dir.glob("line_*.png")))[:8]
        print(f"\nQualitative Recognition on {len(dolil_lines)} Real Dolil Line Crops ({dolil_crop_dir.parent.name}):")
        print(f"{'Crop File':<16} | {'Recognized Text':<40} | {'Conf':<6} | {'Latency (ms)'}")
        print("-" * 75)

        for crop_p in dolil_lines:
            t0 = time.perf_counter()
            res = reader.readtext(str(crop_p), detail=1)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            pred_tokens = [r[1] for r in res]
            confs = [float(r[2]) for r in res]
            text = " ".join(pred_tokens).strip()
            conf = float(sum(confs) / len(confs)) if confs else 0.0

            print(f"{crop_p.name:<16} | {text[:38]:<40} | {conf:<6.2f} | {elapsed_ms:.1f}")
            dolil_results.append({
                "line_crop": crop_p.name,
                "crop_path": str(crop_p),
                "recognized_text": text,
                "confidence": round(conf, 3),
                "latency_ms": round(elapsed_ms, 2)
            })
        print("-" * 75)

    # Save benchmark results
    out_json = WORKSPACE_ROOT / "research" / "htr" / "pretrained_baseline_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "engine": "EasyOCR Pretrained Bengali Baseline (CRAFT + ResNet-BiLSTM-CTC)",
            "test_sample_count": len(references),
            "overall_cer": round(overall_cer, 4),
            "overall_wer": round(overall_wer, 4),
            "average_latency_ms": round(avg_latency, 2),
            "samples": sample_records,
            "dolil_qualitative_eval": dolil_results
        }, f, indent=2, ensure_ascii=False)
    print(f"\nPretrained baseline benchmark written to: {out_json}")
    print("=" * 75)

if __name__ == "__main__":
    run_benchmark()
