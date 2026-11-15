#!/usr/bin/env python3
"""
BhumiLens AI — Dataset Acquisition & Verification Engine
Downloads target Mendeley & Hugging Face datasets into research/datasets/raw/
with strict disk space monitoring (>25 GiB free required).
"""
import os
import sys
import time
import json
import shutil
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "research" / "datasets" / "raw"

DOLIL_DIR = RAW_DIR / "dolil"
BN_HTRD_DIR = RAW_DIR / "bn_htrd"
BLUGE_DIR = RAW_DIR / "bluge_ner"

MENDELEY_TARGETS = {
    "dolil": {
        "name": "Bangla Handwritten Dolil Dataset (653 Images)",
        "dataset_id": "yk3c3xy9vm",
        "version": "1",
        "url": "https://data.mendeley.com/public-api/zip/yk3c3xy9vm/download/1",
        "target_dir": DOLIL_DIR,
        "filename": "dolil_raw.zip"
    },
    "bn_htrd": {
        "name": "BN-HTRd V2 Document Level Offline Bangla HTR",
        "dataset_id": "743k6dm543",
        "version": "2",
        "url": "https://data.mendeley.com/public-api/zip/743k6dm543/download/2",
        "target_dir": BN_HTRD_DIR,
        "filename": "bn_htrd_raw.zip"
    }
}

def get_free_disk_space_gib(path="."):
    _, _, free = shutil.disk_usage(path)
    return round(free / (1024 ** 3), 2)

def download_file_stream(url, dest_path, min_free_gib=25.0):
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    free_gib = get_free_disk_space_gib(dest_path.parent)
    print(f"Checking disk space: {free_gib} GiB available (Minimum required: {min_free_gib} GiB)")
    if free_gib < min_free_gib:
        raise RuntimeError(f"ABORT: Free disk space ({free_gib} GiB) is below safe limit ({min_free_gib} GiB)!")

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dest = dest_path.with_suffix(".downloading")

    print(f"Connecting to: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Apple Silicon)"})
    
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as response, open(temp_dest, "wb") as out_file:
            total_bytes = int(response.headers.get("Content-Length", 0))
            total_mb = total_bytes / (1024 * 1024)
            print(f"Target size: {total_mb:.2f} MB ({total_bytes} bytes)")
            
            # Check if downloading will drop below safe disk space
            needed_gib = total_bytes / (1024 ** 3)
            if (free_gib - needed_gib) < min_free_gib:
                raise RuntimeError(f"ABORT: Downloading {total_mb:.1f} MB will drop free disk ({free_gib} GiB) below {min_free_gib} GiB limit!")

            downloaded = 0
            chunk_size = 1024 * 1024  # 1 MB chunks
            last_print = t0

            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                
                now = time.time()
                if now - last_print > 3.0:
                    pct = (downloaded / total_bytes * 100) if total_bytes else 0
                    elapsed = now - t0
                    speed_mbps = (downloaded / (1024 * 1024)) / max(elapsed, 0.001)
                    print(f"  -> {downloaded / (1024*1024):.1f}/{total_mb:.1f} MB ({pct:.1f}%) | Speed: {speed_mbps:.2f} MB/s")
                    last_print = now

        temp_dest.rename(dest_path)
        elapsed_sec = round(time.time() - t0, 1)
        print(f"Download complete: {dest_path.name} in {elapsed_sec}s")
        return {
            "status": "SUCCESS",
            "file_path": str(dest_path),
            "size_bytes": dest_path.stat().st_size,
            "elapsed_seconds": elapsed_sec
        }
    except Exception as e:
        if temp_dest.exists():
            temp_dest.unlink()
        print(f"Download failed for {url}: {e}")
        return {
            "status": "FAILED",
            "error": str(e),
            "url": url
        }

def acquire_bluge_ner_sample():
    print("\n--- Acquiring BLUGE NER Sample ---")
    BLUGE_DIR.mkdir(parents=True, exist_ok=True)
    out_file = BLUGE_DIR / "bluge_sample.json"
    
    try:
        from datasets import load_dataset
        ds = load_dataset("nahid-hub/BLUGE-bengali-ner", split="train[:100]")
        sample_records = [
            {"id": idx, "tokens": row["tokens"], "ner_tags": row["ner_tags"]}
            for idx, row in enumerate(ds)
        ]
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump({
                "dataset": "nahid-hub/BLUGE-bengali-ner",
                "sample_count": len(sample_records),
                "features": str(ds.features),
                "samples": sample_records
            }, f, ensure_ascii=False, indent=2)
        print(f"BLUGE NER sample saved: {out_file} ({len(sample_records)} sentences)")
        return {"status": "SUCCESS", "count": len(sample_records), "path": str(out_file)}
    except Exception as e:
        print(f"BLUGE NER acquisition error: {e}")
        return {"status": "FAILED", "error": str(e)}

def run_acquisition():
    print("=" * 72)
    print("  BHUMILENS AI — PHASE 2 DATASET ACQUISITION ENGINE")
    print("=" * 72)
    
    initial_free = get_free_disk_space_gib(BASE_DIR)
    print(f"Initial Free Disk Space: {initial_free} GiB")
    
    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "initial_free_disk_gib": initial_free,
        "results": {}
    }

    # 1. Acquire Bangla Handwritten Dolil Dataset (Primary Domain)
    print("\n[TARGET 1/3] Bangla Handwritten Dolil Dataset...")
    dolil_cfg = MENDELEY_TARGETS["dolil"]
    dolil_dest = dolil_cfg["target_dir"] / dolil_cfg["filename"]
    if dolil_dest.exists() and dolil_dest.stat().st_size > 100 * 1024 * 1024:
        print(f"  -> File already exists: {dolil_dest} ({dolil_dest.stat().st_size / (1024*1024):.1f} MB)")
        summary["results"]["dolil"] = {"status": "ALREADY_PRESENT", "file_path": str(dolil_dest), "size_bytes": dolil_dest.stat().st_size}
    else:
        summary["results"]["dolil"] = download_file_stream(dolil_cfg["url"], dolil_dest)

    # 2. Acquire BN-HTRd V2 (Benchmark HTR)
    print("\n[TARGET 2/3] BN-HTRd V2 Benchmark Dataset...")
    htrd_cfg = MENDELEY_TARGETS["bn_htrd"]
    htrd_dest = htrd_cfg["target_dir"] / htrd_cfg["filename"]
    if htrd_dest.exists() and htrd_dest.stat().st_size > 100 * 1024 * 1024:
        print(f"  -> File already exists: {htrd_dest} ({htrd_dest.stat().st_size / (1024*1024):.1f} MB)")
        summary["results"]["bn_htrd"] = {"status": "ALREADY_PRESENT", "file_path": str(htrd_dest), "size_bytes": htrd_dest.stat().st_size}
    else:
        # Check disk space before downloading 2.5 GB
        current_free = get_free_disk_space_gib(BASE_DIR)
        if current_free >= 28.0:
            summary["results"]["bn_htrd"] = download_file_stream(htrd_cfg["url"], htrd_dest)
        else:
            print(f"  [WARN] Skipping automatic download of BN-HTRd ({htrd_cfg['name']}) to maintain >25 GiB disk headroom (Current free: {current_free} GiB).")
            summary["results"]["bn_htrd"] = {
                "status": "PAUSED_HEADROOM_SAFETY",
                "current_free_gib": current_free,
                "manual_url": htrd_cfg["url"]
            }

    # 3. Acquire BLUGE NER Sample
    print("\n[TARGET 3/3] BLUGE Bengali NER Sample...")
    summary["results"]["bluge_ner"] = acquire_bluge_ner_sample()

    final_free = get_free_disk_space_gib(BASE_DIR)
    summary["final_free_disk_gib"] = final_free
    print(f"\nFinal Free Disk Space: {final_free} GiB (Net change: {final_free - initial_free:+.2f} GiB)")

    summary_file = RAW_DIR / "acquisition_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary written to: {summary_file}")
    print("=" * 72)
    return summary

if __name__ == "__main__":
    run_acquisition()
