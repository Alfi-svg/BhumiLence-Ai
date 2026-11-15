# BhumiLens AI — Deep Dataset Inspection & Annotation Audit Report

**Audit Date:** 2026-11-15  
**Auditor:** Autonomous AI/ML Systems Engineer  
**Methodology:** Binary zip header parsing, HTTP Range inspection of S3 archives, direct extraction, and PIL/NumPy geometric profiling.

---

## 1. Executive Summary & Critical Audit Discovery

| Dataset | Total Volume | Ground-Truth Labels Present? | Annotation Format | Dominant Resolution | Primary Finding |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Bangla Handwritten Dolil Dataset** (`yk3c3xy9vm/1`) | 653 Deed Images | **NO (0 Labels)** | None (100% `.jpg` images) | $4000 \times 3000$ (12 MP RGB) | **Pure unannotated raw image collection.** Zero line-level, word-level, or metadata bounding box annotations exist in the original Mendeley archive. |
| **BN-HTRd V2 (Sample_Small)** (`743k6dm543/2`) | 4,379 Files | **YES (387 Texts, 360 XMLs)** | `.txt`, `.xml`, `.xlsx` | $211.5 \times 119.0$ (Median Line/Word Crops) | **Fully annotated benchmark HTR.** Contains word/line bounding boxes paired with authentic Bengali transcriptions. |
| **BLUGE Bengali NER** (`nahid-hub/BLUGE-bengali-ner`) | 100 Sample Sentences | **YES (Token-level NER tags)** | JSON / Parquet | N/A (Text Tokens) | **Annotated Entity Dataset.** Contains B-PER, I-PER, B-LOC, I-LOC token tags for administrative entities. |

---

## 2. Granular Dataset Profiles

### A. Bangla Handwritten Dolil Dataset (Primary Land Domain)
* **Archive Integrity:** Mendeley S3 ZIP archive `yk3c3xy9vm-1.zip` (2,212,865,509 bytes / ~2.06 GiB).
* **Archive File Count:** Exactly 653 files in Central Directory.
* **File Types:** 100% `.jpg` files (located under `Bangla Handwritten Dolil Dataset (653 Images)/Dolil Dataset/dolil_*.jpg`).
* **Image Geometry:**
  * Median Resolution: **$4000 \times 3000$ pixels** (high-resolution smartphone/camera photos).
  * Color Depth: 24-bit RGB (3 channels).
  * Quality: Sharp resolution, but documents exhibit severe aging, paper yellowing, ink bleeding, handwritten deed-writer cursiveMoharar script, official round purple/red seals, and adhesive revenue stamp sheets.
* **Annotation Verdict:** **No annotations whatsoever.** Any system claiming the Mendeley Dolil dataset comes with out-of-the-box ground truth is incorrect. A dedicated pseudo-labeling / human-in-the-loop annotation pipeline is mandatory.

### B. BN-HTRd V2 Benchmark Dataset
* **Extracted Sample Volume:** 4,379 files across `Recognition_Ground_Truth_Texts/` and image folders.
* **File Type Breakdown:**
  * Image crops (`.jpg`): 3,225
  * Ground-truth transcriptions (`.txt`): 387
  * XML layout bounding boxes (`.xml`): 360
  * Metadata registries (`.xlsx`, `.db`, `.pdf`): 12
* **Sample Transcription Real-World Snippets:**
  1. `[50.txt]`: *"ক্রিকেট বিশ্বকাপ ২০১৯: ‘আমার চাওয়া থাকবে বাংলাদেশ যাতে ফাইনাল খেলে’-বোলিং কোচ কোর্টনি ওয়ালশ..."*
  2. `[1.txt]`: *"কথা প্রকাশ বৈচিত্র্যময় এই পৃথিবীর পরতে পরতে লুকিয়ে আছে বিস্ময় ও নানা অজানা বিষয়..."*
  3. `[100.txt]`: *"করোনা ভাইরাস: মহামারির কারণে কতটা ক্ষতিগ্রস্ত হয়েছে বাংলাদেশের এভিয়েশন ইন্ডাস্ট্রি?..."*

---

## 3. Domain Gap Analysis: News Handwriting vs. Historical Land Deed Handwriting

```
+----------------------------------------------------------------------------------------------------+
|                                    DOMAIN GAP COMPARISON MATRIX                                    |
+------------------------------+----------------------------------+----------------------------------+
| Feature                      | BN-HTRd V2 (General Bengali HTR) | Bangla Dolil Dataset (LandTech)  |
+------------------------------+----------------------------------+----------------------------------+
| Vocabulary Source            | Contemporary BBC News, Novels    | 19th-20th C. Legal Land Lexicon |
| Text Style                   | Modern Bengali Prose             | Archaic Moharar Deed Handwriting |
| Layout                       | Lined / plain notebook pages     | Unstructured stamped legal deeds |
| Extraneous Visual Noise      | Minimal (clean paper, ballpoint) | High (revenue stamps, seals, mud)|
| Archaic Numbering & Shares   | Standard Indo-Arabic / Bengali   | Ana-Gonda-Kora-Kranti fractions  |
| Ground-Truth Availability    | Ready for direct HTR training    | Requires Ground-Truth Pipeline   |
+------------------------------+----------------------------------+----------------------------------+
```

### Domain Gap Implications for Model Training:
1. **Direct Zero-Shot Transfer Failure:** A model trained strictly on modern news handwriting (BN-HTRd) will experience significant character error rate (CER) degradation on Moharar deeds due to archaic legal terms (*সাফ কবলা*, *চৌহদ্দি*, *এওয়াজ বদল*, *বায়ে-রেজিস্ট্রি*).
2. **Transfer Learning Strategy:**
   * **Step 1:** Pre-train / fine-tune Bengali vision backbone (GraDeT-HTR) on BN-HTRd V2 line/word crops.
   * **Step 2:** Fine-tune on segmented, annotated Moharar deed snippets using the BhumiLens Land Gazetteer as language model guidance.

---

## 4. Visual Contact Sheets Generated

The visual contact sheets have been generated at 85% quality and stored in `research/datasets/reports/`:
1. [dolil_contact_sheet.jpg](file:///Users/alfi/Downloads/BhumiLens_AI_P1_Prototype/research/datasets/reports/dolil_contact_sheet.jpg) (357.2 KB) — 16 authentic historical deed thumbnails exhibiting stamp headers, stamps, and cursive deed script.
2. [bn_htrd_contact_sheet.jpg](file:///Users/alfi/Downloads/BhumiLens_AI_P1_Prototype/research/datasets/reports/bn_htrd_contact_sheet.jpg) (111.1 KB) — 16 line/word handwriting samples from BN-HTRd V2.
