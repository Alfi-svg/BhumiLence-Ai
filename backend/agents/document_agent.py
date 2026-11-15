"""
Document Agent - Handles image ingestion, classification (Dolil vs Khatian), shadow removal, and evidence cropping.
"""

class DocumentAgent:
    def __init__(self):
        self.agent_name = "DocumentAgent"

    async def process_document(self, image_path: str):
        return {"status": "placeholder", "image_path": image_path}
