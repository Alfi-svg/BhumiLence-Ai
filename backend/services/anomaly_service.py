"""
BhumiLens AI — BhumiGuard Anomaly & Duplicate Detection Service (Layer 6 & Agent 5).
Combines:
1. Visual & Cryptographic Duplicate Detection (SHA-256 + 64-bit Perceptual dHash)
2. Deterministic Cross-Record Land Consistency & Conflict Rules (Over-transfer >16-Ana, Deed Collisions)
3. Unsupervised Tabular Anomaly Scoring (Isolation Forest on Land Transaction Distributions)

Ethical Governance Rule:
Never labels any document or person as 'fraud' or 'forged'.
Produces factual risk indicators, rule triggers, and statistical outlier scores for human Maker-Checker review.
"""
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
import cv2
import numpy as np
from sklearn.ensemble import IsolationForest

from backend.schemas.bhumiguard_schema import (
    RiskLevel,
    DuplicateMatchType,
    DuplicateMatch,
    ConflictRuleType,
    RuleViolation,
    FeatureContribution,
    BhumiGuardReport,
    SCHEMA_VERSION
)
from backend.services.audit_service import AuditPersistenceService
from backend.services.land_validation_service import LandUnitConverter, SixteenAnaValidator

logger = logging.getLogger("bhumilens.bhumiguard")

DEFAULT_SEED_PATH = Path("research/datasets/annotations/deed_extraction_seed.jsonl")

DISCLAIMER_TEXT = (
    "আইনি সতর্কবার্তা: এই অ্যানোমালি ও রিস্ক রিপোর্ট শুধুমাত্র মানুষের পর্যালোচনার "
    "(Maker-Checker Review) জন্য প্রস্তুতকৃত স্ট্যাটিস্টিক্যাল ও লজিক্যাল সতর্কতা। "
    "এটি কোনো জালিয়াতি বা অপরাধের আইনি প্রমাণ নয়।"
)

def compute_dhash(image_input: Any) -> str:
    """
    Computes a 64-bit Difference Hash (dHash) from an image path or numpy array.
    Steps: Grayscale -> Resize to (9, 8) -> Compute horizontal gradients -> 16-hex string.
    """
    if isinstance(image_input, (str, Path)):
        img_path = str(image_input)
        if not os.path.exists(img_path):
            return ""
        gray = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    elif isinstance(image_input, np.ndarray):
        if len(image_input.shape) == 3:
            gray = cv2.cvtColor(image_input, cv2.COLOR_BGR2GRAY)
        else:
            gray = image_input
    else:
        return ""

    if gray is None or gray.size == 0:
        return ""

    # Resize to 9 columns, 8 rows
    resized = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)

    # Compute horizontal difference: 8x8 = 64 boolean bits
    diff = resized[:, 1:] > resized[:, :-1]

    # Convert 64 boolean bits to hex string
    bit_str = "".join(["1" if b else "0" for b in diff.flatten()])
    int_val = int(bit_str, 2)
    return f"{int_val:016x}"

def compute_hamming_distance(hash1_hex: str, hash2_hex: str) -> int:
    """Calculates bitwise Hamming distance between two 16-char hex hashes."""
    if not hash1_hex or not hash2_hex or len(hash1_hex) != 16 or len(hash2_hex) != 16:
        return 64
    val1 = int(hash1_hex, 16)
    val2 = int(hash2_hex, 16)
    return bin(val1 ^ val2).count("1")

class IsolationForestScorer:
    """
    Lightweight, unsupervised tabular anomaly scorer trained on reference deed transaction distributions.
    """
    FEATURE_NAMES = [
        "land_area_shotok",
        "deed_value_bdt",
        "value_per_shotok",
        "stamp_to_value_ratio",
        "sixteen_ana_fraction",
        "missing_field_count"
    ]

    def __init__(self, seed_path: Optional[Path] = None):
        self.seed_path = seed_path or DEFAULT_SEED_PATH
        self.clf: Optional[IsolationForest] = None
        self.feature_means: Dict[str, float] = {}
        self.feature_stds: Dict[str, float] = {}
        self._fit_baseline()

    def _extract_features(self, record: Dict[str, Any]) -> List[float]:
        """Extracts normalized 6-dimensional numeric vector from deed record dictionary."""
        land_details = record.get("land_details") or record.get("land_schedule") or {}
        financials = record.get("financials") or {}
        
        # 1. Land area in Shotok
        raw_area = land_details.get("land_area") or land_details.get("area_shotok") or record.get("land_area") or 0.0
        unit = land_details.get("land_unit") or "SHOTOK"
        area_shotok = float(raw_area)
        if unit == "KATHA":
            area_shotok = float(raw_area) * 1.65289
        elif unit == "BIGHA":
            area_shotok = float(raw_area) * 33.0578
        elif unit == "ACRE":
            area_shotok = float(raw_area) * 100.0

        # 2. Deed value
        deed_value = float(
            record.get("deed_value_bdt") or
            financials.get("consideration_bdt") or
            record.get("consideration_bdt") or 0.0
        )

        # 3. Value per shotok
        value_per_shotok = deed_value / max(0.01, area_shotok) if area_shotok > 0 else 0.0

        # 4. Stamp duty to value ratio
        stamp_duty = float(
            record.get("stamp_duty_bdt") or
            financials.get("stamp_duty_bdt") or
            record.get("stamp_duty") or 0.0
        )
        stamp_ratio = stamp_duty / max(1.0, deed_value) if deed_value > 0 else 0.0

        # 5. Sixteen Ana fraction
        share_frac = 0.0
        if land_details.get("ownership_share") is not None:
            share_frac = float(land_details["ownership_share"])
        elif record.get("sixteen_ana_share") is not None and isinstance(record.get("sixteen_ana_share"), (int, float)):
            share_frac = float(record["sixteen_ana_share"])
        elif land_details.get("sixteen_ana_share"):
            try:
                res = SixteenAnaValidator.calculate_share(str(land_details["sixteen_ana_share"]))
                share_frac = res.decimal_share
            except Exception:
                share_frac = 0.0

        # 6. Missing field count
        missing = 0
        core_fields = ["deed_number", "deed_year", "deed_type", "registration_office"]
        for cf in core_fields:
            if not record.get(cf):
                missing += 1
        loc = record.get("location") or {}
        if not loc.get("mouza"):
            missing += 1

        return [
            float(area_shotok),
            float(deed_value),
            float(value_per_shotok),
            float(stamp_ratio),
            float(share_frac),
            float(missing)
        ]

    def _fit_baseline(self):
        """Fits IsolationForest on seed dataset + synthetic reference distributions."""
        X_train: List[List[float]] = []

        if self.seed_path.exists():
            try:
                with open(self.seed_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            rec = json.loads(line)
                            feats = self._extract_features(rec)
                            X_train.append(feats)
            except Exception as e:
                logger.warning("[BhumiGuard] Failed reading seed dataset: %s", e)

        # Augment with diverse reference bounds for robust generalization
        rng = np.random.RandomState(42)
        for _ in range(150):
            area = float(rng.uniform(2.0, 50.0))
            val_per_shotok = float(rng.uniform(10000.0, 200000.0))
            val = area * val_per_shotok
            stamp = val * float(rng.uniform(0.02, 0.06))
            stamp_ratio = stamp / val
            share = float(rng.choice([0.0625, 0.125, 0.25, 0.5, 0.75, 1.0]))
            missing = float(rng.choice([0, 1]))
            X_train.append([area, val, val_per_shotok, stamp_ratio, share, missing])

        X_mat = np.array(X_train, dtype=np.float32)

        # Calculate means and stds for feature contribution explanations
        means = np.mean(X_mat, axis=0)
        stds = np.std(X_mat, axis=0) + 1e-6
        for i, fname in enumerate(self.FEATURE_NAMES):
            self.feature_means[fname] = float(means[i])
            self.feature_stds[fname] = float(stds[i])

        self.clf = IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=42
        )
        self.clf.fit(X_mat)
        logger.info("[BhumiGuard] IsolationForest baseline fitted on %d reference records", len(X_train))

    def score(self, record: Dict[str, Any]) -> Tuple[float, List[FeatureContribution], str]:
        """
        Evaluates record using Isolation Forest.
        Returns: (anomaly_score, feature_contributions, explanation_bn)
        anomaly_score is normalized in [0.0, 1.0], where > 0.50 indicates a statistical outlier.
        """
        if self.clf is None:
            return 0.0, [], "আইসোলেশন ফরেস্ট মডেল প্রস্তুত নয়।"

        feats = self._extract_features(record)
        feats_arr = np.array([feats], dtype=np.float32)

        dec_score = float(self.clf.decision_function(feats_arr)[0])
        norm_score = float(np.clip(0.50 - (dec_score * 4.0), 0.0, 1.0))

        contributions: List[FeatureContribution] = []
        outlier_reasons: List[str] = []

        for i, fname in enumerate(self.FEATURE_NAMES):
            val = feats[i]
            mean_v = self.feature_means.get(fname, 0.0)
            std_v = self.feature_stds.get(fname, 1.0)
            z_score = abs(val - mean_v) / max(0.001, std_v)

            is_out = bool(
                z_score > 2.5 or
                (fname == "value_per_shotok" and val < 500.0 and feats[0] > 5.0) or
                (fname == "land_area_shotok" and val > 200.0) or
                (fname == "stamp_to_value_ratio" and val > 0.20)
            )
            exp_range = f"{max(0.0, mean_v - 2*std_v):.2f} - {mean_v + 2*std_v:.2f}"
            contributions.append(FeatureContribution(
                feature_name=fname,
                value=round(val, 2),
                expected_range=exp_range,
                is_outlier=is_out
            ))

            if is_out:
                if fname == "value_per_shotok" and val < 500.0 and feats[0] > 5.0:
                    outlier_reasons.append(f"জমির প্রতি শতক মূল্য অস্বাভাবিক কম ({val:.2f} টাকা/শতক)")
                elif fname == "stamp_to_value_ratio" and val > 0.20:
                    outlier_reasons.append(f"দলিল মূল্যের অনুপাতে স্ট্যাম্প শুল্কের হার অস্বাভাবিক বেশি ({val*100:.1f}%)")
                elif fname == "land_area_shotok" and val > 200.0:
                    outlier_reasons.append(f"একক দলিলে হস্তান্তরিত জমির পরিমাণ প্রমিত গড়ের চেয়ে অনেক বেশি ({val:.1f} শতক)")
                elif z_score > 2.5:
                    outlier_reasons.append(f"{fname} এর মান স্বাভাবিক পরিসীমা অতিক্রম করেছে ({val:.2f})")

        if outlier_reasons:
            explanation_bn = "স্ট্যাটিস্টিক্যাল অস্বাভাবিকতা পরিলক্ষিত: " + ", ".join(outlier_reasons) + "।"
        elif norm_score > 0.60:
            explanation_bn = "রেফারেন্স বন্টনের তুলনায় লেনদেনের সংখ্যাগত প্যাটার্নে অস্বাভাবিক বিচ্যুতি পরিলক্ষিত হয়েছে।"
        else:
            explanation_bn = "লেনদেনের সংখ্যাগত মেট্রিকসমূহ সাধারণ রেফারেন্স রেঞ্জের মধ্যে স্বাভাবিক রয়েছে।"

        return round(norm_score, 4), contributions, explanation_bn

class BhumiGuardService:
    """
    Unified multi-layered risk and anomaly evaluation service for Bangladeshi land records.
    """
    def __init__(
        self,
        audit_service: Optional[AuditPersistenceService] = None,
        db_path: Optional[str] = None,
        seed_path: Optional[Path] = None
    ):
        if audit_service is not None:
            self.audit_service = audit_service
        else:
            self.audit_service = AuditPersistenceService(db_path=db_path)
        self.scorer = IsolationForestScorer(seed_path=seed_path)
        # In-memory perceptual hash cache: {doc_id: dhash_hex}
        self.dhash_cache: Dict[str, str] = {}

    def register_perceptual_hash(self, doc_id: str, dhash_hex: str):
        """Caches perceptual hash for document ID."""
        if dhash_hex:
            self.dhash_cache[doc_id] = dhash_hex

    def check_duplicates(
        self,
        image_path: Optional[str] = None,
        target_sha256: Optional[str] = None,
        target_doc_id: Optional[str] = None
    ) -> Tuple[List[DuplicateMatch], Optional[str]]:
        """
        Executes Layer 1: Exact SHA-256 and Perceptual dHash near-duplicate inspection.
        """
        matches: List[DuplicateMatch] = []
        dhash_hex = None

        if image_path and os.path.exists(image_path):
            dhash_hex = compute_dhash(image_path)
            if target_doc_id:
                self.register_perceptual_hash(target_doc_id, dhash_hex)

        if hasattr(self.audit_service, "get_all_documents"):
            all_docs = self.audit_service.get_all_documents()
        else:
            all_docs_raw = self.audit_service.list_documents()
            all_docs = []
            for d in all_docs_raw:
                did = d.get("doc_id") if isinstance(d, dict) else getattr(d, "doc_id", None)
                if did:
                    full_d = self.audit_service.get_document(did)
                    if full_d:
                        all_docs.append(full_d)

        for doc in all_docs:
            d_id = getattr(doc, "doc_id", None) or (doc.get("doc_id") if isinstance(doc, dict) else None)
            if target_doc_id and d_id == target_doc_id:
                continue

            orig_sha = getattr(doc, "original_image_sha256", None) or (doc.get("original_image_sha256") if isinstance(doc, dict) else None)
            # 1. Exact Cryptographic SHA-256 match
            if target_sha256 and orig_sha == target_sha256:
                matches.append(DuplicateMatch(
                    matched_doc_id=d_id,
                    match_type=DuplicateMatchType.EXACT_SHA256,
                    similarity_pct=100.0,
                    hamming_distance=0,
                    detail=f"ডাটাবেজে সংরক্ষিত দলিল '{d_id}' এর সাথে অবিকল একই ক্রিপ্টোগ্রাফিক SHA-256 ইমেজ হ্যাশ মিলেছে।"
                ))
                continue

            # 2. Perceptual Near-Duplicate (dHash)
            doc_dhash = self.dhash_cache.get(d_id)
            manifest = getattr(doc, "evidence_manifest", None) or (doc.get("evidence_manifest") if isinstance(doc, dict) else None) or {}
            if not doc_dhash and manifest:
                if manifest.get("dhash_hex"):
                    doc_dhash = manifest.get("dhash_hex")
                    self.register_perceptual_hash(d_id, doc_dhash)
                else:
                    stored_img = manifest.get("image_path")
                    if stored_img and os.path.exists(stored_img):
                        doc_dhash = compute_dhash(stored_img)
                        self.register_perceptual_hash(d_id, doc_dhash)

            if dhash_hex and doc_dhash:
                h_dist = compute_hamming_distance(dhash_hex, doc_dhash)
                # Hamming distance <= 8 out of 64 bits represents >= 87.5% visual similarity
                if h_dist <= 8:
                    sim_pct = round((1.0 - (h_dist / 64.0)) * 100.0, 2)
                    matches.append(DuplicateMatch(
                        matched_doc_id=d_id,
                        match_type=DuplicateMatchType.PERCEPTUAL_NEAR_DUPLICATE,
                        similarity_pct=sim_pct,
                        hamming_distance=h_dist,
                        detail=(
                            f"সংরক্ষিত দলিল '{d_id}' এর সাথে পারসেপচুয়াল ভিজ্যুয়াল মিল পাওয়া গেছে "
                            f"(Hamming Distance: {h_dist}/64, সাদৃশ্য: {sim_pct}%)।"
                        )
                    ))

        return matches, dhash_hex

    def check_cross_record_conflicts(
        self,
        extracted_data: Dict[str, Any],
        target_doc_id: Optional[str] = None
    ) -> List[RuleViolation]:
        """
        Executes Layer 2: Deterministic cross-record land consistency & conflict rules.
        """
        violations: List[RuleViolation] = []

        deed_num = str(extracted_data.get("deed_number") or "").strip()
        reg_office = str(extracted_data.get("registration_office") or "").strip()
        deed_year = extracted_data.get("deed_year")
        if not deed_year and extracted_data.get("date"):
            date_str = str(extracted_data.get("date")).strip()
            if len(date_str) >= 4 and date_str[:4].isdigit():
                deed_year = int(date_str[:4])
            elif len(date_str) >= 10 and date_str[-4:].isdigit():
                deed_year = int(date_str[-4:])

        deed_type = str(extracted_data.get("deed_type") or "").strip()
        financials = extracted_data.get("financials") or {}
        deed_value = float(
            extracted_data.get("deed_value_bdt") or
            financials.get("consideration_bdt") or
            extracted_data.get("consideration_bdt") or 0.0
        )

        location = extracted_data.get("location") or {}
        mouza = str(location.get("mouza") or "").strip()

        land_details = extracted_data.get("land_details") or extracted_data.get("land_schedule") or {}
        plot_numbers = extracted_data.get("plot_numbers") or {}
        raw_dags = land_details.get("dag_numbers") or plot_numbers.get("dag_numbers") or extracted_data.get("dag_numbers") or []
        raw_khatians = land_details.get("khatian_numbers") or plot_numbers.get("khatian_numbers") or extracted_data.get("khatian_numbers") or []
        dag_numbers = [str(d).strip() for d in (raw_dags if isinstance(raw_dags, list) else [raw_dags])]
        khatian_numbers = [str(k).strip() for k in (raw_khatians if isinstance(raw_khatians, list) else [raw_khatians])]

        current_share = 0.0
        if land_details.get("ownership_share") is not None:
            current_share = float(land_details["ownership_share"])
        elif extracted_data.get("sixteen_ana_share") is not None and isinstance(extracted_data["sixteen_ana_share"], (int, float)):
            current_share = float(extracted_data["sixteen_ana_share"])
        elif land_details.get("sixteen_ana_share"):
            try:
                res = SixteenAnaValidator.calculate_share(str(land_details["sixteen_ana_share"]))
                current_share = res.decimal_share
            except Exception:
                current_share = 0.0

        # 1. Rule: Saf-Kabala deed must have positive consideration value
        if "SAF_KABALA" in deed_type.upper() and deed_value <= 0.0:
            violations.append(RuleViolation(
                rule_type=ConflictRuleType.INVALID_CONSIDERATION_AMOUNT,
                severity="HIGH",
                field_name="deed_value_bdt",
                description_en=f"Saf-Kabala outright sale deed declared with zero or negative value: {deed_value} BDT.",
                description_bn=f"সাফ-কবলা বিক্রয় দলিলের পণমূল্য শূন্য বা ঋণাত্মক ({deed_value} টাকা) হতে পারে না।",
                conflicting_doc_ids=[]
            ))

        # 2. Rule: Suspicious Outlier Consideration (e.g. 1000 shotok for 10 BDT)
        area_shotok = float(
            land_details.get("land_area") or
            land_details.get("area_shotok") or
            extracted_data.get("land_area") or 0.0
        )
        if area_shotok > 100.0 and deed_value > 0 and deed_value < 1000.0:
            violations.append(RuleViolation(
                rule_type=ConflictRuleType.SUSPICIOUS_VALUATION_OUTLIER,
                severity="HIGH",
                field_name="deed_value_bdt",
                description_en=f"Extreme valuation discrepancy: {area_shotok} Shotok land sold for only {deed_value} BDT.",
                description_bn=f"অস্বাভাবিক মূল্য গরমিল: {area_shotok} শতক জমি মাত্র {deed_value} টাকায় বিক্রয় দেখানো হয়েছে।",
                conflicting_doc_ids=[]
            ))

        # Query existing documents for cross-record collisions
        if hasattr(self.audit_service, "get_all_documents"):
            all_docs = self.audit_service.get_all_documents()
        else:
            all_docs_raw = self.audit_service.list_documents()
            all_docs = []
            for d in all_docs_raw:
                did = d.get("doc_id") if isinstance(d, dict) else getattr(d, "doc_id", None)
                if did:
                    full_d = self.audit_service.get_document(did)
                    if full_d:
                        all_docs.append(full_d)

        colliding_deed_ids: List[str] = []
        cumulative_share = current_share
        cumulative_doc_ids: List[str] = [target_doc_id] if target_doc_id else []

        for doc in all_docs:
            d_id = getattr(doc, "doc_id", None) or (doc.get("doc_id") if isinstance(doc, dict) else None)
            if target_doc_id and d_id == target_doc_id:
                continue

            stored_data = getattr(doc, "extracted_data", None) or (doc.get("extracted_data") if isinstance(doc, dict) else None) or {}
            stored_deed_num = str(stored_data.get("deed_number") or "").strip()
            stored_reg_office = str(stored_data.get("registration_office") or "").strip()
            stored_year = stored_data.get("deed_year")
            if not stored_year and stored_data.get("date"):
                d_str = str(stored_data.get("date")).strip()
                if len(d_str) >= 4 and d_str[:4].isdigit():
                    stored_year = int(d_str[:4])
                elif len(d_str) >= 10 and d_str[-4:].isdigit():
                    stored_year = int(d_str[-4:])

            # Check Duplicate Deed Number in same office and year
            if (
                deed_num and stored_deed_num and deed_num == stored_deed_num and
                reg_office and stored_reg_office and reg_office == stored_reg_office and
                (deed_year is None or stored_year is None or deed_year == stored_year)
            ):
                colliding_deed_ids.append(d_id)

            # Check Cumulative 16-Ana Over-transfer (> 1.0) on same Mouza + Dag + Khatian
            stored_loc = stored_data.get("location") or {}
            stored_mouza = str(stored_loc.get("mouza") or "").strip()
            stored_land = stored_data.get("land_details") or stored_data.get("land_schedule") or {}
            stored_plots = stored_data.get("plot_numbers") or {}
            s_dags_raw = stored_land.get("dag_numbers") or stored_plots.get("dag_numbers") or stored_data.get("dag_numbers") or []
            s_khat_raw = stored_land.get("khatian_numbers") or stored_plots.get("khatian_numbers") or stored_data.get("khatian_numbers") or []
            stored_dags = [str(d).strip() for d in (s_dags_raw if isinstance(s_dags_raw, list) else [s_dags_raw])]
            stored_khatians = [str(k).strip() for k in (s_khat_raw if isinstance(s_khat_raw, list) else [s_khat_raw])]

            if (
                mouza and stored_mouza and mouza == stored_mouza and
                set(dag_numbers).intersection(set(stored_dags)) and
                set(khatian_numbers).intersection(set(stored_khatians))
            ):
                s_share = 0.0
                if stored_land.get("ownership_share") is not None:
                    s_share = float(stored_land["ownership_share"])
                elif stored_data.get("sixteen_ana_share") is not None and isinstance(stored_data["sixteen_ana_share"], (int, float)):
                    s_share = float(stored_data["sixteen_ana_share"])
                elif stored_land.get("sixteen_ana_share"):
                    try:
                        res = SixteenAnaValidator.calculate_share(str(stored_land["sixteen_ana_share"]))
                        s_share = res.decimal_share
                    except Exception:
                        s_share = 0.0
                cumulative_share += s_share
                cumulative_doc_ids.append(d_id)

        # Emit Rule: Duplicate Deed Number Collision
        if colliding_deed_ids:
            violations.append(RuleViolation(
                rule_type=ConflictRuleType.DUPLICATE_DEED_NUMBER_CONFLICT,
                severity="CRITICAL",
                field_name="deed_number",
                description_en=(
                    f"Duplicate Deed Serial Conflict: Deed Number '{deed_num}' in '{reg_office}' "
                    f"collides with existing records: {colliding_deed_ids}."
                ),
                description_bn=(
                    f"দলিল নম্বর সংঘর্ষ: '{reg_office}' এ একই দলিল নম্বর '{deed_num}' "
                    f"পূর্ববর্তী রেকর্ডে বিদ্যমান ({', '.join(colliding_deed_ids)})।"
                ),
                conflicting_doc_ids=colliding_deed_ids
            ))

        # Emit Rule: Cumulative Share Exceeded (> 1.0 / 16 Ana)
        if cumulative_share > 1.0001 and len(cumulative_doc_ids) > 1:
            violations.append(RuleViolation(
                rule_type=ConflictRuleType.CUMULATIVE_SHARE_EXCEEDED,
                severity="CRITICAL",
                field_name="ownership_share",
                description_en=(
                    f"Cumulative Transferred Share Exceeded: Total share on Mouza '{mouza}', "
                    f"Dag {dag_numbers}, Khatian {khatian_numbers} is {cumulative_share:.4f} (> 1.0 / 16 Ana)."
                ),
                description_bn=(
                    f"সর্বমোট হস্তান্তরিত অংশ ১৬ আনা অতিক্রম করেছে: মৌজা '{mouza}', "
                    f"দাগ {dag_numbers}, খতিয়ান {khatian_numbers}-এ মোট বিক্রিত অংশ {cumulative_share*16:.2f} আনা "
                    f"({cumulative_share*100:.2f}%), যা সর্বোচ্চ ১৬ আনা (১০০%) এর চেয়ে বেশি।"
                ),
                conflicting_doc_ids=cumulative_doc_ids
            ))

        return violations

    def scan_document(
        self,
        extracted_data: Dict[str, Any],
        image_path: Optional[str] = None,
        target_sha256: Optional[str] = None,
        doc_id: Optional[str] = None
    ) -> BhumiGuardReport:
        """
        Executes complete multi-layered BhumiGuard Intelligence scan:
        Layer 1: Duplicate Detection
        Layer 2: Conflict Rules
        Layer 3: Isolation Forest Anomaly Scoring
        """
        assigned_doc_id = doc_id or extracted_data.get("doc_id") or "UNSPECIFIED_DOC"

        # 1. Visual & Cryptographic Duplicate Matching
        dup_matches, dhash_hex = self.check_duplicates(
            image_path=image_path,
            target_sha256=target_sha256,
            target_doc_id=assigned_doc_id
        )

        # 2. Deterministic Conflict Rules
        violations = self.check_cross_record_conflicts(
            extracted_data=extracted_data,
            target_doc_id=assigned_doc_id
        )

        # 3. Unsupervised Tabular Anomaly Scoring
        anomaly_score, feat_contribs, anomaly_bn = self.scorer.score(extracted_data)

        # 4. Composite Risk Level & Score Computation
        base_score = anomaly_score * 0.35

        has_critical = any(v.severity == "CRITICAL" for v in violations)
        has_high = any(v.severity == "HIGH" for v in violations)
        has_exact_dup = any(m.match_type == DuplicateMatchType.EXACT_SHA256 for m in dup_matches)
        has_near_dup = any(m.match_type == DuplicateMatchType.PERCEPTUAL_NEAR_DUPLICATE for m in dup_matches)

        if has_critical or has_exact_dup:
            risk_level = RiskLevel.RISK_HIGH_REVIEW_REQUIRED
            risk_score = min(1.0, max(0.85, base_score + 0.60))
        elif has_high or has_near_dup or anomaly_score > 0.65:
            risk_level = RiskLevel.RISK_MEDIUM
            risk_score = min(0.84, max(0.50, base_score + 0.35))
        else:
            risk_level = RiskLevel.RISK_LOW
            risk_score = min(0.40, max(0.05, base_score))

        return BhumiGuardReport(
            schema_version=SCHEMA_VERSION,
            doc_id=assigned_doc_id,
            risk_level=risk_level,
            risk_score=round(risk_score, 4),
            duplicate_matches=dup_matches,
            rule_violations=violations,
            anomaly_score=anomaly_score,
            anomaly_explanation_bn=anomaly_bn,
            feature_contributions=feat_contribs,
            disclaimer=DISCLAIMER_TEXT
        )
