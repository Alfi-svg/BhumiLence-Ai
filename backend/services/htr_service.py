"""
Bengali Handwritten Text Recognition (HTR) Production Service (Layer 4).
Supports:
1. PRETRAINED_BASELINE: Real offline EasyOCR (CRAFT + ResNet-BiLSTM-CTC)
2. CUSTOM_PILOT: Custom-trained BhumiLens-HTR-v1-pilot (CRNN on Apple MPS)
3. HYBRID: Primary baseline recognition + low-confidence flagging (< 0.65) for Maker review.
"""
import os
import time
import json
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
import cv2
import numpy as np
import torch
import torch.nn as nn

from backend.schemas.htr_schema import (
    HTREngineType,
    LineRecognitionResult,
    DocumentHTRResult,
    SCHEMA_VERSION
)
from backend.schemas.document_schema import DocumentAnalysisResult, TextLineCrop

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent

# -----------------------------------------------------------------------------
# CRNN Architecture Definition (for CUSTOM_PILOT mode)
# -----------------------------------------------------------------------------
class BhumiLensCRNN(nn.Module):
    def __init__(self, vocab_size: int, hidden_size: int = 128):
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d((2, 1), (2, 1)),

            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d((4, 1), (4, 1)),
        )
        self.rnn = nn.LSTM(
            input_size=256,
            hidden_size=hidden_size,
            num_layers=2,
            bidirectional=True,
            batch_first=False,
            dropout=0.1
        )
        self.fc = nn.Linear(hidden_size * 2, vocab_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.cnn(x).squeeze(2)  # (B, 256, W)
        seq = features.permute(2, 0, 1)      # (T, B, 256)
        rnn_out, _ = self.rnn(seq)
        logits = self.fc(rnn_out)
        return nn.functional.log_softmax(logits, dim=2)

# -----------------------------------------------------------------------------
# HTR Service
# -----------------------------------------------------------------------------
class HTRService:
    def __init__(
        self,
        default_engine: HTREngineType = HTREngineType.HYBRID,
        confidence_threshold: float = 0.65,
        models_base_dir: Optional[str] = None
    ):
        self.default_engine = default_engine
        self.confidence_threshold = confidence_threshold
        self.models_dir = Path(models_base_dir) if models_base_dir else WORKSPACE_ROOT / "models" / "htr"
        
        # Lazy-loaded engine instances
        self._easyocr_reader = None
        self._custom_model = None
        self._custom_vocab = None
        self._device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

    def _get_easyocr_reader(self):
        """Initializes EasyOCR reader with locally cached model weights."""
        if self._easyocr_reader is None:
            import easyocr
            pretrained_dir = self.models_dir / "pretrained_baseline"
            user_net_dir = pretrained_dir / "user_network"
            user_net_dir.mkdir(parents=True, exist_ok=True)
            self._easyocr_reader = easyocr.Reader(
                ["bn", "en"],
                model_storage_directory=str(pretrained_dir),
                user_network_directory=str(user_net_dir),
                download_enabled=False,
                gpu=False
            )
        return self._easyocr_reader

    def _get_custom_model(self):
        """Loads custom-trained BhumiLens-HTR-v1-pilot checkpoint and vocabulary."""
        if self._custom_model is None:
            vocab_p = self.models_dir / "vocab.json"
            ckpt_p = self.models_dir / "bhumilens_htr_v1_pilot.pt"
            if not vocab_p.exists() or not ckpt_p.exists():
                raise FileNotFoundError(f"Custom pilot model weights missing at {ckpt_p}")

            with open(vocab_p, "r", encoding="utf-8") as f:
                self._custom_vocab = json.load(f)

            vocab_size = self._custom_vocab["vocab_size"]
            model = BhumiLensCRNN(vocab_size=vocab_size, hidden_size=128).to(self._device)
            model.load_state_dict(torch.load(str(ckpt_p), map_location=self._device))
            model.eval()
            self._custom_model = model

        return self._custom_model, self._custom_vocab

    @staticmethod
    def preprocess_image_for_crnn(img_path: str, img_h: int = 32, img_w: int = 256) -> np.ndarray:
        """Preprocesses a cropped line image for CRNN inference."""
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            img = np.zeros((img_h, img_w), dtype=np.uint8)

        h, w = img.shape
        scale = min(img_h / max(1, h), img_w / max(1, w))
        nw = max(1, int(w * scale))
        nh = max(1, int(h * scale))
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)

        canvas = np.ones((img_h, img_w), dtype=np.uint8) * 255
        canvas[:nh, :nw] = resized
        norm = (canvas.astype(np.float32) / 127.5) - 1.0
        return np.expand_dims(norm, axis=0)  # (1, H, W)

    def recognize_line(
        self,
        crop_path: str,
        line_index: int,
        bbox: List[int],
        engine: Optional[HTREngineType] = None
    ) -> LineRecognitionResult:
        """
        Runs real neural HTR inference on a single cropped handwritten line.
        """
        active_engine = engine or self.default_engine
        t0 = time.perf_counter()
        crop_p = Path(crop_path)

        if not crop_p.exists() or crop_p.stat().st_size == 0:
            return LineRecognitionResult(
                line_id=f"line_{line_index:03d}",
                line_index=line_index,
                bbox=bbox,
                evidence_crop_path=crop_path,
                raw_text="",
                confidence=0.0,
                uncertain_flag=True,
                engine_used=active_engine,
                model_version="none",
                latency_ms=0.0
            )

        if active_engine in [HTREngineType.PRETRAINED_BASELINE, HTREngineType.HYBRID]:
            reader = self._get_easyocr_reader()
            results = reader.readtext(str(crop_p), detail=1)
            tokens = [r[1] for r in results]
            confs = [float(r[2]) for r in results]

            raw_text = " ".join(tokens).strip()
            conf = float(sum(confs) / len(confs)) if confs else 0.0
            model_ver = "EasyOCR-CRAFT-ResNet-bn-v1.7.2"
            uncertain = (conf < self.confidence_threshold) or (len(raw_text) == 0)

        elif active_engine == HTREngineType.CUSTOM_PILOT:
            model, vocab_data = self._get_custom_model()
            inp = self.preprocess_image_for_crnn(str(crop_p))
            tensor = torch.from_numpy(np.expand_dims(inp, axis=0)).to(self._device)

            with torch.no_grad():
                log_probs = model(tensor)
                probs = torch.exp(log_probs)
                max_probs, preds = torch.max(probs, dim=2)
                pred_indices = preds.squeeze(1).cpu().numpy().tolist()
                conf = float(torch.mean(max_probs).item())

            idx_to_char = vocab_data["idx_to_char"]
            collapsed = []
            prev = None
            for idx in pred_indices:
                if idx != prev:
                    collapsed.append(idx)
                    prev = idx

            decoded_chars = [idx_to_char[str(i)] for i in collapsed if str(i) in idx_to_char and i != 0]
            raw_text = "".join(decoded_chars).strip()
            model_ver = "BhumiLens-HTR-v1-pilot-CRNN-MPS"
            uncertain = (conf < self.confidence_threshold) or (len(raw_text) == 0)

        else:
            raw_text = ""
            conf = 0.0
            uncertain = True
            model_ver = "unknown"

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        return LineRecognitionResult(
            line_id=f"line_{line_index:03d}",
            line_index=line_index,
            bbox=bbox,
            evidence_crop_path=crop_path,
            raw_text=raw_text,
            confidence=round(conf, 3),
            uncertain_flag=uncertain,
            engine_used=active_engine,
            model_version=model_ver,
            latency_ms=round(elapsed_ms, 2)
        )

    def recognize_document(
        self,
        doc_analysis: DocumentAnalysisResult,
        engine: Optional[HTREngineType] = None
    ) -> DocumentHTRResult:
        """
        Orchestrates full-document HTR by running inference across all detected lines.
        """
        t0 = time.perf_counter()
        active_engine = engine or self.default_engine
        recognized_lines: List[LineRecognitionResult] = []

        # 1. Recognize extracted handwritten line crops
        if doc_analysis.layout.line_crops:
            for lc in doc_analysis.layout.line_crops:
                line_res = self.recognize_line(
                    crop_path=lc.crop_path,
                    line_index=lc.line_index,
                    bbox=lc.bbox,
                    engine=active_engine
                )
                recognized_lines.append(line_res)
        else:
            # Fallback: scan for any handwritten lines in evidence_crops
            idx = 1
            for k, ev in doc_analysis.evidence_crops.items():
                if ev.zone_type == "handwritten_line":
                    line_res = self.recognize_line(
                        crop_path=ev.crop_path,
                        line_index=idx,
                        bbox=ev.bbox,
                        engine=active_engine
                    )
                    recognized_lines.append(line_res)
                    idx += 1

        # Calculate statistics
        total_lines = len(recognized_lines)
        valid_confs = [l.confidence for l in recognized_lines if l.confidence > 0]
        avg_conf = float(sum(valid_confs) / len(valid_confs)) if valid_confs else 0.0
        uncertain_count = sum(1 for l in recognized_lines if l.uncertain_flag)

        full_raw_text = "\n".join(l.raw_text for l in recognized_lines if l.raw_text)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        return DocumentHTRResult(
            doc_id=doc_analysis.doc_id,
            schema_version=SCHEMA_VERSION,
            image_sha256=doc_analysis.image_sha256,
            total_lines=total_lines,
            recognized_lines=recognized_lines,
            full_raw_text=full_raw_text,
            average_confidence=round(avg_conf, 3),
            uncertain_lines_count=uncertain_count,
            engine_used=active_engine,
            total_recognition_time_ms=round(elapsed_ms, 2),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ")
        )
