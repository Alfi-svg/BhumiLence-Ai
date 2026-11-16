"""
BhumiLens AI + BhumiGuard — End-to-End System Memory & Latency Benchmark.
Measures:
1. Peak RSS RAM Usage (MB) across 6-agent sequential execution on Apple Silicon M2
2. Stage-by-stage latencies (ms) and throughput
3. Strict offline validation (HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1)
4. Exports benchmark report to outputs/benchmarks/benchmark_e2e_results.json
"""
import os
import sys
import time
import json
import resource
import platform
import logging
from pathlib import Path

# Enforce strict offline execution before any ML imports
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

import torch
from backend.agents.supervisor import BhumiLensSupervisor
from backend.agents.knowledge_audit_agent import KnowledgeAuditAgent
from backend.services.security_service import SecurityGuardService
from scripts.backup_restore_db import backup_database, restore_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bhumilens.benchmark")

BENCHMARK_IMAGE = WORKSPACE_ROOT / "sample_data" / "sample_dolil_100_anonymized.jpg"
BENCHMARK_OUTPUT = WORKSPACE_ROOT / "outputs" / "benchmarks" / "benchmark_e2e_results.json"

def get_current_rss_mb() -> float:
    """Returns current process Resident Set Size (RSS) memory in Megabytes."""
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == "Darwin":
        # macOS ru_maxrss returns bytes
        return usage / (1024.0 * 1024.0)
    else:
        # Linux ru_maxrss returns kilobytes
        return usage / 1024.0

def run_e2e_benchmark():
    logger.info("=================================================================")
    logger.info(" BHUMILENS AI + BHUMIGUARD — E2E SYSTEM BENCHMARK (PHASE 10)")
    logger.info("=================================================================")
    logger.info("Platform: %s (%s)", platform.platform(), platform.machine())
    logger.info("Python: %s | PyTorch: %s", platform.python_version(), torch.__version__)
    logger.info("Apple Silicon MPS Available: %s", torch.backends.mps.is_available())
    logger.info("Strict Offline Mode: HF_HUB_OFFLINE=%s, TRANSFORMERS_OFFLINE=%s",
                os.environ.get("HF_HUB_OFFLINE"), os.environ.get("TRANSFORMERS_OFFLINE"))

    initial_ram_mb = get_current_rss_mb()
    logger.info("Initial Baseline Process RAM: %.2f MB", initial_ram_mb)

    # 1. Initialize Supervisor (Agents 1-5 + Layer 7)
    t_init_start = time.perf_counter()
    supervisor = BhumiLensSupervisor()
    knowledge_agent = KnowledgeAuditAgent()
    init_latency_ms = (time.perf_counter() - t_init_start) * 1000.0
    post_init_ram_mb = get_current_rss_mb()
    logger.info("Supervisor & Agents Initialized in %.2f ms | RAM: %.2f MB", init_latency_ms, post_init_ram_mb)

    # 2. Run Complete End-to-End Pipeline
    if not BENCHMARK_IMAGE.exists():
        raise FileNotFoundError(f"Benchmark sample deed not found: {BENCHMARK_IMAGE}")

    t_pipeline_start = time.perf_counter()
    pipeline_res = supervisor.process_document(
        image_path=str(BENCHMARK_IMAGE),
        doc_id="BENCHMARK_DOLIL_E2E",
        actor_id="E2E_BENCHMARK_OPERATOR"
    )
    total_pipeline_ms = (time.perf_counter() - t_pipeline_start) * 1000.0
    post_pipeline_ram_mb = get_current_rss_mb()

    latencies = pipeline_res.get("stage_latencies_ms", {})
    logger.info("-----------------------------------------------------------------")
    logger.info(" Stage Latency Breakdown (Sequential 6-Agent Execution):")
    logger.info("   1. Stage 1 (Vision & Evidence Crops): %.2f ms", latencies.get("stage_1_vision_ms", 0.0))
    logger.info("   2. Stage 2 (Bengali HTR Line Inference): %.2f ms", latencies.get("stage_2_htr_ms", 0.0))
    logger.info("   3. Stage 3 (Normalization & SLM Extraction): %.2f ms", latencies.get("stage_3_extraction_ms", 0.0))
    logger.info("   4. Stage 4 (Deterministic Math & 16-Ana): %.2f ms", latencies.get("stage_4_verification_ms", 0.0))
    logger.info("   5. Stage 5 (BhumiGuard Duplicate & Anomaly): %.2f ms", latencies.get("stage_5_bhumiguard_ms", 0.0))
    logger.info("   6. Stage 6 (Audit Ledger & SHA-256 Seal): %.2f ms", latencies.get("stage_6_audit_persistence_ms", 0.0))
    logger.info("   -> Total Pipeline Latency: %.2f ms (%.2f s)", total_pipeline_ms, total_pipeline_ms / 1000.0)

    # 3. Knowledge Assistant (RAG Agent 6) Query Benchmark
    t_rag_start = time.perf_counter()
    rag_query = "সাফ কবলা ও বায়নাপত্রের পার্থক্য কী?"
    rag_res = knowledge_agent.ask_land_knowledge(rag_query, top_k=2)
    rag_latency_ms = (time.perf_counter() - t_rag_start) * 1000.0
    post_rag_ram_mb = get_current_rss_mb()
    logger.info("   7. Stage 7 (RAG Knowledge Assistant Query): %.2f ms | Citations: %d",
                rag_latency_ms, len(rag_res.citations))

    # 4. Database Backup & Restore Integrity Benchmark
    t_backup_start = time.perf_counter()
    backup_manifest = backup_database()
    backup_latency_ms = (time.perf_counter() - t_backup_start) * 1000.0

    t_restore_start = time.perf_counter()
    restore_target = WORKSPACE_ROOT / "outputs" / "backups" / "temp_verified_restore.db"
    restore_res = restore_database(
        backup_file=backup_manifest["backup_file"],
        target_db_path=str(restore_target),
        expected_sha256=backup_manifest["backup_sha256"]
    )
    restore_latency_ms = (time.perf_counter() - t_restore_start) * 1000.0
    if restore_target.exists():
        restore_target.unlink()

    logger.info("   8. Database Backup & SHA-256 Verified Restore: %.2f ms + %.2f ms",
                backup_latency_ms, restore_latency_ms)

    peak_ram_mb = get_current_rss_mb()
    ram_delta_mb = peak_ram_mb - initial_ram_mb

    # 5. Compile Benchmark Report
    report = {
        "benchmark_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "system": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "pytorch_version": torch.__version__,
            "apple_silicon_mps": torch.backends.mps.is_available(),
            "offline_mode_enforced": True,
            "macbook_air_m2_16gb_budget": True
        },
        "memory_rss_mb": {
            "initial_baseline_mb": round(initial_ram_mb, 2),
            "post_init_mb": round(post_init_ram_mb, 2),
            "post_pipeline_mb": round(post_pipeline_ram_mb, 2),
            "peak_rss_mb": round(peak_ram_mb, 2),
            "memory_delta_mb": round(ram_delta_mb, 2),
            "within_16gb_budget": peak_ram_mb < 8192.0  # Well below 8GB threshold
        },
        "stage_latencies_ms": {
            "stage_1_vision_ms": latencies.get("stage_1_vision_ms", 0.0),
            "stage_2_htr_ms": latencies.get("stage_2_htr_ms", 0.0),
            "stage_3_extraction_ms": latencies.get("stage_3_extraction_ms", 0.0),
            "stage_4_verification_ms": latencies.get("stage_4_verification_ms", 0.0),
            "stage_5_bhumiguard_ms": latencies.get("stage_5_bhumiguard_ms", 0.0),
            "stage_6_audit_persistence_ms": latencies.get("stage_6_audit_persistence_ms", 0.0),
            "stage_7_rag_query_ms": round(rag_latency_ms, 2),
            "db_backup_ms": round(backup_latency_ms, 2),
            "db_restore_ms": round(restore_latency_ms, 2),
            "total_e2e_pipeline_ms": round(total_pipeline_ms, 2)
        },
        "verification_results": {
            "pipeline_status": pipeline_res.get("status"),
            "pipeline_state": pipeline_res.get("pipeline_state"),
            "record_sha256": pipeline_res.get("record_sha256"),
            "bhumiguard_risk_level": pipeline_res.get("bhumiguard_report", {}).get("risk_level"),
            "bhumiguard_risk_score": pipeline_res.get("bhumiguard_report", {}).get("risk_score"),
            "rag_citations_count": len(rag_res.citations),
            "db_restore_all_intact": restore_res.get("all_records_intact")
        }
    }

    BENCHMARK_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(BENCHMARK_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info("-----------------------------------------------------------------")
    logger.info(" Peak RSS RAM: %.2f MB (< 16GB Budget: %s)", peak_ram_mb, report["memory_rss_mb"]["within_16gb_budget"])
    logger.info(" Benchmark JSON saved to: %s", BENCHMARK_OUTPUT)
    logger.info("=================================================================")
    return report

if __name__ == "__main__":
    run_e2e_benchmark()
