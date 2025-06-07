from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ActionItem(BaseModel):
    id: str
    type: str  # 'critical' | 'warning' | 'advisory' | 'routine'
    title: str
    description: str
    priority: int
    timestamp: str
    context: Optional[str] = None
    completed: Optional[bool] = False

class ActionsRequest(BaseModel):
    transcription: str
    transcription_segments: Optional[List[Dict[str, Any]]] = None
    previous_actions: Optional[List[ActionItem]] = None
    custom_prompt: Optional[str] = None

class ActionsResponse(BaseModel):
    actions: List[ActionItem]
    metadata: Optional[Dict[str, Any]] = None