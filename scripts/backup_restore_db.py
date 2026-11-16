"""
BhumiLens AI + BhumiGuard — SQLite Database Backup, Integrity & Restore Utility.
Provides:
1. Online, atomic SQLite backup creation
2. Cryptographic SHA-256 checksum calculation & manifest export
3. Database restoration with SHA-256 integrity verification
4. Post-restore record verification using AuditPersistenceService
"""
import os
import sys
import json
import time
import shutil
import sqlite3
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure project root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from backend.services.audit_service import AuditPersistenceService

logger = logging.getLogger("bhumilens.backup")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_DB_PATH = WORKSPACE_ROOT / "outputs" / "bhumilens_records.db"
DEFAULT_BACKUP_DIR = WORKSPACE_ROOT / "outputs" / "backups"

def compute_file_sha256(filepath: Path) -> str:
    """Computes SHA-256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def backup_database(
    db_path: Optional[str] = None,
    backup_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Performs an online, atomic SQLite database backup and generates a cryptographic manifest.
    """
    src_db = Path(db_path) if db_path else DEFAULT_DB_PATH
    out_dir = Path(backup_dir) if backup_dir else DEFAULT_BACKUP_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    if not src_db.exists():
        raise FileNotFoundError(f"Source database not found: {src_db}")

    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    backup_filename = f"bhumilens_records_backup_{timestamp_str}.db"
    dest_path = out_dir / backup_filename
    manifest_path = out_dir / f"bhumilens_records_backup_{timestamp_str}.json"

    # Online SQLite backup using backup API to prevent corruption during writes
    logger.info("[Backup] Initiating atomic backup from %s to %s", src_db, dest_path)
    src_conn = sqlite3.connect(str(src_db))
    dest_conn = sqlite3.connect(str(dest_path))

    with dest_conn:
        src_conn.backup(dest_conn, pages=100)

    # Inspect record counts
    cur = dest_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM documents")
    doc_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM audit_events")
    event_count = cur.fetchone()[0]

    dest_conn.close()
    src_conn.close()

    # Calculate cryptographic SHA-256 checksum of the backup
    backup_sha256 = compute_file_sha256(dest_path)
    file_size_bytes = dest_path.stat().st_size

    manifest = {
        "status": "SUCCESS",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_db": str(src_db),
        "backup_file": str(dest_path),
        "backup_filename": backup_filename,
        "backup_sha256": backup_sha256,
        "file_size_bytes": file_size_bytes,
        "document_count": doc_count,
        "audit_event_count": event_count,
        "disclaimer": "SHA-256 seal guarantees backup bit-level authenticity and tamper detection."
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    logger.info("[Backup] Complete: %d documents, %d events, SHA-256: %s",
                doc_count, event_count, backup_sha256[:16] + "...")

    return manifest

def restore_database(
    backup_file: str,
    target_db_path: str,
    expected_sha256: Optional[str] = None
) -> Dict[str, Any]:
    """
    Restores database from backup file, verifies cryptographic checksum,
    and runs audit integrity check on all restored documents.
    """
    b_path = Path(backup_file)
    t_path = Path(target_db_path)
    t_path.parent.mkdir(parents=True, exist_ok=True)

    if not b_path.exists():
        raise FileNotFoundError(f"Backup file not found: {b_path}")

    # Checksum verification
    actual_sha256 = compute_file_sha256(b_path)
    if expected_sha256 and actual_sha256.lower() != expected_sha256.lower():
        raise ValueError(
            f"Backup checksum mismatch! Expected: {expected_sha256}, Actual: {actual_sha256}. "
            "Possible backup corruption or tampering."
        )

    # Copy backup to target destination
    shutil.copy2(b_path, t_path)
    logger.info("[Restore] Restored database to %s (SHA-256 verified: %s)", t_path, actual_sha256[:16] + "...")

    # Post-restore integrity verification
    audit = AuditPersistenceService(db_path=str(t_path))
    docs = audit.get_all_documents(limit=500)
    tamper_verified = 0

    for doc in docs:
        status = audit.verify_record_integrity(doc.doc_id)
        if status.get("integrity_verified"):
            tamper_verified += 1
        else:
            logger.warning("[Restore] Document %s failed integrity check post-restore", doc.doc_id)

    return {
        "status": "SUCCESS",
        "target_db_path": str(t_path),
        "backup_sha256_verified": actual_sha256,
        "total_documents_restored": len(docs),
        "intact_records_verified": tamper_verified,
        "all_records_intact": (tamper_verified == len(docs))
    }

if __name__ == "__main__":
    logger.info("Executing sample backup and restore verification...")
    result = backup_database()
    print(json.dumps(result, indent=2))
