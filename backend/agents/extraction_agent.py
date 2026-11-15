"""
Extraction Agent - Uses small language models (Qwen3-0.6B / SLM) to extract structured key-value entities.
"""

class ExtractionAgent:
    def __init__(self):
        self.agent_name = "ExtractionAgent"

    async def extract_entities(self, raw_text: str):
        return {"status": "placeholder", "raw_text": raw_text, "structured_entities": {}}
