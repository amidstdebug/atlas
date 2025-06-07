from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class TranscriptionResponse(BaseModel):
    transcription: list[dict]
    chunk_id: Optional[int] = None
    processing_applied: Optional[Dict[str, Any]] = None

