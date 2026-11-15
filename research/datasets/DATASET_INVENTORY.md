# BhumiLens AI — Dataset Inventory & Technical Catalog

**Last Updated:** 2026-11-15  
**Storage Root:** `research/datasets/`  
**Governance:** All raw and processed datasets are strictly isolated by `.gitignore` to prevent repository bloat.

---

## 1. Inventory Catalog

| Dataset ID | Full Name | Primary Role in BhumiLens AI | Format | Volume / Size | Local Path | Status |
| :--- | :--- | :--- | :---: | :---: | :--- | :---: |
| **DS-01** | **Bangla Handwritten Dolil Dataset** | Historical Land Deed Layout, Stamp & Moharar Script Domain Benchmark | JPEG Photos / Scans | 653 images (~250 MB) | `research/datasets/raw/dolil/` | Acquisition Ready |
| **DS-02** | **BN-HTRd V2** | Bengali Handwritten Line & Word HTR Ground-Truth Training | PNG / JPG + Line/Word TXT & Box Annotations | 786 pages, 13k lines, 108k words (~1.2 GB) | `research/datasets/raw/bn_htrd/` | Acquisition Ready |
| **DS-03** | **Bayanno V2** | Auxiliary Grapheme & Conjunct (যুক্তবর্ণ) Recognition | PNG images | ~52k character samples (~350 MB) | `research/datasets/raw/bayanno/` | Cataloged |
| **DS-04** | **CHBCR-DB** | Isolated Cursive Character & Ligature Validation | Grayscale Images | ~12k samples (~120 MB) | `research/datasets/raw/chbcr/` | Cataloged |
| **DS-05** | **BPS2025 / BPS V2** | Real-world Handwritten District & Thana Address Recognition | JPEG envelope crops | ~15k samples (~400 MB) | `research/datasets/raw/bps/` | Cataloged |
| **DS-06** | **BanglaDigit** | Numeric Verification for Stamp Math, Dag/Khatian & Dates | PNG digit crops | ~20k digits (~80 MB) | `research/datasets/raw/bangladigit/` | Cataloged |
| **DS-07** | **BLUGE Bengali NER** | Extracting Mouza, Thana, District & Owner Entities | JSON Lines / Parquet | ~15k annotated sentences (~15 MB) | `research/datasets/raw/bluge_ner/` | Acquisition Ready |
| **DS-08** | **MultiCoNER V2 Bangla** | Complex Legal and Administrative Entity Resolution | CoNLL / JSON | ~20k tokens (~10 MB) | `research/datasets/raw/multiconer/` | Cataloged |

---

## 2. Directory Schema & Role Mapping

```
research/datasets/
├── DATASET_LICENSE_REGISTER.md
├── DATASET_INVENTORY.md
├── raw/                      # Downloaded original archives & raw scans (Git-Ignored)
│   ├── dolil/                # 653 Deed scans from Mendeley yk3c3xy9vm
│   ├── bn_htrd/              # BN-HTRd V2 pages and line/word annotations
│   └── bluge_ner/            # BLUGE NER dataset samples
├── processed/                # Normalized, cropped, and binarized images (Git-Ignored)
├── annotations/              # Ground-truth JSONs, YOLO bounding boxes, and label maps
├── splits/                   # Deterministic train/validation/test splits (80/10/10)
└── reports/                  # EDA statistical reports, contact sheets, and confusion matrices
```

---

## 3. Data Integrity & PII Protocol

1. **PII Masking:** Donor/Recipient personal names, signatures, and National ID references from deed scans are masked in visual reports.
2. **Deterministic Partitioning:** All dataset splits are generated using fixed seeds (e.g., `seed=42`) to prevent data leakage between training and evaluation.
3. **Storage Caps:** Raw dataset downloads must strictly respect host storage boundaries ($>25\text{ GiB}$ free space guaranteed at all times).
