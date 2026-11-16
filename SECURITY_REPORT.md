# BhumiLens AI + BhumiGuard — Enterprise GovTech Security Architecture & Hardening Report

**System Name:** BhumiLens AI + BhumiGuard  
**Version:** 1.0.0 (Phase 10 Hardened Release)  
**Security Classification:** GovTech Tier-2 / Land Record Critical  
**Environment:** Air-gapped / Local-First / macOS Apple Silicon (M2 Unified Memory)  
**Verification Date:** November 2026  

---

## 1. Executive Security Summary

BhumiLens AI + BhumiGuard processes sensitive, archaic, handwritten land deeds and mutation records within Bangladeshi land registries. Due to the high risk of property forgery, unauthorized document alteration, and cyber attacks on public land infrastructure, the system implements an enterprise-grade, defense-in-depth security model:

1. **Deterministic Binary Inspection (Magic Bytes):** Rejects disguised executables, scripts, and archives before file parsing or image decoding.
2. **Strict Filesystem Boundary Defense:** Neutralizes path-traversal payloads (`../`, `..\`) and null-byte injections.
3. **Resource Exhaustion Defense:** Enforces a strict 25 MB file size ceiling (HTTP 413) to prevent Denial-of-Service (DoS) and RAM exhaustion on 16 GB Apple Silicon M2.
4. **GovTech Four-Eyes Principle:** Enforces strict role and actor segregation (`maker_id != checker_id`) via API headers (`X-Actor-ID`, `X-Actor-Role`).
5. **PII Masking & Privacy Guard:** Automatically masks 10, 13, and 17-digit Bangladeshi National ID (NID) numbers and 11-digit mobile phone numbers in logs and exported manifests.
6. **Immutable Cryptographic Audit Trail:** Binds every stage of the document lifecycle to SHA-256 state seals with full tamper detection.
7. **Disaster Recovery & Hot Backup:** Atomic SQLite backup with cryptographic manifest verification ensuring zero write corruption.

---

## 2. Threat Modeling & Defense Matrix (STRIDE)

| Threat Category | Attack Vector | Potential Impact | BhumiLens Defense Mechanism | Verification Status |
|---|---|---|---|---|
| **Spoofing** | Attacker uploads malicious `.exe`, `.elf`, or `.php` disguised with `.png` extension. | Remote Code Execution (RCE) on host or image parser exploit. | Magic-byte file signature validation (`SecurityGuardService.validate_file_content`). Inspects binary headers against `DANGEROUS_MAGIC_PREFIXES`. | **Enforced & Tested (HTTP 400)** |
| **Tampering** | Operator alters extracted deed acreage or party names post-approval. | Land title fraud, boundary disputes. | SHA-256 cryptographic seal recalculated at each stage. Records locked with `RecordLockedException`. Periodic integrity audit. | **Enforced & Tested (HTTP 403)** |
| **Repudiation** | Operator denies reviewing a fraudulent deed. | Lack of accountability in government registry. | Maker-Checker audit ledger logs `actor_id`, `role`, `action`, UTC timestamp, and previous hash in an append-only SQLite store. | **Enforced & Tested** |
| **Information Disclosure** | Deed scans leaked via logs or exports revealing NID and phone numbers. | Citizen privacy violation, identity theft. | Recursive PII masker (`SecurityGuardService.mask_pii`) redacting NID digits (retaining last 4) and phone numbers (`017****5678`). | **Enforced & Tested** |
| **Denial of Service** | Uploading 500 MB zip bomb or oversized scan to crash Apple Silicon MPS. | Server crash, OOM kill, unresponsiveness. | 25 MB payload ceiling (`MAX_UPLOAD_SIZE_BYTES`) checked before memory buffering. Returns HTTP 413. | **Enforced & Tested (HTTP 413)** |
| **Elevation of Privilege** | Maker operator attempts to self-approve deed as Checker. | Bypassing land officer supervision. | Four-Eyes invariant (`checker_id != maker_id`) enforced at both service layer and route header layer (`X-Actor-Role: CHECKER`). | **Enforced & Tested (HTTP 400/403)** |

---

## 3. Security Service Implementation Details

### 3.1 Magic-Byte Signature Validation
Attackers frequently disguise malicious scripts or executable binaries by renaming them to innocent document extensions (e.g., `backdoor.php.png` or `exploit.exe.jpg`). BhumiLens refuses to trust file extensions alone.

```
Incoming Stream -> First 128 Bytes -> Match Dangerous Signatures (MZ, \x7fELF, PK\x03\x04, #!/, <?php, <script)
                                   -> If MATCH: Immediate HTTP 400 Rejection
                                   -> Else: Match Allowed Magic Bytes (\xff\xd8\xff, \x89PNG, %PDF-, II*\x00, MM\x00*)
                                   -> If NO MATCH: Immediate HTTP 400 Rejection
                                   -> If VALID: Accept & Proceed
```

### 3.2 Cross-Platform Path-Traversal Defense
Path traversal attacks using `../`, `..\\`, or URI-encoded sequences could allow attackers to write files outside the intended uploads directory:

```python
normalized = filename.replace("\\", "/")
base = os.path.basename(normalized)
base = Path(base).name
base = base.replace("\x00", "").replace("\r", "").replace("\n", "")
if ".." in base or "/" in base or "\\" in base:
    base = re.sub(r"\.\.+", "", base)
cleaned = re.sub(r"[^\w\.\-\u0980-\u09FF]", "_", base)
```
*Note:* Bengali Unicode characters (`\u0980-\u09FF`) are explicitly preserved so filenames like `দলিল_গাজীপুর_২০০১.png` remain legible and valid.

### 3.3 Four-Eyes Governance Separation
```
+--------------------------------------------------------------------------------+
|                             MAKER-CHECKER WORKFLOW                              |
+--------------------------------------------------------------------------------+
|  Stage 1: AI_EXTRACTED_PENDING_MAKER                                           |
|    - System extracts metadata via Qwen3-0.6B LoRA + OCR                         |
|    - SHA-256 seal initialized                                                   |
|                                                                                |
|  Stage 2: MAKER_VERIFIED_PENDING_CHECKER                                       |
|    - Human Operator (Role: MAKER, Header: X-Actor-Role: MAKER)                 |
|    - Inspects evidence crops, corrects fields                                  |
|    - Audit trail records: MAKER_SUBMITTED with maker_id                        |
|                                                                                |
|  Stage 3: CHECKER_APPROVED_LOCKED                                              |
|    - Supervisor (Role: CHECKER, Header: X-Actor-Role: CHECKER)                 |
|    - INVARIANT: checker_id CANNOT equal maker_id                               |
|    - Record is permanently frozen; any subsequent edit raises HTTP 403         |
+--------------------------------------------------------------------------------+
```

---

## 4. Cryptographic Proof vs Legal Authority Governance

A core ethical and legal rule of BhumiLens AI is that **AI software cannot approve a legal title**:

> **LEGAL AUTHORITY DISCLAIMER:**  
> The SHA-256 cryptographic seal proves data immutability and digital record integrity within BhumiLens AI. It certifies that the record has not been altered since human verification. **It does NOT constitute legal title, judicial deed validity, or state-sanctioned land ownership.** Legal ownership remains strictly under the jurisdiction of the Directorate of Registration and the Ministry of Land, Government of Bangladesh.

---

## 5. Hot Backup & Disaster Recovery Architecture

To ensure operational continuity in district sub-registry offices without dedicated DBAs:
- **Online Atomic Backup (`scripts/backup_restore_db.py`):** Utilizes SQLite's native `src_conn.backup(dest_conn, pages=100)` API. This guarantees a consistent snapshot even if concurrent reads or writes are active.
- **Cryptographic Manifest:** Every backup produces an accompanying `.json` manifest containing:
  - Exact file size and timestamp (UTC).
  - Number of documents and audit events archived.
  - Full 256-bit SHA-256 checksum of the backup file.
- **Tamper-Verified Restoration:** During restoration, the target file's SHA-256 is verified against the manifest before copying into the active database path. Any byte-level corruption aborts the restore operation immediately.
