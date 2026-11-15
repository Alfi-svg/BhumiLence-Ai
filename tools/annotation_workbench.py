#!/usr/bin/env python3
"""
BhumiLens AI — Local Human Annotation Workbench
FastAPI + Single-Page Interactive Web Application (Port 8090)
Enables side-by-side deed evidence inspection, transcription, and structured JSONL annotation.
Also includes CLI self-verification mode (--verify).
"""
import os
import sys
import json
import time
import base64
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.schemas.deed_schema import DeedExtractionSchema, DeedType, LandUnit

QUEUE_DIR = BASE_DIR / "research" / "datasets" / "processed" / "dolil_curation_queue"
ANNOTATIONS_DIR = BASE_DIR / "research" / "datasets" / "annotations"
ANNOTATIONS_DIR.mkdir(parents=True, exist_ok=True)
VERIFIED_JSONL = ANNOTATIONS_DIR / "dolil_human_verified.jsonl"

app = FastAPI(title="BhumiLens Human Annotation Workbench", version="1.0.0")

def img_to_base64(path_str: str) -> str:
    p = BASE_DIR / path_str if not os.path.isabs(path_str) else Path(path_str)
    if not p.exists():
        return ""
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    with open(p, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode("ascii")

def load_queue_index() -> List[Dict[str, Any]]:
    idx_file = QUEUE_DIR / "queue_index.json"
    if not idx_file.exists():
        return []
    with open(idx_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("documents", [])

def get_annotated_doc_ids() -> set:
    if not VERIFIED_JSONL.exists():
        return set()
    annotated = set()
    with open(VERIFIED_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    rec = json.loads(line)
                    annotated.add(rec.get("doc_id"))
                except Exception:
                    pass
    return annotated

class AnnotationSubmission(BaseModel):
    annotator_id: str
    doc_id: str
    deed_number: Optional[str] = None
    deed_year: Optional[int] = None
    deed_type: str = "UNKNOWN"
    mouza: Optional[str] = None
    thana_upazila: Optional[str] = None
    district: Optional[str] = None
    dag_numbers: List[str] = []
    khatian_numbers: List[str] = []
    land_area: Optional[float] = None
    land_unit: str = "SHOTOK"
    deed_value_bdt: Optional[float] = None
    stamp_duty_bdt: Optional[float] = None
    registration_date: Optional[str] = None
    copy_issue_date: Optional[str] = None
    field_transcriptions: Dict[str, str] = {}
    verified: bool = True
    notes: Optional[str] = None

@app.get("/api/queue")
async def get_queue():
    docs = load_queue_index()
    annotated = get_annotated_doc_ids()
    for d in docs:
        d["annotated"] = d["doc_id"] in annotated
    return {
        "total": len(docs),
        "annotated_count": len(annotated),
        "remaining_count": max(0, len(docs) - len(annotated)),
        "documents": docs
    }

@app.get("/api/document/{doc_id}")
async def get_document(doc_id: str):
    docs = load_queue_index()
    target = next((d for d in docs if d["doc_id"] == doc_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Document not found in curation queue")
    
    doc_copy = dict(target)
    doc_copy["preview_b64"] = img_to_base64(target["preview_path"])
    doc_copy["binarized_b64"] = img_to_base64(target["binarized_path"])
    doc_copy["crops_b64"] = {
        k: img_to_base64(v) for k, v in target["crop_fields"].items()
    }
    return doc_copy

@app.post("/api/annotate")
async def save_annotation(payload: AnnotationSubmission):
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    record = {
        "schema_version": "1.0.0",
        "doc_id": payload.doc_id,
        "annotator_id": payload.annotator_id,
        "timestamp": now_iso,
        "verified": True,
        "deed_number": payload.deed_number,
        "deed_year": payload.deed_year,
        "deed_type": payload.deed_type,
        "location": {
            "mouza": payload.mouza,
            "upazila": payload.thana_upazila,
            "district": payload.district
        },
        "land_details": {
            "dag_numbers": payload.dag_numbers,
            "khatian_numbers": payload.khatian_numbers,
            "land_area": payload.land_area,
            "land_unit": payload.land_unit
        },
        "financials": {
            "deed_value_bdt": payload.deed_value_bdt,
            "stamp_duty_bdt": payload.stamp_duty_bdt
        },
        "dates": {
            "registration_date": payload.registration_date,
            "copy_issue_date": payload.copy_issue_date
        },
        "field_transcriptions": payload.field_transcriptions,
        "notes": payload.notes
    }
    
    # Append to verified JSONL
    with open(VERIFIED_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        
    return {"status": "SUCCESS", "message": f"Annotation saved for {payload.doc_id}", "timestamp": now_iso}

@app.get("/api/annotations")
async def get_all_annotations():
    if not VERIFIED_JSONL.exists():
        return {"count": 0, "annotations": []}
    records = []
    with open(VERIFIED_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
    return {"count": len(records), "annotations": records}

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    html_content = """<!DOCTYPE html>
<html lang="bn">
<head>
<meta charset="UTF-8">
<title>BhumiLens AI — Local Human Annotation Workbench</title>
<style>
  :root {
    --bg: #0b1120; --card: #1e293b; --border: #334155;
    --text: #f8fafc; --muted: #94a3b8; --accent: #38bdf8;
    --green: #10b981; --amber: #f59e0b;
  }
  * { box-sizing: border-box; font-family: system-ui, -apple-system, sans-serif; }
  body { margin: 0; background: var(--bg); color: var(--text); display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
  .navbar { background: var(--card); border-bottom: 1px solid var(--border); padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; }
  .badge { padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; }
  .bg-green { background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid #10b981; }
  .bg-blue { background: rgba(56,189,248,0.2); color: #38bdf8; border: 1px solid #0284c7; }
  .workspace { display: grid; grid-template-columns: 240px 1fr 420px; flex: 1; overflow: hidden; }
  .queue-pane { background: #0f172a; border-right: 1px solid var(--border); overflow-y: auto; padding: 12px; }
  .q-item { padding: 8px 10px; border-radius: 6px; margin-bottom: 6px; cursor: pointer; font-size: 13px; border: 1px solid transparent; }
  .q-item:hover { background: #1e293b; }
  .q-item.active { background: #1e293b; border-color: var(--accent); font-weight: bold; }
  .center-viewer { overflow-y: auto; padding: 16px; display: flex; flex-direction: column; align-items: center; }
  .viewer-img { max-width: 100%; border-radius: 8px; border: 1px solid var(--border); box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
  .form-pane { background: var(--card); border-left: 1px solid var(--border); overflow-y: auto; padding: 16px; font-size: 13px; }
  .form-group { margin-bottom: 12px; }
  .form-group label { display: block; color: var(--muted); margin-bottom: 4px; font-size: 12px; }
  input[type=text], input[type=number], select, textarea {
    width: 100%; padding: 8px 10px; border-radius: 6px; border: 1px solid #475569;
    background: #0f172a; color: #fff; font-size: 13px;
  }
  .crops-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }
  .crop-card { background: #0f172a; border: 1px solid var(--border); border-radius: 6px; padding: 6px; }
  .crop-card img { width: 100%; max-height: 60px; object-fit: contain; background: #fff; border-radius: 4px; }
  .btn { padding: 10px 16px; border-radius: 6px; border: none; font-weight: 700; cursor: pointer; width: 100%; }
  .btn-primary { background: var(--accent); color: #0f172a; margin-top: 10px; }
  .virtual-keys button {
    background: #1e293b; color: #f8fafc; border: 1px solid var(--border);
    padding: 3px 6px; border-radius: 4px; font-size: 11px; cursor: pointer; margin: 2px;
  }
</style>
</head>
<body>
<div class="navbar">
  <div>
    <strong>BhumiLens AI — Local Human Annotation Workbench</strong>
    <span style="color:var(--muted); font-size:12px; margin-left:12px;">Port 8090 | Offline Ground-Truth Tool</span>
  </div>
  <div>
    <span class="badge bg-blue" id="progressBadge">Loading Queue...</span>
  </div>
</div>

<div class="workspace">
  <!-- Left: Document Queue -->
  <div class="queue-pane" id="queueList"></div>

  <!-- Center: Document Image & Previews -->
  <div class="center-viewer">
    <div style="margin-bottom:10px; display:flex; gap:8px;">
      <button class="badge bg-blue" onclick="switchView('preview')">Original Preview</button>
      <button class="badge bg-blue" onclick="switchView('binarized')">Clean Binarized</button>
    </div>
    <img id="mainImage" class="viewer-img" src="" alt="Deed View">
  </div>

  <!-- Right: Transcription & Structured Metadata Form -->
  <div class="form-pane">
    <h4 style="margin-top:0;" id="docTitle">Select a Deed</h4>

    <!-- Quick Bengali Characters -->
    <div style="margin-bottom:12px;">
      <span style="color:var(--muted); font-size:11px;">Quick Inserts:</span>
      <div class="virtual-keys">
        <button onclick="insertChar('০')">০</button><button onclick="insertChar('১')">১</button>
        <button onclick="insertChar('২')">২</button><button onclick="insertChar('৩')">৩</button>
        <button onclick="insertChar('৪')">৪</button><button onclick="insertChar('৫')">৫</button>
        <button onclick="insertChar('৬')">৬</button><button onclick="insertChar('৭')">৭</button>
        <button onclick="insertChar('৮')">৮</button><button onclick="insertChar('৯')">৯</button>
        <button onclick="insertChar('শতাংশ')">শতাংশ</button><button onclick="insertChar('কাঠা')">কাঠা</button>
        <button onclick="insertChar('আনা')">আনা</button><button onclick="insertChar('গন্ডা')">গন্ডা</button>
      </div>
    </div>

    <!-- Cropped Evidence Previews -->
    <div style="font-weight:600; font-size:12px; margin-bottom:6px;">8 Segmented Visual Crops:</div>
    <div class="crops-grid" id="cropsContainer"></div>

    <div class="form-group">
      <label>দলিল নম্বর (Deed Serial):</label>
      <input type="text" id="inputDeedNo" placeholder="যেমন: ২০০৭৮">
    </div>
    <div class="form-group">
      <label>সাল (Year):</label>
      <input type="number" id="inputYear" placeholder="যেমন: ২০০১">
    </div>
    <div class="form-group">
      <label>দলিলের প্রকৃতি (Type):</label>
      <select id="selectDeedType">
        <option value="SAF_KABALA">সাফ কবলা (Saf-Kabala)</option>
        <option value="BAYNAPATRA">বায়নাপত্র (Baynapatra)</option>
        <option value="BONTONAMA">বণ্টননামা (Bontonama)</option>
        <option value="HEBA_BIL_EWAZ">হেবা বিল এওয়াজ (Heba)</option>
        <option value="UNKNOWN">অনিশ্চিত (Unknown)</option>
      </select>
    </div>
    <div class="form-group">
      <label>মৌজা (Mouza):</label>
      <input type="text" id="inputMouza" placeholder="যেমন: বারেন্ডা">
    </div>
    <div class="form-group">
      <label>দাগ নম্বরসমূহ (Dag Nos, কমা দিয়ে):</label>
      <input type="text" id="inputDags" placeholder="যেমন: ১২৩, ১২৪">
    </div>
    <div class="form-group">
      <label>খতিয়ান নম্বরসমূহ (Khatian Nos):</label>
      <input type="text" id="inputKhatians" placeholder="যেমন: ৪৫, ৪৬">
    </div>
    <div class="form-group">
      <label>জমির পরিমাণ (Area) ও একক:</label>
      <div style="display:flex; gap:6px;">
        <input type="number" step="0.01" id="inputArea" placeholder="৩০.০০" style="width:60%;">
        <select id="selectUnit" style="width:40%;">
          <option value="SHOTOK">শতাংশ</option>
          <option value="KATHA">কাঠা</option>
          <option value="BIGHA">বিঘা</option>
          <option value="ACRE">একর</option>
        </select>
      </div>
    </div>
    <div class="form-group">
      <label>রেজিস্ট্রেশনের তারিখ (DD/MM/YYYY):</label>
      <input type="text" id="inputRegDate" placeholder="২৮/১০/২০০১">
    </div>
    <div class="form-group">
      <label>দলিলের মূল্যের হিসাব (BDT):</label>
      <input type="number" id="inputValueBdt" placeholder="৪০০০">
    </div>
    <div class="form-group">
      <label>অ্যানোটেশনের নোট (Notes):</label>
      <textarea id="inputNotes" rows="2" placeholder="হাতের লেখার বিশেষ বৈশিষ্ট্য বা অস্পষ্টতা"></textarea>
    </div>

    <button class="btn btn-primary" onclick="submitAnnotation()">Save Human Verified Label</button>
  </div>
</div>

<script>
let queue = [];
let currentDoc = null;
let currentView = 'preview';

async function init() {
  const res = await fetch('/api/queue');
  const data = await res.json();
  queue = data.documents;
  document.getElementById('progressBadge').innerText = `${data.annotated_count}/${data.total} Annotated`;
  
  const qList = document.getElementById('queueList');
  qList.innerHTML = '';
  queue.forEach((d, i) => {
    const item = document.createElement('div');
    item.className = 'q-item' + (i === 0 ? ' active' : '');
    item.innerText = (i+1) + '. ' + d.doc_id.replace('DOLIL_MND_', '');
    if (d.annotated) item.innerHTML += ' <span style="color:#34d399;">✓</span>';
    item.onclick = () => loadDoc(d.doc_id, item);
    qList.appendChild(item);
  });
  
  if (queue.length > 0) loadDoc(queue[0].doc_id, qList.children[0]);
}

async function loadDoc(docId, element) {
  document.querySelectorAll('.q-item').forEach(el => el.classList.remove('active'));
  if (element) element.classList.add('active');
  
  const res = await fetch('/api/document/' + docId);
  currentDoc = await res.json();
  
  document.getElementById('docTitle').innerText = currentDoc.doc_id;
  updateImage();
  
  // Render crops
  const cDiv = document.getElementById('cropsContainer');
  cDiv.innerHTML = '';
  Object.entries(currentDoc.crops_b64).forEach(([name, b64]) => {
    cDiv.innerHTML += `
      <div class="crop-card">
        <div style="font-size:10px; color:var(--muted);">${name}</div>
        <img src="${b64}">
      </div>
    `;
  });
}

function updateImage() {
  if (!currentDoc) return;
  const imgEl = document.getElementById('mainImage');
  imgEl.src = (currentView === 'binarized') ? currentDoc.binarized_b64 : currentDoc.preview_b64;
}

function switchView(mode) {
  currentView = mode;
  updateImage();
}

function insertChar(ch) {
  const activeInput = document.activeElement;
  if (activeInput && activeInput.tagName === 'INPUT') {
    activeInput.value += ch;
  }
}

async function submitAnnotation() {
  if (!currentDoc) return;
  const payload = {
    annotator_id: "ALFI_HUMAN_EXPERT_01",
    doc_id: currentDoc.doc_id,
    deed_number: document.getElementById('inputDeedNo').value || null,
    deed_year: parseInt(document.getElementById('inputYear').value) || null,
    deed_type: document.getElementById('selectDeedType').value,
    mouza: document.getElementById('inputMouza').value || null,
    dag_numbers: document.getElementById('inputDags').value.split(',').map(s => s.strip()).filter(Boolean),
    khatian_numbers: document.getElementById('inputKhatians').value.split(',').map(s => s.strip()).filter(Boolean),
    land_area: parseFloat(document.getElementById('inputArea').value) || null,
    land_unit: document.getElementById('selectUnit').value,
    deed_value_bdt: parseFloat(document.getElementById('inputValueBdt').value) || null,
    registration_date: document.getElementById('inputRegDate').value || null,
    notes: document.getElementById('inputNotes').value || null,
    verified: true
  };
  
  const res = await fetch('/api/annotate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const respData = await res.json();
  alert('Annotation saved successfully for ' + currentDoc.doc_id);
  init();
}

init();
</script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)

def verify_workbench_cli():
    print("=" * 72)
    print("  BHUMILENS AI — HUMAN ANNOTATION WORKBENCH CLI VERIFICATION")
    print("=" * 72)
    
    docs = load_queue_index()
    print(f"Loaded {len(docs)} documents from curation queue.")
    
    test_doc = docs[0] if docs else {"doc_id": "DOLIL_TEST_01"}
    test_record = {
        "schema_version": "1.0.0",
        "doc_id": test_doc["doc_id"],
        "annotator_id": "AUTOMATED_BENCH_TESTER",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verified": True,
        "deed_number": "২০৭৮",
        "deed_year": 2001,
        "deed_type": "SAF_KABALA",
        "location": {
            "mouza": "বারেন্ডা",
            "upazila": "গাজীপুর সদর",
            "district": "গাজীপুর"
        },
        "land_details": {
            "dag_numbers": ["৪৫২", "৪৫৩"],
            "khatian_numbers": ["১০১"],
            "land_area": 30.0,
            "land_unit": "SHOTOK"
        },
        "financials": {
            "deed_value_bdt": 4000.0,
            "stamp_duty_bdt": 450.0
        },
        "dates": {
            "registration_date": "28/10/2001"
        },
        "notes": "Automated verification test record"
    }
    
    # Test append
    with open(VERIFIED_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(test_record, ensure_ascii=False) + "\n")
    print(f"Appended test record for {test_doc['doc_id']} to {VERIFIED_JSONL.name}")
    
    # Test read
    annotated_ids = get_annotated_doc_ids()
    assert test_doc["doc_id"] in annotated_ids, f"Failed to retrieve {test_doc['doc_id']} from JSONL!"
    print(f"Verified retrieval: Found {len(annotated_ids)} unique annotated doc(s) in {VERIFIED_JSONL.name} [PASS]")
    print("=" * 72)
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BhumiLens Human Annotation Workbench")
    parser.add_argument("--verify", action="store_true", help="Run automated CLI verification test and exit")
    parser.add_argument("--port", type=int, default=8090, help="Web server port (default: 8090)")
    args = parser.parse_args()
    
    if args.verify:
        verify_workbench_cli()
    else:
        print(f"Starting BhumiLens Annotation Workbench at http://127.0.0.1:{args.port}")
        uvicorn.run(app, host="127.0.0.1", port=args.port)
