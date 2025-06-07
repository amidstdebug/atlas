from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Optional, List, Any
import logging
import json
from datetime import datetime

from models.AuthType import TokenData
from models.ActionsResponse import ActionsRequest, ActionsResponse, ActionItem
from services.auth.jwt import get_token_data
from services.summary.ollama_service import generate_summary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Actions"])

# Store current actions for users
current_actions = {}

@router.post("/actions/suggest", response_model=ActionsResponse)
async def suggest_actions(
    request: ActionsRequest,
    token_data: TokenData = Depends(get_token_data)
):
    """Generate suggested actions based on transcription analysis"""
    try:
        # Generate actions using Ollama service
        actions_result = await generate_suggested_actions(
            request.transcription,
            request.transcription_segments or [],
            request.previous_actions or [],
            request.custom_prompt
        )

        # Store the actions for this user
        user_id = token_data.user_id
        if user_id not in current_actions:
            current_actions[user_id] = []

        # Add new actions to user's list
        current_actions[user_id].extend(actions_result)

        return ActionsResponse(
            actions=actions_result,
            metadata={
                "generated_at": datetime.now().isoformat(),
                "transcription_length": len(request.transcription),
                "segments_count": len(request.transcription_segments) if request.transcription_segments else 0
            }
        )

    except Exception as e:
        logger.error(f"Error generating suggested actions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Actions generation failed: {str(e)}")

@router.get("/actions/history")
async def get_actions_history(
    token_data: TokenData = Depends(get_token_data)
):
    """Get actions history for the current user"""
    user_id = token_data.user_id
    return current_actions.get(user_id, [])

@router.post("/actions/{action_id}/complete")
async def complete_action(
    action_id: str,
    token_data: TokenData = Depends(get_token_data)
):
    """Mark an action as completed"""
    user_id = token_data.user_id
    user_actions = current_actions.get(user_id, [])
    
    for action in user_actions:
        if action.get("id") == action_id:
            action["completed"] = True
            action["completed_at"] = datetime.now().isoformat()
            return {"message": "Action marked as completed", "action_id": action_id}
    
    raise HTTPException(status_code=404, detail="Action not found")

async def generate_suggested_actions(
    transcription: str,
    transcription_segments: List[Dict[str, Any]],
    previous_actions: List[ActionItem],
    custom_prompt: Optional[str] = None
) -> List[ActionItem]:
    """Generate suggested actions based on ATC transcription analysis"""
    
    # Create timestamped transcription for the prompt
    timestamped_transcription = create_timestamped_transcription(transcription_segments)
    
    # Get context from previous actions
    previous_actions_context = create_previous_actions_context(previous_actions)
    
    actions_prompt = f"""
    You are an expert Air Traffic Control operations analyst. Based on the following ATC transcription, suggest specific ACTIONABLE items that air traffic controllers or supervisors should consider.

    Focus on:
    1. CRITICAL actions (immediate safety concerns, emergencies)
    2. WARNING actions (potential issues that need attention)
    3. ADVISORY actions (recommendations for improved operations)
    4. ROUTINE actions (standard operational improvements)

    {f"Custom instructions: {custom_prompt}" if custom_prompt else ""}

    PREVIOUS ACTIONS CONTEXT:
    {previous_actions_context}

    CURRENT TRANSCRIPTION:
    {timestamped_transcription}

    Provide your response as a JSON array of action objects. Each action should have:
    - type: "critical" | "warning" | "advisory" | "routine"
    - title: Brief action title (max 50 characters)
    - description: Detailed description of the action needed
    - priority: Number from 1-10 (10 = highest priority)
    - context: Brief context explaining why this action is needed

    Only suggest NEW actions that are not already covered by previous actions. If no new actions are needed, return an empty array.

    Example format:
    [
        {{
            "type": "critical",
            "title": "Review emergency procedures",
            "description": "Aircraft XYZ declared emergency at 15:30. Review and ensure all emergency protocols were followed correctly.",
            "priority": 9,
            "context": "Emergency declaration detected in transcription"
        }}
    ]

    Return only the JSON array, no additional text.
    """
    
    # Call the summary service with actions prompt
    actions_result = await generate_summary(
        transcription,
        "",
        "actions",
        actions_prompt
    )
    
    # Parse the JSON response
    try:
        actions_data = json.loads(actions_result.summary)
        if not isinstance(actions_data, list):
            actions_data = []
    except json.JSONDecodeError:
        logger.warning("Failed to parse actions JSON, attempting to extract from text")
        actions_data = extract_actions_from_text(actions_result.summary)
    
    # Convert to ActionItem objects
    suggested_actions = []
    current_timestamp = datetime.now().isoformat()
    
    for i, action_data in enumerate(actions_data):
        if isinstance(action_data, dict):
            action_item = ActionItem(
                id=f"action_{int(datetime.now().timestamp())}_{i}",
                type=action_data.get("type", "routine"),
                title=action_data.get("title", "Action Required"),
                description=action_data.get("description", ""),
                priority=action_data.get("priority", 5),
                timestamp=current_timestamp,
                context=action_data.get("context"),
                completed=False
            )
            suggested_actions.append(action_item)
    
    return suggested_actions

def create_timestamped_transcription(segments: List[Dict[str, Any]]) -> str:
    """Create a timestamped transcription for the AI prompt"""
    if not segments:
        return "No timestamped segments available"
    
    formatted_segments = []
    for segment in segments:
        start = segment.get("start", 0)
        end = segment.get("end", 0)
        text = segment.get("text", "")
        timestamp = f"[{start:.1f}s-{end:.1f}s]"
        formatted_segments.append(f"{timestamp} {text}")
    
    return "\n".join(formatted_segments)

def create_previous_actions_context(previous_actions: List[ActionItem]) -> str:
    """Create context from previous actions"""
    if not previous_actions:
        return "No previous actions available"
    
    context_lines = []
    for action in previous_actions[-10:]:  # Last 10 actions
        status = "COMPLETED" if getattr(action, 'completed', False) else "PENDING"
        context_lines.append(f"- [{status}] {action.title} (Priority: {action.priority})")
    
    return "\n".join(context_lines)

def extract_actions_from_text(text: str) -> List[Dict[str, Any]]:
    """Extract actions from text when JSON parsing fails"""
    # Fallback method to extract actions from malformed responses
    actions = []
    
    # Look for action-like patterns in the text
    lines = text.split('\n')
    current_action = {}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Try to identify action fields
        if line.lower().startswith(('critical:', 'warning:', 'advisory:', 'routine:')):
            if current_action:
                actions.append(current_action)
            current_action = {
                "type": line.split(':')[0].lower(),
                "title": line.split(':', 1)[1].strip() if ':' in line else "Action Required"
            }
        elif line.lower().startswith('description:'):
            current_action["description"] = line.split(':', 1)[1].strip()
        elif line.lower().startswith('priority:'):
            try:
                current_action["priority"] = int(line.split(':')[1].strip())
            except:
                current_action["priority"] = 5
        elif line.lower().startswith('context:'):
            current_action["context"] = line.split(':', 1)[1].strip()
    
    if current_action:
        actions.append(current_action)
    
    return actions[:5]  # Limit to 5 actions from text extraction