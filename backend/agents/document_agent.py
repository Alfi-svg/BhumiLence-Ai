"""
Document Intelligence Agent (Layers 1, 2 & 3 Orchestration).
Orchestrates DocumentVisionService to:
1. Assess image quality (blur, contrast, skew, illumination, resolution)
2. Perform structural layout segmentation and classification (Deed vs Khatian vs Mixed)
3. Generate visual evidence crops with pixel bounding boxes and SHA-256 provenance hashing.
"""
import asyncio
from typing import Optional
from backend.schemas.document_schema import DocumentAnalysisResult
from backend.services.document_vision_service import DocumentVisionService

class DocumentIntelligenceAgent:
    def __init__(self, output_base_dir: str = "outputs/evidence"):
        self.agent_name = "DocumentIntelligenceAgent"
        self.vision_service = DocumentVisionService(output_base_dir=output_base_dir)

    def process_document(
        self,
        image_path: str,
        doc_id: Optional[str] = None
    ) -> DocumentAnalysisResult:
        """
        Synchronously processes a document image through Layers 1, 2, and 3.
        """
        return self.vision_service.process_document(image_path, doc_id=doc_id)

    async def aprocess_document(
        self,
        image_path: str,
        doc_id: Optional[str] = None
    ) -> DocumentAnalysisResult:
        """
        Asynchronously processes a document image (FastAPI async route friendly).
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.vision_service.process_document, image_path, doc_id
        )

# Backward-compatible alias
DocumentAgent = DocumentIntelligenceAgent
