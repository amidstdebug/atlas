import logging
from typing import Dict, Any, Optional
import httpx
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from config.settings import get_settings
from models.SummaryResponse import SummaryResponse

logger = logging.getLogger(__name__)
settings = get_settings()

async def generate_summary(
    transcription: str,
    previous_report: Optional[str] = None,
    summary_mode: str = "standard",
    custom_prompt: Optional[str] = None
) -> SummaryResponse:
    """
    Send transcription text to Ollama service for summary generation.
    """
    try:
        # Build the prompt based on the mode and custom prompt
        if custom_prompt:
            system_prompt = custom_prompt
        else:
            system_prompt = _get_default_prompt(summary_mode)
        
        # Build the user message
        user_message = f"Transcription text:\n{transcription}"
        if previous_report:
            user_message += f"\n\nPrevious report:\n{previous_report}"
        
        # Prepare the request payload for Ollama
        payload = {
            "model": settings.ollama_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "stream": False
        }
        
        # Send request to Ollama service
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(settings.llm_uri, json=payload)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ollama service error: {response.text}"
            )
        
        # Parse the response
        result = response.json()
        summary_text = result.get('message', {}).get('content', '')
        
        if not summary_text:
            raise HTTPException(
                status_code=500,
                detail="Empty response from Ollama service"
            )
        
        return SummaryResponse(
            summary=summary_text,
            metadata={
                "model": settings.ollama_model,
                "mode": summary_mode,
                "transcription_length": len(transcription)
            }
        )
        
    except httpx.TimeoutException:
        logger.error("Timeout connecting to Ollama service")
        raise HTTPException(status_code=504, detail="Summary service timeout")
    except Exception as e:
        logger.error(f"Error in generate_summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(e)}")

def _get_default_prompt(mode: str) -> str:
    """Get the default prompt based on summary mode."""
    prompts = {
        "standard": """You are an expert air traffic control analyst. Analyze the provided transcription and generate a clear, concise summary that includes:

1. Key communications and instructions
2. Aircraft callsigns and movements
3. Any unusual events or incidents
4. Important operational details

Keep the summary professional and focused on safety-critical information.""",
        
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

Focus on risk assessment and safety implications."""
    }
    
    return prompts.get(mode, prompts["standard"])