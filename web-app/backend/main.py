"""
Main FastAPI application entry point for ATLAS backend.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from api.auth import router as auth_router
from api.transcription import router as transcription_router
from api.summary import router as summary_router
from api.health import router as health_router
from api.ner_keywords import router as ner_keywords_router
from config.settings import settings

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

# Include API routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(transcription_router)
app.include_router(summary_router)
app.include_router(ner_keywords_router)

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "ATLAS Backend API", "docs": "/docs"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5002,
        reload=True
    )