/**
 * BhumiLens AI + BhumiGuard — Workbench Application Client Logic (Vanilla ES6)
 * 100% Offline-Capable | Zero External Dependencies
 */

const state = {
  activeDocId: null,
  activeImagePath: null,
  uploadedFilePath: null,
  extractedData: null,
  pipelineResult: null,
  isProcessing: false
};

// DOM Elements
const elements = {
  fileUpload: document.getElementById("file-upload"),
  btnCleanSampleRun: document.getElementById("btn-clean-sample-run"),
  btnSampleRun: document.getElementById("btn-sample-run"),
  btnRunPipeline: document.getElementById("btn-run-pipeline"),
  activeDocBadge: document.getElementById("active-doc-badge"),
  pipelineStatusText: document.getElementById("pipeline-status-text"),
  
  imagePlaceholder: document.getElementById("image-placeholder"),
  mainDocImage: document.getElementById("main-doc-image"),
  imageSha256Display: document.getElementById("image-sha256-display"),
  cropsContainer: document.getElementById("crops-container"),
  
  rawOcrDisplay: document.getElementById("raw-ocr-display"),
  normOcrDisplay: document.getElementById("norm-ocr-display"),
  
  // Tabs
  tabBtns: document.querySelectorAll(".tab-btn"),
  tabContents: document.querySelectorAll(".tab-content"),
  
  // Metadata Form
  deedNumber: document.getElementById("field-deed-number"),
  deedYear: document.getElementById("field-deed-year"),
  deedType: document.getElementById("field-deed-type"),
  regOffice: document.getElementById("field-reg-office"),
  mouza: document.getElementById("field-mouza"),
  upazila: document.getElementById("field-upazila"),
  dags: document.getElementById("field-dags"),
  khatians: document.getElementById("field-khatians"),
  landArea: document.getElementById("field-land-area"),
  landUnit: document.getElementById("field-land-unit"),
  consideration: document.getElementById("field-consideration"),
  stampDuty: document.getElementById("field-stamp-duty"),
  sellers: document.getElementById("field-sellers"),
  buyers: document.getElementById("field-buyers"),
  
  // Math & Share
  calcAreaInput: document.getElementById("calc-area-input"),
  calcUnitSelect: document.getElementById("calc-unit-select"),
  unitConvertResults: document.getElementById("unit-convert-results"),
  shareNotationInput: document.getElementById("share-notation-input"),
  btnCalcShare: document.getElementById("btn-calc-share"),
  shareCalcResults: document.getElementById("share-calc-results"),
  
  // BhumiGuard
  riskBanner: document.getElementById("risk-banner"),
  riskLevelText: document.getElementById("risk-level-text"),
  riskScoreDisplay: document.getElementById("risk-score-display"),
  anomalyExplanationText: document.getElementById("anomaly-explanation-text"),
  violationsContainer: document.getElementById("violations-container"),
  duplicatesContainer: document.getElementById("duplicates-container"),
  
  // Governance
  currentSha256Seal: document.getElementById("current-sha256-seal"),
  btnVerifyHash: document.getElementById("btn-verify-hash"),
  tamperStatusDisplay: document.getElementById("tamper-status-display"),
  makerIdInput: document.getElementById("maker-id-input"),
  makerCommentsInput: document.getElementById("maker-comments-input"),
  btnMakerSubmit: document.getElementById("btn-maker-submit"),
  checkerIdInput: document.getElementById("checker-id-input"),
  checkerCommentsInput: document.getElementById("checker-comments-input"),
  btnCheckerApprove: document.getElementById("btn-checker-approve"),
  auditTimeline: document.getElementById("audit-timeline"),
  
  // RAG Chat Drawer
  btnToggleRag: document.getElementById("btn-toggle-rag"),
  btnCloseRag: document.getElementById("btn-close-rag"),
  chatDrawer: document.getElementById("chat-drawer"),
  chatMessages: document.getElementById("chat-messages"),
  chatInput: document.getElementById("chat-input"),
  btnSendChat: document.getElementById("btn-send-chat"),
  chipExplainCurrent: document.getElementById("chip-explain-current"),
  quickChips: document.querySelectorAll(".quick-chip"),
  
  toastContainer: document.getElementById("toast-container")
};

// Toast Notifications
function showToast(message, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerText = message;
  elements.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

// Tab Switching
elements.tabBtns.forEach(btn => {
  btn.addEventListener("click", () => {
    elements.tabBtns.forEach(b => b.classList.remove("active"));
    elements.tabContents.forEach(c => c.classList.remove("active"));
    
    btn.classList.add("active");
    const targetId = btn.getAttribute("data-tab");
    document.getElementById(targetId)?.classList.add("active");
  });
});

// Unit Converter
async function updateUnitConversions() {
  const area = parseFloat(elements.calcAreaInput.value) || 0;
  const unit = elements.calcUnitSelect.value;
  if (area <= 0) return;

  try {
    const res = await fetch("/api/v1/verify/convert-unit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ area, unit })
    });
    if (!res.ok) throw new Error("Conversion failed");
    const data = await res.json();
    const c = data.conversions;
    elements.unitConvertResults.innerHTML = `
      <div><strong>শতক / শতাংশ (Shotok):</strong> ${c.shotok.toFixed(4)} শতক</div>
      <div><strong>কাঠা (Katha):</strong> ${c.katha.toFixed(4)} কাঠা</div>
      <div><strong>বিঘা (Bigha):</strong> ${c.bigha.toFixed(4)} বিঘা</div>
      <div><strong>একর (Acre):</strong> ${c.acre.toFixed(4)} একর</div>
      <div><strong>অযুতাংশ (Ajutangsho):</strong> ${c.ajutangsho.toFixed(1)} অযুতাংশ</div>
      <div><strong>বর্গফুট (Sq Ft):</strong> ${data.square_feet.toFixed(2)} বর্গফুট</div>
    `;
  } catch (err) {
    elements.unitConvertResults.innerText = "রূপান্তর হিসাব করতে সমস্যা হয়েছে।";
  }
}
elements.calcAreaInput.addEventListener("input", updateUnitConversions);
elements.calcUnitSelect.addEventListener("change", updateUnitConversions);

// Archaic 16-Ana Share Calculator
async function updateShareCalculations() {
  const notation = elements.shareNotationInput.value.trim();
  if (!notation) return;

  try {
    const res = await fetch("/api/v1/verify/calculate-share", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ share_notation: notation })
    });
    if (!res.ok) throw new Error("Share calculation failed");
    const data = await res.json();
    elements.shareCalcResults.innerHTML = `
      <div><strong>দশমিক ভগ্নাংশ (Decimal Share):</strong> ${data.decimal_share.toFixed(6)} (${(data.decimal_share * 100).toFixed(4)}%)</div>
      <div><strong>১৬-আনা রূপান্তর:</strong> ${(data.decimal_share * 16).toFixed(4)} আনা</div>
      <div><strong>হিস্যা বিশ্লেষণ:</strong> আনা=${data.breakdown.ana}, গন্ডা=${data.breakdown.gonda}, কড়া=${data.breakdown.kora}, ক্রান্তি=${data.breakdown.kranti}, তিল=${data.breakdown.til}</div>
      <div style="color: ${data.is_valid ? '#34d399' : '#f87171'};"><strong>আইনি বৈধতা:</strong> ${data.is_valid ? 'সঠিক (১৬ আনার মধ্যে)' : 'অবৈধ (১৬ আনার বেশি)'}</div>
    `;
  } catch (err) {
    elements.shareCalcResults.innerText = "হিস্যা বিশ্লেষণ করতে সমস্যা হয়েছে।";
  }
}
elements.btnCalcShare.addEventListener("click", updateShareCalculations);

// HTML Sanitizer
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Render Document Pipeline Results
function renderPipelineOutput(output) {
  if (!output) return;
  state.pipelineResult = output;
  state.activeDocId = output.doc_id || "UNKNOWN_DOC";
  state.extractedData = output.extracted_deed || {};

  try {
    // Header and status
    elements.activeDocBadge.innerText = `ডকুমেন্ট: ${state.activeDocId}`;
    updateStateBadge(output.pipeline_state);

    // Main Image
    const imgPath = output.evidence_manifest?.image_path || state.activeImagePath;
    if (imgPath) {
      elements.mainDocImage.src = "/" + String(imgPath).replace(/^\/+/, "");
      elements.mainDocImage.style.display = "block";
      elements.imagePlaceholder.style.display = "none";
    }
    const sha = output.original_image_sha256 || "";
    elements.imageSha256Display.innerText = sha ? `SHA-256: ${sha.slice(0, 16)}...` : "SHA-256: N/A";

    // Evidence Crops
    renderEvidenceCrops(output);

    // OCR Text
    const prov = output.extracted_deed?.provenance || {};
    elements.rawOcrDisplay.innerText = prov.raw_ocr_text || "তথ্য পাওয়া যায়নি।";
    elements.normOcrDisplay.innerText = prov.normalized_ocr_text || "তথ্য পাওয়া যায়নি।";

    // Form Fields
    populateMetadataForm(output.extracted_deed);

    // BhumiGuard Risk Report
    renderBhumiGuardReport(output.bhumiguard_report);

    // Cryptographic Seal & Audit
    elements.currentSha256Seal.innerText = output.record_sha256 || "N/A";
    elements.tamperStatusDisplay.innerText = "";
    if (output.doc_id) {
      fetchAuditTrail(output.doc_id);
    }
  } catch (err) {
    console.error("[BhumiLens] Error rendering pipeline output:", err);
    showToast(`UI প্রদর্শনে ত্রুটি: ${err.message}`, "error");
  }
}

// Render Evidence Crops
function renderEvidenceCrops(output) {
  elements.cropsContainer.innerHTML = "";
  const layout = output.layout_analysis || {};
  const manifest = output.evidence_manifest || {};
  const crops = manifest.field_crops || manifest.evidence_crops || {};

  const cropEntries = Object.entries(crops);
  if (cropEntries.length > 0) {
    cropEntries.forEach(([key, val], idx) => {
      const card = document.createElement("div");
      card.className = "crop-card";
      
      const cropPath = (typeof val === "object" && val !== null) ? (val.crop_path || "") : String(val || "");
      const cropUrl = cropPath ? "/" + cropPath.replace(/^\/+/, "") : "";
      const safeKey = escapeHtml(key);

      card.innerHTML = `
        <img src="${cropUrl}" alt="${safeKey}" onerror="this.parentElement.style.opacity='0.6'; this.style.display='none';">
        <div style="font-weight: 600; font-size: 0.72rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${safeKey}">${safeKey}</div>
        <div class="crop-meta">
          <span>Crop #${idx + 1}</span>
          <span style="color: #34d399;">এভিডেন্স</span>
        </div>
      `;
      if (cropUrl) {
        card.addEventListener("click", () => {
          elements.mainDocImage.src = cropUrl;
        });
      }
      elements.cropsContainer.appendChild(card);
    });
  } else {
    elements.cropsContainer.innerHTML = `
      <div style="font-size: 0.75rem; color: var(--text-muted); padding: 8px;">
        ${layout.segmented_lines_count || 0}টি হস্তাক্ষর লাইন সেগমেন্ট করা হয়েছে। সিল শনাক্ত: ${layout.has_official_seal ? 'হ্যাঁ' : 'না'}।
      </div>
    `;
  }
}

// Populate Form
function populateMetadataForm(deed) {
  deed = deed || {};
  elements.deedNumber.value = deed.deed_number ?? "";
  elements.deedYear.value = deed.deed_year ?? "";
  elements.deedType.value = deed.deed_type || "SAF_KABALA";
  elements.regOffice.value = deed.registration_office ?? "";
  
  const loc = deed.location || {};
  elements.mouza.value = loc.mouza ?? "";
  elements.upazila.value = loc.upazila ?? "";
  
  const land = deed.land_details || {};
  
  // Safe array or string handling for dags and khatians
  const dags = Array.isArray(land.dag_numbers)
    ? land.dag_numbers.join(", ")
    : (land.dag_numbers != null ? String(land.dag_numbers) : "");
  elements.dags.value = dags;

  const khatians = Array.isArray(land.khatian_numbers)
    ? land.khatian_numbers.join(", ")
    : (land.khatian_numbers != null ? String(land.khatian_numbers) : "");
  elements.khatians.value = khatians;

  elements.landArea.value = land.land_area ?? "";
  elements.landUnit.value = land.land_unit || "SHOTOK";
  
  elements.consideration.value = deed.deed_value_bdt ?? "";
  elements.stampDuty.value = deed.stamp_duty_bdt ?? "";
  
  // Safe array or string handling for sellers and buyers
  let sellersStr = "";
  if (Array.isArray(deed.sellers)) {
    sellersStr = deed.sellers.map(s => {
      if (typeof s === "object" && s !== null) {
        return s.name || s.nid || "";
      }
      return String(s || "");
    }).filter(Boolean).join("; ");
  } else if (deed.sellers != null) {
    sellersStr = String(deed.sellers);
  }
  elements.sellers.value = sellersStr;

  let buyersStr = "";
  if (Array.isArray(deed.buyers)) {
    buyersStr = deed.buyers.map(b => {
      if (typeof b === "object" && b !== null) {
        return b.name || b.nid || "";
      }
      return String(b || "");
    }).filter(Boolean).join("; ");
  } else if (deed.buyers != null) {
    buyersStr = String(deed.buyers);
  }
  elements.buyers.value = buyersStr;

  // Trigger sync to unit converter if area provided
  if (land.land_area != null && land.land_area !== "") {
    elements.calcAreaInput.value = land.land_area;
    elements.calcUnitSelect.value = land.land_unit || "SHOTOK";
    updateUnitConversions();
  }
}

// Render BhumiGuard Report
function renderBhumiGuardReport(report) {
  if (!report) {
    elements.riskBanner.className = "risk-banner risk-low";
    elements.riskLevelText.innerText = "ঝুঁকি তথ্য পাওয়া যায়নি";
    elements.riskScoreDisplay.innerText = "0.00";
    elements.anomalyExplanationText.innerText = "কোনো অ্যানোমালি রিপোর্ট নেই।";
    elements.violationsContainer.innerHTML = `<div style="font-size: 0.78rem; color: var(--text-muted); padding: 8px;">কোনো নিয়ম লঙ্ঘন নেই।</div>`;
    elements.duplicatesContainer.innerHTML = `<div style="font-size: 0.78rem; color: var(--text-muted); padding: 8px;">কোনো সদৃশ কপি নেই।</div>`;
    return;
  }

  const level = report.risk_level || "RISK_LOW";
  const score = typeof report.risk_score === "number" ? report.risk_score : (parseFloat(report.risk_score) || 0);

  // Banner color
  elements.riskBanner.className = "risk-banner";
  if (level === "RISK_HIGH_REVIEW_REQUIRED") {
    elements.riskBanner.classList.add("risk-high");
    elements.riskLevelText.innerText = "উচ্চ ঝুঁকি (HIGH REVIEW REQUIRED)";
  } else if (level === "RISK_MEDIUM") {
    elements.riskBanner.classList.add("risk-medium");
    elements.riskLevelText.innerText = "মাঝারি ঝুঁকি (MEDIUM RISK)";
  } else {
    elements.riskBanner.classList.add("risk-low");
    elements.riskLevelText.innerText = "নিম্ন ঝুঁকি — স্বাভাবিক (LOW RISK)";
  }
  elements.riskScoreDisplay.innerText = score.toFixed(4);

  // Explanation
  elements.anomalyExplanationText.innerText = report.anomaly_explanation_bn || report.anomaly_explanation_en || "কোনো সংখ্যাগত অসঙ্গতি পাওয়া যায়নি।";

  // Violations
  elements.violationsContainer.innerHTML = "";
  const violations = Array.isArray(report.rule_violations) ? report.rule_violations : [];
  if (violations.length > 0) {
    violations.forEach(v => {
      const card = document.createElement("div");
      card.className = "violation-card";
      const ruleType = escapeHtml(v.rule_type || "RULE");
      const severity = escapeHtml(v.severity || "INFO");
      const fieldName = escapeHtml(v.field_name || "N/A");
      const desc = escapeHtml(v.description_bn || v.description_en || "");
      card.innerHTML = `
        <div class="v-header">
          <span>⚠️ [${ruleType}] (${severity})</span>
          <span>ফিল্ড: ${fieldName}</span>
        </div>
        <div class="v-body">${desc}</div>
      `;
      elements.violationsContainer.appendChild(card);
    });
  } else {
    elements.violationsContainer.innerHTML = `<div style="font-size: 0.78rem; color: #34d399; padding: 6px;">✓ কোনো ক্রস-রেকর্ড ল্যান্ড সংঘাত পাওয়া যায়নি।</div>`;
  }

  // Duplicates
  elements.duplicatesContainer.innerHTML = "";
  const dups = Array.isArray(report.duplicate_matches) ? report.duplicate_matches : [];
  if (dups.length > 0) {
    dups.forEach(d => {
      const div = document.createElement("div");
      div.style.padding = "8px";
      div.style.background = "var(--bg-input)";
      div.style.borderRadius = "4px";
      div.style.marginTop = "4px";
      div.style.fontSize = "0.78rem";
      const matchType = escapeHtml(d.match_type || "MATCH");
      const detail = escapeHtml(d.detail || "");
      const sim = typeof d.similarity_pct === "number" ? d.similarity_pct.toFixed(1) : escapeHtml(String(d.similarity_pct ?? "N/A"));
      div.innerHTML = `<strong>${matchType}:</strong> ${detail} (সাদৃশ্য: ${sim}%)`;
      elements.duplicatesContainer.appendChild(div);
    });
  } else {
    elements.duplicatesContainer.innerHTML = `<div style="font-size: 0.78rem; color: #34d399; padding: 6px;">✓ ডাটাবেজে কোনো নকল দলিল শনাক্ত হয়নি।</div>`;
  }
}

// Update State Badge
function updateStateBadge(pipelineState) {
  elements.activeDocBadge.className = "state-badge";
  if (pipelineState === "CHECKER_APPROVED_LOCKED") {
    elements.activeDocBadge.classList.add("state-locked");
    elements.activeDocBadge.innerText = `লকড ও অনুমোদিত (${state.activeDocId})`;
  } else if (pipelineState === "MAKER_VERIFIED_PENDING_CHECKER") {
    elements.activeDocBadge.classList.add("state-pending-checker");
    elements.activeDocBadge.innerText = `চেকার অপেক্ষমান (${state.activeDocId})`;
  } else {
    elements.activeDocBadge.classList.add("state-pending-maker");
    elements.activeDocBadge.innerText = `মেকার অপেক্ষমান (${state.activeDocId})`;
  }
}

// Fetch Audit Trail
async function fetchAuditTrail(docId) {
  if (!docId) return;
  try {
    const res = await fetch(`/api/v1/documents/${encodeURIComponent(docId)}`);
    if (!res.ok) return;
    const doc = await res.json();
    
    elements.auditTimeline.innerHTML = "";
    const trail = Array.isArray(doc.audit_trail) ? doc.audit_trail : [];
    if (trail.length === 0) {
      elements.auditTimeline.innerHTML = `<div style="font-size: 0.75rem; color: var(--text-muted);">এখনও কোনো অডিট ইভেন্ট নেই।</div>`;
      return;
    }

    trail.forEach(ev => {
      const item = document.createElement("div");
      item.className = "timeline-item";
      const action = escapeHtml(ev.action || "");
      const role = escapeHtml(ev.role || "");
      const actorId = escapeHtml(ev.actor_id || "SYSTEM");
      const hash = escapeHtml(ev.record_sha256 || "N/A");
      let timeStr = "";
      try {
        timeStr = new Date(ev.timestamp_utc).toLocaleString('bn-BD');
      } catch (e) {
        timeStr = ev.timestamp_utc || "";
      }
      item.innerHTML = `
        <div><strong>${action}</strong> (${role}) — কর্মকর্তা: <em>${actorId}</em></div>
        <div class="timeline-meta">${timeStr}</div>
        <div class="timeline-hash">Seal: ${hash}</div>
      `;
      elements.auditTimeline.appendChild(item);
    });
  } catch (e) {
    console.error("Audit trail fetch failed:", e);
  }
}

// 1-Click Clean Sample Deed (Pre-calibrated Demo)
if (elements.btnCleanSampleRun) {
  elements.btnCleanSampleRun.addEventListener("click", async () => {
    if (state.isProcessing) return;
    state.isProcessing = true;
    elements.btnCleanSampleRun.disabled = true;
    elements.pipelineStatusText.innerText = "ক্যালিব্রেটেড ডেমো দলিল লোড হচ্ছে...";
    showToast("ক্যালিব্রেটেড নমুনা দলিল লোড করা হচ্ছে...", "info");

    try {
      const res = await fetch("/api/v1/process/demo-calibrated", {
        method: "GET"
      });
      if (!res.ok) throw new Error("Calibrated demo fetch failed");
      const result = await res.json();
      renderPipelineOutput(result);
      showToast("ক্যালিব্রেটেড নমুনা দলিলের তথ্য ও এভিডেন্স ক্রপস লোড করা হয়েছে!", "success");
    } catch (err) {
      showToast(`ডেমো লোডে ত্রুটি: ${err.message}`, "error");
    } finally {
      state.isProcessing = false;
      elements.btnCleanSampleRun.disabled = false;
      elements.pipelineStatusText.innerText = "প্রস্তুত";
    }
  });
}

// 1-Click Raw Sample Dolil Test (Dolil 100)
elements.btnSampleRun.addEventListener("click", async () => {
  if (state.isProcessing) return;
  state.isProcessing = true;
  elements.btnSampleRun.disabled = true;
  elements.pipelineStatusText.innerText = "নমুনা দলিলে পূর্ণাঙ্গ পাইপলাইন চলছে (Agents 1-6)...";
  showToast("নমুনা দলিলে (Dolil 100) এআই পাইপলাইন শুরু হয়েছে...", "info");

  try {
    const res = await fetch("/api/v1/process/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image_path: "sample_data/sample_dolil_100_anonymized.jpg",
        doc_id: "DOLIL_100_SAMPLE",
        actor_id: "BENCHMARK_RUNNER"
      })
    });
    if (!res.ok) throw new Error("Pipeline run failed");
    const result = await res.json();
    renderPipelineOutput(result);
    showToast("পাইপলাইন সফলভাবে সম্পন্ন হয়েছে! সকল তথ্য লোড করা হয়েছে।", "success");
  } catch (err) {
    showToast(`পাইপলাইন পরিচালনায় ত্রুটি: ${err.message}`, "error");
  } finally {
    state.isProcessing = false;
    elements.btnSampleRun.disabled = false;
    elements.pipelineStatusText.innerText = "প্রস্তুত";
  }
});

// File Upload Handler
elements.fileUpload.addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  showToast(`ফাইল আপলোড হচ্ছে: ${file.name}...`, "info");
  try {
    const res = await fetch("/api/v1/documents/upload", {
      method: "POST",
      body: formData
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Upload rejected");
    }
    const data = await res.json();
    state.uploadedFilePath = data.file_path;
    state.activeDocId = data.doc_id;
    state.activeImagePath = data.file_path;
    elements.btnRunPipeline.disabled = false;
    elements.activeDocBadge.innerText = `আপলোড সম্পন্ন (${data.doc_id})`;
    showToast(`ফাইল সফলভাবে আপলোড ও হ্যাশ যাচাই হয়েছে! (MIME: ${data.detected_mime})`, "success");
  } catch (err) {
    showToast(`ফাইল আপলোড ব্যর্থ: ${err.message}`, "error");
    elements.btnRunPipeline.disabled = true;
  }
});

// Run Uploaded Pipeline
elements.btnRunPipeline.addEventListener("click", async () => {
  if (!state.uploadedFilePath || state.isProcessing) return;
  state.isProcessing = true;
  elements.btnRunPipeline.disabled = true;
  elements.pipelineStatusText.innerText = "আপলোডকৃত ফাইলে পাইপলাইন চলছে...";

  try {
    const res = await fetch("/api/v1/process/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image_path: state.uploadedFilePath,
        doc_id: state.activeDocId,
        actor_id: "WORKBENCH_OPERATOR"
      })
    });
    if (!res.ok) throw new Error("Pipeline execution failed");
    const result = await res.json();
    renderPipelineOutput(result);
    showToast("আপলোডকৃত দলিলের পাইপলাইন সফলভাবে সম্পন্ন হয়েছে!", "success");
  } catch (err) {
    showToast(`পাইপলাইন ত্রুটি: ${err.message}`, "error");
  } finally {
    state.isProcessing = false;
    elements.btnRunPipeline.disabled = false;
    elements.pipelineStatusText.innerText = "প্রস্তুত";
  }
});

// Maker Submit Handler
elements.btnMakerSubmit.addEventListener("click", async () => {
  if (!state.activeDocId) {
    showToast("অনুগ্রহ করে প্রথমে একটি দলিল লোড করুন।", "warning");
    return;
  }

  const makerId = elements.makerIdInput.value.trim();
  const comments = elements.makerCommentsInput.value.trim();
  if (!makerId) {
    showToast("মেকার অপারেটর আইডি প্রদান করুন।", "warning");
    return;
  }

  // Gather human-corrected values
  const correctedData = {
    deed_number: elements.deedNumber.value,
    deed_year: parseInt(elements.deedYear.value) || null,
    deed_type: elements.deedType.value,
    registration_office: elements.regOffice.value,
    location: {
      mouza: elements.mouza.value,
      upazila: elements.upazila.value
    },
    land_details: {
      dag_numbers: elements.dags.value.split(",").map(s => s.trim()).filter(Boolean),
      khatian_numbers: elements.khatians.value.split(",").map(s => s.trim()).filter(Boolean),
      land_area: parseFloat(elements.landArea.value) || null,
      land_unit: elements.landUnit.value
    },
    deed_value_bdt: parseFloat(elements.consideration.value) || null,
    stamp_duty_bdt: parseFloat(elements.stampDuty.value) || null,
    sellers: elements.sellers.value.split(";").map(s => ({ name: s.trim() })).filter(s => s.name),
    buyers: elements.buyers.value.split(";").map(b => ({ name: b.trim() })).filter(b => b.name)
  };

  try {
    const res = await fetch(`/api/v1/review/${state.activeDocId}/maker-submit`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Actor-ID": makerId,
        "X-Actor-Role": "MAKER"
      },
      body: JSON.stringify({
        maker_id: makerId,
        human_corrected_data: correctedData,
        comments: comments || "Maker verified line crops."
      })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Submission failed");
    }
    const data = await res.json();
    elements.currentSha256Seal.innerText = data.record_sha256;
    updateStateBadge(data.pipeline_state);
    fetchAuditTrail(state.activeDocId);
    showToast("মেকার পর্যালোচনা সংরক্ষিত হয়েছে! রেকর্ড চেকার অনুমোদনের অপেক্ষায়।", "success");
  } catch (err) {
    showToast(`মেকার সাবমিট ব্যর্থ: ${err.message}`, "error");
  }
});

// Checker Approve Handler
elements.btnCheckerApprove.addEventListener("click", async () => {
  if (!state.activeDocId) {
    showToast("অনুগ্রহ করে প্রথমে একটি দলিল লোড করুন।", "warning");
    return;
  }

  const checkerId = elements.checkerIdInput.value.trim();
  const comments = elements.checkerCommentsInput.value.trim();
  const makerId = elements.makerIdInput.value.trim();

  if (!checkerId) {
    showToast("চেকার সুপারভাইজার আইডি প্রদান করুন।", "warning");
    return;
  }

  if (checkerId.toLowerCase() === makerId.toLowerCase()) {
    showToast("নিরাপত্তা নীতি লঙ্ঘন: মেকার ও চেকার একই ব্যক্তি হতে পারবেন না (Four-Eyes Principle)।", "error");
    return;
  }

  try {
    const res = await fetch(`/api/v1/review/${state.activeDocId}/checker-approve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Actor-ID": checkerId,
        "X-Actor-Role": "CHECKER"
      },
      body: JSON.stringify({
        checker_id: checkerId,
        comments: comments || "Audited and approved."
      })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Approval failed");
    }
    const data = await res.json();
    elements.currentSha256Seal.innerText = data.record_sha256;
    updateStateBadge(data.pipeline_state);
    fetchAuditTrail(state.activeDocId);
    showToast("চেকার অনুমোদন সম্পন্ন ও রেকর্ড চিরতরে লক করা হয়েছে!", "success");
  } catch (err) {
    showToast(`চেকার অনুমোদন ব্যর্থ: ${err.message}`, "error");
  }
});

// Tamper Verify Handler
elements.btnVerifyHash.addEventListener("click", async () => {
  if (!state.activeDocId) {
    showToast("কোনো সক্রিয় দলিল নেই।", "warning");
    return;
  }

  try {
    const res = await fetch(`/api/v1/audit/${state.activeDocId}/verify-hash`);
    if (!res.ok) throw new Error("Hash verification failed");
    const data = await res.json();
    if (data.integrity_verified && !data.is_tampered) {
      elements.tamperStatusDisplay.style.color = "#34d399";
      elements.tamperStatusDisplay.innerText = "✓ ক্রিপ্টোগ্রাফিক সিল অক্ষত: কোনো ট্যাম্পারিং বা পরিবর্তন ঘটেনি।";
      showToast("ক্রিপ্টোগ্রাফিক SHA-256 অখণ্ডতা যাচাই সফল!", "success");
    } else {
      elements.tamperStatusDisplay.style.color = "#ef4444";
      elements.tamperStatusDisplay.innerText = "⚠️ সতর্কবার্তা: ডাটাবেজ ট্যাম্পারিং শনাক্ত হয়েছে! সিল মিলছে না।";
      showToast("সতর্কতা: দলিলের তথ্যে অননুমোদিত পরিবর্তন ঘটেছে!", "error");
    }
  } catch (err) {
    showToast(`ট্যাম্পার যাচাই ব্যর্থ: ${err.message}`, "error");
  }
});

// RAG Drawer Controls
elements.btnToggleRag.addEventListener("click", () => {
  elements.chatDrawer.classList.toggle("open");
});
elements.btnCloseRag.addEventListener("click", () => {
  elements.chatDrawer.classList.remove("open");
});

// Send Chat Query
async function handleSendQuery(query) {
  const q = query || elements.chatInput.value.trim();
  if (!q) return;

  // Append user bubble
  const userBubble = document.createElement("div");
  userBubble.className = "chat-bubble user";
  userBubble.innerText = q;
  elements.chatMessages.appendChild(userBubble);
  elements.chatInput.value = "";
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;

  // Thinking bubble
  const thinkBubble = document.createElement("div");
  thinkBubble.className = "chat-bubble assistant";
  thinkBubble.innerText = "ভূমি জ্ঞানভাণ্ডার থেকে যাচাই করা হচ্ছে...";
  elements.chatMessages.appendChild(thinkBubble);
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;

  try {
    const res = await fetch("/api/v1/knowledge/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: q, top_k: 2 })
    });
    if (!res.ok) throw new Error("Knowledge query failed");
    const data = await res.json();

    let citationsHtml = "";
    if (data.citations && data.citations.length > 0) {
      citationsHtml = `<div class="chat-citations"><strong>সরাসরি সোর্স রেফারেন্স:</strong><br>${data.citations.map(c => `• ${c.title} (${c.source_authority}) [স্কোর: ${c.similarity_score.toFixed(3)}]`).join("<br>")}</div>`;
    }

    thinkBubble.innerHTML = `
      <div>${data.explanation_bn || data.answer}</div>
      ${citationsHtml}
      <div style="font-size: 0.65rem; color: var(--text-muted); margin-top: 6px;">${data.legal_disclaimer}</div>
    `;
  } catch (err) {
    thinkBubble.innerText = `সহকারী ত্রুটি: ${err.message}`;
  }
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

elements.btnSendChat.addEventListener("click", () => handleSendQuery());
elements.chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") handleSendQuery();
});

// Quick chips
elements.quickChips.forEach(chip => {
  chip.addEventListener("click", () => {
    const q = chip.getAttribute("data-query");
    if (q) handleSendQuery(q);
  });
});

// Explain Current Doc
elements.chipExplainCurrent.addEventListener("click", async () => {
  if (!state.activeDocId) {
    showToast("প্রথমে একটি দলিল লোড করুন।", "warning");
    return;
  }
  handleSendQuery(`বর্তমান দলিল ${state.activeDocId} এর সারসংক্ষেপ ও আইনি বিশ্লেষণ দিন`);
});

// Initial health check on page load
window.addEventListener("DOMContentLoaded", async () => {
  try {
    const res = await fetch("/health");
    if (res.ok) {
      const h = await res.json();
      console.log("[BhumiLens] System Health:", h);
    }
  } catch (e) {
    console.warn("Backend health check warning:", e);
  }
});
