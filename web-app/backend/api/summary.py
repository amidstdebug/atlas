from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Optional, List, Any
import logging
import json
import datetime

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
from services.summary.gemini_service import generate_completion
from config.settings import settings

import re
import difflib

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Summary"])

@router.post("/v1/chat/completions")
async def chat_completions(
    request: Dict[str, Any],
    token_data: TokenData = Depends(get_token_data)
):
    """Proxy ChatCompletion requests through Gemini"""
    try:
        if "model" not in request:
            request["model"] = "gemini-2.5-flash"
        
        if "temperature" not in request:
            request["temperature"] = 0.0
        if "max_tokens" not in request:
            request["max_tokens"] = 512
            
        summary_result = await generate_completion(request)
        return summary_result

    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(e)}")

@router.post("/summary/analyze")
async def analyze_transcription(
    request: Dict[str, Any],
    token_data: TokenData = Depends(get_token_data)
):
    """
    SIMPLIFIED: Single endpoint that analyzes transcription and determines if updates are needed.
    Does everything in one Gemini call: analyze changes, decide if update needed, generate structured summary.
    """
    try:
        # Extract request data
        current_report = request.get("current_report")
        new_segments = request.get("new_segments", [])
        old_segments = request.get("old_segments", [])
        custom_prompt = request.get("custom_prompt", "")
        
        logger.info(f"Analyze request: {len(new_segments)} new, {len(old_segments)} old segments")
        
        # If no new segments, no update needed
        if not new_segments:
            return {
                "should_update": False,
                "reason": "No new transcription segments",
                "structured_summary": None
            }
        
        # Create text from segments
        new_text = " ".join([seg.get("text", "") for seg in new_segments])
        old_text = " ".join([seg.get("text", "") for seg in old_segments[-10:]])  # Last 10 for context
        
        if not new_text.strip():
            return {
                "should_update": False,
                "reason": "No new text content",
                "structured_summary": None
            }
        
        # Single Gemini call that does everything
        analysis_prompt = f"""You are an air traffic control analyst. Analyze new transcription segments to determine if they contain information worth reporting.

CONTEXT (Recent): {old_text}

NEW SEGMENTS: {new_text}

CURRENT REPORT: {current_report or "None"}

TASK: 
1. Determine if NEW SEGMENTS contain ATC communications worth reporting
2. If yes, extract structured information

INSTRUCTIONS:
- Look for: pilot requests, controller instructions, emergencies, position reports, clearances
- Only report NEW information not already in current report
- Be precise - avoid false alarms

Respond in this EXACT JSON format:
{{
    "should_update": true/false,
    "reason": "Brief explanation",
    "structured_summary": {{
        "pending_information": [
            {{
                "description": "What is pending",
                "priority": "low/medium/high",
                "timestamps": [{{start: 0, end: 10}}]
            }}
        ],
        "emergency_information": [
            {{
                "category": "MAYDAY_PAN/CASEVAC/AIRCRAFT_DIVERSION/OTHERS",
                "description": "Emergency description",
                "severity": "high",
                "immediate_action_required": true,
                "timestamps": [{{start: 0, end: 10}}]
            }}
        ]
    }}
}}

If no update needed, set should_update to false and structured_summary to null.
If update needed but no specific items found, use empty arrays in structured_summary."""

        # Call Gemini
        payload = {
            "model": "gemini-1.5-flash",
            "messages": [{"role": "user", "content": analysis_prompt}],
            "stream": False,
            "temperature": 0.1,
            "max_tokens": 1000
        }
        
        result = await generate_completion(payload)
        
        # Parse response
        if not result or "error" in result:
            logger.error(f"Gemini error: {result}")
            return {
                "should_update": True,  # Default to update on error
                "reason": "Analysis failed - defaulting to update",
                "structured_summary": None
            }
        
        choices = result.get("choices", [])
        if not choices or "message" not in choices[0]:
            return {
                "should_update": True,
                "reason": "Invalid response format",
                "structured_summary": None
            }
        
        content = choices[0]["message"].get("content", "").strip()
        if not content:
            return {
                "should_update": True,
                "reason": "Empty response",
                "structured_summary": None
            }
        
        # Clean and parse JSON
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            response_data = json.loads(content)
            
            # Validate response structure
            should_update = response_data.get("should_update", True)
            reason = response_data.get("reason", "Analysis completed")
            structured_summary_data = response_data.get("structured_summary")
            
            # Convert to proper structure if update needed
            structured_summary = None
            if should_update and structured_summary_data:
                # Add timestamps from segments if missing
                all_segments = old_segments + new_segments
                
                pending_items = []
                for item in structured_summary_data.get("pending_information", []):
                    if not item.get("timestamps") and all_segments:
                        # Use last few segments for timestamps
                        item["timestamps"] = [
                            {"start": seg["start"], "end": seg["end"]} 
                            for seg in all_segments[-3:]
                        ]
                    pending_items.append(PendingInformationItem(**item))
                
                emergency_items = []
                for item in structured_summary_data.get("emergency_information", []):
                    if not item.get("timestamps") and all_segments:
                        item["timestamps"] = [
                            {"start": seg["start"], "end": seg["end"]} 
                            for seg in all_segments[-3:]
                        ]
                    emergency_items.append(EmergencyItem(**item))
                
                if pending_items or emergency_items:
                    structured_summary = StructuredSummary(
                        pending_information=pending_items,
                        emergency_information=emergency_items
                    )
            
            return {
                "should_update": should_update,
                "reason": reason,
                "structured_summary": structured_summary.dict() if structured_summary else None
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}, content: {content}")
            # Fallback - check if there's any meaningful content
            has_content = bool(new_text.strip())
            return {
                "should_update": has_content,
                "reason": f"Parse error - defaulting based on content: {has_content}",
                "structured_summary": None
            }
        
    except Exception as e:
        logger.error(f"Error in analyze_transcription: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.post("/summary/structured")
async def generate_structured_summary_endpoint(
    request: SummaryRequest,
    token_data: TokenData = Depends(get_token_data)
):
    """Generate a structured summary - simplified version"""
    try:
        if not request.transcription.strip():
            raise HTTPException(status_code=400, detail="Transcription text is required")
        
        if not request.custom_prompt or not request.custom_prompt.strip():
            raise HTTPException(status_code=400, detail="Custom prompt is required")

        # Simple single-call approach
        current_time = datetime.datetime.now()
        
        prompt = f"""ATC analyst. Current time: {current_time.strftime("%H:%M")}H.

{request.custom_prompt}

TRANSCRIPTION:
{request.transcription}

Extract structured information in this JSON format:
{{
    "pending_information": [
        {{
            "description": "What is pending",
            "priority": "low/medium/high",
            "timestamps": []
        }}
    ],
    "emergency_information": [
        {{
            "category": "MAYDAY_PAN/CASEVAC/AIRCRAFT_DIVERSION/OTHERS",
            "description": "Emergency details",
            "severity": "high",
            "immediate_action_required": true,
            "timestamps": []
        }}
    ]
}}

Return only valid JSON. Use empty arrays if no items found."""

        payload = {
            "model": "gemini-1.5-flash",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0.2,
            "max_tokens": 800
        }
        
        result = await generate_completion(payload)
        
        if not result or "error" in result:
            return SummaryResponse(
                summary="",
                structured_summary=None,
                metadata={"mode": "structured", "error": "Generation failed"}
            )
        
        choices = result.get("choices", [])
        if not choices or "message" not in choices[0]:
            return SummaryResponse(
                summary="",
                structured_summary=None,
                metadata={"mode": "structured", "error": "Invalid response"}
            )
        
        content = choices[0]["message"].get("content", "").strip()
        
        # Clean JSON
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            response_data = json.loads(content)
            
            # Parse items
            pending_items = []
            for item_data in response_data.get("pending_information", []):
                # Add timestamps from segments if missing
                if not item_data.get("timestamps") and request.transcription_segments:
                    item_data["timestamps"] = [
                        {"start": seg.start, "end": seg.end} 
                        for seg in request.transcription_segments[-3:]
                    ]
                pending_items.append(PendingInformationItem(**item_data))
            
            emergency_items = []
            for item_data in response_data.get("emergency_information", []):
                if not item_data.get("timestamps") and request.transcription_segments:
                    item_data["timestamps"] = [
                        {"start": seg.start, "end": seg.end} 
                        for seg in request.transcription_segments[-3:]
                    ]
                emergency_items.append(EmergencyItem(**item_data))
            
            structured_summary = None
            if pending_items or emergency_items:
                structured_summary = StructuredSummary(
                    pending_information=pending_items,
                    emergency_information=emergency_items
                )
            
            return SummaryResponse(
                summary="",
                structured_summary=structured_summary,
                metadata={
                    "mode": "structured",
                    "segments_count": len(request.transcription_segments or [])
                }
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return SummaryResponse(
                summary="",
                structured_summary=None,
                metadata={"mode": "structured", "error": "Parse failed"}
            )
        
    except Exception as e:
        logger.error(f"Error generating structured summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Structured summary generation failed: {str(e)}")

# Legacy endpoints for compatibility
@router.post("/summary/intelligent-situation-report")
async def generate_intelligent_situation_report(
    request: Dict[str, Any],
    token_data: TokenData = Depends(get_token_data)
):
    """Legacy endpoint - redirects to simplified analyze endpoint"""
    return await analyze_transcription(request, token_data)

@router.get("/summary/default-prompt")
async def get_default_prompt(
    token_data: TokenData = Depends(get_token_data)
):
    """Get the default prompt template"""
    try:
        import os
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "config", "default_prompt.txt")

        with open(prompt_path, 'r', encoding='utf-8') as file:
            default_prompt = file.read().strip()

        return {"default_prompt": default_prompt}

    except FileNotFoundError:
        return {"default_prompt": "Extract pending items and emergencies from ATC transcription. Focus on safety issues and required actions."}
    except Exception as e:
        logger.error(f"Error reading default prompt: {str(e)}")
        return {"default_prompt": "Extract pending items and emergencies from ATC transcription. Focus on safety issues and required actions."}

@router.get("/summary/default-format")
async def get_default_format(
    token_data: TokenData = Depends(get_token_data)
):
    """Get the default JSON format template"""
    try:
        default_format = {
            "pending_information": [
                {
                    "description": "",
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

@router.post("/process-block")
async def process_transcription_block(
    request: dict,
    token_data: TokenData = Depends(get_token_data)
):
    """Process a transcription block with NER"""
    try:
        raw_text = request.get("text", "")
        if not raw_text.strip():
            return {"cleaned_text": "", "ner_text": ""}

        # Load keywords
        from services.ner_keywords.simple_manager import simple_ner_manager
        try:
            keywords_by_category = simple_ner_manager.get_keywords_by_category()
            keyword_data = {'default': [], 'categorized': keywords_by_category}
        except Exception as e:
            logger.error(f"Failed to load NER keywords: {e}")
            keyword_data = {'default': [], 'categorized': {}}

        # Default category mappings
        default_category_mappings = {
            'mayday': 'red', 'pan pan': 'red', 'emergency': 'red', 'fire': 'red',
            'wind': 'blue', 'visibility': 'blue', 'weather': 'blue',
            'minutes': 'purple', 'thousand': 'purple', 'hundred': 'purple',
            'runway': 'green', 'taxiway': 'green', 'tower': 'green',
            'squawk': 'yellow', 'roger': 'yellow', 'cessna': 'yellow'
        }

        # Build keyword list
        categorized_keywords = {}
        
        for color_category, keywords in keyword_data['categorized'].items():
            if color_category not in categorized_keywords:
                categorized_keywords[color_category] = []
            categorized_keywords[color_category].extend(keywords)
        
        for keyword in keyword_data['default']:
            category = default_category_mappings.get(keyword.lower(), 'red')
            if category not in categorized_keywords:
                categorized_keywords[category] = []
            categorized_keywords[category].append(keyword)

        cleaned_text = raw_text
        ner_text = raw_text

        # Apply NER
        for category, keywords in categorized_keywords.items():
            short_kw = [kw for kw in keywords if len(kw) <= 3]
            long_kw = [kw for kw in keywords if len(kw) > 3]
            
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

        return {"cleaned_text": cleaned_text, "ner_text": ner_text}

    except Exception as e:
        logger.error(f"Error processing transcription block: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Block processing failed: {str(e)}")