"""
Pydantic v2 Schema for Bengali Handwritten Text Recognition (HTR) & Recognition Provenance.
Defines strict data models for LineRecognitionResult and DocumentHTRResult.
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0.0"

class HTREngineType(str, Enum):
    PRETRAINED_BASELINE = "PRETRAINED_BASELINE"  # EasyOCR CRAFT + ResNet-BiLSTM
    CUSTOM_PILOT = "CUSTOM_PILOT"                # BhumiLens-HTR-v1-pilot
    HYBRID = "HYBRID"                            # Dual-Engine + Maker review routing

class LineRecognitionResult(BaseModel):
    line_id: str
    line_index: int
    bbox: List[int]  # [x, y, w, h]
    evidence_crop_path: str
    raw_text: str
    confidence: float
    uncertain_flag: bool = False  # True if confidence < 0.65
    engine_used: HTREngineType
    model_version: str
    latency_ms: float = 0.0

class DocumentHTRResult(BaseModel):
    doc_id: str
    schema_version: str = SCHEMA_VERSION
    image_sha256: str
    total_lines: int
    recognized_lines: List[LineRecognitionResult] = Field(default_factory=list)
    full_raw_text: str
    average_confidence: float
    uncertain_lines_count: int = 0
    engine_used: HTREngineType
    total_recognition_time_ms: float
    timestamp: str
