from pydantic import BaseModel
from typing import Optional, Dict, Any

class SummaryRequest(BaseModel):
    transcription: str
    previous_report: Optional[str] = None
    summary_mode: str = "standard"
    custom_prompt: Optional[str] = None

class SummaryResponse(BaseModel):
    summary: str
    metadata: Optional[Dict[str, Any]] = None