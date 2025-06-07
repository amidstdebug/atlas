from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Optional, List, Any
import logging

from models.AuthType import TokenData
from models.SummaryResponse import SummaryRequest, SummaryResponse, InvestigationRequest, InvestigationResponse, StructuredSummary, SectionWithTimestamps, TranscriptionSegment, StructuredSummaryAppendSuggestions, SectionAppendSuggestion
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
        # Call the summary service
        summary_result = await generate_summary(
            request.transcription,
            request.previous_report,
            request.summary_mode,
            request.custom_prompt
        )

        # Generate structured summary if requested
        structured_summary = None
        append_suggestions = None
        
        if request.structured and request.summary_mode == "atc":
            user_id = token_data.user_id
            existing_summaries = current_summaries.get(user_id, [])
            previous_structured = existing_summaries[-1].get("structured_summary") if existing_summaries else None
            
            if previous_structured and request.previous_report:
                # Generate append suggestions for existing summaries
                append_suggestions = await generate_append_suggestions(
                    request.transcription,
                    request.transcription_segments or [],
                    previous_structured,
                    request.custom_prompt
                )
            else:
                # Generate initial structured summary
                structured_summary = await generate_structured_summary(
                    request.transcription,
                    request.transcription_segments or [],
                    request.custom_prompt
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
            append_suggestions=append_suggestions,
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

@router.post("/investigate", response_model=InvestigationResponse)
async def investigate_transcription(
    request: InvestigationRequest,
    token_data: TokenData = Depends(get_token_data)
):
    """Investigate transcription data with specific questions and time ranges"""
    try:
        # Filter transcription by time range if provided
        filtered_transcription = filter_transcription_by_time(
            request.transcription,
            request.start_time,
            request.end_time
        )

        # Generate investigation response
        investigation_result = await generate_investigation_response(
            filtered_transcription,
            request.question,
            request.context
        )

        return investigation_result

    except Exception as e:
        logger.error(f"Error during investigation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Investigation failed: {str(e)}")

async def generate_structured_summary(
    transcription: str,
    transcription_segments: List[TranscriptionSegment],
    custom_prompt: Optional[str] = None
) -> StructuredSummary:
    """Generate a structured summary with specific sections for ATC analysis"""

    # Create timestamped transcription for the prompt
    timestamped_transcription = create_timestamped_transcription(transcription_segments)

    structured_prompt = f"""
    Based on the following air traffic control transcription with timestamps, provide a structured analysis with the following sections.
    For each section, identify the most relevant timestamps that support your analysis.

    1. SITUATION UPDATE: A brief overview of the current operational status and any immediate concerns
    2. CURRENT SITUATION DETAILS: Detailed breakdown of aircraft positions, weather conditions, and operational factors
    3. RECENT ACTIONS TAKEN: Summary of control actions, clearances, and coordination activities
    4. OVERALL STATUS: Assessment of operational safety, efficiency, and any recommendations

    {f"Additional instructions: {custom_prompt}" if custom_prompt else ""}

    Timestamped Transcription:
    {timestamped_transcription}

    For each section, provide:
    - The analysis content
    - Reference specific timestamps (e.g., "at 15.2s", "between 30.5s-35.1s") that support your analysis

    Provide your response in a structured format with clear sections.
    """

    # Call the summary service with structured prompt
    summary_result = await generate_summary(
        transcription,
        "",
        "atc",
        structured_prompt
    )

    # Parse the structured response and extract timestamps
    sections = parse_structured_response_with_timestamps(summary_result.summary, transcription_segments)

    return StructuredSummary(
        situation_update=sections.get("situation_update", create_empty_section()),
        current_situation_details=sections.get("current_situation_details", create_empty_section()),
        recent_actions_taken=sections.get("recent_actions_taken", create_empty_section()),
        overall_status=sections.get("overall_status", create_empty_section())
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

async def generate_investigation_response(
    transcription: str,
    question: str,
    context: Optional[str] = None
) -> InvestigationResponse:
    """Generate a response to investigation questions about the transcription"""

    investigation_prompt = f"""
    You are an air traffic control investigation assistant. Answer the following question based on the provided transcription data.

    Question: {question}

    {f"Additional context: {context}" if context else ""}

    Transcription data:
    {transcription}

    Provide a detailed answer and identify any relevant segments that support your response.
    """

    # Call the summary service for investigation
    investigation_result = await generate_summary(
        transcription,
        "",
        "investigation",
        investigation_prompt
    )

    # Extract relevant segments (basic implementation)
    relevant_segments = extract_relevant_segments(transcription, question)

    return InvestigationResponse(
        answer=investigation_result.summary,
        relevant_segments=relevant_segments,
        metadata={"question": question, "segments_count": len(relevant_segments)}
    )

def filter_transcription_by_time(transcription: str, start_time: Optional[float], end_time: Optional[float]) -> str:
    """Filter transcription segments by time range"""
    if not start_time and not end_time:
        return transcription

    # This is a simplified implementation
    # In a real scenario, you'd parse the transcription format and filter by timestamps
    lines = transcription.split('\n')
    filtered_lines = []

    for line in lines:
        # Basic time filtering logic - adapt based on your transcription format
        if start_time is not None or end_time is not None:
            # Extract timestamp from line if available
            # This is a placeholder - implement based on your actual format
            filtered_lines.append(line)
        else:
            filtered_lines.append(line)

    return '\n'.join(filtered_lines)

def parse_structured_response(response: str) -> Dict[str, str]:
    """Parse structured response into sections"""
    sections = {}
    current_section = None
    current_content = []

    lines = response.split('\n')
    for line in lines:
        line = line.strip()
        if any(keyword in line.upper() for keyword in ['SITUATION UPDATE', 'CURRENT SITUATION', 'RECENT ACTIONS', 'OVERALL STATUS']):
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()

            if 'SITUATION UPDATE' in line.upper():
                current_section = 'situation_update'
            elif 'CURRENT SITUATION' in line.upper():
                current_section = 'current_situation_details'
            elif 'RECENT ACTIONS' in line.upper():
                current_section = 'recent_actions_taken'
            elif 'OVERALL STATUS' in line.upper():
                current_section = 'overall_status'

            current_content = []
        elif current_section:
            current_content.append(line)

    if current_section and current_content:
        sections[current_section] = '\n'.join(current_content).strip()

    return sections

def extract_relevant_segments(transcription: str, question: str) -> List[Dict[str, Any]]:
    """Extract segments relevant to the investigation question"""
    # Basic implementation - in production, you'd use more sophisticated analysis
    segments = []
    lines = transcription.split('\n')

    # Look for keywords from the question in the transcription
    question_keywords = question.lower().split()

    for i, line in enumerate(lines):
        if any(keyword in line.lower() for keyword in question_keywords if len(keyword) > 3):
            segments.append({
                "line_number": i + 1,
                "content": line.strip(),
                "relevance_score": 0.8  # Placeholder scoring
            })

    return segments[:10]  # Return top 10 relevant segments

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
        if any(keyword in line.upper() for keyword in ['SITUATION UPDATE', 'CURRENT SITUATION', 'RECENT ACTIONS', 'OVERALL STATUS']):
            if current_section:
                content = '\n'.join(current_content).strip()
                timestamps = extract_timestamps_from_content(content, segments)
                sections[current_section] = SectionWithTimestamps(
                    content=content,
                    timestamps=timestamps,
                    latest_timestamp=get_latest_timestamp(timestamps)
                )
            
            if 'SITUATION UPDATE' in line.upper():
                current_section = 'situation_update'
            elif 'CURRENT SITUATION' in line.upper():
                current_section = 'current_situation_details'
            elif 'RECENT ACTIONS' in line.upper():
                current_section = 'recent_actions_taken'
            elif 'OVERALL STATUS' in line.upper():
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