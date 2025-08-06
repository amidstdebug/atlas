import logging
import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI
from fastapi import HTTPException

from config.settings import get_settings
from services.queue.redis_queue import RedisQueue

logger = logging.getLogger(__name__)
settings = get_settings()
queue = RedisQueue("summary_tasks", settings.redis_url)

# Initialize AsyncOpenAI client for Gemini
def get_gemini_client():
	"""Get AsyncOpenAI client configured for Gemini API"""
	api_key = os.getenv("GEMINI_API_KEY")
	if not api_key:
		raise ValueError("GEMINI_API_KEY environment variable is required")
	
	return AsyncOpenAI(
		api_key=api_key,
		base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
	)

# Initialize Gemini client
try:
	gemini_client = get_gemini_client()
	logger.info("Gemini AsyncOpenAI-compatible client initialized successfully")
except Exception as e:
	logger.error(f"Failed to initialize Gemini client: {e}")
	gemini_client = None

async def _call_gemini(payload: Dict[str, Any]) -> Dict[str, Any]:
	"""Call Gemini using OpenAI-compatible interface"""
	try:
		if gemini_client is None:
			raise HTTPException(status_code=500, detail="Gemini client not initialized")
		
		# Extract parameters with defaults
		model = payload.get("model", "gemini-2.5-flash")
		messages = payload.get("messages", [])
		temperature = payload.get("temperature", 0.1)
		max_tokens = payload.get("max_tokens", 2048)
		
		if not messages:
			raise HTTPException(status_code=400, detail="No messages provided")
		
		logger.info(f"Calling Gemini with model: {model}, messages: {len(messages)}")
		
		messages = [{"role": "system", "content": "You are a helpful assistant."}, *messages]
		print("messages:", messages)
		# messages = {"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": "hi there"}]
		# Make the async API call
		response = await gemini_client.chat.completions.create(
			model=model,
			reasoning_effort="low",
			messages=messages,
			temperature=temperature,
			max_tokens=max_tokens
		)
		
		return response
		
	except Exception as e:
		logger.error(f"Gemini API call failed: {str(e)}")
		return {"error": f"Gemini API error: {str(e)}"}

async def generate_completion(payload: Dict[str, Any]) -> Dict[str, Any]:
	"""
	Main function to generate completion - uses direct Gemini call for simplicity
	"""
	try:
		# For now, call Gemini directly without Redis queue for simplicity
		# This makes the API much more reliable and faster
		return await _call_gemini(payload)
		
	except Exception as e:
		logger.error(f"Error in generate_completion: {str(e)}")
		return {"error": f"Generation failed: {str(e)}"}

def analyze_situation_change(
	old_segments: List[Dict[str, Any]], 
	new_segments: List[Dict[str, Any]], 
	custom_prompt: str
) -> Dict[str, Any]:
	"""Legacy function for backward compatibility"""
	logger.warning("analyze_situation_change is deprecated, use the new /summary/analyze endpoint instead")
	return {
		"should_update": True,
		"reason": "Legacy function - always returns true",
		"analysis_type": "legacy"
	} 