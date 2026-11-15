# BhumiLens AI — P1: Digitize Old Land Records (LandTech 2026)

**Subtitle:** 100% On-Premise Bangla Land Document Digitization, Visual-Grapheme Lexicon Normalization & Human-in-the-Loop Verification System.

## 1. Quick Start (How to Test on MacBook Air M2 in 30 Seconds)

### Step 1: Install Minimal Local Dependencies
```bash
pip3 install -r requirements.txt
```
*(Optional for live Tesseract OCR: `brew install tesseract tesseract-lang` and `pip3 install pytesseract`)*

### Step 2: Run the Automated 5-Module Diagnostic Test Suite
```bash
python3 test_pipeline.py
```
This tests:
1. **Dual-Template Layout Classifier** (Stamp Dolil vs Tabular Khatian Grid)
2. **OpenCV Morphological Shadow Removal, HSV Seal Detection & 8-Field Evidence Cropping**
3. **Bangla Handwritten Visual-Grapheme Confusion Matrix & Geo-Gazetteer** (`গাজীপুর মদর` -> `গাজীপুর সদর`, `বারেনডা` -> `বারেন্ডা`, `শাতাংশ` -> `শতাংশ`)
4. **Deterministic Land-Math, Stamp Sum (`100+100+100+100+50=450`), Date Chronology & 16-Ana Share Validator**
5. **SQLite Persistence, Four-Eyes (Maker-Checker) Approval & SHA-256 Audit Seal**

### Step 3: Launch the Interactive Web Application
```bash
python3 app.py
```
Open **`http://127.0.0.1:8080`** in your browser to inspect preprocessed images, view cropped visual evidence next to each field, test noisy Bangla OCR normalization live, approve records as Maker/Checker, and export JSON/CSV.

## 2. Data Privacy, Licensing & AI Disclosure (Rule Book Section 10 Compliance)
- **Dataset Citation:** Saifullah Anik et al. (2025), *Bangla Handwritten Dolil Dataset*, Mendeley Data, V1, DOI: `10.17632/yk3c3xy9vm.1`.
- **Privacy Protection (Rule 10):** All personal donor/recipient names and signatures in `sample_dolil_100_anonymized.jpg` have been redacted using Gaussian blurring and bounding-box masking before public demonstration.
- **Non-Goal Disclaimer:** BhumiLens AI is a document digitization and indexing tool. It does NOT claim legal validity of deeds or establish legal ownership.
- **AI Tools Used:** Gemini AI was used for system architecture research, code scaffolding, and documentation formatting. All image processing and validation code is locally executable and fully explainable.
