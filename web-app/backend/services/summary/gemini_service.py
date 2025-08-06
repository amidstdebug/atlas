import logging
import os
import json
from typing import Dict, Any, Optional, List
from google import genai  # NEW: Using the updated Google GenAI client
from fastapi import HTTPException

from config.settings import get_settings
from services.queue.redis_queue import RedisQueue

logger = logging.getLogger(__name__)
settings = get_settings()
queue = RedisQueue("summary_tasks", settings.redis_url)

# Initialize Gemini client
def get_gemini_client():
    """Get Gemini client - API key is read from GEMINI_API_KEY environment variable"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required")
    return genai.Client(api_key=api_key)

# Initialize Gemini client
try:
    gemini_client = get_gemini_client()
    logger.info("Gemini API client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Gemini API client: {e}")
    gemini_client = None

async def _call_gemini(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Forward a ChatCompletion request to the Gemini service using new GenAI client."""
    try:
        if gemini_client is None:
            raise HTTPException(status_code=500, detail="Gemini client not initialized")
            
        # Extract messages from payload
        messages = payload.get("messages", [])
        if not messages:
            raise HTTPException(status_code=400, detail="No messages provided")

        # Build content from messages
        content_parts = []
        system_instruction = ""
        
        for message in messages:
            role = message.get("role")
            message_content = message.get("content", "")
            
            if role == "system":
                system_instruction = message_content
            elif role == "user":
                if system_instruction:
                    # Combine system instruction with user message
                    content_parts.append(f"{system_instruction}\n\nUser: {message_content}")
                    system_instruction = ""  # Only use it once
                else:
                    content_parts.append(message_content)
            elif role == "assistant":
                content_parts.append(f"Assistant: {message_content}")

        # Combine all content
        combined_content = "\n\n".join(content_parts)
        
        # Configure generation parameters
        generation_config = {
            'temperature': payload.get('temperature', 0.3),
            'top_p': payload.get('top_p', 0.9),
            'top_k': payload.get('top_k', 40),
            'max_output_tokens': payload.get('max_tokens', 1024),
        }

        # FIXED: Add safety settings to prevent blocking
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]

        # Use the new GenAI client API
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=combined_content,
            config=generation_config,
            safety_settings=safety_settings  # FIXED: Add safety settings
        )

        # FIXED: Handle None response
        response_text = response.text if response.text is not None else ""
        
        # Log if we got an empty response
        if not response_text:
            logger.warning(f"Gemini returned empty response for content: {combined_content[:200]}...")
            # Try to get more info about why it was blocked
            if hasattr(response, 'prompt_feedback'):
                logger.warning(f"Prompt feedback: {response.prompt_feedback}")
            if hasattr(response, 'candidates') and response.candidates:
                for i, candidate in enumerate(response.candidates):
                    logger.warning(f"Candidate {i}: {candidate}")

        # Format response in OpenAI-compatible format
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": response_text  # FIXED: Use response_text instead of response.text
                },
                "finish_reason": "stop",
                "index": 0
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }

    except Exception as e:
        logger.error(f"Error in Gemini API call: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Gemini API call failed: {str(e)}")


async def generate_completion(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Queue a ChatCompletion request and wait for the result."""
    try:
        job_id = await queue.enqueue(payload)
        result = await queue.await_result(job_id)
        if isinstance(result, dict) and result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except Exception as e:
        logger.error(f"Error in generate_completion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(e)}")


def _get_default_prompt(mode: str) -> str:
    """Get the default prompt based on summary mode."""
    prompts = {
        "standard": """You are an expert air traffic control analyst. Your task is to summarize the provided transcription.
Focus on key instructions, callsigns, and any unusual events.
Keep the summary clear, concise, and focused on safety.""",

        "detailed": """You are an expert air traffic control analyst. Provide a detailed analysis of the transcription including:

1. Complete timeline of events
2. All aircraft involved with callsigns
3. Controller instructions and pilot responses
4. Weather or traffic conditions mentioned
5. Any deviations from standard procedures
6. Safety implications and recommendations

Organize the summary with clear sections and maintain chronological order.""",

        "incident": """You are an expert air traffic control safety analyst. Analyze this transcription for potential safety incidents or concerns:

1. Identify any safety-critical events
2. Assess compliance with procedures
3. Note any communication issues
4. Highlight risk factors
5. Provide safety recommendations

Focus on risk assessment and safety implications.""",

        "investigation": """You are an air traffic control investigation assistant. Answer questions about air traffic control transcriptions with accuracy and detail.

Analyze the provided transcription data to answer specific questions. Focus on:
1. Extracting relevant information to answer the question
2. Identifying supporting evidence from the transcription
3. Providing clear, factual responses
4. Highlighting any important context or implications

Be concise but thorough in your analysis.""",

        "atc": """You are an expert Air Traffic Control analysis system. Analyze ATC transcriptions to provide structured summaries and detect alerts.

Generate comprehensive structured analysis including:
1. SITUATION_UPDATE: Current status overview
2. CURRENT_SITUATION_DETAILS: Detailed analysis of events
3. RECENT_ACTIONS_TAKEN: Actions and communications observed

Also detect and report any safety alerts, procedural deviations, or critical events. Format responses as valid JSON objects."""
    }

    return prompts.get(mode, prompts["standard"])


async def analyze_situation_change(
    current_report: Optional[str],
    new_segments: List[Dict[str, Any]], 
    old_segments: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Intelligent analysis to determine if a new situation report is needed.
    Returns analysis with recommendation on whether to generate new report.
    """
    try:
        # If no current report exists, always generate one
        if not current_report:
            return {"should_update": True, "reason": "No existing report"}

        # If no new segments, no update needed
        if not new_segments:
            return {"should_update": False, "reason": "No new transcription data"}

        # Create analysis prompt - REVISED to be more permissive and detailed
        analysis_prompt = f"""You are an ATC situation analysis system. Analyze new transcription segments to determine if they warrant updating the live situation report.

CURRENT SITUATION REPORT:
{current_report}

NEW TRANSCRIPTION SEGMENTS (since last report):
{json.dumps([{"text": seg.get("text", ""), "start": seg.get("start", 0), "end": seg.get("end", 0)} for seg in new_segments], indent=2)}

RECENT CONTEXT (last 10 segments):
{json.dumps([{"text": seg.get("text", ""), "start": seg.get("start", 0), "end": seg.get("end", 0)} for seg in old_segments[-10:]], indent=2) if old_segments else "None"}

ANALYSIS CRITERIA - Consider updating if NEW segments contain ANY of:
1. **Emergency situations** (mayday, pan-pan, medical, fire, security alerts)
2. **New pending requests** (pilots waiting for clearance, information, routing)
3. **Status changes** (weather updates, runway changes, traffic flow changes)
4. **New aircraft communications** (first contact, new callsigns, position reports)
5. **Operational updates** (approach changes, holding patterns, diversions)
6. **Any information not already covered** in the current report
7. **Routine communications** that add context or operational awareness

IMPORTANT: Err on the side of updating. Even routine communications can provide valuable situational awareness. Only skip updates if the new segments are truly redundant or contain no operational information.

Respond with JSON only:
{{
    "should_update": true/false,
    "reason": "Detailed explanation of decision",
    "significance_score": 1-10,
    "key_changes": ["specific changes or new information found"],
    "emergency_detected": true/false,
    "new_aircraft": ["any new callsigns mentioned"],
    "operational_changes": ["any operational updates"]
}}

Default to should_update: true unless segments are completely empty or purely repetitive."""

        # Configure generation settings for analysis
        generation_config = {
            'temperature': 0.2,  # Slightly higher for more nuanced analysis
            'top_p': 0.9,
            'top_k': 40,
            'max_output_tokens': 1024,  # Increased for more detailed analysis
        }

        # Use the new GenAI client for analysis
        if gemini_client is None:
            raise Exception("Gemini client not initialized")
            
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=analysis_prompt,
            config=generation_config
        )
        
        # Parse JSON response
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        analysis_result = json.loads(response_text.strip())
        
        # Ensure we have a reasonable default
        if "should_update" not in analysis_result:
            analysis_result["should_update"] = True
            analysis_result["reason"] = "Analysis incomplete - defaulting to update"
        
        logger.info(f"Situation change analysis: {analysis_result}")
        return analysis_result

    except Exception as e:
        logger.error(f"Error in situation change analysis: {e}")
        # Default to updating on error to be safe
        return {
            "should_update": True, 
            "reason": f"Analysis error - defaulting to update: {str(e)}", 
            "significance_score": 7,
            "key_changes": ["Analysis system error"],
            "emergency_detected": False
        } 