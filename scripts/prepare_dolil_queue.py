#!/usr/bin/env python3
"""
BhumiLens AI — Dolil Curation Queue Generator
Prepares 20-30 authentic Dolil images with OpenCV shadow removal, binarization,
and 8-field evidence crops for the Human Annotation Workbench.
"""
import os
import sys
import json
import time
import shutil
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.vision_pipeline import BhumiVisionPipeline

EXTRACTED_DIR = BASE_DIR / "research" / "datasets" / "raw" / "dolil" / "extracted"
QUEUE_DIR = BASE_DIR / "research" / "datasets" / "processed" / "dolil_curation_queue"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

def prepare_queue():
    print("=" * 72)
    print("  BHUMILENS AI — DOLIL CURATION QUEUE GENERATOR")
    print("=" * 72)
    
    deed_files = sorted(list(EXTRACTED_DIR.glob("*.jpg")))
    print(f"Found {len(deed_files)} authentic deed scans in {EXTRACTED_DIR.relative_to(BASE_DIR)}")
    
    pipeline = BhumiVisionPipeline(output_dir=str(QUEUE_DIR / "_temp_crops"))
    
    index = []
    
    for idx, img_path in enumerate(deed_files):
        doc_id = f"DOLIL_MND_{img_path.stem.upper()}"
        doc_out_dir = QUEUE_DIR / doc_id
        doc_crops_dir = doc_out_dir / "crops"
        doc_crops_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Generate normalized 1200px preview for fast UI loading
        preview_path = doc_out_dir / "preview.jpg"
        with Image.open(img_path) as im:
            orig_w, orig_h = im.size
            scale = 1200 / float(orig_w)
            new_h = int(orig_h * scale)
            preview_im = im.resize((1200, new_h), Image.Resampling.LANCZOS)
            preview_im.save(preview_path, "JPEG", quality=85)
            
        # 2. Run OpenCV preprocessing & 8-field evidence cropping
        doc_pipeline = BhumiVisionPipeline(output_dir=str(doc_out_dir))
        doc_pipeline.crops_dir = str(doc_crops_dir)
        vis_meta = doc_pipeline.process_document(str(img_path), doc_id=doc_id)
        
        item_entry = {
            "queue_index": idx + 1,
            "doc_id": doc_id,
            "raw_filename": img_path.name,
            "original_dimensions": {"width": orig_w, "height": orig_h},
            "preview_path": str(preview_path.relative_to(BASE_DIR)),
            "binarized_path": str(Path(vis_meta["preprocessed_paths"]["binarized_clean"]).relative_to(BASE_DIR)),
            "shadow_removed_path": str(Path(vis_meta["preprocessed_paths"]["shadow_removed"]).relative_to(BASE_DIR)),
            "layout": vis_meta["layout_classification"]["detected_type"],
            "seal_detected": vis_meta["seal_metadata"]["official_seal_detected"],
            "crop_fields": {
                k: str(Path(v["crop_path"]).relative_to(BASE_DIR))
                for k, v in vis_meta["field_crops"].items()
            },
            "status": "READY_FOR_HUMAN_ANNOTATION"
        }
        index.append(item_entry)
        print(f"[{idx+1}/{len(deed_files)}] Prepared: {doc_id} (Preview 1200x{new_h}, 8 crops generated)")

    # Clean up temp
    temp_dir = QUEUE_DIR / "_temp_crops"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

    index_file = QUEUE_DIR / "queue_index.json"
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_documents": len(index),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "documents": index
        }, f, ensure_ascii=False, indent=2)
        
    print(f"\nCuration queue generation complete! {len(index)} documents ready in {QUEUE_DIR.relative_to(BASE_DIR)}")
    print(f"Index catalog: {index_file}")
    print("=" * 72)
    return index

if __name__ == "__main__":
    prepare_queue()
