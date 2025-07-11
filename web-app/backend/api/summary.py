from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Optional, List, Any
import logging
import json

from models.AuthType import TokenData
from models.SummaryResponse import SummaryRequest, SummaryResponse, InvestigationRequest, InvestigationResponse, StructuredSummary, SectionWithTimestamps, TranscriptionSegment, StructuredSummaryAppendSuggestions, SectionAppendSuggestion, PendingInformationItem, EmergencyItem
from services.auth.jwt import get_token_data
from services.summary.ollama_service import generate_summary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Summary"])

# Store current summaries for users
current_summaries = {}

@router.post("/summary", response_model=SummaryResponse)
async def create_summary(
    request: SummaryRequest,
    token_data: TokenData = Depends(get_token_data)
):
    """Generate a summary from transcription text using Ollama service"""
    try:
        # Generate the main summary text
        summary_result = await generate_summary(
            request.transcription,
            request.previous_report,
            request.summary_mode,
            request.custom_prompt
        )

        # Initialize response components
        structured_summary = None
        append_suggestions = None

        # --- Structured Summary Generation ---
        if request.structured and request.summary_mode == "atc":
            user_id = token_data.user_id
            existing_summaries = current_summaries.get(user_id, [])
            previous_structured = existing_summaries[-1].get("structured_summary") if existing_summaries else None

            # Generate structured summary
            structured_summary = await generate_structured_summary(
                transcription=request.transcription,
                transcription_segments=request.transcription_segments or [],
                custom_prompt=request.custom_prompt
            )

        # Store the summary for this user
        user_id = token_data.user_id
        if user_id not in current_summaries:
            current_summaries[user_id] = []

        current_summaries[user_id].append({
            "summary": summary_result.summary,
            "structured_summary": structured_summary,
            "metadata": summary_result.metadata,
            "transcription_preview": request.transcription[:100] + "..." if len(request.transcription) > 100 else request.transcription
        })

        return SummaryResponse(
            summary=summary_result.summary,
            structured_summary=structured_summary,
            append_suggestions=append_suggestions, # Append suggestions might need to be re-evaluated in this flow
            metadata=summary_result.metadata
        )

    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(e)}")

@router.get("/summary/history")
async def get_summary_history(
    token_data: TokenData = Depends(get_token_data)
):
    """Get summary history for the current user"""
    user_id = token_data.user_id
    return current_summaries.get(user_id, [])

@router.get("/summary/default-prompt")
async def get_default_prompt(
    token_data: TokenData = Depends(get_token_data)
):
    """Get the default prompt template for summary generation"""
    try:
        import os
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "config", "default_prompt.txt")

        with open(prompt_path, 'r', encoding='utf-8') as file:
            default_prompt = file.read().strip()

        return {"default_prompt": default_prompt}

    except FileNotFoundError:
        logger.error("Default prompt file not found")
        return {"default_prompt": "Default ATC analysis prompt for structured summaries."}
    except Exception as e:
        logger.error(f"Error reading default prompt: {str(e)}")
        return {"default_prompt": "Default ATC analysis prompt for structured summaries."}

@router.post("/clean-text")
async def clean_text_block(
    request: dict,
    token_data: TokenData = Depends(get_token_data)
):
    """Clean a single text block by removing filler words, unnecessary questions, etc."""
    try:
        text_block = request.get("text", "")
        if not text_block.strip():
            return {"cleaned_text": ""}

        # System prompt for cleaning transcription text
        system_prompt = """You are an expert text cleaner for air traffic control transcriptions. 
Your task is to clean up raw transcription text by:

1. Removing filler words (um, uh, er, ah, etc.)
2. Removing unnecessary questions or confirmations that don't add informational value
3. Keeping only clear, informative statements
4. Maintaining technical accuracy and aviation terminology
5. Preserving callsigns, frequencies, and operational instructions exactly
6. Keeping the essential meaning while making it more readable

Return only the cleaned text without any explanations or additional formatting."""

        # Clean the text using the LLM
        summary_result = await generate_summary(
            text_block,
            "",
            "standard", 
            system_prompt
        )

        return {"cleaned_text": summary_result.summary.strip()}

    except Exception as e:
        logger.error(f"Error cleaning text block: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Text cleaning failed: {str(e)}")



async def generate_structured_summary(
    transcription: str,
    transcription_segments: List[TranscriptionSegment],
    custom_prompt: Optional[str] = None
) -> StructuredSummary:
    """Generate a structured summary with Kanban-style categorization for ATC analysis"""
    import datetime
    import re

    # Create timestamped transcription for the prompt
    timestamped_transcription = create_timestamped_transcription(transcription_segments)
    current_time = datetime.datetime.now()

    structured_prompt = f"""
    You are an expert Air Traffic Control analyst. Based on the following transcription, categorize information into two main areas:

    CURRENT TIME: {current_time.strftime("%H%M")}H

    **PENDING INFORMATION ANALYSIS:**
    Identify any pending information, requests, or actions that require follow-up, including:
    - ETAs/ETRs that need to be converted to actual times (e.g., "15 minutes from now" should be calculated as actual clock time)
    - Pending clearances or requests
    - Information awaiting response
    - Coordination requirements
    - Weather updates pending
    - Any unresolved operational matters

    **EMERGENCY INFORMATION ANALYSIS:**
    Identify and categorize emergency situations:
    - MAYDAY_PAN: Emergency distress calls (MAYDAY, PAN-PAN)
    - CASEVAC: Medical evacuation requests
    - AIRCRAFT_DIVERSION: Unplanned aircraft diversions
    - OTHERS: Situations requiring immediate controller attention, threats to life or mission

    {f"Additional instructions: {custom_prompt}" if custom_prompt else ""}

    Timestamped Transcription:
    {timestamped_transcription}

    RESPONSE FORMAT: Provide your response as a valid JSON object with this exact structure:
    {{
        "pending_information": [
            {{
                "description": "Description of pending item",
                "eta_etr_info": "Original ETA/ETR mentioned if any",
                "calculated_time": "Actual clock time (HHMM format) if applicable",
                "priority": "low|medium|high",
                "timestamps": [relevant timestamp references]
            }}
        ],
        "emergency_information": [
            {{
                "category": "MAYDAY_PAN|CASEVAC|AIRCRAFT_DIVERSION|OTHERS",
                "description": "Description of emergency",
                "severity": "high",
                "immediate_action_required": true,
                "timestamps": [relevant timestamp references]
            }}
        ]
    }}

    If no items exist for a category, return an empty array.
    """

    # Call the summary service with structured prompt
    summary_result = await generate_summary(
        transcription,
        "",
        "atc",
        structured_prompt
    )

    # Parse the JSON response
    try:
        # Clean the response string to ensure it's valid JSON
        json_response_str = summary_result.summary.strip()
        if json_response_str.startswith("```json"):
            json_response_str = json_response_str[7:]
        if json_response_str.endswith("```"):
            json_response_str = json_response_str[:-3]
        json_response_str = json_response_str.strip()

        logger.debug(f"Attempting to parse Kanban JSON response: {json_response_str}")
        response_data = json.loads(json_response_str)

        # Parse pending information
        pending_items = []
        for item_data in response_data.get("pending_information", []):
            pending_items.append(PendingInformationItem(**item_data))

        # Parse emergency information
        emergency_items = []
        for item_data in response_data.get("emergency_information", []):
            emergency_items.append(EmergencyItem(**item_data))

        return StructuredSummary(
            pending_information=pending_items,
            emergency_information=emergency_items
        )

    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Failed to parse Kanban JSON response: {e}\nRaw response: {summary_result.summary}")
        # Return empty structure on parse failure
        return StructuredSummary(
            pending_information=[],
            emergency_information=[]
        )

async def generate_append_suggestions(
    transcription: str,
    transcription_segments: List[TranscriptionSegment],
    previous_structured: Dict,
    custom_prompt: Optional[str] = None
) -> StructuredSummaryAppendSuggestions:
    """Generate suggestions for what to append to existing structured summary sections"""

    # Create timestamped transcription for the prompt
    timestamped_transcription = create_timestamped_transcription(transcription_segments)

    # Extract existing section contents for context
    existing_situation = previous_structured.get("situation_update", {}).get("content", "")
    existing_details = previous_structured.get("current_situation_details", {}).get("content", "")
    existing_actions = previous_structured.get("recent_actions_taken", {}).get("content", "")
    existing_status = previous_structured.get("overall_status", {}).get("content", "")

    append_prompt = f"""
    You are analyzing NEW air traffic control transcription data. Your task is to identify what NEW information should be APPENDED to existing analysis sections, NOT to replace them.

    EXISTING ANALYSIS:

    Situation Update: {existing_situation}
    Current Situation Details: {existing_details}
    Recent Actions Taken: {existing_actions}
    Overall Status: {existing_status}

    NEW TRANSCRIPTION DATA:
    {timestamped_transcription}

    {f"Additional instructions: {custom_prompt}" if custom_prompt else ""}

    For each section below, provide ONLY new information that should be APPENDED. If there's no new information for a section, respond with "NO_NEW_INFO".

    Format your response as:

    SITUATION_UPDATE_APPEND:
    [New information to append, or NO_NEW_INFO]

    CURRENT_SITUATION_APPEND:
    [New information to append, or NO_NEW_INFO]

    RECENT_ACTIONS_APPEND:
    [New information to append, or NO_NEW_INFO]

    OVERALL_STATUS_APPEND:
    [New information to append, or NO_NEW_INFO]

    Reference specific timestamps for any new information you identify.
    """

    # Call the summary service with append prompt
    append_result = await generate_summary(
        transcription,
        "",
        "atc",
        append_prompt
    )

    # Parse the append suggestions
    suggestions = parse_append_response(append_result.summary, transcription_segments)

    return StructuredSummaryAppendSuggestions(
        situation_update=suggestions.get("situation_update", create_empty_append()),
        current_situation_details=suggestions.get("current_situation_details", create_empty_append()),
        recent_actions_taken=suggestions.get("recent_actions_taken", create_empty_append()),
        overall_status=suggestions.get("overall_status", create_empty_append())
    )



def parse_structured_response(response: str) -> Dict[str, str]:
    """Parse structured response into sections"""
    sections = {}
    current_section = None
    current_content = []

    lines = response.split('\n')
    for line in lines:
        line = line.strip()
        if any(keyword in line.upper() for keyword in ['SITUATION_UPDATE', 'CURRENT_SITUATION', 'RECENT_ACTIONS', 'OVERALL_STATUS']):
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()

            if 'SITUATION_UPDATE' in line.upper():
                current_section = 'situation_update'
            elif 'CURRENT_SITUATION' in line.upper():
                current_section = 'current_situation_details'
            elif 'RECENT_ACTIONS' in line.upper():
                current_section = 'recent_actions_taken'
            elif 'OVERALL_STATUS' in line.upper():
                current_section = 'overall_status'

            current_content = []
        elif current_section:
            current_content.append(line)

    if current_section and current_content:
        sections[current_section] = '\n'.join(current_content).strip()

    return sections

def parse_structured_summary_from_json(summary_data: Dict[str, Any], segments: List[TranscriptionSegment]) -> Dict[str, SectionWithTimestamps]:
    """Parse the structured summary part of the LLM's JSON response."""
    sections = {}

    # Define mapping from JSON keys (which we ask the LLM for) to internal keys
    key_mapping = {
        "SITUATION_UPDATE": "situation_update",
        "CURRENT_SITUATION_DETAILS": "current_situation_details",
        "RECENT_ACTIONS_TAKEN": "recent_actions_taken",
        "OVERALL_STATUS": "overall_status"
    }

    for json_key, internal_key in key_mapping.items():
        content = summary_data.get(json_key, "")
        if content and isinstance(content, str):
            timestamps = extract_timestamps_from_content(content, segments)
            sections[internal_key] = SectionWithTimestamps(
                content=content,
                timestamps=timestamps,
                latest_timestamp=get_latest_timestamp(timestamps)
            )
        else:
            sections[internal_key] = create_empty_section()

    return sections


def create_timestamped_transcription(segments: List[TranscriptionSegment]) -> str:
    """Create a timestamped transcription for the AI prompt"""
    if not segments:
        return "No timestamped segments available"

    formatted_segments = []
    for segment in segments:
        timestamp = f"[{segment.start:.1f}s-{segment.end:.1f}s]"
        formatted_segments.append(f"{timestamp} {segment.text}")

    return "\n".join(formatted_segments)

def create_empty_section() -> SectionWithTimestamps:
    """Create an empty section with timestamps"""
    return SectionWithTimestamps(
        content="No information available",
        timestamps=[],
        latest_timestamp=None
    )

def parse_structured_response_with_timestamps(response: str, segments: List[TranscriptionSegment]) -> Dict[str, SectionWithTimestamps]:
    """Parse structured response into sections with extracted timestamps"""
    sections = {}
    current_section = None
    current_content = []

    lines = response.split('\n')
    for line in lines:
        line = line.strip()
        if any(keyword in line.upper() for keyword in ['SITUATION_UPDATE', 'CURRENT_SITUATION_DETAILS', 'RECENT_ACTIONS_TAKEN', 'OVERALL_STATUS']):
            if current_section:
                content = '\n'.join(current_content).strip()
                timestamps = extract_timestamps_from_content(content, segments)
                sections[current_section] = SectionWithTimestamps(
                    content=content,
                    timestamps=timestamps,
                    latest_timestamp=get_latest_timestamp(timestamps)
                )

            if 'SITUATION_UPDATE' in line.upper():
                current_section = 'situation_update'
            elif 'CURRENT_SITUATION_DETAILS' in line.upper():
                current_section = 'current_situation_details'
            elif 'RECENT_ACTIONS_TAKEN' in line.upper():
                current_section = 'recent_actions_taken'
            elif 'OVERALL_STATUS' in line.upper():
                current_section = 'overall_status'

            current_content = []
        elif current_section:
            current_content.append(line)

    if current_section and current_content:
        content = '\n'.join(current_content).strip()
        timestamps = extract_timestamps_from_content(content, segments)
        sections[current_section] = SectionWithTimestamps(
            content=content,
            timestamps=timestamps,
            latest_timestamp=get_latest_timestamp(timestamps)
        )

    return sections

def extract_timestamps_from_content(content: str, segments: List[TranscriptionSegment]) -> List[Dict[str, Any]]:
    """Extract timestamp references from content and find corresponding segments"""
    import re

    timestamps = []

    # Find timestamp patterns like "15.2s", "at 30.5s", "between 25.1s-35.2s"
    timestamp_patterns = [
        r'(\d+\.?\d*)s',  # Simple timestamp like "15.2s"
        r'at (\d+\.?\d*)s',  # "at 15.2s"
        r'between (\d+\.?\d*)s[—-](\d+\.?\d*)s',  # "between 15.2s-20.5s"
    ]

    for pattern in timestamp_patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            if len(match.groups()) == 1:
                # Single timestamp
                timestamp = float(match.group(1))
                relevant_segment = find_segment_by_timestamp(timestamp, segments)
                if relevant_segment:
                    timestamps.append({
                        "start": relevant_segment.start,
                        "end": relevant_segment.end,
                        "text": relevant_segment.text,
                        "referenced_time": timestamp
                    })
            elif len(match.groups()) == 2:
                # Range timestamp
                start_time = float(match.group(1))
                end_time = float(match.group(2))
                range_segments = find_segments_in_range(start_time, end_time, segments)
                for seg in range_segments:
                    timestamps.append({
                        "start": seg.start,
                        "end": seg.end,
                        "text": seg.text,
                        "referenced_time": (start_time + end_time) / 2
                    })

    # If no explicit timestamps found, find segments that contain keywords from the content
    if not timestamps:
        keywords = extract_keywords_from_content(content)
        for keyword in keywords:
            relevant_segments = find_segments_by_keyword(keyword, segments)
            for seg in relevant_segments[:3]:  # Limit to top 3 matches
                timestamps.append({
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                    "keyword_match": keyword
                })

    return timestamps

def find_segment_by_timestamp(timestamp: float, segments: List[TranscriptionSegment]) -> Optional[TranscriptionSegment]:
    """Find the segment that contains the given timestamp"""
    for segment in segments:
        if segment.start <= timestamp <= segment.end:
            return segment

    # If no exact match, find the closest segment
    closest_segment = None
    min_distance = float('inf')

    for segment in segments:
        distance = min(abs(segment.start - timestamp), abs(segment.end - timestamp))
        if distance < min_distance:
            min_distance = distance
            closest_segment = segment

    return closest_segment

def find_segments_in_range(start_time: float, end_time: float, segments: List[TranscriptionSegment]) -> List[TranscriptionSegment]:
    """Find all segments that overlap with the given time range"""
    result = []
    for segment in segments:
        if segment.start <= end_time and segment.end >= start_time:
            result.append(segment)
    return result

def find_segments_by_keyword(keyword: str, segments: List[TranscriptionSegment]) -> List[TranscriptionSegment]:
    """Find segments containing the keyword"""
    result = []
    keyword_lower = keyword.lower()
    for segment in segments:
        if keyword_lower in segment.text.lower():
            result.append(segment)
    return result

def extract_keywords_from_content(content: str) -> List[str]:
    """Extract important keywords from the summary content"""
    # Simple keyword extraction - in production you might want more sophisticated NLP
    import re

    # Remove common stop words and extract meaningful phrases
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'}

    # Extract words that are likely to be aviation-related
    words = re.findall(r'\b[A-Za-z]{3,}\b', content.lower())
    keywords = [word for word in words if word not in stop_words and len(word) > 3]

    # Prioritize aviation-related terms
    aviation_terms = ['aircraft', 'runway', 'tower', 'control', 'altitude', 'heading', 'approach', 'departure', 'clearance', 'frequency', 'transponder', 'squawk']
    prioritized_keywords = []

    for term in aviation_terms:
        if term in keywords:
            prioritized_keywords.append(term)

    # Add other keywords
    for keyword in keywords:
        if keyword not in prioritized_keywords:
            prioritized_keywords.append(keyword)

    return prioritized_keywords[:10]  # Return top 10 keywords

def get_latest_timestamp(timestamps: List[Dict[str, Any]]) -> Optional[float]:
    """Get the latest timestamp from a list of timestamp objects"""
    if not timestamps:
        return None

    latest = max(timestamps, key=lambda t: t.get("end", t.get("start", 0)))
    return latest.get("end", latest.get("start"))

def create_empty_append() -> SectionAppendSuggestion:
    """Create an empty append suggestion"""
    return SectionAppendSuggestion(
        new_content=None,
        new_timestamps=[],
        has_updates=False
    )

def parse_append_response(response: str, segments: List[TranscriptionSegment]) -> Dict[str, SectionAppendSuggestion]:
    """Parse append suggestions response into structured sections"""
    suggestions = {}
    current_section = None
    current_content = []

    lines = response.split('\n')
    for line in lines:
        line = line.strip()

        # Check for section headers
        if 'SITUATION_UPDATE_APPEND:' in line.upper():
            if current_section:
                suggestions[current_section] = process_append_content(current_content, segments)
            current_section = 'situation_update'
            current_content = []
        elif 'CURRENT_SITUATION_APPEND:' in line.upper():
            if current_section:
                suggestions[current_section] = process_append_content(current_content, segments)
            current_section = 'current_situation_details'
            current_content = []
        elif 'RECENT_ACTIONS_APPEND:' in line.upper():
            if current_section:
                suggestions[current_section] = process_append_content(current_content, segments)
            current_section = 'recent_actions_taken'
            current_content = []
        elif 'OVERALL_STATUS_APPEND:' in line.upper():
            if current_section:
                suggestions[current_section] = process_append_content(current_content, segments)
            current_section = 'overall_status'
            current_content = []
        elif current_section and line:
            current_content.append(line)

    # Process the last section
    if current_section and current_content:
        suggestions[current_section] = process_append_content(current_content, segments)

    return suggestions

def process_append_content(content_lines: List[str], segments: List[TranscriptionSegment]) -> SectionAppendSuggestion:
    """Process append content lines into a SectionAppendSuggestion"""
    content = '\n'.join(content_lines).strip()

    # Check if there's no new info
    if not content or 'NO_NEW_INFO' in content.upper():
        return create_empty_append()

    # Extract timestamps from the new content
    timestamps = extract_timestamps_from_content(content, segments)

    return SectionAppendSuggestion(
        new_content=content,
        new_timestamps=timestamps,
        has_updates=True
    )