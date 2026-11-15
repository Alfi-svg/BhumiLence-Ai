#!/usr/bin/env python3
"""
BhumiLens AI — Land Extraction Benchmark Seed Generator
Generates 30 authentic-structure benchmark examples strictly tagged as
'synthetic_bangla_deed_template', validating each against DeedExtractionSchema.
"""
import os
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.schemas.deed_schema import (
    DeedExtractionSchema,
    DeedType,
    LandUnit,
    Party,
    LocationDetails,
    LandDetails,
    Boundaries,
    FieldProvenance
)

OUT_FILE = BASE_DIR / "research" / "datasets" / "annotations" / "deed_extraction_seed.jsonl"
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

SEED_TEMPLATES = [
    {
        "doc_id": "SEED_DOLIL_001",
        "deed_number": "২০০৭৮",
        "deed_year": 2001,
        "deed_type": DeedType.HEBA_BIL_EWAZ,
        "registration_date": "28/10/2001",
        "copy_issue_date": "11/03/2010",
        "deed_value_bdt": 4000.0,
        "stamp_duty_bdt": 450.0,
        "registration_office": "গাজীপুর সদর সাব-রেজিস্ট্রি অফিস",
        "sellers": [Party(name="মোসাঃ সালেহা খাতুন", father_or_husband="মৃত হাজী আবদুল গণি", address="বারেন্ডা, কাশিমপুর, গাজীপুর")],
        "buyers": [Party(name="মোসাঃ মাজেদা বেগম", father_or_husband="মোঃ ইউনুস আলী", address="বারেন্ডা, কাশিমপুর, গাজীপুর")],
        "location": LocationDetails(mouza="বারেন্ডা", jl_number="১০৫", union="কাশিমপুর", upazila="গাজীপুর সদর", district="গাজীপুর"),
        "land_details": LandDetails(dag_numbers=[], khatian_numbers=[], land_area=30.0, land_unit=LandUnit.SHOTOK, ownership_share=0.282813, sixteen_ana_share="৪ আনা ১০ গন্ডা ২ কড়া"),
        "boundaries": Boundaries(north="রাস্তা", south="আব্দুল আলীর জমি", east="নিজ দখল", west="খালের সীমানা"),
        "raw_ocr": "দলিল নং ২০০৭৮/২০০১ বেল এওয়াজ হেবা দলিল মৌজা বারেনডা জমি ৩০ শাতাংশ ১০০+১০০+১০০+১০০+৫০=৪৫০",
        "warnings": ["MISSING_TAFSIL_SCHEDULE_PAGE: ১ম পাতায় দাগ বা খতিয়ান নম্বর উল্লেখ নেই"]
    },
    {
        "doc_id": "SEED_DOLIL_002",
        "deed_number": "১২৪৩",
        "deed_year": 1998,
        "deed_type": DeedType.SAF_KABALA,
        "registration_date": "15/04/1998",
        "copy_issue_date": None,
        "deed_value_bdt": 85000.0,
        "stamp_duty_bdt": 2550.0,
        "registration_office": "কালিয়াকৈর সাব-রেজিস্ট্রি অফিস",
        "sellers": [Party(name="শ্রী বিমলেন্দু রায়", father_or_husband="মৃত কামিনী কুমার রায়", address="মৌচাক, কালিয়াকৈর, গাজীপুর")],
        "buyers": [Party(name="মোঃ হাবিবুর রহমান", father_or_husband="মোঃ খলিলুর রহমান", address="কোনাবাড়ী, গাজীপুর")],
        "location": LocationDetails(mouza="মৌচাক", jl_number="৮২", union="মৌচাক", upazila="কালিয়াকৈর", district="গাজীপুর"),
        "land_details": LandDetails(dag_numbers=["১৪২০", "১৪২১"], khatian_numbers=["৩১২"], land_area=12.5, land_unit=LandUnit.SHOTOK, ownership_share=1.0, sixteen_ana_share="১৬ আনা"),
        "boundaries": Boundaries(north="সরকারি হালট", south="বিমল রায়ের অবশিষ্টাংশ", east="তোফাজ্জলের জমি", west="নল জমি"),
        "raw_ocr": "১২৪৩ সাফ কবলা মৌচাক কালিয়াকৈর দাগ ১৪২০, ১৪২১ খতিয়ান ৩১২ সাড়ে ১২ শতাংশ টাকা ৮৫০০০/-",
        "warnings": []
    },
    {
        "doc_id": "SEED_DOLIL_003",
        "deed_number": "৫৬৭",
        "deed_year": 2012,
        "deed_type": DeedType.BONTONAMA,
        "registration_date": "05/08/2012",
        "copy_issue_date": "20/01/2018",
        "deed_value_bdt": 350000.0,
        "stamp_duty_bdt": 500.0,
        "registration_office": "সাভার সাব-রেজিস্ট্রি অফিস",
        "sellers": [Party(name="মোঃ জসিম উদ্দিন", father_or_husband="মৃত নুরুল হক", address="বিরুলিয়া, সাভার, ঢাকা")],
        "buyers": [Party(name="মোঃ রফিক উদ্দিন", father_or_husband="মৃত নুরুল হক", address="বিরুলিয়া, সাভার, ঢাকা")],
        "location": LocationDetails(mouza="বিরুলিয়া", jl_number="৩৪", union="বিরুলিয়া", upazila="সাভার", district="ঢাকা"),
        "land_details": LandDetails(dag_numbers=["৮৯০"], khatian_numbers=["৪৫"], land_area=5.0, land_unit=LandUnit.KATHA, ownership_share=0.5, sixteen_ana_share="৮ আনা"),
        "boundaries": Boundaries(north="১নং পক্ষের সীমানা", south="রাস্তা", east="খাল", west="২নং পক্ষের বাড়ি"),
        "raw_ocr": "বণ্টননামা দলিল নং ৫৬৭ সাভার ঢাকা মৌজা বিরুলিয়া দাগ ৮৯০ জমি ৫ কাঠা শেয়ার ৮ আনা",
        "warnings": []
    },
    {
        "doc_id": "SEED_DOLIL_004",
        "deed_number": "৮৯০২",
        "deed_year": 2005,
        "deed_type": DeedType.BAYNAPATRA,
        "registration_date": "12/12/2005",
        "copy_issue_date": None,
        "deed_value_bdt": 120000.0,
        "stamp_duty_bdt": 1000.0,
        "registration_office": "শ্রীপুর সাব-রেজিস্ট্রি অফিস",
        "sellers": [Party(name="মোঃ আকরাম হোসেন", father_or_husband="আমীর হোসেন", address="কাওরাইদ, শ্রীপুর, গাজীপুর")],
        "buyers": [Party(name="মোঃ সিরাজুল ইসলাম", father_or_husband="আব্দুস সামাদ", address="শ্রীপুর, গাজীপুর")],
        "location": LocationDetails(mouza="কাওরাইদ", jl_number="১৯", union="কাওরাইদ", upazila="শ্রীপুর", district="গাজীপুর"),
        "land_details": LandDetails(dag_numbers=["২১০"], khatian_numbers=["৮৮"], land_area=1.0, land_unit=LandUnit.BIGHA, ownership_share=1.0, sixteen_ana_share="১৬ আনা"),
        "boundaries": Boundaries(north="বন বিভাগের সীমানা", south="কাঁচা রাস্তা", east="আকরামের বাড়ি", west="পুকুর"),
        "raw_ocr": "বায়নাপত্র ৮৯০২ শ্রীপুর কাওরাইদ দাগ ২১০ ১ বিঘা বায়না বাবদ ৫০০০০ টাকা গ্রহণ",
        "warnings": []
    },
    {
        "doc_id": "SEED_DOLIL_005",
        "deed_number": "৩৪৫১",
        "deed_year": 1985,
        "deed_type": DeedType.SAF_KABALA,
        "registration_date": "22/02/1985",
        "copy_issue_date": "14/06/1999",
        "deed_value_bdt": 15000.0,
        "stamp_duty_bdt": 450.0,
        "registration_office": "ধনবাড়ী সাব-রেজিস্ট্রি অফিস",
        "sellers": [Party(name="মোঃ কাসেম আলী", father_or_husband="মৃত সোলেমান মণ্ডল", address="পাইস্কা, ধনবাড়ী, টাঙ্গাইল")],
        "buyers": [Party(name="মোঃ আবদুল জলিল", father_or_husband="মৃত মোসলেম মিয়া", address="ধনবাড়ী, টাঙ্গাইল")],
        "location": LocationDetails(mouza="পাইস্কা", jl_number="০৩", union="পাইস্কা", upazila="ধনবাড়ী", district="টাঙ্গাইল"),
        "land_details": LandDetails(dag_numbers=["৫১২", "৫১৩"], khatian_numbers=["১২"], land_area=40.0, land_unit=LandUnit.SHOTOK, ownership_share=0.75, sixteen_ana_share="১২ আনা"),
        "boundaries": Boundaries(north="বংশাই নদী", south="জলিলের জমি", east="আমবাগান", west="আইল"),
        "raw_ocr": "৩৪৫১ সাফ কবলা পাইস্কা ধনবাড়ী টাঙ্গাইল ৪০ শতাংশ ১২ আনা হিস্যা মূল্য ১৫০০০ টাকা",
        "warnings": []
    }
]

# Synthesize a total of 30 distinct validated instances
def generate_seed_dataset():
    print("=" * 72)
    print("  BHUMILENS AI — GENERATING LAND EXTRACTION BENCHMARK SEED DATASET")
    print("=" * 72)
    
    records = []
    
    mouzas = ["বারেন্ডা", "মৌচাক", "বিরুলিয়া", "কাওরাইদ", "পাইস্কা", "জয়দেবপুর", "টঙ্গী", "কালীগঞ্জ", "কাপাসিয়া", "শ্রীপুর"]
    districts = ["গাজীপুর", "গাজীপুর", "ঢাকা", "গাজীপুর", "টাঙ্গাইল", "গাজীপুর", "গাজীপুর", "গাজীপুর", "গাজীপুর", "গাজীপুর"]
    upazilas = ["গাজীপুর সদর", "কালিয়াকৈর", "সাভার", "শ্রীপুর", "ধনবাড়ী", "গাজীপুর সদর", "গাজীপুর সদর", "কালীগঞ্জ", "কাপাসিয়া", "শ্রীপুর"]
    types = [DeedType.SAF_KABALA, DeedType.HEBA_BIL_EWAZ, DeedType.BONTONAMA, DeedType.BAYNAPATRA, DeedType.SAF_KABALA]
    
    for i in range(30):
        base_tmpl = SEED_TEMPLATES[i % len(SEED_TEMPLATES)]
        idx_str = f"{i+1:03d}"
        doc_id = f"SEED_DOLIL_{idx_str}"
        
        m_idx = i % len(mouzas)
        deed_no = str(1000 + i * 137)
        year = 1980 + (i * 3) % 44
        dtype = types[i % len(types)]
        
        d_val = round(10000.0 + (i * 25000.0), 2)
        stamp_val = round(450.0 + (i * 50.0), 2)
        area = round(5.0 + (i * 2.5), 2)
        
        schema_obj = DeedExtractionSchema(
            doc_id=doc_id,
            deed_number=deed_no,
            deed_year=year,
            deed_type=dtype,
            registration_date=f"{10 + (i%18):02d}/{1 + (i%12):02d}/{year}",
            copy_issue_date=f"{15 + (i%12):02d}/{2 + (i%10):02d}/{year + 5}" if i % 2 == 0 else None,
            deed_value_bdt=d_val,
            stamp_duty_bdt=stamp_val,
            registration_office=f"{upazilas[m_idx]} সাব-রেজিস্ট্রি অফিস",
            sellers=base_tmpl["sellers"],
            buyers=base_tmpl["buyers"],
            location=LocationDetails(
                mouza=mouzas[m_idx],
                jl_number=str(10 + i),
                union=mouzas[m_idx],
                upazila=upazilas[m_idx],
                district=districts[m_idx]
            ),
            land_details=LandDetails(
                dag_numbers=[str(300 + i * 3), str(301 + i * 3)] if i % 3 != 0 else [],
                khatian_numbers=[str(50 + i * 2)] if i % 3 != 0 else [],
                land_area=area,
                land_unit=LandUnit.SHOTOK,
                ownership_share=round(min(1.0, 0.25 + (i % 4) * 0.25), 4),
                sixteen_ana_share=f"{(i%4 + 1)*4} আনা"
            ),
            boundaries=base_tmpl["boundaries"],
            provenance=FieldProvenance(
                raw_ocr_text=f"দলিল নং {deed_no}/{year} {dtype.value} মৌজা {mouzas[m_idx]} জমি {area} শতক",
                normalized_ocr_text=f"দলিল নং {deed_no}/{year} {dtype.value} মৌজা {mouzas[m_idx]} জমি {area} শতাংশ",
                field_confidence={"deed_number": 0.94, "mouza": 0.96, "land_area": 0.91},
                warnings=["MISSING_TAFSIL_SCHEDULE_PAGE"] if i % 3 == 0 else []
            )
        )
        
        record_dict = schema_obj.to_canonical_dict()
        record_dict["source_type"] = "synthetic_bangla_deed_template"
        records.append(record_dict)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            
    print(f"Generated & validated {len(records)} benchmark records in {OUT_FILE.relative_to(BASE_DIR)}")
    print(f"Verified strict tagging: source_type='synthetic_bangla_deed_template'")
    print(f"Sample record 1 ID: {records[0]['doc_id']} | Mouza: {records[0]['location']['mouza']} | Dag count: {len(records[0]['land_details']['dag_numbers'])}")
    print("=" * 72)
    return records

if __name__ == "__main__":
    generate_seed_dataset()
