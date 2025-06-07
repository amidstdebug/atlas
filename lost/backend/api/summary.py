from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Optional
import logging

from models.AuthType import TokenData
from models.SummaryResponse import SummaryRequest, SummaryResponse
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

        # Store the summary for this user
        user_id = token_data.user_id
        if user_id not in current_summaries:
            current_summaries[user_id] = []

        current_summaries[user_id].append({
            "summary": summary_result.summary,
            "metadata": summary_result.metadata,
            "transcription_preview": request.transcription[:100] + "..." if len(request.transcription) > 100 else request.transcription
        })

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