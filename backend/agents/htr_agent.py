"""
HTR Agent - Coordinates Bengali Handwritten Text Recognition (GraDeT-HTR / OCR pipeline).
"""

class HTRAgent:
    def __init__(self):
        self.agent_name = "HTRAgent"

    async def recognize_text(self, crop_image_path: str):
        return {"status": "placeholder", "crop_image_path": crop_image_path, "predicted_text": ""}
