#!/usr/bin/env python3
"""
BhumiLens AI - ML Environment & Hardware Verification Script
Checks Python, PyTorch, Apple Silicon MPS acceleration, and disk space.
"""
import sys
import shutil
import platform

def verify():
    print("=" * 65)
    print("  BHUMILENS AI — ML ENVIRONMENT & MPS VERIFICATION")
    print("=" * 65)

    # 1. Platform & Python Info
    print(f"OS Platform        : {platform.system()} ({platform.release()})")
    print(f"Machine Arch       : {platform.machine()} ({platform.processor()})")
    print(f"Python Executable  : {sys.executable}")
    print(f"Python Version     : {sys.version.split()[0]}")

    # 2. PyTorch & Apple Silicon MPS Check
    try:
        import torch
        print(f"PyTorch Version    : {torch.__version__}")
        print(f"PyTorch MPS Built  : {torch.backends.mps.is_built()}")
        print(f"PyTorch MPS Active : {torch.backends.mps.is_available()}")

        if torch.backends.mps.is_available():
            # Quick tensor compute test on MPS
            device = torch.device("mps")
            x = torch.ones(5, 5, device=device)
            y = x * 2
            print(f"MPS Compute Test   : SUCCESS (Allocated {y.device} tensor)")
        else:
            print("MPS Compute Test   : SKIPPED (MPS not available)")
    except ImportError as e:
        print(f"PyTorch Import Err : {e}")

    # 3. Core Libraries Check
    libraries = [
        ("torchvision", "torchvision"),
        ("torchaudio", "torchaudio"),
        ("transformers", "transformers"),
        ("accelerate", "accelerate"),
        ("datasets", "datasets"),
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("pydantic", "pydantic"),
        ("cv2", "opencv-python-headless"),
        ("PIL", "pillow"),
        ("fitz", "pymupdf"),
        ("numpy", "numpy"),
        ("pandas", "pandas"),
        ("sklearn", "scikit-learn"),
        ("pytest", "pytest"),
        ("httpx", "httpx")
    ]

    print("-" * 65)
    print("Core Dependencies Check:")
    for mod_name, pkg_name in libraries:
        try:
            mod = __import__(mod_name)
            ver = getattr(mod, "__version__", "installed")
            print(f"  [PASS] {pkg_name:<24}: {ver}")
        except ImportError:
            print(f"  [WAIT] {pkg_name:<24}: not installed yet")

    # 4. Storage Space Check
    total, used, free = shutil.disk_usage(".")
    print("-" * 65)
    print(f"Disk Total Space   : {total / (1024**3):.2f} GiB")
    print(f"Disk Used Space    : {used / (1024**3):.2f} GiB")
    print(f"Disk Free Space    : {free / (1024**3):.2f} GiB")
    print("=" * 65)

if __name__ == "__main__":
    verify()
