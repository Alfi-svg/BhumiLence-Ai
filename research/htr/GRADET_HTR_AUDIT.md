# GraDeT-HTR Feasibility & Architecture Audit Report

**Audit Date:** 2026-11-15  
**Repository:** `https://github.com/mahmudulyeamim/GraDeT-HTR` (Accepted at EMNLP 2025 System Demonstrations)  
**Status:** **INSPECTED & AUDITED — PRETRAINED WEIGHTS ARE GATED / RESTRICTED**

---

## 1. Executive Summary

GraDeT-HTR proposes a decoder-only Bengali Handwritten Text Recognition (HTR) architecture combining a Vision Transformer (ViT) patch embedding layer with a GPT-2 decoder block stack and a specialized Bengali grapheme tokenizer. 

**Critical Discovery:**
The GitHub repository **DOES NOT include or link to public pretrained text recognition weights (`.pth`)**.
As stated explicitly in Section 'Request Access to Weights' of their official README:
> *"To request access to our pre-trained text recognition model weights or synthetic datasets, please email mahmudulyeamim@gmail.com... Pre-trained weights and synthetic datasets are provided strictly for academic and research purposes."*

Therefore, **GraDeT-HTR cannot be used immediately as a plug-and-play pretrained checkpoint out of the box without manual academic authorization**.

---

## 2. Technical Inspection Findings

| Audit Item | Inspection Result | Severity / Impact |
| :--- | :--- | :--- |
| **Local Checkpoints** | **0 `.pt` / `.pth` recognition weights** in repository | High — Cannot run `inference.py` without external checkpoint |
| **Weight Distribution** | Gated via manual email request (`mahmudulyeamim@gmail.com`) | High — Unsuitable for unattended CI/CD or offline GovTech deploy |
| **Model Architecture** | `DTrOCRLMHeadModel` (ViT Patch Embedding + 6-layer GPT2 Blocks) | High Innovation — Grapheme-level decoder architecture |
| **Tokenizer** | Custom `bntokenizer.py` + `BnGraphemizer` (CSE BUET NLP normalizer) | Good — Grapheme-level segmentation for Bengali conjuncts |
| **Hardware Compatibility** | Hardcoded `cuda` / `cpu` only; **No Apple MPS support** (`train.py`) | Medium — Requires patching `device = 'mps'` for M2 Mac |
| **PyTorch Compile** | Uses `torch.compile(model)` in `train.py` | Medium — `torch.compile` is unsupported/unstable on macOS MPS |
| **Dependencies** | Dumped Linux CUDA environment (`nvidia-cublas-cu12`, etc.) in `requirements.txt` | Low — Must install only portable PyTorch packages |

---

## 3. Architecture Specification

From `GraDeT_HTR/model.py` and `config.py`:
- **Model Type:** Decoder-only Vision-to-Text Transformer (inspired by DTrOCR).
- **Vision Front-end:** `ViTPatchEmbeddings` projecting image patches into $D=768$ embedding space.
- **Decoder Stack:** Standard Hugging Face `GPT2Block` layers (cross-attention over patch tokens + causal auto-regressive text token generation).
- **Target Vocabulary:** Grapheme cluster vocabulary (~1,200 unique Bengali graphemes including diacritics and ligatures/যুক্তবর্ণ).

---

## 4. Strategic Engineering Path for BhumiLens AI

To guarantee a reliable, reproducible, and offline-capable system for BhumiLens AI Phase 5:
1. **Pretrained Offline Baseline (Task 2):** Deploy a proven, mature, offline-capable Bengali OCR/HTR engine (e.g. `EasyOCR` Bengali model / Hugging Face TrOCR) that runs natively on Apple Silicon M2 without API keys or manual email requests.
2. **Held-Out Evaluation:** Measure exact Character Error Rate (CER) and Word Error Rate (WER) using `jiwer` on our held-out `BN-HTRd` test split.
3. **Custom Mini-Training Experiment on BN-HTRd (Task 3):** Train a native PyTorch CTC-based Bengali HTR model (`BhumiLens-HTR-v1-pilot`) on our leak-free `train.jsonl` split using Apple MPS (`mps:0`).
4. **Dual-Engine Architecture (Task 4):** Provide seamless switching between the pretrained baseline and custom pilot models in `HTRService` and `HTRAgent`.
