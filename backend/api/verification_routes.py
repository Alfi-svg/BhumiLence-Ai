"""
Deterministic Land-Math, Unit Conversion & Chronology Verification Routes.
Endpoints:
- POST /api/v1/verify/validate-json : Validates deed extraction schema against deterministic land math rules
- POST /api/v1/verify/convert-unit : Exact unit conversion using Python Decimal
- POST /api/v1/verify/calculate-share : Parses traditional 16-Ana share notation using Python Fraction
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.schemas.deed_schema import DeedExtractionSchema, LandUnit
from backend.schemas.bhumiguard_schema import BhumiGuardScanRequest, BhumiGuardReport
from backend.services.land_validation_service import LandValidationService, LandUnitConverter, SixteenAnaValidator
from backend.services.audit_service import AuditPersistenceService
from backend.agents.verification_agent import VerificationAgent
from backend.agents.bhumiguard_agent import BhumiGuardAgent

router = APIRouter(prefix="/verify", tags=["verification"])
validation_service = LandValidationService()
verification_agent = VerificationAgent(validation_service=validation_service)
audit_service = AuditPersistenceService()
bhumiguard_agent = BhumiGuardAgent()

class UnitConvertRequest(BaseModel):
    area: float = Field(..., gt=0, description="Numerical land area")
    unit: str = Field(default="SHOTOK", description="Unit of measurement: SHOTOK, KATHA, BIGHA, ACRE, AJUTANGSHO")

class ShareCalculateRequest(BaseModel):
    share_notation: str = Field(..., description="Archaic Bengali share string, e.g. '4 আনা 10 গন্ডা 2 কড়া 0 ক্রান্তি'")

@router.post("/validate-json")
async def validate_extracted_deed(deed_payload: Dict[str, Any]):
    """
    Performs deterministic mathematical, 16-Ana share, stamp duty, and chronological validation.
    """
    try:
        # If payload doesn't have doc_id, assign dummy for validation
        if "doc_id" not in deed_payload:
            deed_payload["doc_id"] = "VERIFY_QUERY"

        report = await verification_agent.averify_deed(deed_payload)
        return report.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid deed payload: {str(e)}")

@router.post("/convert-unit")
async def convert_land_unit(payload: UnitConvertRequest):
    """
    Converts land area exactly between Shotok, Katha, Bigha, Acre, and Ajutangsho using Decimal.
    """
    try:
        unit_enum = LandUnit(payload.unit.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid land unit '{payload.unit}'. Allowed: {[u.value for u in LandUnit]}"
        )

    res = LandUnitConverter.convert_area(payload.area, unit_enum)
    return res.model_dump()

@router.post("/calculate-share")
async def calculate_sixteen_ana_share(payload: ShareCalculateRequest):
    """
    Parses archaic 16-Ana notation and computes exact decimal and percentage ownership share using Fraction.
    """
    res = SixteenAnaValidator.parse_notation(payload.share_notation)
    return res.model_dump()

@router.post("/bhumiguard-scan")
async def scan_deed_bhumiguard(request: BhumiGuardScanRequest):
    """
    Executes on-demand multi-layered BhumiGuard Intelligence scan on deed data and optional image.
    """
    try:
        report = await bhumiguard_agent.ascan_deed(
            deed_input=request.extracted_data or {"doc_id": request.doc_id},
            image_path=request.image_path,
            doc_id=request.doc_id
        )
        return report.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"BhumiGuard scan failed: {str(e)}")

@router.get("/bhumiguard/{doc_id}")
async def get_bhumiguard_report(doc_id: str):
    """
    Retrieves document from persistence DB and executes complete BhumiGuard Intelligence scan.
    """
    doc = audit_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found in audit database.")

    image_path = None
    if doc.evidence_manifest and isinstance(doc.evidence_manifest, dict):
        image_path = doc.evidence_manifest.get("image_path")

    report = await bhumiguard_agent.ascan_deed(
        deed_input=doc.extracted_data or {},
        image_path=image_path,
        target_sha256=doc.original_image_sha256,
        doc_id=doc.doc_id
    )
    return report.model_dump()

