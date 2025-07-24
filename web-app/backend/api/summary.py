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
        if "model" not in request:
            request["model"] = settings.vllm_model
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

        system_prompt = f"""Clean ATC transcription and identify entities. Return valid JSON only.

Clean the text factually, then tag entities with HTML spans:
- IDENTIFIER: <span class="ner-identifier">callsign/name</span>
- WEATHER: <span class="ner-weather">weather info</span> 
- TIMES: <span class="ner-times">time reference</span>
- LOCATION: <span class="ner-location">position/runway</span>
- IMPACT: <span class="ner-impact">emergency/deviation</span>

Return JSON with keys: cleaned_text, ner_text, entities
Example: {{"cleaned_text": "Tower cleared United 123 to land", "ner_text": "<span class=\"ner-identifier\">Tower</span> cleared <span class=\"ner-identifier\">United 123</span> to land", "entities": []}}"""
        # Call the summarization service once with the combined prompt
        payload = {
            "model": settings.vllm_model,
            "messages": [
				{"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_text},
            ],
            "stream": False,
            "temperature": 0.0,
            "chat_template_kwargs": {"enable_thinking": False}
        }
        result = await generate_completion(payload)

        # Robust OpenAI-compatible response parsing
        if isinstance(result, dict) and "error" in result:
            logger.error(f"vLLM/OpenAI error: {result['error']}")
            raise HTTPException(status_code=500, detail=f"vLLM/OpenAI error: {result['error']}")

        content = ""
        try:
            choices = result.get("choices", [])
            if choices and "message" in choices[0] and "content" in choices[0]["message"]:
                content = choices[0]["message"]["content"].strip()
            else:
                logger.error(f"No valid content in vLLM/OpenAI response: {result}")
                raise HTTPException(status_code=500, detail="No valid content in vLLM/OpenAI response.")

            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)

            # Ensure all keys are present, providing sensible defaults
            cleaned_text = data.get("cleaned_text", raw_text) # Fallback to raw_text if not in response
            return {
                "cleaned_text": cleaned_text,
                "ner_text": data.get("ner_text", cleaned_text),
                "entities": data.get("entities", [])
            }

        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse combined processing JSON: {e}\nRaw response: {content}")
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

    structured_prompt = f"""Analyze ATC transcription. Current time: {current_time.strftime("%H%M")}H

{timestamped_transcription}

{custom_prompt if custom_prompt else ""}

Return JSON with pending_information (ETAs, clearances, coordination) and emergency_information (MAYDAY_PAN, CASEVAC, AIRCRAFT_DIVERSION, OTHERS). Include description, priority/severity, timestamps.

Format: {{"pending_information": [{{"description": "", "eta_etr_info": "", "calculated_time": "", "priority": "low|medium|high", "timestamps": []}}], "emergency_information": [{{"category": "MAYDAY_PAN|CASEVAC|AIRCRAFT_DIVERSION|OTHERS", "description": "", "severity": "high", "immediate_action_required": true, "timestamps": []}}]}}"""

    # Call the summary service with structured prompt
    payload = {
        "model": settings.vllm_model,
        "messages": [
            {"role": "user", "content": structured_prompt},
        ],
        "stream": False,
		"chat_template_kwargs": {"enable_thinking": False}
    }
    summary_result = await generate_completion(payload)

    # Robust OpenAI-compatible response parsing
    if isinstance(summary_result, dict) and "error" in summary_result:
        logger.error(f"vLLM/OpenAI error: {summary_result['error']}")
        # Return empty structure on parse failure
        return StructuredSummary(
            pending_information=[],
            emergency_information=[]
        )

    content = ""
    try:
        choices = summary_result.get("choices", [])
        if choices and "message" in choices[0] and "content" in choices[0]["message"]:
            content = choices[0]["message"]["content"].strip()
        else:
            logger.error(f"No valid content in vLLM/OpenAI response: {summary_result}")
            # Return empty structure on parse failure
            return StructuredSummary(
                pending_information=[],
                emergency_information=[]
            )

        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        logger.debug(f"Attempting to parse Kanban JSON response: {content}")
        response_data = json.loads(content)

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
        logger.error(f"Failed to parse Kanban JSON response: {e}\nRaw response: {content}")
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