import os
import sys
import time
import json
from pathlib import Path
import cv2
import numpy as np

# Ensure root directory is on python path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from src.vision_pipeline import BhumiVisionPipeline

def compute_rms_contrast(gray_img: np.ndarray) -> float:
    return float(np.std(gray_img))

def compute_blur_laplacian_var(gray_img: np.ndarray) -> float:
    return float(cv2.Laplacian(gray_img, cv2.CV_64F).var())

def main():
    print("=" * 70)
    print("  BHUMILENS AI — PHASE 4: VISION PIPELINE BASELINE BENCHMARK")
    print("=" * 70)

    # 1. Gather 10 diverse sample images
    image_paths = []
    
    # Baseline sample data
    sample_dolil = WORKSPACE_ROOT / "sample_data" / "sample_dolil_100_anonymized.jpg"
    sample_khatian = WORKSPACE_ROOT / "sample_data" / "sample_khatian_synthetic.png"
    if sample_dolil.exists():
        image_paths.append(("SAMPLE_DOLIL_100", sample_dolil))
    if sample_khatian.exists():
        image_paths.append(("SAMPLE_KHATIAN_SYN", sample_khatian))
        
    # Queue samples
    queue_dir = WORKSPACE_ROOT / "research" / "datasets" / "processed" / "dolil_curation_queue"
    candidate_folders = [
        "DOLIL_MND_DOLIL_1",
        "DOLIL_MND_DOLIL_10",
        "DOLIL_MND_DOLIL_100",
        "DOLIL_MND_DOLIL_105",
        "DOLIL_MND_DOLIL_110",
        "DOLIL_MND_DOLIL_115",
        "DOLIL_MND_DOLIL_118",
        "DOLIL_MND_DOLIL_120"
    ]
    for folder in candidate_folders:
        img_p = queue_dir / folder / "preview.jpg"
        if img_p.exists():
            image_paths.append((folder, img_p))

    print(f"Selected {len(image_paths)} benchmark sample images.\n")

    pipeline = BhumiVisionPipeline(output_dir=str(WORKSPACE_ROOT / "outputs" / "benchmark_crops"))
    benchmark_records = []
    total_time_ms = 0.0

    print(f"{'Doc ID':<22} | {'Dims (WxH)':<11} | {'Latency (ms)':<12} | {'Raw RMS':<8} | {'Norm RMS':<8} | {'Blur Var':<9} | {'Layout':<22} | {'Seal'}")
    print("-" * 115)

    for doc_name, path in image_paths:
        img_bgr = cv2.imread(str(path))
        if img_bgr is None:
            print(f"Warning: could not read {path}")
            continue
            
        h, w = img_bgr.shape[:2]
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        raw_rms = compute_rms_contrast(gray)
        blur_var = compute_blur_laplacian_var(gray)

        t0 = time.perf_counter()
        result = pipeline.process_document(str(path), doc_id=doc_name)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        total_time_ms += elapsed_ms

        # Read normalized image to compute contrast improvement
        norm_img_path = result["preprocessed_paths"]["shadow_removed"]
        norm_gray = cv2.imread(norm_img_path, cv2.IMREAD_GRAYSCALE)
        norm_rms = compute_rms_contrast(norm_gray) if norm_gray is not None else raw_rms

        layout = result["layout_classification"]["detected_type"]
        seal_detected = result["seal_metadata"]["official_seal_detected"]

        print(f"{doc_name:<22} | {w}x{h:<6} | {elapsed_ms:<12.2f} | {raw_rms:<8.2f} | {norm_rms:<8.2f} | {blur_var:<9.1f} | {layout:<22} | {seal_detected}")

        benchmark_records.append({
            "doc_id": doc_name,
            "width": w,
            "height": h,
            "latency_ms": round(elapsed_ms, 2),
            "raw_rms_contrast": round(raw_rms, 2),
            "normalized_rms_contrast": round(norm_rms, 2),
            "contrast_improvement_factor": round(norm_rms / max(1e-5, raw_rms), 2),
            "laplacian_blur_variance": round(blur_var, 2),
            "layout_detected": layout,
            "grid_intersections": result["layout_classification"].get("grid_intersections", 0),
            "seal_detected": seal_detected,
            "crop_count": len(result.get("field_crops", {}))
        })

    avg_latency = total_time_ms / len(benchmark_records) if benchmark_records else 0
    print("-" * 115)
    print(f"Average processing latency: {avg_latency:.2f} ms per page across {len(benchmark_records)} images.")
    print("=" * 70)

    out_json = WORKSPACE_ROOT / "research" / "experiments" / "benchmark_baseline_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "image_count": len(benchmark_records),
            "average_latency_ms": round(avg_latency, 2),
            "records": benchmark_records
        }, f, indent=2, ensure_ascii=False)
    print(f"Results written to: {out_json}")

if __name__ == "__main__":
    main()
