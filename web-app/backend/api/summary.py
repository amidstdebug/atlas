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

@router.post("/process-block")
async def process_transcription_block(
    request: dict,
    token_data: TokenData = Depends(get_token_data)
):
    """Process a completed transcription block: clean text and extract NER entities"""
    try:
        raw_text = request.get("text", "")
        if not raw_text.strip():
            return {"cleaned_text": "", "ner_text": "", "entities": []}

        # Step 1: Clean the text
        clean_prompt = """You are an expert text cleaner for air traffic control transcriptions.
Your task is to clean up raw transcription text by:

1. Removing filler words (um, uh, er, ah, etc.)
2. Removing unnecessary questions or confirmations that don't add informational value
3. Keeping only clear, informative statements
4. Maintaining technical accuracy and aviation terminology
5. Preserving callsigns, frequencies, and operational instructions exactly
6. Keeping the essential meaning while making it more readable

Return only the cleaned text without any explanations or additional formatting."""

        # Clean the text
        clean_result = await generate_summary(raw_text, "", "standard", clean_prompt)
        cleaned_text = clean_result.summary.strip()

        # Step 2: Extract NER entities and create highlighted text
        ner_prompt = f"""You are an expert aviation Named Entity Recognition system. Analyze the following cleaned ATC transcription and identify entities in these categories:

CATEGORIES:
1. IMPORTANT_INFO: Critical operational information (clearances, instructions, restrictions, alerts)
2. WEATHER: Weather-related information (conditions, visibility, wind, precipitation)
3. TIMES: Time references (ETAs, ETRs, specific times, deadlines)

CLEANED TEXT: {cleaned_text}

Your task:
1. Identify all entities in the above categories
2. Return the text with HTML span tags around identified entities
3. Use these exact class names for highlighting:
   - IMPORTANT_INFO: class="ner-important"
   - WEATHER: class="ner-weather"
   - TIMES: class="ner-times"

RESPONSE FORMAT: Return a JSON object with this structure:
{{
    "ner_text": "Text with <span class='ner-category'>highlighted entities</span>",
    "entities": [
        {{
            "text": "entity text",
            "category": "IMPORTANT_INFO|WEATHER|TIMES",
            "start_pos": 0,
            "end_pos": 10
        }}
    ]
}}

Return only the JSON object, no other text."""

        # Get NER results
        ner_result = await generate_summary(cleaned_text, "", "standard", ner_prompt)

        # Parse NER JSON response
        try:
            import json
            ner_json_str = ner_result.summary.strip()
            if ner_json_str.startswith("```json"):
                ner_json_str = ner_json_str[7:]
            if ner_json_str.endswith("```"):
                ner_json_str = ner_json_str[:-3]
            ner_json_str = ner_json_str.strip()

            ner_data = json.loads(ner_json_str)

            return {
                "cleaned_text": cleaned_text,
                "ner_text": ner_data.get("ner_text", cleaned_text),
                "entities": ner_data.get("entities", [])
            }

        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse NER JSON: {e}\nRaw response: {ner_result.summary}")
            # Fallback - return cleaned text without NER highlighting
            return {
                "cleaned_text": cleaned_text,
                "ner_text": cleaned_text,
                "entities": []
            }

    except Exception as e:
        logger.error(f"Error processing transcription block: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Block processing failed: {str(e)}")



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


def create_timestamped_transcription(segments: List[TranscriptionSegment]) -> str:
    """Create a timestamped transcription for the AI prompt"""
    if not segments:
        return "No timestamped segments available"

    formatted_segments = []
    for segment in segments:
        timestamp = f"[{segment.start:.1f}s-{segment.end:.1f}s]"
        formatted_segments.append(f"{timestamp} {segment.text}")

    return "\n".join(formatted_segments)