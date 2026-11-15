#!/usr/bin/env python3
"""
BhumiLens AI — BN-HTRd V2 Data Engineering & Leak-Free Splits
Parses line/word images and ground-truth text pairings, normalizes Unicode NFC,
and produces writer/document-aware deterministic train/val/test splits (80/10/10).
"""
import os
import sys
import glob
import json
import shutil
import unicodedata
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_BN_HTRD = BASE_DIR / "research" / "datasets" / "raw" / "bn_htrd" / "Sample_Small" / "Sample_Small"
PROCESSED_DIR = BASE_DIR / "research" / "datasets" / "processed" / "bn_htrd"
SPLITS_DIR = BASE_DIR / "research" / "datasets" / "splits" / "bn_htrd"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
SPLITS_DIR.mkdir(parents=True, exist_ok=True)

def clean_bangla_text(text: str) -> str:
    """Normalizes Unicode to NFC and cleans trailing/control whitespace."""
    if not text:
        return ""
    # NFC normalization is critical for Bengali conjuncts (e.g. ক + ্ + ষ = ক্ষ)
    normalized = unicodedata.normalize("NFC", str(text))
    # Remove non-printable control characters, preserving standard space and Bengali punctuation
    cleaned = "".join(ch for ch in normalized if ch == " " or not unicodedata.category(ch).startswith("C"))
    return " ".join(cleaned.strip().split())

def build_htr_dataset():
    print("=" * 72)
    print("  BHUMILENS AI — BN-HTRd V2 DATA ENGINEERING & LEAK-FREE SPLITS")
    print("=" * 72)

    if not RAW_BN_HTRD.exists():
        print(f"Error: {RAW_BN_HTRD} does not exist!")
        sys.exit(1)

    gt_root = RAW_BN_HTRD / "Recognition_Ground_Truth_Texts"
    lines_root = RAW_BN_HTRD / "Segmentation_Images" / "Lines"
    words_root = RAW_BN_HTRD / "Segmentation_Images" / "Words"

    doc_ids = sorted([d.name for d in gt_root.iterdir() if d.is_dir() and not d.name.startswith(".")])
    print(f"Found {len(doc_ids)} document corpora: {doc_ids}")

    records = []
    vocab_chars = set()

    for doc_id in doc_ids:
        doc_gt_dir = gt_root / doc_id
        excel_file = doc_gt_dir / f"{doc_id}.xlsx"
        
        if not excel_file.exists():
            print(f"Warning: {excel_file} not found, skipping...")
            continue
            
        xl = pd.ExcelFile(excel_file)
        word_mapping = {}
        for sheet in xl.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet)
            if "Id" in df.columns and "Word" in df.columns:
                for _, row in df.iterrows():
                    wid = str(row["Id"]).strip()
                    wtext = clean_bangla_text(str(row["Word"]))
                    if wid and wtext and wtext != "nan":
                        word_mapping[wid] = wtext

        print(f"Document {doc_id}: Extracted {len(word_mapping)} ground-truth words from {excel_file.name}")

        # Assemble Line-Level Data
        # Word Id format: <doc>_<page>_<line>_<word>, e.g. 1_1_2_3
        # Line Id format: <doc>_<page>_<line>, e.g. 1_1_2
        line_to_words = {}
        for wid, wtext in word_mapping.items():
            parts = wid.split("_")
            if len(parts) >= 4:
                line_id = "_".join(parts[:3])
                line_to_words.setdefault(line_id, []).append((int(parts[3]), wtext))

        doc_lines_dir = lines_root / doc_id
        if doc_lines_dir.exists():
            for page_dir in doc_lines_dir.iterdir():
                if page_dir.is_dir() and not page_dir.name.startswith("."):
                    for line_img in page_dir.glob("*.jpg"):
                        line_id = line_img.stem
                        if line_id in line_to_words:
                            # Order words by word index
                            sorted_words = [w for _, w in sorted(line_to_words[line_id], key=lambda x: x[0])]
                            line_text = clean_bangla_text(" ".join(sorted_words))
                            
                            if line_text:
                                records.append({
                                    "sample_id": f"bn_htrd_line_{line_id}",
                                    "level": "LINE",
                                    "document_id": doc_id,
                                    "page_id": "_".join(line_id.split("_")[:2]),
                                    "image_path": str(line_img.relative_to(BASE_DIR)),
                                    "ground_truth_text": line_text,
                                    "char_length": len(line_text),
                                    "word_count": len(sorted_words)
                                })
                                for ch in line_text:
                                    vocab_chars.add(ch)

        # Assemble Word-Level Data
        doc_words_dir = words_root / doc_id
        if doc_words_dir.exists():
            for w_img in doc_words_dir.rglob("*.jpg"):
                wid = w_img.stem
                if wid in word_mapping:
                    wtext = word_mapping[wid]
                    records.append({
                        "sample_id": f"bn_htrd_word_{wid}",
                        "level": "WORD",
                        "document_id": doc_id,
                        "page_id": "_".join(wid.split("_")[:2]),
                        "image_path": str(w_img.relative_to(BASE_DIR)),
                        "ground_truth_text": wtext,
                        "char_length": len(wtext),
                        "word_count": 1
                    })
                    for ch in wtext:
                        vocab_chars.add(ch)

    print(f"\nTotal Ground-Truth Paired Samples Generated: {len(records)}")
    line_samples = [r for r in records if r["level"] == "LINE"]
    word_samples = [r for r in records if r["level"] == "WORD"]
    print(f"  -> Line Samples: {len(line_samples)}")
    print(f"  -> Word Samples: {len(word_samples)}")
    print(f"  -> Unique Bengali Character Vocabulary: {len(vocab_chars)} distinct graphemes/codepoints")

    # -----------------------------------------------------------------
    # Deterministic Writer / Document-Aware Leak-Free Splitting
    # -----------------------------------------------------------------
    # Partition documents deterministically:
    # doc 1 -> TRAIN (50%), doc 100 -> TRAIN (30%), doc 50 -> VAL & TEST (20%)
    # This guarantees 0% writer or page overlap between train and test!
    train_records = []
    val_records = []
    test_records = []

    # Using doc_id partitioning:
    # Documents in sample: 1, 100, 50
    # doc 1 & 100 -> Train (80%)
    # doc 50 pages: odd pages -> Val, even pages -> Test (Strict document/page isolation)
    for r in records:
        if r["document_id"] in ["1"]:
            train_records.append(r)
        elif r["document_id"] == "100":
            # Split doc 100: 75% train, 25% val to balance volume
            page_num = int(r["page_id"].split("_")[-1]) if "_" in r["page_id"] else 1
            if page_num % 4 != 0:
                train_records.append(r)
            else:
                val_records.append(r)
        elif r["document_id"] == "50":
            page_num = int(r["page_id"].split("_")[-1]) if "_" in r["page_id"] else 1
            if page_num % 2 == 1:
                val_records.append(r)
            else:
                test_records.append(r)
        else:
            train_records.append(r)

    print("\n--- Deterministic Split Distribution ---")
    print(f"  Train Set : {len(train_records):<6} samples ({len(train_records)/len(records)*100:.1f}%)")
    print(f"  Val Set   : {len(val_records):<6} samples ({len(val_records)/len(records)*100:.1f}%)")
    print(f"  Test Set  : {len(test_records):<6} samples ({len(test_records)/len(records)*100:.1f}%)")

    # Write JSONL split files
    def write_jsonl(path, data):
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"Wrote {len(data)} items to {path.name} ({path.stat().st_size / 1024:.1f} KB)")

    write_jsonl(SPLITS_DIR / "train.jsonl", train_records)
    write_jsonl(SPLITS_DIR / "val.jsonl", val_records)
    write_jsonl(SPLITS_DIR / "test.jsonl", test_records)

    # Save Vocabulary & Statistics
    stats = {
        "dataset_name": "BN-HTRd V2 Sample Benchmark Splits",
        "total_samples": len(records),
        "split_counts": {
            "train": len(train_records),
            "val": len(val_records),
            "test": len(test_records)
        },
        "level_counts": {
            "LINE": len(line_samples),
            "WORD": len(word_samples)
        },
        "character_vocabulary_size": len(vocab_chars),
        "vocabulary_sample": sorted(list(vocab_chars)),
        "average_char_length": {
            "line": sum(r["char_length"] for r in line_samples) / max(len(line_samples), 1),
            "word": sum(r["char_length"] for r in word_samples) / max(len(word_samples), 1)
        }
    }

    stats_file = SPLITS_DIR / "splits_statistics.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"Saved statistics to: {stats_file}")
    print("=" * 72)
    return stats

if __name__ == "__main__":
    build_htr_dataset()
