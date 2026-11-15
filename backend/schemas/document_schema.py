"""
Pydantic v2 Schema for Document Intelligence, Layout & Evidence Cropping (Layers 1, 2, and 3).
Defines strict type models for Image Quality Gate, Document Layout Classification, and Evidence Provenance.
"""
from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0.0"

class QualityStatus(str, Enum):
    PASS = "PASS"
    WARN_LOW_CONTRAST = "WARN_LOW_CONTRAST"
    WARN_BLURRY = "WARN_BLURRY"
    WARN_SKEWED = "WARN_SKEWED"
    WARN_LOW_RESOLUTION = "WARN_LOW_RESOLUTION"

class LayoutPattern(str, Enum):
    DEED_PROSE_LAYOUT = "DEED_PROSE_LAYOUT"
    KHATIAN_TABULAR_LAYOUT = "KHATIAN_TABULAR_LAYOUT"
    MIXED_SCHEDULE_LAYOUT = "MIXED_SCHEDULE_LAYOUT"
    UNKNOWN = "UNKNOWN"

class ImageDimensions(BaseModel):
    width: int
    height: int

class QualityAssessment(BaseModel):
    status: QualityStatus
    laplacian_blur_variance: float
    rms_contrast: float
    mean_brightness: float
    skew_angle_deg: float
    dimensions: ImageDimensions
    warnings: List[str] = Field(default_factory=list)
    is_acceptable: bool = True

class EvidenceCrop(BaseModel):
    crop_id: str
    zone_type: str  # header, seal, tabular_grid, handwritten_line, field_evidence
    bbox: List[int]  # [x, y, w, h]
    crop_path: str
    confidence: float = 1.0

class TextLineCrop(BaseModel):
    line_index: int
    bbox: List[int]  # [x, y, w, h]
    crop_path: str
    aspect_ratio: float = 1.0

class LayoutAnalysis(BaseModel):
    pattern: LayoutPattern
    confidence: float
    grid_intersections: int = 0
    has_tabular_grid: bool = False
    official_seal_detected: bool = False
    colored_ink_ratio: float = 0.0
    header_zone_bbox: Optional[List[int]] = None
    seal_bboxes: List[List[int]] = Field(default_factory=list)
    tabular_bboxes: List[List[int]] = Field(default_factory=list)
    detected_lines_count: int = 0
    line_crops: List[TextLineCrop] = Field(default_factory=list)

class DocumentAnalysisResult(BaseModel):
    doc_id: str
    schema_version: str = SCHEMA_VERSION
    image_sha256: str
    original_image_path: str
    normalized_image_path: str
    binarized_image_path: str
    quality: QualityAssessment
    layout: LayoutAnalysis
    evidence_crops: Dict[str, EvidenceCrop] = Field(default_factory=dict)
    processing_time_ms: float
    timestamp: str
