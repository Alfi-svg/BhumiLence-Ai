#!/usr/bin/env bash
# ==============================================================================
# BhumiLens AI + BhumiGuard — Production One-Click System Launcher
# ==============================================================================
# Environment: Apple Silicon M2 (arm64, macOS) | Python 3.11.17 | Offline-Ready
# Usage: ./run_bhumilens.sh [--port 8000] [--reload]
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=============================================================================="
echo "    BHUMILENS AI + BHUMIGUARD — LAND DOCUMENT INTELLIGENCE SYSTEM"
echo "        Offline GovTech Land Record Verification & Anomaly Detection"
echo "=============================================================================="

# 1. Check Python ML Virtual Environment
VENV_PATH="$SCRIPT_DIR/.venv_ml"
if [ ! -d "$VENV_PATH" ]; then
    echo "  [✗] ERROR: Python 3.11 virtual environment not found at .venv_ml"
    echo "      Please ensure .venv_ml is configured before running."
    exit 1
fi

echo "  [1/4] Activating Python 3.11 ML Environment (.venv_ml)..."
source "$VENV_PATH/bin/activate"

# 2. System Hardware & Apple Silicon MPS Check
echo "  [2/4] Verifying Hardware & Apple Silicon MPS Acceleration..."
python3 -c "
import sys, torch
print(f'        - Python Version: {sys.version.split()[0]}')
print(f'        - PyTorch Version: {torch.__version__}')
mps_status = 'AVAILABLE (Apple Metal Acceleration Enabled)' if torch.backends.mps.is_available() else 'UNAVAILABLE (CPU Fallback)'
print(f'        - Apple MPS:      {mps_status}')
"

# 3. Model Weights & Offline Directory Verification
echo "  [3/4] Checking Offline Model Weights & Assets..."
python3 -c "
from pathlib import Path
models = [
    ('models/htr/pretrained_baseline', 'EasyOCR Baseline Weights'),
    ('models/extractor/qwen3-0.6b-deed-lora', 'Qwen3-0.6B LoRA Checkpoint'),
    ('models/embeddings/multilingual-e5-small', 'Multilingual-E5 Embeddings'),
    ('frontend/index.html', 'Zero-Bloat Workbench UI')
]
for path_str, desc in models:
    p = Path(path_str)
    status = 'FOUND' if p.exists() else 'MISSING (Check assets)'
    print(f'        - {desc:32s}: [{status}]')
"

# 4. Enforce Air-Gapped / Offline Runtime Flags
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export PYTHONUNBUFFERED=1

echo "  [4/4] Starting Unified FastAPI Backend & Full-Stack Workbench UI..."
echo "------------------------------------------------------------------------------"
echo "  -> Workbench Web UI:    http://127.0.0.1:8000/"
echo "  -> Alternative UI URL:  http://127.0.0.1:8000/workbench"
echo "  -> Interactive OpenAPI: http://127.0.0.1:8000/docs"
echo "  -> System Health:       http://127.0.0.1:8000/health"
echo "------------------------------------------------------------------------------"
echo "  Press Ctrl+C to stop the server."
echo "=============================================================================="

exec uvicorn backend.main:app --host 127.0.0.1 --port 8000 "$@"
