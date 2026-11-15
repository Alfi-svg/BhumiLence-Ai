"""
BhumiLens AI — Verification & Deterministic Land Math Schema.
Pydantic v2 data models for:
- Validation severity & flags
- Exact land unit conversions (Shotok, Katha, Bigha, Acre, Ajutangsho)
- 16-Ana traditional Bengali share calculations
- Stamp duty equation validation
- Chronological consistency
- Complete VerificationReport
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.schemas.deed_schema import LandUnit

class ValidationSeverity(str, Enum):
    PASS = "PASS"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

class ValidationFlag(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    severity: ValidationSeverity
    code: str
    message: str
    field: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)

class LandUnitConversionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    original_area: float
    original_unit: LandUnit
    conversions: Dict[str, float]  # shotok, katha, bigha, acre, ajutangsho, sq_ft

class SixteenAnaValidationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    raw_notation: Optional[str] = None
    ana: float = 0.0
    gonda: float = 0.0
    kara: float = 0.0
    kranti: float = 0.0
    til: float = 0.0
    decimal_share: float = 0.0  # 0.0 to 1.0
    percentage_share: float = 0.0  # 0.0 to 100.0%
    is_valid: bool = True
    error_message: Optional[str] = None

class StampDutyValidationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    raw_math_text: Optional[str] = None
    addends: List[float] = Field(default_factory=list)
    computed_sum: float = 0.0
    stated_total: float = 0.0
    is_valid: bool = True
    status: str = "NO_STAMP_EQUATION"

class ChronologyValidationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    registration_date_iso: Optional[str] = None
    copy_issue_date_iso: Optional[str] = None
    gap_years: Optional[float] = None
    is_valid: bool = True
    status: str = "DATES_VALID"

class VerificationReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    doc_id: str
    is_valid: bool = True  # False if any flag has severity ERROR
    score: float = 1.0     # 0.0 to 1.0 confidence score
    flags: List[ValidationFlag] = Field(default_factory=list)
    unit_conversions: Optional[LandUnitConversionResult] = None
    share_validation: Optional[SixteenAnaValidationResult] = None
    stamp_validation: Optional[StampDutyValidationResult] = None
    chronology_validation: Optional[ChronologyValidationResult] = None
    missing_mandatory_fields: List[str] = Field(default_factory=list)
    timestamp_utc: str
    legal_disclaimer: str = (
        "NON-GOAL COMPLIANCE: Automated mathematical and domain rule verification. "
        "Does NOT establish legal ownership, state title, or authentic right to land."
    )
