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
    SummaryRequest,
    SummaryResponse,
)
from services.auth.jwt import get_token_data
from services.summary.vllm_service import generate_completion
from config.settings import settings

import re
import difflib

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
        
        # Optimize defaults for small models
        if "temperature" not in request:
            request["temperature"] = 0.0
        if "max_tokens" not in request:
            request["max_tokens"] = 512
            
        summary_result = await generate_completion(request)
        return summary_result

    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(e)}")

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

@router.get("/summary/default-format")
async def get_default_format(
    token_data: TokenData = Depends(get_token_data)
):
    """Get the default JSON format template for structured summary generation"""
    try:
        default_format = {
            "pending_information": [
                {
                    "description": "",
                    "eta_etr_info": "",
                    "calculated_time": "",
                    "priority": "low|medium|high",
                    "timestamps": []
                }
            ],
            "emergency_information": [
                {
                    "category": "MAYDAY_PAN|CASEVAC|AIRCRAFT_DIVERSION|OTHERS",
                    "description": "",
                    "severity": "high",
                    "immediate_action_required": True,
                    "timestamps": []
                }
            ]
        }

        return {"default_format": json.dumps(default_format, indent=2)}

    except Exception as e:
        logger.error(f"Error getting default format: {str(e)}")
        return {"default_format": "{}"}

@router.post("/summary/structured")
async def generate_structured_summary_endpoint(
    request: SummaryRequest,
    token_data: TokenData = Depends(get_token_data)
):
    """Generate a structured summary with configurable format and prompts"""
    try:
        if not request.transcription.strip():
            raise HTTPException(status_code=400, detail="Transcription text is required")
        
        if not request.custom_prompt or not request.custom_prompt.strip():
            raise HTTPException(status_code=400, detail="Custom prompt is required")

        # Get format from request (defaults provided in SummaryRequest model)
        format_template = getattr(request, 'format_template', None)
        
        structured_summary = await generate_structured_summary(
            transcription=request.transcription,
            transcription_segments=request.transcription_segments or [],
            custom_prompt=request.custom_prompt,
            format_template=format_template
        )

        return SummaryResponse(
            summary="",  # No traditional summary for structured mode
            structured_summary=structured_summary,
            metadata={"mode": "structured", "segments_count": len(request.transcription_segments or [])}
        )

    except Exception as e:
        logger.error(f"Error generating structured summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Structured summary generation failed: {str(e)}")


@router.get("/ner/default-prompt")
async def get_default_ner_prompt(
    token_data: TokenData = Depends(get_token_data)
):
    """Get the default prompt template for NER processing"""
    try:
        # Optimized default prompt for small models
        default_ner_prompt = """Clean ATC text and tag entities. Return JSON only.

Entity tags:
- IDENTIFIER: <span class="ner-identifier">callsign</span>
- WEATHER: <span class="ner-weather">weather</span> 
- TIMES: <span class="ner-times">time</span>
- LOCATION: <span class="ner-location">location</span>
- IMPACT: <span class="ner-impact">emergency</span>

Format: {"cleaned_text": "text", "ner_text": "tagged_text"}"""

        return {"default_ner_prompt": default_ner_prompt}

    except Exception as e:
        logger.error(f"Error getting default NER prompt: {str(e)}")
        return {"default_ner_prompt": "Default NER prompt for entity recognition."}

@router.post("/process-block")
async def process_transcription_block(
    request: dict,
    token_data: TokenData = Depends(get_token_data)
):
    """Process a completed transcription block: apply manual keyword-based NER with fuzzy matching."""
    try:
        raw_text = request.get("text", "")
        if not raw_text.strip():
            return {"cleaned_text": "", "ner_text": ""}

        # Load manual NER keywords
        try:
            with open('ner_keywords.txt', 'r') as f:
                keywords = [line.strip() for line in f if line.strip()]
        except Exception as e:
            logger.error(f"Failed to load NER keywords file: {e}")
            keywords = []

        # Split keywords by length to avoid fuzzy on short ones
        short_kw = [kw for kw in keywords if len(kw) <= 3]
        long_kw  = [kw for kw in keywords if len(kw) >  3]

        cleaned_text = raw_text

        # First pass: token-level exact or fuzzy matching
        tokens = re.findall(r'\w+|\W+', raw_text)
        ner_tokens = []
        for tok in tokens:
            if re.fullmatch(r'\w+', tok):
                norm = tok
                matched = False

                # fuzzy match long keywords
                for kw in long_kw:
                    ratio = difflib.SequenceMatcher(None, norm.lower(), kw.lower()).ratio()
                    if ratio >= 0.8:
                        matched = True
                        break

                # exact match short keywords
                if not matched:
                    for kw in short_kw:
                        if norm.lower() == kw.lower():
                            matched = True
                            break

                if matched:
                    ner_tokens.append(f'<span class="ner-keyword">{tok}</span>')
                else:
                    ner_tokens.append(tok)
            else:
                ner_tokens.append(tok)

        ner_text = "".join(ner_tokens)

        # Second pass: catch spaced-out variants of short keywords (e.g. "E T A")
        for kw in short_kw:
            spaced_pattern = r"\b" + r"\s*".join(map(re.escape, kw)) + r"\b"
            pattern = re.compile(spaced_pattern, flags=re.IGNORECASE)
            ner_text = pattern.sub(lambda m: f'<span class="ner-keyword">{m.group(0)}</span>', ner_text)

        return {
            "cleaned_text": cleaned_text,
            "ner_text": ner_text
        }

    except Exception as e:
        logger.error(f"Error processing transcription block: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Block processing failed: {str(e)}")

async def generate_structured_summary(
    transcription: str,
    transcription_segments: List[TranscriptionSegment],
    custom_prompt: str,  # Now required, no Optional
    format_template: Optional[str] = None
) -> StructuredSummary:
    """Generate a structured summary with configurable format for ATC analysis"""
    import datetime

    # Create timestamped transcription for the prompt
    timestamped_transcription = create_timestamped_transcription(transcription_segments)
    current_time = datetime.datetime.now()

    # Default format if none provided
    if not format_template:
        format_template = json.dumps({
            "pending_information": [
                {
                    "description": "",
                    "eta_etr_info": "",
                    "calculated_time": "",
                    "priority": "low|medium|high",
                    "timestamps": []
                }
            ],
            "emergency_information": [
                {
                    "category": "MAYDAY_PAN|CASEVAC|AIRCRAFT_DIVERSION|OTHERS",
                    "description": "",
                    "severity": "high", 
                    "immediate_action_required": True,
                    "timestamps": []
                }
            ]
        }, indent=2)

    # Simple prompt structure - custom_prompt is always provided
    system_prompt = f"""ATC analyst. Time: {current_time.strftime("%H%M")}H. {custom_prompt}

Output JSON format:
{format_template}

Return only valid JSON."""

    user_prompt = timestamped_transcription

    # Call the summary service with optimized prompt structure
    payload = {
        "model": settings.vllm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 20,
        "min_p": 0,
        "max_tokens": 512,  # Limit output length for efficiency
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

        logger.debug(f"Attempting to parse structured JSON response: {content}")
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
        logger.error(f"Failed to parse structured JSON response: {e}\nRaw response: {content}")
        # Return empty structure on parse failure
        return StructuredSummary(
            pending_information=[],
            emergency_information=[]
        )


def create_timestamped_transcription(segments: List[TranscriptionSegment]) -> str:
    """Create a timestamped transcription for the AI prompt"""
    if not segments:
        return "No transcription available"

    # Optimize for small model - shorter format, limit segments
    formatted_segments = []
    for i, segment in enumerate(segments[-20:]):  # Only last 20 segments to save context
        timestamp = f"[{segment.start:.0f}s]"  # Shorter timestamp format
        formatted_segments.append(f"{timestamp} {segment.text}")

    return "\n".join(formatted_segments)