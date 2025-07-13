import logging
from typing import Dict, Any, Optional
import httpx
from fastapi import HTTPException

from config.settings import get_settings, settings
from models.SummaryResponse import SummaryResponse
from services.queue.redis_queue import RedisQueue

logger = logging.getLogger(__name__)
settings = get_settings()
queue = RedisQueue("summary_tasks", settings.redis_url)

async def _call_ollama(
    transcription: str,
    previous_report: Optional[str] = None,
    summary_mode: str = "standard",
    custom_prompt: Optional[str] = None,
) -> SummaryResponse:
    """Directly send transcription text to the Ollama service."""
    try:
        system_prompt = custom_prompt if custom_prompt else _get_default_prompt(summary_mode)
        user_message = f"Transcription text:\n{transcription}"
        if previous_report:
            user_message += f"\n\nPrevious report:\n{previous_report}"

        payload = {
            "model": settings.ollama_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(settings.llm_uri, json=payload)

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"Ollama service error: {response.text}")

        result = response.json()
        summary_text = result.get("message", {}).get("content", "")
        if not summary_text:
            raise HTTPException(status_code=500, detail="Empty response from Ollama service")

        return SummaryResponse(
            summary=summary_text,
            metadata={
                "model": settings.ollama_model,
                "mode": summary_mode,
                "transcription_length": len(transcription),
            },
        )
    except httpx.TimeoutException:
        logger.error("Timeout connecting to Ollama service")
        raise HTTPException(status_code=504, detail="Summary service timeout")
    except Exception as e:
        logger.error(f"Error in generate_summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(e)}")


async def generate_summary(
    transcription: str,
    previous_report: Optional[str] = None,
    summary_mode: str = "standard",
    custom_prompt: Optional[str] = None,
) -> SummaryResponse:
    """Queue the summarization request and wait for the result."""
    try:
        job_id = await queue.enqueue(
            {
                "transcription": transcription,
                "previous_report": previous_report,
                "summary_mode": summary_mode,
                "custom_prompt": custom_prompt,
            }
        )
        result = await queue.await_result(job_id)
        if isinstance(result, dict) and result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])
        return SummaryResponse(**result)
    except Exception as e:
        logger.error(f"Error in generate_summary: {str(e)}")
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
