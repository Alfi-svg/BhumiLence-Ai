"""
Land Gazetteers, Mouza Registries & Legal Knowledge Base Routes
"""
from fastapi import APIRouter

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

@router.get("/gazetteer")
async def query_gazetteer(query: str = ""):
    return {"status": "placeholder", "query": query, "matches": []}
