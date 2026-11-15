"""
Pydantic Data Models & Schemas Package
"""
from backend.schemas.deed_schema import (
    DeedExtractionSchema,
    DeedType,
    LandUnit,
    Party,
    LocationDetails,
    LandDetails,
    Boundaries,
    FieldProvenance,
    SCHEMA_VERSION as DEED_SCHEMA_VERSION
)
from backend.schemas.document_schema import (
    QualityStatus,
    LayoutPattern,
    ImageDimensions,
    QualityAssessment,
    EvidenceCrop,
    TextLineCrop,
    LayoutAnalysis,
    DocumentAnalysisResult,
    SCHEMA_VERSION as DOCUMENT_SCHEMA_VERSION
)
from backend.schemas.htr_schema import (
    HTREngineType,
    LineRecognitionResult,
    DocumentHTRResult,
    SCHEMA_VERSION as HTR_SCHEMA_VERSION
)
from backend.schemas.verification_schema import (
    ValidationSeverity,
    ValidationFlag,
    LandUnitConversionResult,
    SixteenAnaValidationResult,
    StampDutyValidationResult,
    ChronologyValidationResult,
    VerificationReport
)
from backend.schemas.audit_schema import (
    WorkflowState,
    AuditRole,
    AuditAction,
    AuditEvent,
    DocumentRecord
)
from backend.schemas.rag_schema import (
    RAGCitation,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGCorpusStats,
    DeedFieldExplanation,
    DeedExplanationResponse,
    SCHEMA_VERSION as RAG_SCHEMA_VERSION
)
from backend.schemas.bhumiguard_schema import (
    RiskLevel,
    DuplicateMatchType,
    DuplicateMatch,
    ConflictRuleType,
    RuleViolation,
    FeatureContribution,
    BhumiGuardReport,
    BhumiGuardScanRequest,
    SCHEMA_VERSION as BHUMIGUARD_SCHEMA_VERSION
)

__all__ = [
    "DeedExtractionSchema",
    "DeedType",
    "LandUnit",
    "Party",
    "LocationDetails",
    "LandDetails",
    "Boundaries",
    "FieldProvenance",
    "DEED_SCHEMA_VERSION",
    "QualityStatus",
    "LayoutPattern",
    "ImageDimensions",
    "QualityAssessment",
    "EvidenceCrop",
    "TextLineCrop",
    "LayoutAnalysis",
    "DocumentAnalysisResult",
    "DOCUMENT_SCHEMA_VERSION",
    "HTREngineType",
    "LineRecognitionResult",
    "DocumentHTRResult",
    "HTR_SCHEMA_VERSION",
    "ValidationSeverity",
    "ValidationFlag",
    "LandUnitConversionResult",
    "SixteenAnaValidationResult",
    "StampDutyValidationResult",
    "ChronologyValidationResult",
    "VerificationReport",
    "WorkflowState",
    "AuditRole",
    "AuditAction",
    "AuditEvent",
    "DocumentRecord",
    "RAGCitation",
    "RAGQueryRequest",
    "RAGQueryResponse",
    "RAGCorpusStats",
    "DeedFieldExplanation",
    "DeedExplanationResponse",
    "RAG_SCHEMA_VERSION",
    "RiskLevel",
    "DuplicateMatchType",
    "DuplicateMatch",
    "ConflictRuleType",
    "RuleViolation",
    "FeatureContribution",
    "BhumiGuardReport",
    "BhumiGuardScanRequest",
    "BHUMIGUARD_SCHEMA_VERSION"
]
