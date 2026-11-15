"""
BhumiLens AI — Deterministic Land Validation Service (Layer 6).
Implements exact mathematical verification for Bangladeshi land documents:
1. Exact Land Unit Conversions (Shotok, Katha, Bigha, Acre, Ajutangsho) using Python Decimal.
2. 16-Ana Traditional Bengali Land Share (আনা-গন্ডা-কড়া-ক্রান্তি-তিল) using Python Fraction.
3. Left-Margin Stamp Duty Equation Arithmetic.
4. Date Chronology & Cross-Field Consistency.
5. Emits strict VerificationReport schema.
"""
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from typing import Optional, Dict, Any, List, Tuple

from backend.schemas.deed_schema import DeedExtractionSchema, LandUnit, DeedType
from backend.schemas.verification_schema import (
    ValidationSeverity,
    ValidationFlag,
    LandUnitConversionResult,
    SixteenAnaValidationResult,
    StampDutyValidationResult,
    ChronologyValidationResult,
    VerificationReport
)

BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

# Bangladeshi Land Revenue Constants (Exact Decimals)
# 1 Acre = 100 Shotok (Decimal)
# 1 Bigha = 33 Shotok (20 Katha)
# 1 Katha = 1.65 Shotok (33 / 20)
# 1 Ajutangsho = 0.01 Shotok (1/100)
# 1 Shotok = 435.6 sq ft
SHOTOK_PER_ACRE = Decimal("100.0")
SHOTOK_PER_BIGHA = Decimal("33.0")
SHOTOK_PER_KATHA = Decimal("1.65")
SHOTOK_PER_AJUTANGSHO = Decimal("0.01")
SQFT_PER_SHOTOK = Decimal("435.6")

def bn_to_en(text: Any) -> str:
    if not text:
        return ""
    return str(text).translate(BN_DIGITS).strip()

class LandUnitConverter:
    """Exact arithmetic land unit converter using Python Decimal."""

    @classmethod
    def convert_area(cls, area: float, unit: LandUnit) -> LandUnitConversionResult:
        dec_area = Decimal(str(area))

        # Convert to base unit: Shotok
        if unit == LandUnit.SHOTOK:
            shotok = dec_area
        elif unit == LandUnit.KATHA:
            shotok = dec_area * SHOTOK_PER_KATHA
        elif unit == LandUnit.BIGHA:
            shotok = dec_area * SHOTOK_PER_BIGHA
        elif unit == LandUnit.ACRE:
            shotok = dec_area * SHOTOK_PER_ACRE
        elif unit == LandUnit.AJUTANGSHO:
            shotok = dec_area * SHOTOK_PER_AJUTANGSHO
        else:
            shotok = dec_area

        # Convert from Shotok to all units
        katha = shotok / SHOTOK_PER_KATHA
        bigha = shotok / SHOTOK_PER_BIGHA
        acre = shotok / SHOTOK_PER_ACRE
        ajutangsho = shotok / SHOTOK_PER_AJUTANGSHO
        sq_ft = shotok * SQFT_PER_SHOTOK

        precision = Decimal("0.0001")
        conversions = {
            "shotok": float(shotok.quantize(precision, rounding=ROUND_HALF_UP)),
            "katha": float(katha.quantize(precision, rounding=ROUND_HALF_UP)),
            "bigha": float(bigha.quantize(precision, rounding=ROUND_HALF_UP)),
            "acre": float(acre.quantize(precision, rounding=ROUND_HALF_UP)),
            "ajutangsho": float(ajutangsho.quantize(precision, rounding=ROUND_HALF_UP)),
            "sq_ft": float(sq_ft.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        }

        return LandUnitConversionResult(
            original_area=area,
            original_unit=unit,
            conversions=conversions
        )

class SixteenAnaValidator:
    """Validates archaic 16-Ana ownership shares using Python Fraction."""

    @classmethod
    def parse_notation(cls, notation: str) -> SixteenAnaValidationResult:
        en_str = bn_to_en(notation)

        ana = Decimal("0")
        gonda = Decimal("0")
        kara = Decimal("0")
        kranti = Decimal("0")
        til = Decimal("0")

        m_ana = re.search(r"(\d+(?:\.\d+)?)\s*(?:আনা|ana)", en_str, re.IGNORECASE)
        if m_ana:
            ana = Decimal(m_ana.group(1))

        m_gonda = re.search(r"(\d+(?:\.\d+)?)\s*(?:গন্ডা|গণ্ডা|gonda)", en_str, re.IGNORECASE)
        if m_gonda:
            gonda = Decimal(m_gonda.group(1))

        m_kara = re.search(r"(\d+(?:\.\d+)?)\s*(?:কড়া|কড়া|করা|kara|kora)", en_str, re.IGNORECASE)
        if m_kara:
            kara = Decimal(m_kara.group(1))

        m_kranti = re.search(r"(\d+(?:\.\d+)?)\s*(?:ক্রান্তি|kranti)", en_str, re.IGNORECASE)
        if m_kranti:
            kranti = Decimal(m_kranti.group(1))

        m_til = re.search(r"(\d+(?:\.\d+)?)\s*(?:তিল|til)", en_str, re.IGNORECASE)
        if m_til:
            til = Decimal(m_til.group(1))

        # 16 Ana = 1.0 (Full ownership)
        # 1 Ana = 1/16
        # 1 Gonda = 1/320
        # 1 Kara = 1/1280
        # 1 Kranti = 1/3840
        # 1 Til = 1/76800
        total_frac = (
            Fraction(int(ana * 100), 1600) +
            Fraction(int(gonda * 100), 32000) +
            Fraction(int(kara * 100), 128000) +
            Fraction(int(kranti * 100), 384000) +
            Fraction(int(til * 100), 7680000)
        )

        decimal_val = float(total_frac)
        percentage_val = decimal_val * 100.0

        is_valid = 0.0 <= decimal_val <= 1.00001
        err_msg = None if is_valid else f"Transferred share ({percentage_val:.2f}%) exceeds 16 Ana (100%)"

        return SixteenAnaValidationResult(
            raw_notation=notation,
            ana=float(ana),
            gonda=float(gonda),
            kara=float(kara),
            kranti=float(kranti),
            til=float(til),
            decimal_share=round(decimal_val, 6),
            percentage_share=round(percentage_val, 4),
            is_valid=is_valid,
            error_message=err_msg
        )

class LandValidationService:
    """GovTech-grade deterministic rule engine for Bangladeshi Land Documents."""

    def __init__(self):
        self.unit_converter = LandUnitConverter()
        self.ana_validator = SixteenAnaValidator()

    def validate_stamp_duty(self, raw_stamp_text: Optional[str], declared_total: Optional[float] = None) -> StampDutyValidationResult:
        if not raw_stamp_text:
            return StampDutyValidationResult(is_valid=True, status="NO_STAMP_EQUATION")

        en_str = bn_to_en(raw_stamp_text)
        addends: List[float] = []
        stated_total: float = 0.0

        if "=" in en_str:
            left, right = en_str.split("=", 1)
            addends = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", left)]
            r_nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", right)]
            stated_total = r_nums[0] if r_nums else 0.0
        else:
            nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", en_str)]
            if len(nums) >= 2:
                addends = nums[:-1]
                stated_total = nums[-1]
            elif len(nums) == 1 and declared_total:
                addends = [nums[0]]
                stated_total = declared_total

        computed_sum = sum(addends)
        if stated_total == 0.0 and declared_total:
            stated_total = declared_total

        is_match = abs(computed_sum - stated_total) < 0.01 and len(addends) > 0
        status = "STAMP_SUM_VERIFIED" if is_match else "STAMP_MATH_MISMATCH"

        return StampDutyValidationResult(
            raw_math_text=raw_stamp_text,
            addends=addends,
            computed_sum=computed_sum,
            stated_total=stated_total,
            is_valid=is_match,
            status=status
        )

    def validate_chronology(self, registration_date_str: Optional[str], copy_issue_date_str: Optional[str]) -> ChronologyValidationResult:
        if not registration_date_str:
            return ChronologyValidationResult(is_valid=True, status="NO_REGISTRATION_DATE")

        en_reg = bn_to_en(registration_date_str)
        en_copy = bn_to_en(copy_issue_date_str) if copy_issue_date_str else ""

        def parse_date(date_text: str) -> Optional[datetime]:
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(date_text, fmt)
                except ValueError:
                    pass
            return None

        d_reg = parse_date(en_reg)
        if not d_reg:
            return ChronologyValidationResult(
                is_valid=False,
                status="INVALID_REGISTRATION_DATE_FORMAT"
            )

        now = datetime.now()
        if d_reg > now:
            return ChronologyValidationResult(
                registration_date_iso=d_reg.strftime("%Y-%m-%d"),
                is_valid=False,
                status="FUTURE_REGISTRATION_DATE"
            )

        d_copy = parse_date(en_copy) if en_copy else None
        gap_years = None
        is_valid = True
        status = "CHRONOLOGY_VALID"

        if d_copy:
            if d_copy < d_reg:
                is_valid = False
                status = "COPY_DATE_PRECEEDS_REGISTRATION"
            else:
                gap_days = (d_copy - d_reg).days
                gap_years = round(gap_days / 365.25, 2)

        return ChronologyValidationResult(
            registration_date_iso=d_reg.strftime("%Y-%m-%d"),
            copy_issue_date_iso=d_copy.strftime("%Y-%m-%d") if d_copy else None,
            gap_years=gap_years,
            is_valid=is_valid,
            status=status
        )

    def validate_deed(self, deed: DeedExtractionSchema) -> VerificationReport:
        flags: List[ValidationFlag] = []
        missing_mandatory: List[str] = []

        # 1. Mandatory Core Fields Check
        if not deed.deed_number:
            missing_mandatory.append("deed_number")
            flags.append(ValidationFlag(
                severity=ValidationSeverity.ERROR,
                code="MISSING_DEED_NUMBER",
                message="দলিল নম্বর পাওয়া যায়নি। সরকারি রেকর্ডে দলিল নম্বর বাধ্যতামূলক।",
                field="deed_number"
            ))
        else:
            flags.append(ValidationFlag(
                severity=ValidationSeverity.PASS,
                code="DEED_NUMBER_PRESENT",
                message=f"দলিল নম্বর বিদ্যমান: {deed.deed_number}",
                field="deed_number"
            ))

        if deed.deed_type == DeedType.UNKNOWN:
            missing_mandatory.append("deed_type")
            flags.append(ValidationFlag(
                severity=ValidationSeverity.WARNING,
                code="UNKNOWN_DEED_TYPE",
                message="দলিলের প্রকৃতি / শ্রেণিবিভাগ নিশ্চিত হওয়া যায়নি।",
                field="deed_type"
            ))

        if not deed.location.mouza:
            missing_mandatory.append("mouza")
            flags.append(ValidationFlag(
                severity=ValidationSeverity.WARNING,
                code="MISSING_MOUZA",
                message="মৌজার নাম অনুপস্থিত। জমি শনাক্তকরণে মৌজা প্রয়োজন।",
                field="location.mouza"
            ))
        else:
            flags.append(ValidationFlag(
                severity=ValidationSeverity.PASS,
                code="MOUZA_PRESENT",
                message=f"মৌজা শনাক্তকৃত: {deed.location.mouza}",
                field="location.mouza"
            ))

        # Check Dag / Khatian presence
        has_dags = bool(deed.land_details.dag_numbers)
        has_khatians = bool(deed.land_details.khatian_numbers)
        if not has_dags and not has_khatians:
            flags.append(ValidationFlag(
                severity=ValidationSeverity.WARNING,
                code="MISSING_TAFSIL_SCHEDULE_PAGE",
                message="এই পাতায় দাগ বা খতিয়ান নম্বর পাওয়া যায়নি (দলিলের পরবর্তী তফসিল পাতায় থাকতে পারে)—মনগড়া তথ্য বসানো নিষেধ।",
                field="land_details"
            ))
        else:
            flags.append(ValidationFlag(
                severity=ValidationSeverity.PASS,
                code="TAFSIL_SCHEDULE_FOUND",
                message=f"দাগ: {deed.land_details.dag_numbers}, খতিয়ান: {deed.land_details.khatian_numbers}",
                field="land_details"
            ))

        # 2. Land Area Conversion & Validation
        unit_res: Optional[LandUnitConversionResult] = None
        if deed.land_details.land_area is not None:
            if deed.land_details.land_area <= 0:
                flags.append(ValidationFlag(
                    severity=ValidationSeverity.ERROR,
                    code="INVALID_LAND_AREA_NON_POSITIVE",
                    message="জমির পরিমাণ শূন্য বা ঋণাত্মক হতে পারে না।",
                    field="land_details.land_area"
                ))
            else:
                unit = deed.land_details.land_unit if deed.land_details.land_unit != LandUnit.UNKNOWN else LandUnit.SHOTOK
                unit_res = self.unit_converter.convert_area(deed.land_details.land_area, unit)
                flags.append(ValidationFlag(
                    severity=ValidationSeverity.PASS,
                    code="LAND_AREA_CONVERTED",
                    message=f"জমির পরিমাণ {deed.land_details.land_area} {unit.value} ({unit_res.conversions['shotok']} শতাংশ / {unit_res.conversions['sq_ft']} বর্গফুট)।",
                    field="land_details.land_area",
                    details=unit_res.conversions
                ))
        else:
            missing_mandatory.append("land_area")
            flags.append(ValidationFlag(
                severity=ValidationSeverity.INFO,
                code="LAND_AREA_NOT_STATED",
                message="জমির পরিমাণ এই পাতায় উল্লেখ নেই।",
                field="land_details.land_area"
            ))

        # 3. 16-Ana Share Validation
        share_res: Optional[SixteenAnaValidationResult] = None
        if deed.land_details.sixteen_ana_share:
            share_res = self.ana_validator.parse_notation(deed.land_details.sixteen_ana_share)
            if not share_res.is_valid:
                flags.append(ValidationFlag(
                    severity=ValidationSeverity.ERROR,
                    code="EXCESS_ANA_SHARE",
                    message=share_res.error_message or "১৬ আনা শেয়ার অতিক্রম করেছে!",
                    field="land_details.sixteen_ana_share",
                    details={"share_pct": share_res.percentage_share}
                ))
            else:
                flags.append(ValidationFlag(
                    severity=ValidationSeverity.PASS,
                    code="ANA_SHARE_VALID",
                    message=f"আনা-গন্ডা শেয়ার সঠিক: {share_res.percentage_share:.2f}% (দশমিক: {share_res.decimal_share})",
                    field="land_details.sixteen_ana_share"
                ))
        elif deed.land_details.ownership_share is not None:
            if 0.0 < deed.land_details.ownership_share <= 1.00001:
                flags.append(ValidationFlag(
                    severity=ValidationSeverity.PASS,
                    code="DECIMAL_SHARE_VALID",
                    message=f"মালিকানার অংশ বৈধ: {deed.land_details.ownership_share * 100:.2f}%",
                    field="land_details.ownership_share"
                ))
            else:
                flags.append(ValidationFlag(
                    severity=ValidationSeverity.ERROR,
                    code="INVALID_DECIMAL_SHARE_RANGE",
                    message=f"মালিকানার অংশ ০ থেকে ১-এর মধ্যে হতে হবে (প্রাপ্ত: {deed.land_details.ownership_share})",
                    field="land_details.ownership_share"
                ))

        # 4. Stamp Duty Arithmetic
        stamp_math_text = deed.provenance.raw_ocr_text or ""
        stamp_res = self.validate_stamp_duty(stamp_math_text, deed.stamp_duty_bdt)
        if stamp_res.status == "STAMP_MATH_MISMATCH":
            flags.append(ValidationFlag(
                severity=ValidationSeverity.ERROR,
                code="STAMP_MATH_MISMATCH",
                message=f"স্ট্যাম্প শুল্কের যোগফল মেলেনি: গণনাকৃত {stamp_res.computed_sum} টাকা != উল্লেখিত {stamp_res.stated_total} টাকা।",
                field="stamp_duty_bdt"
            ))
        elif stamp_res.status == "STAMP_SUM_VERIFIED":
            flags.append(ValidationFlag(
                severity=ValidationSeverity.PASS,
                code="STAMP_MATH_VERIFIED",
                message=f"স্ট্যাম্প শুল্কের গাণিতিক যোগফল সঠিক ({stamp_res.computed_sum} টাকা)।",
                field="stamp_duty_bdt"
            ))

        # 5. Date Chronology Validation
        chrono_res = self.validate_chronology(deed.registration_date, deed.copy_issue_date)
        if not chrono_res.is_valid:
            flags.append(ValidationFlag(
                severity=ValidationSeverity.ERROR,
                code="CHRONOLOGY_ANOMALY",
                message=f"তারিখের অসঙ্গতি: {chrono_res.status}",
                field="registration_date"
            ))
        else:
            if chrono_res.registration_date_iso:
                msg = f"রেজিস্ট্রেশনের তারিখ বৈধ ({chrono_res.registration_date_iso})"
                if chrono_res.copy_issue_date_iso:
                    msg += f" <= নকল ইস্যুর তারিখ ({chrono_res.copy_issue_date_iso}, ব্যবধান: {chrono_res.gap_years} বছর)"
                flags.append(ValidationFlag(
                    severity=ValidationSeverity.PASS,
                    code="CHRONOLOGY_VERIFIED",
                    message=msg,
                    field="registration_date"
                ))

        # Determine overall validity and score
        has_errors = any(f.severity == ValidationSeverity.ERROR for f in flags)
        is_overall_valid = not has_errors

        score = 1.0
        for f in flags:
            if f.severity == ValidationSeverity.ERROR:
                score -= 0.3
            elif f.severity == ValidationSeverity.WARNING:
                score -= 0.1
            elif f.severity == ValidationSeverity.INFO:
                score -= 0.02
        score = max(0.0, min(1.0, round(score, 2)))

        now_utc = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        return VerificationReport(
            doc_id=deed.doc_id,
            is_valid=is_overall_valid,
            score=score,
            flags=flags,
            unit_conversions=unit_res,
            share_validation=share_res,
            stamp_validation=stamp_res,
            chronology_validation=chrono_res,
            missing_mandatory_fields=missing_mandatory,
            timestamp_utc=now_utc
        )
