from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class TranscriptionSegment(BaseModel):
    text: str
    start: float
    end: float

class SummaryRequest(BaseModel):
    transcription: str
    transcription_segments: Optional[List[TranscriptionSegment]] = None
    previous_report: Optional[str] = None
    summary_mode: str = "standard"
    custom_prompt: Optional[str] = None
    structured: bool = False

class SectionWithTimestamps(BaseModel):
    content: str
    timestamps: List[Dict[str, Any]]  # List of {start: float, end: float, text: str}
    latest_timestamp: Optional[float] = None

class SectionAppendSuggestion(BaseModel):
    new_content: Optional[str] = None  # Content to append, None if no changes
    new_timestamps: List[Dict[str, Any]] = []  # New timestamps to add
    has_updates: bool = False  # Whether this section has new information

class StructuredSummary(BaseModel):
    situation_update: SectionWithTimestamps
    current_situation_details: SectionWithTimestamps
    recent_actions_taken: SectionWithTimestamps
    overall_status: SectionWithTimestamps

class StructuredSummaryAppendSuggestions(BaseModel):
    situation_update: SectionAppendSuggestion
    current_situation_details: SectionAppendSuggestion
    recent_actions_taken: SectionAppendSuggestion
    overall_status: SectionAppendSuggestion

class SummaryResponse(BaseModel):
    summary: str
    structured_summary: Optional[StructuredSummary] = None
    append_suggestions: Optional[StructuredSummaryAppendSuggestions] = None
    metadata: Optional[Dict[str, Any]] = None

class InvestigationRequest(BaseModel):
    transcription: str
    question: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    context: Optional[str] = None

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: str

class InvestigationResponse(BaseModel):
    answer: str
    relevant_segments: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None