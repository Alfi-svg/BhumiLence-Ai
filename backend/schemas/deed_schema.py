"""
BhumiLens AI — Versioned Land Deed Extraction Schema
Standardized Pydantic v2 Schema for Bangladeshi Land Records (Deeds/Dolil & Khatian)
Schema Version: 1.0.0
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

SCHEMA_VERSION = "1.0.0"

class DeedType(str, Enum):
    SAF_KABALA = "SAF_KABALA"              # সাফ কবলা (Outright Sale)
    BAYNAPATRA = "BAYNAPATRA"              # বায়নাপত্র (Executory Agreement to Sell)
    BONTONAMA = "BONTONAMA"                # বণ্টননামা (Partition Deed)
    HEBA_BIL_EWAZ = "HEBA_BIL_EWAZ"        # হেবা বিল এওয়াজ (Gift for Consideration)
    HEBA_DECLARATION = "HEBA_DECLARATION"  # দানপত্র / হেবা ঘোষণা (Gift Declaration)
    MORTGAGE = "MORTGAGE"                  # বন্ধকী দলিল (Mortgage)
    KHATIAN_RECORD = "KHATIAN_RECORD"      # খতিয়ান / পর্চা (Survey of Rights)
    UNKNOWN = "UNKNOWN"

class LandUnit(str, Enum):
    SHOTOK = "SHOTOK"                      # শতাংশ / ডেসিমেল (Decimal: ~435.6 sq ft)
    KATHA = "KATHA"                        # কাঠা (~720 sq ft)
    BIGHA = "BIGHA"                        # বিঘা (20 Katha / 33 Shotok)
    ACRE = "ACRE"                          # একর (100 Shotok)
    AJUTANGSHO = "AJUTANGSHO"              # অযুতাংশ (1/100 of Shotok)
    UNKNOWN = "UNKNOWN"

class Party(BaseModel):
    """Represents a buyer, seller, donor, or recipient party."""
    model_config = ConfigDict(extra="ignore")
    
    name: Optional[str] = Field(default=None, description="Party Full Name in Bangla/English")
    father_or_husband: Optional[str] = Field(default=None, description="Father or Husband name")
    address: Optional[str] = Field(default=None, description="Village, Post Office, Upazila, District")
    nid_or_id: Optional[str] = Field(default=None, description="National ID or passport number if recorded")

class LocationDetails(BaseModel):
    """Administrative and revenue geographical hierarchy in Bangladesh."""
    model_config = ConfigDict(extra="ignore")
    
    mouza: Optional[str] = Field(default=None, description="Mouza name (e.g. বারেন্ডা, কাশিমপুর)")
    jl_number: Optional[str] = Field(default=None, description="Jurisdiction List (জে.এল.) Number")
    union: Optional[str] = Field(default=None, description="Union Parishad or Ward")
    upazila: Optional[str] = Field(default=None, description="Thana / Upazila (e.g. গাজীপুর সদর)")
    district: Optional[str] = Field(default=None, description="District (e.g. গাজীপুর, ঢাকা)")

class Boundaries(BaseModel):
    """Chouhaddi (চৌহদ্দি) / Four physical border boundaries."""
    model_config = ConfigDict(extra="ignore")
    
    north: Optional[str] = Field(default=None, description="উত্তর সীমানা")
    south: Optional[str] = Field(default=None, description="দক্ষিণ সীমানা")
    east: Optional[str] = Field(default=None, description="পূর্ব সীমানা")
    west: Optional[str] = Field(default=None, description="পশ্চিম সীমানা")

class LandDetails(BaseModel):
    """Plot numbers, survey units, areas, and archaic ownership shares."""
    model_config = ConfigDict(extra="ignore")
    
    dag_numbers: List[str] = Field(default_factory=list, description="দাগ নম্বর (CS/SA/RS/BS Plot Numbers)")
    khatian_numbers: List[str] = Field(default_factory=list, description="খতিয়ান নম্বর (Record of Rights)")
    land_area: Optional[float] = Field(default=None, description="Quantitative land area in land_unit")
    land_unit: LandUnit = Field(default=LandUnit.UNKNOWN, description="Unit of measurement")
    ownership_share: Optional[float] = Field(default=None, description="Decimal ownership share fraction (0.0 to 1.0)")
    sixteen_ana_share: Optional[str] = Field(default=None, description="আনা-গন্ডা-কড়া-ক্রান্তি share string")

class FieldProvenance(BaseModel):
    """Lineage, raw OCR strings, model confidence, and visual crop coordinates."""
    model_config = ConfigDict(extra="ignore")
    
    raw_ocr_text: Optional[str] = Field(default=None, description="Exact OCR/HTR string before normalization")
    normalized_ocr_text: Optional[str] = Field(default=None, description="Post-gazetteer / post-SLM corrected string")
    field_confidence: Dict[str, float] = Field(default_factory=dict, description="Confidence per field key (0.0 to 1.0)")
    evidence_crops: Dict[str, Any] = Field(default_factory=dict, description="Bounding boxes or image crop paths")
    warnings: List[str] = Field(default_factory=list, description="Data validation alerts (e.g. Missing Tafsil)")

class DeedExtractionSchema(BaseModel):
    """
    Master unified schema for digitized Bangladeshi land deeds.
    Enforces that unstated or uncertain fields remain None (null) rather than hallucinated.
    """
    model_config = ConfigDict(extra="ignore")
    
    schema_version: str = Field(default=SCHEMA_VERSION, description="Schema Version SemVer")
    doc_id: str = Field(..., description="Unique document tracking identifier")
    deed_number: Optional[str] = Field(default=None, description="দলিল নম্বর (Deed Serial Number)")
    deed_year: Optional[int] = Field(default=None, description="দলিল রেজিস্ট্রি সাল (Deed Year)")
    deed_type: DeedType = Field(default=DeedType.UNKNOWN, description="দলিলের প্রকৃতি / শ্রেণিবিভাগ")
    registration_date: Optional[str] = Field(default=None, description="মূল রেজিস্ট্রেশনের তারিখ (DD/MM/YYYY or ISO)")
    copy_issue_date: Optional[str] = Field(default=None, description="নকল তোলার তারিখ (DD/MM/YYYY or ISO)")
    deed_value_bdt: Optional[float] = Field(default=None, description="দলিল মূল্য (Declared consideration BDT)")
    stamp_duty_bdt: Optional[float] = Field(default=None, description="স্ট্যাম্প শুল্কের মোট মূল্য (BDT)")
    registration_office: Optional[str] = Field(default=None, description="সাব-রেজিস্ট্রি অফিস (Sub-Registry Office)")
    
    sellers: List[Party] = Field(default_factory=list, description="দাতা / বিক্রেতা পক্ষ")
    buyers: List[Party] = Field(default_factory=list, description="গ্রহীতা / ক্রেতা পক্ষ")
    
    location: LocationDetails = Field(default_factory=LocationDetails, description="জমি বা দলিলের ভৌগোলিক অবস্থান")
    land_details: LandDetails = Field(default_factory=LandDetails, description="জমির তফসিল (দাগ, খতিয়ান, পরিমাণ)")
    boundaries: Boundaries = Field(default_factory=Boundaries, description="চৌহদ্দি বিবরণী")
    provenance: FieldProvenance = Field(default_factory=FieldProvenance, description="OCR ও এভিডেন্স ট্র্যাকিং")

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Returns clean serializable dictionary."""
        return self.model_dump(mode="json", exclude_none=False)
