"""
BhumiLens-HTR-v1-pilot: Resource-Safe Bengali Handwritten Text Recognition (HTR) Pilot Training.
Model: CRNN (CNN Feature Extractor + BiLSTM Sequence Modeler + CTC Loss)
Hardware: Apple Silicon M2 via Metal Performance Shaders (MPS:0)
Dataset: Leak-Free BN-HTRd Splits (train.jsonl / val.jsonl)
"""
import os
import sys
import time
import json
from pathlib import Path
from typing import List, Tuple, Dict
import cv2
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import jiwer

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent

# -----------------------------------------------------------------------------
# 1. VOCABULARY & TOKENIZER
# -----------------------------------------------------------------------------
class BengaliCTCCharTokenizer:
    def __init__(self, vocab_file: Path):
        self.blank_token = "<BLANK>"
        self.blank_idx = 0
        self.char_to_idx = {self.blank_token: self.blank_idx}
        self.idx_to_char = {self.blank_idx: self.blank_token}

        with open(vocab_file, "r", encoding="utf-8") as f:
            stats = json.load(f)
            chars = stats.get("vocabulary_sample", [])

        # Assign indices 1, 2, ...
        idx = 1
        for ch in chars:
            if ch not in self.char_to_idx:
                self.char_to_idx[ch] = idx
                self.idx_to_char[idx] = ch
                idx += 1

        self.vocab_size = len(self.char_to_idx)

    def encode(self, text: str) -> List[int]:
        encoded = []
        for ch in text:
            if ch in self.char_to_idx:
                encoded.append(self.char_to_idx[ch])
        return encoded

    def decode_greedy(self, indices: List[int]) -> str:
        """CTC greedy collapse: remove consecutive repeats, then drop blank (0)."""
        collapsed = []
        prev = None
        for idx in indices:
            if idx != prev:
                collapsed.append(idx)
                prev = idx
        decoded_chars = [self.idx_to_char[idx] for idx in collapsed if idx != self.blank_idx and idx in self.idx_to_char]
        return "".join(decoded_chars)

    def save(self, out_file: Path):
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump({
                "vocab_size": self.vocab_size,
                "blank_idx": self.blank_idx,
                "char_to_idx": self.char_to_idx,
                "idx_to_char": {str(k): v for k, v in self.idx_to_char.items()}
            }, f, indent=2, ensure_ascii=False)

# -----------------------------------------------------------------------------
# 2. DATASET & PREPROCESSING
# -----------------------------------------------------------------------------
class BNHTRdDataset(Dataset):
    def __init__(self, jsonl_path: Path, tokenizer: BengaliCTCCharTokenizer, max_samples: int = 500, img_h: int = 32, img_w: int = 256):
        self.img_h = img_h
        self.img_w = img_w
        self.tokenizer = tokenizer
        self.samples = []

        if jsonl_path.exists():
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        p = WORKSPACE_ROOT / data["image_path"]
                        if p.exists() and len(data.get("ground_truth_text", "").strip()) > 0:
                            self.samples.append({
                                "img_path": str(p),
                                "text": data["ground_truth_text"].strip()
                            })
        if max_samples and max_samples > 0:
            self.samples = self.samples[:max_samples]

    def __len__(self):
        return len(self.samples)

    def preprocess_image(self, img_path: str) -> np.ndarray:
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            img = np.zeros((self.img_h, self.img_w), dtype=np.uint8)

        # Aspect ratio preserving resize
        h, w = img.shape
        scale = min(self.img_h / max(1, h), self.img_w / max(1, w))
        nw = max(1, int(w * scale))
        nh = max(1, int(h * scale))
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)

        # Pad with white (255)
        canvas = np.ones((self.img_h, self.img_w), dtype=np.uint8) * 255
        canvas[:nh, :nw] = resized

        # Normalize to [-1, 1]
        norm = (canvas.astype(np.float32) / 127.5) - 1.0
        return np.expand_dims(norm, axis=0)  # (1, H, W)

    def __getitem__(self, idx):
        item = self.samples[idx]
        img_tensor = torch.from_numpy(self.preprocess_image(item["img_path"]))
        target_ids = self.tokenizer.encode(item["text"])
        if len(target_ids) == 0:
            target_ids = [self.tokenizer.blank_idx]
        return img_tensor, torch.tensor(target_ids, dtype=torch.long), item["text"]

def collate_fn_ctc(batch):
    imgs, targets, texts = zip(*batch)
    imgs = torch.stack(imgs, 0)
    target_lengths = torch.tensor([len(t) for t in targets], dtype=torch.long)
    targets_flat = torch.cat(targets, 0)
    return imgs, targets_flat, target_lengths, texts

# -----------------------------------------------------------------------------
# 3. CRNN ARCHITECTURE
# -----------------------------------------------------------------------------
class BhumiLensCRNN(nn.Module):
    def __init__(self, vocab_size: int, hidden_size: int = 128):
        super().__init__()
        # CNN Feature Extractor
        self.cnn = nn.Sequential(
            # Stage 1: (1, 32, 256) -> (32, 16, 128)
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            # Stage 2: (32, 16, 128) -> (64, 8, 64)
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            # Stage 3: (64, 8, 64) -> (128, 4, 64)
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d((2, 1), (2, 1)),

            # Stage 4: (128, 4, 64) -> (256, 1, 64)
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d((4, 1), (4, 1)),
        )

        # Sequence Modeler (BiLSTM)
        self.rnn = nn.LSTM(
            input_size=256,
            hidden_size=hidden_size,
            num_layers=2,
            bidirectional=True,
            batch_first=False,
            dropout=0.1
        )

        # Output Classifier
        self.fc = nn.Linear(hidden_size * 2, vocab_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, 1, 32, 256)
        features = self.cnn(x)  # (B, 256, 1, 64)
        features = features.squeeze(2)  # (B, 256, 64)
        # Permute to (T=64, B, C=256) for LSTM
        seq = features.permute(2, 0, 1)
        rnn_out, _ = self.rnn(seq)  # (T=64, B, hidden*2)
        logits = self.fc(rnn_out)  # (T=64, B, vocab_size)
        log_probs = nn.functional.log_softmax(logits, dim=2)
        return log_probs

# -----------------------------------------------------------------------------
# 4. TRAINING & EVALUATION LOOP
# -----------------------------------------------------------------------------
def train_pilot():
    print("=" * 75)
    print("  BHUMILENS AI — CUSTOM BENGALI HTR PILOT EXPERIMENT (BN-HTRd)")
    print("=" * 75)

    # Device selection: Apple Silicon MPS if available
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Active Compute Device: {device} (Apple Metal Performance Shaders)")

    # Load Tokenizer
    vocab_file = WORKSPACE_ROOT / "research" / "datasets" / "splits" / "bn_htrd" / "splits_statistics.json"
    tokenizer = BengaliCTCCharTokenizer(vocab_file)
    print(f"Loaded Tokenizer: {tokenizer.vocab_size} grapheme tokens (Blank index: {tokenizer.blank_idx})")

    # Datasets
    train_split = WORKSPACE_ROOT / "research" / "datasets" / "splits" / "bn_htrd" / "train.jsonl"
    val_split = WORKSPACE_ROOT / "research" / "datasets" / "splits" / "bn_htrd" / "val.jsonl"

    train_ds = BNHTRdDataset(train_split, tokenizer, max_samples=400)
    val_ds = BNHTRdDataset(val_split, tokenizer, max_samples=100)
    print(f"Pilot Dataset: {len(train_ds)} train samples, {len(val_ds)} validation samples.")

    train_loader = DataLoader(train_ds, batch_size=8, shuffle=True, collate_fn=collate_fn_ctc)
    val_loader = DataLoader(val_ds, batch_size=8, shuffle=False, collate_fn=collate_fn_ctc)

    # Model & Loss
    model = BhumiLensCRNN(vocab_size=tokenizer.vocab_size, hidden_size=128).to(device)
    criterion = nn.CTCLoss(blank=tokenizer.blank_idx, zero_infinity=True)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    EPOCHS = 6
    history = []
    best_val_cer = 1.0
    models_dir = WORKSPACE_ROOT / "models" / "htr"
    models_dir.mkdir(parents=True, exist_ok=True)
    best_ckpt_path = models_dir / "bhumilens_htr_v1_pilot.pt"

    print("\nStarting pilot training...")
    t_start = time.time()

    for epoch in range(1, EPOCHS + 1):
        model.train()
        train_loss = 0.0
        n_train_batches = 0

        for imgs, targets_flat, target_lengths, _ in train_loader:
            imgs = imgs.to(device)
            targets_flat = targets_flat.to(device)
            target_lengths = target_lengths.to(device)
            batch_size = imgs.size(0)

            optimizer.zero_grad()
            log_probs = model(imgs)  # (T=64, B, V)
            T = log_probs.size(0)
            input_lengths = torch.full((batch_size,), T, dtype=torch.long, device=device)

            loss = criterion(log_probs, targets_flat, input_lengths, target_lengths)
            if not torch.isnan(loss) and not torch.isinf(loss):
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
                optimizer.step()
                train_loss += loss.item()
                n_train_batches += 1

        avg_train_loss = train_loss / max(1, n_train_batches)

        # Validation
        model.eval()
        val_loss = 0.0
        n_val_batches = 0
        val_refs = []
        val_hyps = []

        with torch.no_grad():
            for imgs, targets_flat, target_lengths, texts in val_loader:
                imgs = imgs.to(device)
                targets_flat = targets_flat.to(device)
                target_lengths = target_lengths.to(device)
                batch_size = imgs.size(0)

                log_probs = model(imgs)
                T = log_probs.size(0)
                input_lengths = torch.full((batch_size,), T, dtype=torch.long, device=device)

                loss = criterion(log_probs, targets_flat, input_lengths, target_lengths)
                if not torch.isnan(loss) and not torch.isinf(loss):
                    val_loss += loss.item()
                    n_val_batches += 1

                # Greedy CTC decoding
                preds = log_probs.argmax(dim=2).permute(1, 0).cpu().numpy()  # (B, T)
                for b in range(batch_size):
                    decoded_text = tokenizer.decode_greedy(preds[b].tolist())
                    val_hyps.append(decoded_text if decoded_text else "empty")
                    val_refs.append(texts[b] if texts[b] else "empty")

        avg_val_loss = val_loss / max(1, n_val_batches)
        epoch_cer = float(jiwer.cer(val_refs, val_hyps)) if val_refs else 1.0

        history.append({
            "epoch": epoch,
            "train_loss": round(avg_train_loss, 4),
            "val_loss": round(avg_val_loss, 4),
            "val_cer": round(epoch_cer, 4)
        })

        print(f"Epoch {epoch}/{EPOCHS} | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f} | Val CER: {epoch_cer * 100:.2f}%")

        if epoch_cer < best_val_cer or epoch == EPOCHS:
            best_val_cer = epoch_cer
            torch.save(model.state_dict(), str(best_ckpt_path))

    training_duration_s = round(time.time() - t_start, 2)
    print("-" * 75)
    print(f"Pilot training finished in {training_duration_s}s. Best Val CER: {best_val_cer * 100:.2f}%.")
    print(f"Saved checkpoint: {best_ckpt_path}")

    # Save Tokenizer & Metrics
    tokenizer_path = models_dir / "vocab.json"
    tokenizer.save(tokenizer_path)

    metrics_path = models_dir / "training_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump({
            "model_name": "BhumiLens-HTR-v1-pilot",
            "architecture": "CRNN (CNN + BiLSTM + CTC)",
            "device": str(device),
            "epochs": EPOCHS,
            "training_duration_seconds": training_duration_s,
            "best_val_cer": round(best_val_cer, 4),
            "epoch_history": history
        }, f, indent=2)

    # -------------------------------------------------------------------------
    # 5. HELD-OUT TEST EVALUATION & COMPARISON
    # -------------------------------------------------------------------------
    print("\nEvaluating BhumiLens-HTR-v1-pilot on 50 held-out test samples...")
    test_split = WORKSPACE_ROOT / "research" / "datasets" / "splits" / "bn_htrd" / "test.jsonl"
    test_ds = BNHTRdDataset(test_split, tokenizer, max_samples=50)
    test_loader = DataLoader(test_ds, batch_size=1, shuffle=False)

    model.load_state_dict(torch.load(str(best_ckpt_path), map_location=device))
    model.eval()

    test_refs = []
    test_hyps = []
    test_latencies = []

    with torch.no_grad():
        for i, (img, _, text) in enumerate(test_loader, start=1):
            img = img.to(device)
            t0 = time.perf_counter()
            log_probs = model(img)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            test_latencies.append(elapsed_ms)

            pred_indices = log_probs.argmax(dim=2).squeeze(1).cpu().numpy().tolist()
            pred_text = tokenizer.decode_greedy(pred_indices)

            test_hyps.append(pred_text if pred_text else "empty")
            test_refs.append(text[0] if text[0] else "empty")

    pilot_cer = float(jiwer.cer(test_refs, test_hyps))
    pilot_wer = float(jiwer.wer(test_refs, test_hyps))
    pilot_latency = float(np.mean(test_latencies)) if test_latencies else 0.0

    print("-" * 75)
    print("HELD-OUT TEST SPLIT EVALUATION RESULTS:")
    print(f"  -> Model:           BhumiLens-HTR-v1-pilot")
    print(f"  -> Test CER:        {pilot_cer * 100:.2f}% (CER = {pilot_cer:.4f})")
    print(f"  -> Test WER:        {pilot_wer * 100:.2f}% (WER = {pilot_wer:.4f})")
    print(f"  -> Average Latency: {pilot_latency:.2f} ms per line")
    print("=" * 75)

    # Save Comparison Report
    eval_json = WORKSPACE_ROOT / "research" / "htr" / "pilot_evaluation_results.json"
    with open(eval_json, "w", encoding="utf-8") as f:
        json.dump({
            "model": "BhumiLens-HTR-v1-pilot",
            "test_sample_count": len(test_refs),
            "test_cer": round(pilot_cer, 4),
            "test_wer": round(pilot_wer, 4),
            "average_latency_ms": round(pilot_latency, 2),
            "samples_evaluated": len(test_refs)
        }, f, indent=2)

if __name__ == "__main__":
    train_pilot()
