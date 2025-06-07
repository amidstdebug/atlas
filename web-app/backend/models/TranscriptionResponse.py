from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class TranscriptionSegment(BaseModel):
    text: str
    start: float
    end: float

class TranscriptionResponse(BaseModel):
    segments: List[TranscriptionSegment]
    chunk_id: Optional[int] = None
    processing_applied: Optional[Dict[str, Any]] = None

