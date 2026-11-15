"""
Upgrade 3: Deterministic Land-Math, Stamp Arithmetic, Chronological & Ana-Gonda Share Validator.
Performs mathematical cross-verification without claiming legal ownership.
"""
import re
from datetime import datetime

BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

def bn_to_en_number(text):
    if not text:
        return ""
    return str(text).translate(BN_DIGITS)

def extract_numbers(text):
    en_text = bn_to_en_number(text)
    return [float(x.replace(",", "")) for x in re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", en_text)]

class LandMathValidator:
    """
    Validates mathematical and domain consistency across extracted land record fields.
    """

    @staticmethod
    def verify_stamp_duty_equation(raw_stamp_text):
        """
        Parses left-margin stamp equations such as: '১০০+১০০+১০০+১০০+৫০=৪৫০/-'
        and checks if the sum of individual stamp sheets equals the stated total.
        """
        en_str = bn_to_en_number(raw_stamp_text)
        if "=" not in en_str:
            nums = [int(n) for n in re.findall(r"\d+", en_str)]
            if len(nums) >= 2:
                addends, stated_total = nums[:-1], nums[-1]
            else:
                return {"valid": False, "status": "UNPARSEABLE_STAMP_MATH", "details": raw_stamp_text}
        else:
            left_part, right_part = en_str.split("=", 1)
            addends = [int(n) for n in re.findall(r"\d+", left_part)]
            right_nums = [int(n) for n in re.findall(r"\d+", right_part)]
            stated_total = right_nums[0] if right_nums else 0

        computed_sum = sum(addends)
        is_match = (computed_sum == stated_total) and len(addends) > 0
        return {
            "valid": is_match,
            "addends": addends,
            "computed_sum": computed_sum,
            "stated_total": stated_total,
            "status": "STAMP_SUM_VERIFIED" if is_match else "MATH_MISMATCH_FLAGGED"
        }

    @staticmethod
    def verify_date_chronology(registration_date_str, copy_issue_date_str):
        """
        Checks that Original Deed Registration Date <= Certified Copy Issue Date.
        Example: Registration 28/10/2001 <= Copy Issue 11/03/2010.
        """
        en_reg = bn_to_en_number(registration_date_str).strip()
        en_copy = bn_to_en_number(copy_issue_date_str).strip()
        try:
            d_reg = datetime.strptime(en_reg, "%d/%m/%Y")
            d_copy = datetime.strptime(en_copy, "%d/%m/%Y")
            is_valid = d_copy >= d_reg
            gap_days = (d_copy - d_reg).days
            return {
                "valid": is_valid,
                "registration_date_iso": d_reg.strftime("%Y-%m-%d"),
                "copy_issue_date_iso": d_copy.strftime("%Y-%m-%d"),
                "gap_years": round(gap_days / 365.25, 2),
                "status": "CHRONOLOGY_VALID" if is_valid else "TEMPORAL_ANOMALY_FLAGGED"
            }
        except ValueError as e:
            return {"valid": False, "status": "DATE_FORMAT_ERROR", "error": str(e)}

    @staticmethod
    def convert_ana_gonda_to_decimal_share(ana=0, gonda=0, kora=0, kranti=0):
        """
        Converts traditional Bangladeshi 16-Ana land ownership share notation into exact decimal fraction:
        16 Ana = 1.0000 (Full Share)
        1 Ana = 20 Gonda -> 320 Gonda = 1.0
        1 Gonda = 4 Kora -> 1280 Kora = 1.0
        1 Kora = 3 Kranti -> 3840 Kranti = 1.0
        """
        total_fraction = (ana / 16.0) + (gonda / 320.0) + (kora / 1280.0) + (kranti / 3840.0)
        return {
            "input_notation": f"{ana} আনা {gonda} গন্ডা {kora} কড়া {kranti} ক্রান্তি",
            "decimal_share": round(total_fraction, 6),
            "percentage_share": round(total_fraction * 100.0, 4),
            "valid_range": 0.0 < total_fraction <= 1.00001
        }

    @classmethod
    def run_full_document_validation(cls, structured_fields):
        flags = []
        stamp_check = cls.verify_stamp_duty_equation(structured_fields.get("stamp_duty_math", ""))
        if not stamp_check["valid"]:
            flags.append({
                "severity": "ERROR",
                "code": "STAMP_MATH_MISMATCH",
                "message": f"স্ট্যাম্প শুল্কের যোগফল মেলেনি: {stamp_check}"
            })
        else:
            flags.append({
                "severity": "PASS",
                "code": "STAMP_MATH_VERIFIED",
                "message": f"স্ট্যাম্প শুল্কের গাণিতিক যোগফল সঠিক ({'+'.join(map(str, stamp_check['addends']))} = {stamp_check['computed_sum']} টাকা)।"
            })

        date_check = cls.verify_date_chronology(
            structured_fields.get("registration_date", ""),
            structured_fields.get("copy_issue_date", "")
        )
        if not date_check["valid"]:
            flags.append({
                "severity": "ERROR",
                "code": "CHRONOLOGY_INVALID",
                "message": "নকল ইস্যুর তারিখ মূল রেজিস্ট্রেশনের তারিখের আগের হতে পারে না!"
            })
        else:
            flags.append({
                "severity": "PASS",
                "code": "CHRONOLOGY_VERIFIED",
                "message": f"তারিখের ক্রম সঠিক: মূল রেজিস্ট্রেশন ({date_check['registration_date_iso']}) <= নকল ইস্যু ({date_check['copy_issue_date_iso']})।"
            })

        # Check Dag / Khatian absence on Page 1 of Deed
        if not structured_fields.get("dag_number") or not structured_fields.get("khatian_number"):
            flags.append({
                "severity": "WARNING",
                "code": "MISSING_TAFSIL_SCHEDULE_PAGE",
                "message": "এই ১ম পাতায় দাগ বা খতিয়ান নম্বর নেই (দলিলের পরবর্তী 'তফসিল/Schedule' পাতায় সংযুক্ত থাকে)—অপারেটরকে মনগড়া দাগ নম্বর বসাতে নিষেধ করা হলো।"
            })

        return {
            "stamp_validation": stamp_check,
            "date_validation": date_check,
            "validation_flags": flags
        }
