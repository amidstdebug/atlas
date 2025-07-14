from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Optional, List, Any
import logging
import json

from models.AuthType import TokenData
from models.SummaryResponse import (
    InvestigationRequest,
    InvestigationResponse,
    StructuredSummary,
    SectionWithTimestamps,
    TranscriptionSegment,
    StructuredSummaryAppendSuggestions,
    SectionAppendSuggestion,
    PendingInformationItem,
    EmergencyItem,
)
from services.auth.jwt import get_token_data
from services.summary.vllm_service import generate_completion
from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Summary"])

# Store current summaries for users
current_summaries = {}

@router.post("/v1/chat/completions")
async def chat_completions(
    request: Dict[str, Any],
    token_data: TokenData = Depends(get_token_data)
):
    """Proxy ChatCompletion requests through a Redis queue"""
    try:
        summary_result = await generate_completion(request)
        return summary_result

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


@router.post("/process-block")
async def process_transcription_block(
    request: dict,
    token_data: TokenData = Depends(get_token_data)
):
    """Process a completed transcription block: clean text and extract NER entities in one step."""
    try:
        raw_text = request.get("text", "")
        if not raw_text.strip():
            return {"cleaned_text": "", "ner_text": "", "entities": []}

        combined_prompt = f"""
You are an expert Air Traffic Control text processor. Your task is to process a raw transcription block by first cleaning it and then performing Named Entity Recognition (NER).

RAW TRANSCRIPTION:
{raw_text}

**Instructions:**

1.  **Clean the Text:**
    *   Transform the conversational `RAW TRANSCRIPTION` into a factual, clean version.
    *   Keep only clear, informative statements.
    *   Maintain all technical accuracy and aviation terminology.
    *   Preserve factual information exactly. Do not add or assume information.
    *   Maintain the identity of speakers (e.g., "Tower to Speedbird 123").

2.  **Perform NER on Cleaned Text:**
    *   Analyze the cleaned text you generated.
    *   Identify entities from the following categories:
        *   `IDENTIFIER`: Identification, name, or callsign (e.g., "Speedbird 123", "Tower").
        *   `WEATHER`: Weather information (e.g., "wind 270 at 10 knots", "visibility 10k").
        *   `TIMES`: Time references (e.g., "at 14:35Z", "in 10 minutes").
        *   `LOCATION`: Locations (e.g., "runway 27 right", "overhead the field").
        *   `IMPACT`: Any mentioned impact to mission (e.g., "unable to comply", "declaring an emergency").

3.  **Format the Output:**
    *   Return a single, valid JSON object. Do not include any other text, explanations, or markdown formatting.
    *   The JSON object must have three keys: `cleaned_text`, `ner_text`, and `entities`.
    *   `cleaned_text`: The cleaned version of the transcription.
    *   `ner_text`: The cleaned text with identified entities wrapped in HTML `<span>` tags. Use these exact class names: `ner-identifier`, `ner-weather`, `ner-times`, `ner-location`, `ner-impact`.
    *   `entities`: A list of JSON objects, one for each entity found, with `text`, `category`, `start_pos`, and `end_pos`.

**Crucial:** This data is for air incident investigation. Inaccuracies or assumptions could have serious consequences. If you have insufficient information, do not attempt to extrapolate.
Return only a valid JSON object using double quotes.
"""
        # Call the summarization service once with the combined prompt
        payload = {
            "model": settings.vllm_model,
            "messages": [
                {"role": "system", "content": combined_prompt},
                {"role": "user", "content": raw_text},
            ],
            "stream": False,
        }
        result = await generate_completion(payload)

        # Parse the JSON response
        try:
            json_str = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            json_str = json_str.strip()

            data = json.loads(json_str)

            # Ensure all keys are present, providing sensible defaults
            cleaned_text = data.get("cleaned_text", raw_text) # Fallback to raw_text if not in response
            return {
                "cleaned_text": cleaned_text,
                "ner_text": data.get("ner_text", cleaned_text),
                "entities": data.get("entities", [])
            }

        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse combined processing JSON: {e}\nRaw response: {result.summary}")
            # Fallback - return the raw text if JSON parsing fails
            return {
                "cleaned_text": raw_text,
                "ner_text": raw_text,
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
    payload = {
        "model": settings.vllm_model,
        "messages": [
            {"role": "system", "content": structured_prompt},
            {"role": "user", "content": transcription},
        ],
        "stream": False,
    }
    summary_result = await generate_completion(payload)

    # Parse the JSON response
    try:
        # Clean the response string to ensure it's valid JSON
        json_response_str = summary_result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
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