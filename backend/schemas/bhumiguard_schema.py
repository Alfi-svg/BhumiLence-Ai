"""
Pydantic v2 Schemas for BhumiGuard Intelligence (Agent 5).
Defines typed models for Visual & Cryptographic Duplicate Matching, Cross-Record Conflict Rules,
Unsupervised Isolation Forest Anomaly Scoring, and Human-in-the-Loop Risk Reporting.
"""
from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0.0"

class RiskLevel(str, Enum):
    RISK_LOW = "RISK_LOW"
    RISK_MEDIUM = "RISK_MEDIUM"
    RISK_HIGH_REVIEW_REQUIRED = "RISK_HIGH_REVIEW_REQUIRED"

class DuplicateMatchType(str, Enum):
    EXACT_SHA256 = "EXACT_SHA256"
    PERCEPTUAL_NEAR_DUPLICATE = "PERCEPTUAL_NEAR_DUPLICATE"

class DuplicateMatch(BaseModel):
    """Details of a matching duplicate or near-duplicate document."""
    matched_doc_id: str = Field(..., description="Target document ID in persistence DB")
    match_type: DuplicateMatchType = Field(..., description="Exact cryptographic or perceptual visual match")
    similarity_pct: float = Field(..., ge=0.0, le=100.0, description="Similarity percentage")
    hamming_distance: Optional[int] = Field(default=None, description="Perceptual hash bit distance (0-64)")
    detail: str = Field(..., description="Human-readable match explanation")

class ConflictRuleType(str, Enum):
    DUPLICATE_DEED_NUMBER_CONFLICT = "DUPLICATE_DEED_NUMBER_CONFLICT"
    CUMULATIVE_SHARE_EXCEEDED = "CUMULATIVE_SHARE_EXCEEDED"
    INVALID_CONSIDERATION_AMOUNT = "INVALID_CONSIDERATION_AMOUNT"
    MISSING_CORE_PARTIES = "MISSING_CORE_PARTIES"
    STAMP_DUTY_DISCREPANCY = "STAMP_DUTY_DISCREPANCY"
    CHRONOLOGY_INVERSION = "CHRONOLOGY_INVERSION"
    SUSPICIOUS_VALUATION_OUTLIER = "SUSPICIOUS_VALUATION_OUTLIER"

class RuleViolation(BaseModel):
    """Deterministic cross-record or metadata conflict alert."""
    rule_type: ConflictRuleType = Field(..., description="Classification category of the conflict rule")
    severity: str = Field(default="HIGH", description="Severity level: MEDIUM, HIGH, CRITICAL")
    field_name: str = Field(..., description="Target field associated with the violation")
    description_en: str = Field(..., description="Detailed explanation in English")
    description_bn: str = Field(..., description="Detailed explanation in simple Bangla")
    conflicting_doc_ids: List[str] = Field(default_factory=list, description="Associated conflicting document IDs")

class FeatureContribution(BaseModel):
    """Tabular feature analysis from Isolation Forest."""
    feature_name: str
    value: float
    expected_range: str
    is_outlier: bool

class BhumiGuardReport(BaseModel):
    """
    Comprehensive risk evaluation report from BhumiGuardAgent (Agent 5).
    Ethical Governance Rule: Strictly presents factual risk indicators and statistical
    anomalies without labeling any document or human as 'fraudulent' or 'forged'.
    """
    schema_version: str = SCHEMA_VERSION
    doc_id: str = Field(..., description="Scanned document ID")
    risk_level: RiskLevel = Field(..., description="Overall risk classification level")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Normalized composite risk score")
    duplicate_matches: List[DuplicateMatch] = Field(default_factory=list, description="Visual or cryptographic matches")
    rule_violations: List[RuleViolation] = Field(default_factory=list, description="Cross-record and logical conflict flags")
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Isolation Forest anomaly score (0=normal, 1=outlier)")
    anomaly_explanation_bn: str = Field(..., description="Statistical anomaly summary in simple Bangla")
    feature_contributions: List[FeatureContribution] = Field(default_factory=list, description="Tabular feature metrics")
    disclaimer: str = Field(
        default=(
            "আইনি সতর্কবার্তা: এই অ্যানোমালি ও রিস্ক রিপোর্ট শুধুমাত্র মানুষের পর্যালোচনার "
            "(Maker-Checker Review) জন্য প্রস্তুতকৃত স্ট্যাটিস্টিক্যাল ও লজিক্যাল সতর্কতা। "
            "এটি কোনো জালিয়াতি বা অপরাধের আইনি প্রমাণ নয়।"
        ),
        description="Mandatory legal disclaimer"
    )

class BhumiGuardScanRequest(BaseModel):
    """Request payload for manual BhumiGuard scan."""
    doc_id: str
    image_path: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
