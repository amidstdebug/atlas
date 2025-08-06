from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging
import httpx
import asyncio
from datetime import datetime

from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["Health"])

async def check_service_health(service_name: str, url: str, timeout: float = 5.0) -> Dict[str, Any]:
    """Check the health of a service by pinging its health endpoint"""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Try common health endpoints
            health_endpoints = ["/health", "/healthz", "/v1/models", "/"]
            
            for endpoint in health_endpoints:
                try:
                    response = await client.get(f"{url}{endpoint}")
                    if response.status_code == 200:
                        return {
                            "status": "healthy",
                            "response_time_ms": response.elapsed.total_seconds() * 1000,
                            "endpoint": endpoint,
                            "status_code": response.status_code
                        }
                except:
                    continue
                    
            # If no health endpoint works, try a basic connection
            response = await client.get(url)
            return {
                "status": "healthy" if response.status_code < 500 else "unhealthy",
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "endpoint": "/",
                "status_code": response.status_code
            }
            
    except httpx.TimeoutException:
        return {
            "status": "unhealthy",
            "error": "Timeout",
            "response_time_ms": timeout * 1000
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "response_time_ms": None
        }

@router.get("/health")
async def health_check():
    """Check the health of the API and all dependent services"""
    timestamp = datetime.utcnow().isoformat()
    
    # Check services concurrently - Only Whisper now, Gemini API is external
    whisper_health = await check_service_health("whisper", settings.whisper_service_url)
    
    # Handle exceptions from service call
    if isinstance(whisper_health, Exception):
        whisper_health = {"status": "unhealthy", "error": str(whisper_health)}
    
    # Determine overall health - Only need Whisper to be healthy
    all_healthy = whisper_health.get("status") == "healthy"
    
    overall_status = "healthy" if all_healthy else "degraded"
    
    health_data = {
        "status": overall_status,
        "timestamp": timestamp,
        "version": settings.app_version,
        "services": {
            "whisper": {
                "name": "Whisper Transcription Service",
                "url": settings.whisper_service_url,
                **whisper_health
            },
            "gemini": {
                "name": "Google Gemini API",
                "status": "external_service",
                "note": "External API - health not monitored"
            }
        }
    }
    
    # Return appropriate HTTP status
    status_code = 200 if all_healthy else 503
    
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=health_data)
    
    return health_data

@router.get("/health/simple")
async def simple_health_check():
    """Simple health check that only verifies API is running"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "API is running"
    } 