"""
Main FastAPI application entry point for ATLAS backend.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging

from api.auth import router as auth_router
from api.transcription import router as transcription_router
from api.summary import router as summary_router
from api.health import router as health_router
from api.ner_keywords_simple import router as ner_keywords_router
from config.settings import settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title="ATLAS Backend API",
    description="Automated Transmission Language Analysis System",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Pre-warm caches and initialize services on startup"""
    try:
        # Pre-warm NER keywords cache to avoid first-call delays
        from api.summary import _get_ner_keywords_cached
        keyword_data = _get_ner_keywords_cached()
        total_keywords = sum(len(keywords) for keywords in keyword_data['categorized'].values())
        logger.info(f"NER cache pre-warmed on startup: {len(keyword_data['categorized'])} categories, {total_keywords} keywords")
    except Exception as e:
        logger.warning(f"Failed to pre-warm NER cache on startup: {e}")

# Include API routers
app.include_router(health_router)  # Keep health endpoints at root level
app.include_router(auth_router)    # Already has /auth prefix
app.include_router(transcription_router)
app.include_router(summary_router)
app.include_router(ner_keywords_router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "ATLAS Backend API", "docs": "/docs"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5002,
        reload=True
    )