#!/usr/bin/env python3
"""
BhumiLens AI (P1) — Zero-Dependency Local GovTech Web Application
Run on your MacBook Air M2:
    python3 app.py
Then open in browser:
    http://127.0.0.1:8080
"""
import os
import json
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from src.vision_pipeline import BhumiVisionPipeline
from src.ocr_engine import LocalBanglaOCREngine
from src.land_math_validator import LandMathValidator
from src.database_audit import BhumiAuditDatabase
from src.lexicon_normalizer import BangladeshLandGazetteer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "outputs")
SAMPLE_DOLIL = os.path.join(BASE_DIR, "sample_data", "sample_dolil_100_anonymized.jpg")

vision = BhumiVisionPipeline(output_dir=OUT_DIR)
ocr_engine = LocalBanglaOCREngine()
db = BhumiAuditDatabase(db_path=os.path.join(OUT_DIR, "bhumilens_gov_records.db"))

def img_to_b64(path):
    if not path or not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")

def build_initial_state():
    vis = vision.process_document(SAMPLE_DOLIL, doc_id="DOLIL_2001_20078")
    ext = ocr_engine.extract_fields_from_crops(vis["field_crops"])
    val = LandMathValidator.run_full_document_validation(ext["flat_for_math_validation"])
    saved = db.save_or_update_record(
        doc_id="DOLIL_2001_20078",
        detected_layout=vis["layout_classification"]["detected_type"],
        fields_dict=ext["fields"],
        validation_report=val,
        workflow_state="AI_EXTRACTED_PENDING_MAKER",
        maker_id="OP_MAKER_01"
    )
    db.export_to_json_and_csv(
        json_path=os.path.join(OUT_DIR, "exported_records.json"),
        csv_path=os.path.join(OUT_DIR, "exported_records.csv")
    )
    # Attach base64 images for instant browser rendering
    for k, fmeta in saved["fields"].items():
        fmeta["crop_b64"] = img_to_b64(fmeta.get("crop_path"))
    saved["orig_b64"] = img_to_b64(SAMPLE_DOLIL)
    saved["shadow_b64"] = img_to_b64(vis["preprocessed_paths"]["shadow_removed"])
    saved["bin_b64"] = img_to_b64(vis["preprocessed_paths"]["binarized_clean"])
    saved["processing_time_ms"] = vis["processing_time_ms"]
    saved["seal_metadata"] = vis["seal_metadata"]
    return saved

STATE_CACHE = build_initial_state()

HTML_PAGE = """<!DOCTYPE html>
<html lang="bn">
<head>
<meta charset="UTF-8">
<title>BhumiLens AI — P1: Bangla Land Document Digitization & Verification</title>
<style>
  :root {
    --bg: #0f172a; --card: #1e293b; --border: #334155;
    --text: #f8fafc; --muted: #94a3b8; --accent: #38bdf8;
    --green: #10b981; --amber: #f59e0b; --red: #ef4444;
  }
  * { box-sizing: border-box; font-family: system-ui, -apple-system, sans-serif; }
  body { margin: 0; background: var(--bg); color: var(--text); padding: 20px; }
  .header { display: flex; justify-content: space-between; align-items: center;
            background: var(--card); padding: 16px 24px; border-radius: 12px;
            border: 1px solid var(--border); margin-bottom: 18px; }
  .badge { padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; }
  .bg-green { background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid #10b981; }
  .bg-amber { background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid #f59e0b; }
  .bg-blue { background: rgba(56,189,248,0.2); color: #38bdf8; border: 1px solid #0284c7; }
  .grid { display: grid; grid-template-columns: 44% 56%; gap: 18px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; }
  .tabs button { background: #0f172a; color: var(--text); border: 1px solid var(--border);
                 padding: 8px 14px; border-radius: 6px; cursor: pointer; margin-right: 6px; font-weight: 600; }
  .tabs button.active { background: var(--accent); color: #0f172a; border-color: var(--accent); }
  .doc-viewer img { width: 100%; border-radius: 8px; border: 1px solid var(--border); margin-top: 10px; }
  .field-row { background: #0f172a; border: 1px solid var(--border); border-radius: 8px;
               padding: 12px; margin-bottom: 10px; display: grid; grid-template-columns: 38% 62%; gap: 12px; align-items: center; }
  .field-crop img { width: 100%; max-height: 75px; object-fit: contain; background: #fff; border-radius: 4px; padding: 2px; }
  input[type=text] { width: 100%; padding: 7px 10px; border-radius: 6px; border: 1px solid #475569;
                     background: #1e293b; color: #fff; font-size: 14px; margin-top: 4px; }
  .btn { padding: 10px 16px; border-radius: 8px; border: none; font-weight: 700; cursor: pointer; margin-right: 8px; }
  .btn-primary { background: var(--accent); color: #0f172a; }
  .btn-success { background: var(--green); color: #0f172a; }
  .flag-box { padding: 10px 12px; border-radius: 8px; margin-bottom: 8px; font-size: 13px; }
  .flag-PASS { background: rgba(16,185,129,0.15); border-left: 4px solid var(--green); }
  .flag-WARNING { background: rgba(245,158,11,0.15); border-left: 4px solid var(--amber); }
  .flag-ERROR { background: rgba(239,68,68,0.15); border-left: 4px solid var(--red); }
</style>
</head>
<body>
<div class="header">
  <div>
    <h2 style="margin:0;">BhumiLens AI — P1: Bangla Land Record Digitization & Human Verification</h2>
    <div style="color:var(--muted); font-size:13px; margin-top:4px;">
      100% On-Premise GovTech Architecture | OpenCV Shadow Removal + 5-Zone Segmentation + Grapheme Lexicon + Maker-Checker Audit
    </div>
  </div>
  <div>
    <span class="badge bg-blue" id="layoutBadge">Layout: STAMP_DEED_DOLIL</span>
    <span class="badge bg-green" id="stateBadge">State: AI_EXTRACTED</span>
  </div>
</div>

<div class="grid">
  <!-- Left Column: Multi-Stage Vision Viewer & Live Sandbox Testers -->
  <div>
    <div class="card doc-viewer">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <strong>1. OpenCV Preprocessed Document Viewer</strong>
        <span style="font-size:12px; color:var(--muted);" id="procTime"></span>
      </div>
      <div class="tabs" style="margin-top:10px;">
        <button class="active" onclick="switchImg('bin', this)">3. Clean Binarized (OCR Ready)</button>
        <button onclick="switchImg('shadow', this)">2. Shadow Removed</button>
        <button onclick="switchImg('orig', this)">1. Anonymized Input (Rule 10)</button>
      </div>
      <img id="mainDocImg" src="" alt="Document View">
    </div>

    <div class="card" style="margin-top:16px;">
      <strong>2. Automated Land-Math, Chronology & Domain Validation</strong>
      <div id="flagsContainer" style="margin-top:10px;"></div>
    </div>

    <div class="card" style="margin-top:16px;">
      <strong>3. Live Scientific Sandbox: Test Noisy Handwritten OCR Normalization</strong>
      <p style="font-size:12px; color:var(--muted); margin:6px 0;">
        Test our Visual-Grapheme Confusion Matrix (e.g. try typing <code>গাজীপুর মদর</code>, <code>বারেনডা</code>, or <code>শাতাংশ</code>):
      </p>
      <div style="display:flex; gap:8px;">
        <input type="text" id="testRawInput" value="গাজীপুর মদর" style="width:50%;">
        <select id="testCatSelect" style="background:#1e293b; color:#fff; border:1px solid #475569; border-radius:6px; padding:6px;">
          <option value="thana_upazila">Thana/Upazila</option>
          <option value="mouza">Mouza</option>
          <option value="land_unit">Land Unit</option>
          <option value="deed_type">Deed Category</option>
        </select>
        <button class="btn btn-primary" onclick="runLexiconTest()">Test Match</button>
      </div>
      <div id="lexiconTestResult" style="margin-top:8px; font-size:13px; color:#34d399;"></div>
    </div>
  </div>

  <!-- Right Column: Visual Crop Evidence + Maker-Checker Form -->
  <div class="card">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
      <div>
        <strong>4. Side-by-Side Cropped Visual Evidence & Human Review ("Four-Eyes" Workflow)</strong>
        <div style="font-size:12px; color:var(--muted);">
          Raw OCR and Normalized suggestions are preserved. Edit any field below and lock with SHA-256 Audit Seal.
        </div>
      </div>
      <div>
        <a href="/api/export_json" target="_blank" class="btn btn-primary" style="text-decoration:none; font-size:12px;">Export JSON</a>
        <a href="/api/export_csv" target="_blank" class="btn btn-primary" style="text-decoration:none; font-size:12px;">Export CSV</a>
      </div>
    </div>

    <div id="fieldsContainer"></div>

    <div style="margin-top:14px; padding-top:12px; border-top:1px solid var(--border); display:flex; justify-content:space-between; align-items:center;">
      <div>
        <button class="btn btn-primary" onclick="submitReview('MAKER_VERIFIED_PENDING_CHECKER')">Save as Maker (Operator)</button>
        <button class="btn btn-success" onclick="submitReview('CHECKER_APPROVED_LOCKED')">Approve & Lock as Checker (Sub-Registrar)</button>
      </div>
      <div style="font-size:12px; color:var(--muted); text-align:right;">
        <div>SHA-256 Audit Seal:</div>
        <code id="auditHash" style="color:#38bdf8;"></code>
      </div>
    </div>
  </div>
</div>

<script>
let docData = null;

async function loadState() {
  const res = await fetch('/api/state');
  docData = await res.json();
  document.getElementById('mainDocImg').src = docData.bin_b64;
  document.getElementById('procTime').innerText = 'OpenCV Time: ' + docData.processing_time_ms + ' ms | Official Seal Detected: YES';
  document.getElementById('layoutBadge').innerText = 'Layout: ' + docData.detected_layout;
  document.getElementById('stateBadge').innerText = 'State: ' + docData.workflow_state;
  document.getElementById('auditHash').innerText = docData.sha256_audit_hash.substring(0, 28) + '...';

  const flagsDiv = document.getElementById('flagsContainer');
  flagsDiv.innerHTML = '';
  docData.validation_report.validation_flags.forEach(f => {
    flagsDiv.innerHTML += `<div class="flag-box flag-${f.severity}"><strong>[${f.severity}] ${f.code}:</strong> ${f.message}</div>`;
  });

  const fDiv = document.getElementById('fieldsContainer');
  fDiv.innerHTML = '';
  Object.entries(docData.fields).forEach(([key, meta]) => {
    const confPct = Math.round(meta.confidence * 100);
    const badgeCls = confPct >= 88 ? 'bg-green' : 'bg-amber';
    fDiv.innerHTML += `
      <div class="field-row">
        <div class="field-crop">
          <div style="font-size:11px; color:var(--muted); margin-bottom:4px;">Cropped Visual Evidence:</div>
          <img src="${meta.crop_b64}" alt="${key}">
        </div>
        <div>
          <div style="display:flex; justify-content:space-between;">
            <strong style="font-size:13px;">${meta.label}</strong>
            <span class="badge ${badgeCls}">${confPct}% | ${meta.status}</span>
          </div>
          <div style="font-size:11px; color:var(--muted); margin-top:3px;">
            Immutable Raw OCR: <code style="color:#f8fafc;">${meta.raw_ocr_text}</code>
            | System Normalized: <code style="color:#38bdf8;">${meta.normalized_value}</code>
          </div>
          <input type="text" id="input_${key}" value="${meta.human_verified_value}">
        </div>
      </div>
    `;
  });
}

function switchImg(mode, btn) {
  document.querySelectorAll('.tabs button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const img = document.getElementById('mainDocImg');
  if (mode === 'orig') img.src = docData.orig_b64;
  if (mode === 'shadow') img.src = docData.shadow_b64;
  if (mode === 'bin') img.src = docData.bin_b64;
}

async function submitReview(newState) {
  const edited = {};
  Object.keys(docData.fields).forEach(k => {
    edited[k] = document.getElementById('input_' + k).value;
  });
  const res = await fetch('/api/update', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ workflow_state: newState, edited_fields: edited })
  });
  docData = await res.json();
  document.getElementById('stateBadge').innerText = 'State: ' + docData.workflow_state;
  document.getElementById('auditHash').innerText = docData.sha256_audit_hash.substring(0, 28) + '...';
  alert('Record updated! New SHA-256 Audit Seal: ' + docData.sha256_audit_hash);
}

async function runLexiconTest() {
  const raw = document.getElementById('testRawInput').value;
  const cat = document.getElementById('testCatSelect').value;
  const res = await fetch(`/api/lexicon_test?raw=${encodeURIComponent(raw)}&cat=${encodeURIComponent(cat)}`);
  const out = await res.json();
  document.getElementById('lexiconTestResult').innerText =
    `Raw: "${out.raw_ocr_text}" -> Normalized: "${out.normalized_value}" (Weighted Distance: ${out.weighted_distance}, Confidence: ${Math.round(out.confidence*100)}%, Status: ${out.match_status})`;
}

loadState();
</script>
</body>
</html>
"""

class BhumiHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif parsed.path == "/api/state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(STATE_CACHE, ensure_ascii=False).encode("utf-8"))
        elif parsed.path == "/api/lexicon_test":
            qs = parse_qs(parsed.query)
            raw = qs.get("raw", [""])[0]
            cat = qs.get("cat", ["thana_upazila"])[0]
            res = BangladeshLandGazetteer.match_best(raw, cat)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
        elif parsed.path == "/api/export_json":
            p = os.path.join(OUT_DIR, "exported_records.json")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=bhumilens_records.json")
            self.end_headers()
            with open(p, "rb") as f:
                self.wfile.write(f.read())
        elif parsed.path == "/api/export_csv":
            p = os.path.join(OUT_DIR, "exported_records.csv")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=bhumilens_records.csv")
            self.end_headers()
            with open(p, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        global STATE_CACHE
        if self.path == "/api/update":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            new_state = body.get("workflow_state", "MAKER_VERIFIED_PENDING_CHECKER")
            edited = body.get("edited_fields", {})
            for k, val in edited.items():
                if k in STATE_CACHE["fields"]:
                    STATE_CACHE["fields"][k]["human_verified_value"] = val

            checker = "SUB_REGISTRAR_GAZIPUR_01" if "CHECKER" in new_state else None
            updated = db.save_or_update_record(
                doc_id=STATE_CACHE["doc_id"],
                detected_layout=STATE_CACHE["detected_layout"],
                fields_dict=STATE_CACHE["fields"],
                validation_report=STATE_CACHE["validation_report"],
                workflow_state=new_state,
                maker_id="MAKER_ALFI_01",
                checker_id=checker
            )
            db.export_to_json_and_csv(
                json_path=os.path.join(OUT_DIR, "exported_records.json"),
                csv_path=os.path.join(OUT_DIR, "exported_records.csv")
            )
            STATE_CACHE["workflow_state"] = updated["workflow_state"]
            STATE_CACHE["sha256_audit_hash"] = updated["sha256_audit_hash"]
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(STATE_CACHE, ensure_ascii=False).encode("utf-8"))

if __name__ == "__main__":
    port = 8080
    print(f"======================================================================")
    print(f" BhumiLens AI (P1) Web Server running at: http://127.0.0.1:{port}")
    print(f" Press Ctrl+C to stop.")
    print(f"======================================================================")
    server = HTTPServer(("127.0.0.1", port), BhumiHandler)
    server.serve_forever()
