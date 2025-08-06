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

        # Handle case where no relevant information was found
        if structured_summary is None:
            return SummaryResponse(
                summary="",
                structured_summary=None,
                metadata={
                    "mode": "structured", 
                    "segments_count": len(request.transcription_segments or []),
                    "relevance_check": "no_updates_needed"
                }
            )

        return SummaryResponse(
            summary="",  # No traditional summary for structured mode
            structured_summary=structured_summary,
            metadata={
                "mode": "structured", 
                "segments_count": len(request.transcription_segments or []),
                "relevance_check": "updates_found"
            }
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
    """Process a completed transcription block: apply categorized NER with fuzzy matching."""
    try:
        raw_text = request.get("text", "")
        if not raw_text.strip():
            return {"cleaned_text": "", "ner_text": ""}

        # Load categorized keywords from the keyword manager
        from services.ner_keywords.simple_manager import simple_ner_manager
        try:
            keywords_by_category = simple_ner_manager.get_keywords_by_category()
            keyword_data = {'default': [], 'categorized': keywords_by_category}
        except Exception as e:
            logger.error(f"Failed to load NER keywords: {e}")
            keyword_data = {'default': [], 'categorized': {}}

        # Define default category mappings for uncategorized keywords
        default_category_mappings = {
            # Emergency keywords
            'mayday': 'red',
            'pan pan': 'red', 
            'emergency': 'red',
            'fire': 'red',
            'medical': 'red',
            'alert': 'red',
            'priority': 'red',
            'urgent': 'red',
            
            # Weather keywords
            'wind': 'blue',
            'visibility': 'blue',
            'ceiling': 'blue',
            'clouds': 'blue',
            'overcast': 'blue',
            'clear': 'blue',
            'turbulence': 'blue',
            'icing': 'blue',
            'precipitation': 'blue',
            
            # Time keywords
            'minutes': 'purple',
            'thousand': 'purple',
            'hundred': 'purple',
            
            # Location keywords
            'runway': 'green',
            'taxiway': 'green',
            'apron': 'green',
            'gate': 'green',
            'terminal': 'green',
            'tower': 'green',
            'ground': 'green',
            'approach': 'green',
            'departure': 'green',
            'center': 'green',
            
            # Identifier keywords
            'squawk': 'yellow',
            'transponder': 'yellow',
            'roger': 'yellow',
            'wilco': 'yellow',
            'affirm': 'yellow',
            'negative': 'yellow',
            'standby': 'yellow',
            'cessna': 'yellow',
            'boeing': 'yellow',
            'airbus': 'yellow',
            'helicopter': 'yellow',
            'fighter': 'yellow',
            'cargo': 'yellow',
            'commercial': 'yellow'
        }

        # Build comprehensive keyword list with categories
        categorized_keywords = {}
        
        # Add user-defined categorized keywords using color names directly
        for color_category, keywords in keyword_data['categorized'].items():
            if color_category not in categorized_keywords:
                categorized_keywords[color_category] = []
            categorized_keywords[color_category].extend(keywords)
        
        # Add default keywords with automatic categorization
        for keyword in keyword_data['default']:
            category = default_category_mappings.get(keyword.lower(), 'red')  # default to red
            if category not in categorized_keywords:
                categorized_keywords[category] = []
            categorized_keywords[category].append(keyword)

        cleaned_text = raw_text
        ner_text = raw_text

        # Process each category
        for category, keywords in categorized_keywords.items():
            # Split by length for different matching strategies
            short_kw = [kw for kw in keywords if len(kw) <= 3]
            long_kw = [kw for kw in keywords if len(kw) > 3]
            
            # Token-level matching
            tokens = re.findall(r'\w+|\W+', ner_text)
            ner_tokens = []
            
            for tok in tokens:
                if re.fullmatch(r'\w+', tok) and not re.search(r'<span class="ner-', tok):
                    matched = False
                    
                    # Fuzzy match for longer keywords
                    for kw in long_kw:
                        ratio = difflib.SequenceMatcher(None, tok.lower(), kw.lower()).ratio()
                        if ratio >= 0.8:
                            matched = True
                            break
                    
                    # Exact match for short keywords
                    if not matched:
                        for kw in short_kw:
                            if tok.lower() == kw.lower():
                                matched = True
                                break
                    
                    if matched:
                        ner_tokens.append(f'<span class="ner-{category}">{tok}</span>')
                    else:
                        ner_tokens.append(tok)
                else:
                    ner_tokens.append(tok)
            
            ner_text = "".join(ner_tokens)
            
            # Second pass: spaced-out variants for short keywords
            for kw in short_kw:
                spaced_pattern = r"\b" + r"\s*".join(map(re.escape, kw)) + r"\b"
                pattern = re.compile(spaced_pattern, flags=re.IGNORECASE)
                
                def replace_match(match):
                    matched_text = match.group(0)
                    if not re.search(r'<span class="ner-', matched_text):
                        return f'<span class="ner-{category}">{matched_text}</span>'
                    return matched_text
                
                ner_text = pattern.sub(replace_match, ner_text)

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
) -> Optional[StructuredSummary]:
    """Generate a structured summary with configurable format for ATC analysis"""
    import datetime

    # Create timestamped transcription for the prompt
    timestamped_transcription = create_timestamped_transcription(transcription_segments)
    current_time = datetime.datetime.now()

    # First stage: Relevance check to avoid unnecessary processing
    relevance_check = await check_transcription_relevance(timestamped_transcription, custom_prompt)
    if not relevance_check:
        logger.info("No relevant updates found in transcription - skipping structured summary generation")
        return None

    # Default format if none provided
    if not format_template:
        format_template = json.dumps({
            "pending_information": [
                {
                    "description": "",
                    "eta_etr_info": "",
                    "calculated_time": "",
                    "priority": "low|medium|high",
                    "timestamps": [],
                    "segment_indices": []
                }
            ],
            "emergency_information": [
                {
                    "category": "MAYDAY_PAN|CASEVAC|AIRCRAFT_DIVERSION|OTHERS",
                    "description": "",
                    "severity": "high", 
                    "immediate_action_required": True,
                    "timestamps": [],
                    "segment_indices": []
                }
            ]
        }, indent=2)

    # Enhanced prompt structure with better instructions
    system_prompt = f"""ATC analyst. Current time: {current_time.strftime("%H:%M")}H. 

{custom_prompt}

CRITICAL INSTRUCTIONS:
1. Only include NEW pending or emergency information that requires attention
2. Include specific segment timestamps and indices for each item
3. Be precise - avoid false alarms or redundant information
4. If no new critical information exists, return empty arrays

Output JSON format:
{format_template}

Return only valid JSON with accurate timestamps and segment references."""

    user_prompt = timestamped_transcription

    # Call the summary service with optimized prompt structure
    payload = {
        "model": settings.vllm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "temperature": 0.3,  # Lower temperature for more consistent output
        "top_p": 0.9,
        "top_k": 40,
        "min_p": 0,
        "max_tokens": 1024,  # Increased for better detail
        "chat_template_kwargs": {"enable_thinking": False}
    }
    summary_result = await generate_completion(payload)

    # Robust OpenAI-compatible response parsing
    if isinstance(summary_result, dict) and "error" in summary_result:
        logger.error(f"vLLM/OpenAI error: {summary_result['error']}")
        return None

    content = ""
    try:
        choices = summary_result.get("choices", [])
        if choices and "message" in choices[0] and "content" in choices[0]["message"]:
            content = choices[0]["message"]["content"].strip()
        else:
            logger.error(f"No valid content in vLLM/OpenAI response: {summary_result}")
            return None

        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        logger.debug(f"Attempting to parse structured JSON response: {content}")
        response_data = json.loads(content)

        # Parse pending information with enhanced timestamp handling
        pending_items = []
        for item_data in response_data.get("pending_information", []):
            # Validate and enhance timestamp data
            enhanced_item = enhance_item_timestamps(item_data, transcription_segments)
            if enhanced_item:  # Only add if timestamps are valid
                pending_items.append(PendingInformationItem(**enhanced_item))

        # Parse emergency information with enhanced timestamp handling
        emergency_items = []
        for item_data in response_data.get("emergency_information", []):
            # Validate and enhance timestamp data
            enhanced_item = enhance_item_timestamps(item_data, transcription_segments)
            if enhanced_item:  # Only add if timestamps are valid
                emergency_items.append(EmergencyItem(**enhanced_item))

        # Return None if no items were found (avoiding empty structure)
        if not pending_items and not emergency_items:
            logger.info("No valid pending or emergency items found after processing")
            return None

        return StructuredSummary(
            pending_information=pending_items,
            emergency_information=emergency_items
        )

    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Failed to parse structured JSON response: {e}\nRaw response: {content}")
        return None


async def check_transcription_relevance(timestamped_transcription: str, custom_prompt: str) -> bool:
    """First stage check to determine if transcription contains relevant information"""
    relevance_prompt = f"""Analyze this ATC transcription for NEW information requiring attention.

Context: {custom_prompt}

Question: Does this transcription contain any NEW:
1. Emergency situations (mayday, pan-pan, medical, fire, etc.)
2. Pending requests (pilot waiting for clearance, information, etc.)
3. Critical operational updates requiring immediate attention

Transcription:
{timestamped_transcription}

Respond with only "YES" if new critical information exists, "NO" if routine communication only."""

    payload = {
        "model": settings.vllm_model,
        "messages": [{"role": "user", "content": relevance_prompt}],
        "stream": False,
        "temperature": 0.1,
        "max_tokens": 10,
        "chat_template_kwargs": {"enable_thinking": False}
    }
    
    try:
        result = await generate_completion(payload)
        choices = result.get("choices", [])
        if choices and "message" in choices[0]:
            response = choices[0]["message"]["content"].strip().upper()
            return "YES" in response
    except Exception as e:
        logger.error(f"Error in relevance check: {e}")
        return True  # Default to processing if check fails
    
    return False


def enhance_item_timestamps(item_data: dict, segments: List[TranscriptionSegment]) -> Optional[dict]:
    """Enhance item with accurate timestamp and segment index information"""
    if not segments:
        return None
    
    # Extract timestamps if provided by LLM
    timestamps = item_data.get("timestamps", [])
    segment_indices = item_data.get("segment_indices", [])
    
    # If no specific timestamps provided, try to infer from description
    if not timestamps and not segment_indices:
        description = item_data.get("description", "").lower()
        
        # Find relevant segments based on content matching
        relevant_indices = []
        for i, segment in enumerate(segments):
            if any(keyword in segment.text.lower() for keyword in 
                   ["emergency", "mayday", "pan", "medical", "fire", "request", "clearance", "waiting"]):
                relevant_indices.append(i)
        
        # Use the most recent relevant segments (last 3)
        segment_indices = relevant_indices[-3:] if relevant_indices else [len(segments) - 1]
    
    # Validate and populate timestamps from segment indices
    validated_timestamps = []
    validated_indices = []
    
    for idx in segment_indices:
        if 0 <= idx < len(segments):
            segment = segments[idx]
            validated_timestamps.extend([segment.start, segment.end])
            validated_indices.append(idx)
    
    # Fallback to recent segments if no valid indices
    if not validated_indices:
        last_segment = segments[-1]
        validated_timestamps = [last_segment.start, last_segment.end]
        validated_indices = [len(segments) - 1]
    
    # Update item with validated data
    item_data["timestamps"] = validated_timestamps
    item_data["segment_indices"] = validated_indices
    
    return item_data


def create_timestamped_transcription(segments: List[TranscriptionSegment]) -> str:
    """Create a timestamped transcription for the AI prompt with enhanced context"""
    if not segments:
        return "No transcription available"

    # Use more segments for better context, but optimize format for efficiency
    context_window = min(30, len(segments))  # Increased from 20 to 30
    recent_segments = segments[-context_window:]
    
    formatted_segments = []
    for i, segment in enumerate(recent_segments):
        segment_index = len(segments) - context_window + i
        timestamp = f"[{segment.start:.0f}s-{segment.end:.0f}s|#{segment_index}]"
        formatted_segments.append(f"{timestamp} {segment.text}")

    return "\n".join(formatted_segments)