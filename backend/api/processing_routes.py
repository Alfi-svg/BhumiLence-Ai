"""
Vision, Preprocessing, Cropping & HTR Processing Routes
"""
from fastapi import APIRouter

router = APIRouter(prefix="/processing", tags=["processing"])

@router.post("/preprocess")
async def trigger_preprocessing():
    return {"status": "placeholder", "message": "Vision preprocessing placeholder"}
