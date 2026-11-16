"""
BhumiLens AI — Production Land Information Extraction Service (Layer 5).
Combines:
1. Normalization (Unicode NFC, Digit Canonicalization, Domain Lexicon Correction).
2. Qwen3-0.6B Fine-Tuned LoRA Extractor (or offline deterministic rule engine).
3. Deterministic Gazetteers and Regex Fallbacks for 100% schema compliance.
4. Line-to-Entity Provenance & Visual Evidence Crop Mapping.
5. Strict Zero-Hallucination Grounding Validation (null preservation).
"""
import os
import re
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from backend.schemas.deed_schema import (
    DeedExtractionSchema,
    DeedType,
    LandUnit,
    LocationDetails,
    LandDetails,
    Boundaries,
    Party,
    FieldProvenance,
    SCHEMA_VERSION
)
from backend.schemas.htr_schema import DocumentHTRResult, LineRecognitionResult
from backend.services.normalization_service import BanglaLandNormalizer, default_normalizer

logger = logging.getLogger("bhumilens.extraction_service")

# Common Gazeteer Mappings
MOUZA_LIST = [
    "বারেন্ডা", "মৌচাক", "বিরুলিয়া", "বিরুলিয়া", "কাওরাইদ", "পাইস্কা",
    "জয়দেবপুর", "জয়দেবপুর", "টঙ্গী", "কালীগঞ্জ", "কাপাসিয়া", "কাপাসিয়া", "শ্রীপুর"
]

UPAZILA_LIST = [
    "গাজীপুর সদর", "কালিয়াকৈর", "কালিয়াকৈর", "সাভার", "শ্রীপুর", "ধনবাড়ী", "ধনবাড়ী",
    "কালীগঞ্জ", "কাপাসিয়া", "কাপাসিয়া", "মিরপুর", "মোহাম্মদপুর"
]

DISTRICT_LIST = ["গাজীপুর", "ঢাকা", "টাঙ্গাইল", "নারায়ণগঞ্জ", "নারায়ণগঞ্জ", "মানিকগঞ্জ", "মুন্সিগঞ্জ"]

DEED_TYPE_PATTERNS = [
    (re.compile(r"(সাফ\s*কবলা|SAF[_\s]*KABALA|কবলা|বিক্রয়|খরিদা)", re.IGNORECASE), DeedType.SAF_KABALA),
    (re.compile(r"(বায়না|বায়না|BAYNA[_\s]*PATRA|BAYANAPATRA)", re.IGNORECASE), DeedType.BAYNAPATRA),
    (re.compile(r"(বণ্টন|বন্টন|আপোষ\s*বন্টন|BONTON[_\s]*AMA)", re.IGNORECASE), DeedType.BONTONAMA),
    (re.compile(r"(হেবা\s*বিল\s*এওয়াজ|হেবা\s*বিল\s*এওয়াজ|HEBA[_\s]*BIL[_\s]*EWAZ)", re.IGNORECASE), DeedType.HEBA_BIL_EWAZ),
    (re.compile(r"(দানপত্র|হেবা\s*ঘোষণা|হেবানামা|HEBA[_\s]*DECLARATION|HEBA)", re.IGNORECASE), DeedType.HEBA_DECLARATION),
    (re.compile(r"(খতিয়ান|খতিয়ান|পর্চা|KHATIAN)", re.IGNORECASE), DeedType.KHATIAN_RECORD),
    (re.compile(r"(বন্ধক|বন্ধকী|MORTGAGE)", re.IGNORECASE), DeedType.MORTGAGE),
]

LAND_UNIT_PATTERNS = [
    (re.compile(r"(শতাংশ|শতক|ডেসিমেল|SHOTOK)", re.IGNORECASE), LandUnit.SHOTOK),
    (re.compile(r"(কাঠা|কাটা|KATHA)", re.IGNORECASE), LandUnit.KATHA),
    (re.compile(r"(বিঘা|BIGHA)", re.IGNORECASE), LandUnit.BIGHA),
    (re.compile(r"(একর|ACRE)", re.IGNORECASE), LandUnit.ACRE),
    (re.compile(r"(অযুতাংশ|AJUTANGSHO)", re.IGNORECASE), LandUnit.AJUTANGSHO),
]

class LandExtractionService:
    def __init__(
        self,
        normalizer: Optional[BanglaLandNormalizer] = None,
        model_mode: str = "hybrid",  # "hybrid", "deterministic", "qwen_lora"
        lora_adapter_dir: Optional[str] = None,
        base_model_dir: Optional[str] = None
    ):
        self.normalizer = normalizer or default_normalizer
        self.model_mode = model_mode
        self.lora_adapter_dir = Path(lora_adapter_dir) if lora_adapter_dir else Path("models/extractor/qwen3-0.6b-deed-lora")
        self.base_model_dir = Path(base_model_dir) if base_model_dir else Path("models/extractor/qwen3-0.6b-base")
        self._qwen_model = None
        self._qwen_tokenizer = None

    def _ensure_qwen_loaded(self):
        """Lazy loads fine-tuned LoRA model if requested and available."""
        if self._qwen_model is not None:
            return

        if not self.lora_adapter_dir.exists():
            logger.info("LoRA adapter directory %s not found. Operating in deterministic mode.", self.lora_adapter_dir)
            return

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import PeftModel

            # Use CPU for small 0.6B LLM generation to bypass PyTorch 2.15 macOS MPS Event issues
            device = torch.device("cpu")
            model_name = "Qwen/Qwen3-0.6B"
            cache_dir = str(self.base_model_dir) if self.base_model_dir.exists() else None

            self._qwen_tokenizer = AutoTokenizer.from_pretrained(
                str(self.lora_adapter_dir),
                cache_dir=cache_dir,
                local_files_only=True if cache_dir else False
            )
            base = AutoModelForCausalLM.from_pretrained(
                model_name,
                cache_dir=cache_dir,
                local_files_only=True if cache_dir else False,
                torch_dtype=torch.float32
            ).to(device)
            self._qwen_model = PeftModel.from_pretrained(base, str(self.lora_adapter_dir)).to(device)
            self._qwen_model.eval()
            logger.info("Qwen3-0.6B + LoRA extractor successfully loaded on %s.", device)
        except Exception as e:
            logger.warning("Could not load Qwen3 LoRA model (%s). Falling back to deterministic extraction.", e)
            self._qwen_model = None

    def extract_from_text(
        self,
        raw_text: str,
        doc_id: str = "DEED_DOC",
        line_crops_map: Optional[Dict[str, Any]] = None
    ) -> DeedExtractionSchema:
        """
        Extracts structured land deed data from text with strict zero-hallucination validation.
        """
        # Step 1: Normalization
        norm_result = self.normalizer.normalize(raw_text)
        normalized_text = norm_result["normalized_text"]
        norm_en_digits = self.normalizer.to_english_digits(normalized_text)

        warnings: List[str] = []
        field_confidence: Dict[str, float] = {}
        evidence_crops: Dict[str, Any] = {}

        # Step 2: Deterministic Extraction (always runs as high-precision anchor)
        det_data = self._extract_deterministic(normalized_text, norm_en_digits)

        # Step 3: SLM / LoRA Extraction (if enabled and loaded)
        llm_data: Optional[Dict[str, Any]] = None
        if self.model_mode in ["hybrid", "qwen_lora"]:
            self._ensure_qwen_loaded()
            if self._qwen_model is not None and self._qwen_tokenizer is not None:
                llm_data = self._extract_with_qwen(normalized_text)

        # Step 4: Merge & Grounding Enforcement (Zero Hallucination)
        final_fields = self._merge_and_validate(det_data, llm_data, normalized_text, norm_en_digits, warnings)

        # Step 5: Map visual evidence crops if available
        if line_crops_map:
            evidence_crops.update(line_crops_map)

        # Build schema instance
        deed_schema = DeedExtractionSchema(
            schema_version=SCHEMA_VERSION,
            doc_id=doc_id,
            deed_number=final_fields.get("deed_number"),
            deed_year=final_fields.get("deed_year"),
            deed_type=final_fields.get("deed_type") or DeedType.UNKNOWN,
            registration_date=final_fields.get("registration_date"),
            copy_issue_date=final_fields.get("copy_issue_date"),
            deed_value_bdt=final_fields.get("deed_value_bdt"),
            stamp_duty_bdt=final_fields.get("stamp_duty_bdt"),
            registration_office=final_fields.get("registration_office"),
            location=LocationDetails(
                mouza=final_fields.get("mouza"),
                jl_number=final_fields.get("jl_number"),
                union=final_fields.get("union"),
                upazila=final_fields.get("upazila"),
                district=final_fields.get("district")
            ),
            land_details=LandDetails(
                dag_numbers=final_fields.get("dag_numbers") or [],
                khatian_numbers=final_fields.get("khatian_numbers") or [],
                land_area=final_fields.get("land_area"),
                land_unit=final_fields.get("land_unit") or LandUnit.UNKNOWN,
                ownership_share=final_fields.get("ownership_share"),
                sixteen_ana_share=final_fields.get("sixteen_ana_share")
            ),
            boundaries=Boundaries(
                north=final_fields.get("north"),
                south=final_fields.get("south"),
                east=final_fields.get("east"),
                west=final_fields.get("west")
            ),
            provenance=FieldProvenance(
                raw_ocr_text=raw_text,
                normalized_ocr_text=normalized_text,
                field_confidence=final_fields.get("field_confidence", {}),
                evidence_crops=evidence_crops,
                warnings=warnings
            )
        )
        return deed_schema

    def extract_from_htr_result(self, htr_result: DocumentHTRResult) -> DeedExtractionSchema:
        """
        Extracts structured information from full DocumentHTRResult and links lines to evidence crops.
        """
        # Map line crops by matching text tokens
        line_crops_map: Dict[str, Any] = {}
        for line in htr_result.recognized_lines:
            norm_line = self.normalizer.clean_unicode(line.raw_text)
            if "দলিল" in norm_line:
                line_crops_map["deed_number"] = {
                    "line_id": line.line_id,
                    "crop_path": line.evidence_crop_path,
                    "confidence": line.confidence
                }
            if "মৌজা" in norm_line:
                line_crops_map["mouza"] = {
                    "line_id": line.line_id,
                    "crop_path": line.evidence_crop_path,
                    "confidence": line.confidence
                }
            if any(u in norm_line for u in ["শতাংশ", "শতক", "জমির পরিমাণ", "জমি"]):
                line_crops_map["land_area"] = {
                    "line_id": line.line_id,
                    "crop_path": line.evidence_crop_path,
                    "confidence": line.confidence
                }
            if "দাগ" in norm_line:
                line_crops_map["dag_numbers"] = {
                    "line_id": line.line_id,
                    "crop_path": line.evidence_crop_path,
                    "confidence": line.confidence
                }

        return self.extract_from_text(
            raw_text=htr_result.full_raw_text,
            doc_id=htr_result.doc_id,
            line_crops_map=line_crops_map
        )

    def _extract_deterministic(self, text: str, text_en_digits: str) -> Dict[str, Any]:
        """High-precision regex and gazetteer extraction."""
        extracted: Dict[str, Any] = {
            "field_confidence": {}
        }

        # 1. Deed Number & Year
        deed_no_match = re.search(r"দলিল\s*নং?\s*([0-9\/\-]+)", text_en_digits)
        if deed_no_match:
            full_val = deed_no_match.group(1).strip()
            if "/" in full_val:
                parts = full_val.split("/")
                extracted["deed_number"] = parts[0].strip()
                try:
                    yr = int(parts[1].strip())
                    if 1900 <= yr <= 2035:
                        extracted["deed_year"] = yr
                except ValueError:
                    pass
            else:
                extracted["deed_number"] = full_val
            extracted["field_confidence"]["deed_number"] = 0.95

        # 2. Deed Type
        for pattern, dtype in DEED_TYPE_PATTERNS:
            if pattern.search(text):
                extracted["deed_type"] = dtype
                extracted["field_confidence"]["deed_type"] = 0.94
                break

        # 3. Mouza
        mouza_match = re.search(r"মৌজা\s*[:\-\s]*([^\s,।\n]+)", text)
        if mouza_match:
            cand = mouza_match.group(1).strip()
            extracted["mouza"] = cand
            extracted["field_confidence"]["mouza"] = 0.92
        else:
            for m in MOUZA_LIST:
                if m in text:
                    extracted["mouza"] = m
                    extracted["field_confidence"]["mouza"] = 0.88
                    break

        # 4. Upazila
        for u in UPAZILA_LIST:
            if u in text:
                extracted["upazila"] = u
                extracted["field_confidence"]["upazila"] = 0.90
                break

        # 5. District
        for d in DISTRICT_LIST:
            if d in text:
                extracted["district"] = d
                extracted["field_confidence"]["district"] = 0.90
                break

        # 6. Registration Date
        date_match = re.search(r"(\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4}\b)", text_en_digits)
        if date_match:
            extracted["registration_date"] = date_match.group(1).replace("-", "/").replace(".", "/")
            extracted["field_confidence"]["registration_date"] = 0.92

        # 7. Land Area and Unit
        area_match = re.search(r"(\d+(?:\.\d+)?)\s*(শতক|শতাংশ|ডেসিমেল|কাঠা|বিঘা|একর|SHOTOK|KATHA|BIGHA|ACRE)", text_en_digits, re.IGNORECASE)
        if area_match:
            try:
                extracted["land_area"] = float(area_match.group(1))
                unit_str = area_match.group(2).lower()
                for u_pat, u_enum in LAND_UNIT_PATTERNS:
                    if u_pat.search(unit_str):
                        extracted["land_unit"] = u_enum
                        break
                extracted["field_confidence"]["land_area"] = 0.93
            except ValueError:
                pass
        else:
            # Fallback for "জমি X শতক"
            alt_match = re.search(r"জমি\s*(\d+(?:\.\d+)?)\s*(শতাংশ|শতক|SHOTOK)?", text_en_digits)
            if alt_match:
                try:
                    extracted["land_area"] = float(alt_match.group(1))
                    extracted["land_unit"] = LandUnit.SHOTOK
                    extracted["field_confidence"]["land_area"] = 0.88
                except ValueError:
                    pass

        # 8. Dag Numbers
        dag_match = re.search(r"দাগ\s*নং?\s*([0-9\s,ওএবং\-]+)", text_en_digits)
        if dag_match:
            raw_dags = re.findall(r"\b\d+\b", dag_match.group(1))
            if raw_dags:
                extracted["dag_numbers"] = raw_dags
                extracted["field_confidence"]["dag_numbers"] = 0.90

        # 9. Khatian Numbers
        khatian_match = re.search(r"খতিয়ান\s*নং?\s*([0-9\s,ওএবং\-]+)", text_en_digits)
        if khatian_match:
            raw_khatians = re.findall(r"\b\d+\b", khatian_match.group(1))
            if raw_khatians:
                extracted["khatian_numbers"] = raw_khatians
                extracted["field_confidence"]["khatian_numbers"] = 0.90

        return extracted

    def _extract_with_qwen(self, normalized_text: str) -> Optional[Dict[str, Any]]:
        """Invokes fine-tuned Qwen3-0.6B LoRA model."""
        try:
            import torch
            device = next(self._qwen_model.parameters()).device
            system_prompt = "You are an expert GovTech Land Document Extraction Assistant. Extract structured information in pure JSON."
            user_msg = f"দলিলের টেক্সট:\n{normalized_text}\n\nউপরে উল্লিখিত দলিলের টেক্সট থেকে নির্ধারিত স্কিমা অনুযায়ী তথ্য এক্সট্র্যাক্ট করে JSON ফরম্যাটে আউটপুট দাও:"
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ]
            prompt = self._qwen_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = self._qwen_tokenizer(prompt, return_tensors="pt").to(device)

            with torch.inference_mode():
                outputs = self._qwen_model.generate(
                    **inputs,
                    max_new_tokens=256,
                    do_sample=False,
                    pad_token_id=self._qwen_tokenizer.eos_token_id
                )
            gen_text = self._qwen_tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()

            # Parse JSON
            match = re.search(r"```json\s*(\{.*?\})\s*```", gen_text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            start, end = gen_text.find("{"), gen_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(gen_text[start:end+1])
        except Exception as e:
            logger.debug("Qwen LoRA extraction exception: %s", e)
        return None

    def _merge_and_validate(
        self,
        det: Dict[str, Any],
        llm: Optional[Dict[str, Any]],
        text_bn: str,
        text_en: str,
        warnings: List[str]
    ) -> Dict[str, Any]:
        """
        Merges deterministic and LLM extraction outputs with strict grounding.
        If a field is not verified in the input text, it remains None.
        """
        result: Dict[str, Any] = {}
        conf = det.get("field_confidence", {})

        # Primary fields
        for field in ["deed_number", "deed_year", "deed_type", "registration_date",
                      "copy_issue_date", "deed_value_bdt", "stamp_duty_bdt", "registration_office",
                      "mouza", "jl_number", "union", "upazila", "district",
                      "land_area", "land_unit", "ownership_share", "sixteen_ana_share",
                      "north", "south", "east", "west"]:
            # Prioritize deterministic if found
            val = det.get(field)
            if val is not None:
                result[field] = val
            elif llm and llm.get(field) is not None:
                # Validate grounding before accepting LLM candidate
                llm_val = llm.get(field)
                val_str = str(llm_val)
                if val_str in text_bn or val_str in text_en:
                    result[field] = llm_val
                    conf[field] = 0.85
                else:
                    warnings.append(f"SUPPRESSED_UNGROUNDED_LLM_FIELD: {field}='{val_str}'")
                    result[field] = None
            else:
                result[field] = None

        # List fields (dag_numbers, khatian_numbers)
        for list_field in ["dag_numbers", "khatian_numbers"]:
            d_list = det.get(list_field, [])
            if d_list:
                result[list_field] = d_list
            elif llm and isinstance(llm.get(list_field), list):
                # Filter grounded items
                grounded = [item for item in llm[list_field] if str(item) in text_bn or str(item) in text_en]
                result[list_field] = grounded
                if grounded:
                    conf[list_field] = 0.80
            else:
                result[list_field] = []

        result["field_confidence"] = conf
        return result
