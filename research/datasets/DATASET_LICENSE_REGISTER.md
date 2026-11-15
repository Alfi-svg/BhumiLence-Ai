# BhumiLens AI — Dataset Licensing & Governance Register

This register documents the formal licenses, data origins, intellectual property terms, and compliance requirements for all datasets utilized within the BhumiLens AI and BhumiGuard systems.

---

## 1. Domain-Specific Bengali Legal & Historical Land Document Datasets

### A. Bangla Handwritten Dolil Dataset (Primary Domain Benchmark)
* **Dataset Identifier:** `yk3c3xy9vm/1`
* **Canonical URL:** `https://data.mendeley.com/datasets/yk3c3xy9vm/1`
* **Authors:** Saifullah Anik, Md. Obydul Hossain, Radoanul Arifen, Md. Shakib Ahammed (Daffodil International University, Bangladesh)
* **Release Year:** 2025
* **License:** **Creative Commons Attribution 4.0 International (CC BY 4.0)**
* **License URL:** `https://creativecommons.org/licenses/by/4.0/`
* **Commercial Use:** Permitted with proper attribution.
* **Derivative Works:** Permitted with attribution and documentation of modifications.
* **Data Privacy / Redaction Policy (Rule 10):** Historical deeds contain citizen names, signatures, and thumbprints. Public demonstrations and test artifacts must apply Gaussian blurring or bounding box masks to personal identifiable information (PII) of living individuals.

---

## 2. General Bengali Handwritten Text Recognition (HTR) Datasets

### B. BN-HTRd V2 (Benchmark Bengali Handwritten Text Recognition Dataset)
* **Dataset Identifier:** `743k6dm543/2`
* **Canonical URL:** `https://data.mendeley.com/datasets/743k6dm543/2`
* **Authors:** Md. Asifur Rahman, S. M. Farhad, et al.
* **License:** **Creative Commons Attribution 4.0 International (CC BY 4.0)**
* **Volume:** 786 full-page handwritten document images, 13,867 line images, 108,147 word bounding boxes and ground-truth text annotations.
* **Commercial Use:** Permitted with academic attribution.
* **Intended Use:** Pre-training and fine-tuning baseline Bengali handwriting recognizers (GraDeT-HTR, CRNN, TrOCR).

---

## 3. Auxiliary Bengali Handwriting, Digit & Script Datasets

### C. Bayanno V2
* **Identifier:** `jtpfd6j55n/2`
* **URL:** `https://data.mendeley.com/datasets/jtpfd6j55n/2`
* **License:** **CC BY 4.0**
* **Scope:** Bengali handwritten character and compound character recognition benchmark.

### D. CHBCR-DB
* **Identifier:** `2wnyt8d9gy/4`
* **URL:** `https://data.mendeley.com/datasets/2wnyt8d9gy/4`
* **License:** **CC BY 4.0**
* **Scope:** Cursive handwritten Bengali characters and isolated numeral recognition.

### E. BPS2025 / BPS V2 (Bangla Postal Services Dataset)
* **Identifier:** `mt6jfkxprj/3`
* **URL:** `https://data.mendeley.com/datasets/mt6jfkxprj/3`
* **License:** **CC BY 4.0**
* **Scope:** Real-world handwriting from postal envelopes, addresses, and district names.

### F. BanglaDigit
* **Identifier:** `s2nr768mhr/1`
* **URL:** `https://data.mendeley.com/datasets/s2nr768mhr/1`
* **License:** **CC BY 4.0**
* **Scope:** Isolated handwritten Bengali numerals (`০, ১, ২, ৩, ৪, ৫, ৬, ৭, ৮, ৯`). Crucial for validating deed numbers, stamp values, and land area digits.

---

## 4. NLP & Named Entity Recognition (NER) Datasets

### G. BLUGE Bengali NER (`nahid-hub/BLUGE-bengali-ner`)
* **Host:** Hugging Face Hub
* **License:** **Apache 2.0 / MIT** (Permissive Open Source)
* **Scope:** Bengali named entity recognition for administrative units, person names, and locations.

### H. MultiCoNER V2 (Bangla Subset)
* **Host:** `MultiCoNER/multiconer_v2`
* **License:** **CC BY-SA 4.0 / MIT**
* **Scope:** Fine-grained complex named entities (LOC, GPE, PER) in low-context environments.

---

## 5. Compliance Checklist Summary

| Dataset | License | Commercial Permitted? | Redistribution Permitted? | Attribution Required? | PII Risk |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Dolil Dataset** | CC BY 4.0 | Yes | Yes | Yes | Medium (Deed PII) |
| **BN-HTRd V2** | CC BY 4.0 | Yes | Yes | Yes | Low (Standard Text) |
| **Bayanno V2** | CC BY 4.0 | Yes | Yes | Yes | None (Characters) |
| **CHBCR-DB** | CC BY 4.0 | Yes | Yes | Yes | None (Characters) |
| **BPS V2** | CC BY 4.0 | Yes | Yes | Yes | Low (Postal Addr) |
| **BanglaDigit** | CC BY 4.0 | Yes | Yes | Yes | None (Digits) |
| **BLUGE NER** | Apache 2.0 | Yes | Yes | Yes | None (Public Text) |
| **MultiCoNER** | CC BY-SA 4.0 | Yes | Yes | Yes | None (Public Text) |
