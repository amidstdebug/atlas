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
    format_template: Optional[str] = None  # JSON format template for structured summaries

class SectionWithTimestamps(BaseModel):
    content: str
    timestamps: List[Dict[str, Any]]  # List of {start: float, end: float, text: str}
    latest_timestamp: Optional[float] = None

class SectionAppendSuggestion(BaseModel):
    new_content: Optional[str] = None  # Content to append, None if no changes
    new_timestamps: List[Dict[str, Any]] = []  # New timestamps to add
    has_updates: bool = False  # Whether this section has new information

class PendingInformationItem(BaseModel):
    description: str
    eta_etr_info: Optional[str] = None
    calculated_time: Optional[str] = None  # Calculated actual time
    priority: str = "medium"  # low, medium, high
    timestamps: List[Dict[str, float]] = []  # List of {start: float, end: float} timestamps
    segment_indices: List[int] = []  # Indices of relevant transcription segments

class EmergencyItem(BaseModel):
    category: str  # MAYDAY_PAN, CASEVAC, AIRCRAFT_DIVERSION, OTHERS
    description: str
    severity: str = "high"  # always high for emergencies
    immediate_action_required: bool = True
    timestamps: List[Dict[str, float]] = []  # List of {start: float, end: float} timestamps
    segment_indices: List[int] = []  # Indices of relevant transcription segments

class StructuredSummary(BaseModel):
    pending_information: List[PendingInformationItem]
    emergency_information: List[EmergencyItem]

class StructuredSummaryAppendSuggestions(BaseModel):
    pending_information: List[PendingInformationItem]
    emergency_information: List[EmergencyItem]

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