from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import logging
from ..services.auth.auth import get_token_data, TokenData
from ..services.ner_keywords.manager import ner_keyword_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# Request/Response models
class InitializeEncryptionRequest(BaseModel):
    password: str

class AddKeywordsRequest(BaseModel):
    keywords: List[str]
    password: str

class RemoveKeywordsRequest(BaseModel):
    keywords: List[str]

class KeywordResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

@router.post("/ner-keywords/initialize", response_model=KeywordResponse)
async def initialize_encryption(
    request: InitializeEncryptionRequest,
    token_data: TokenData = Depends(get_token_data)
):
    """Initialize encryption for NER keywords"""
    try:
        if not request.password or len(request.password.strip()) < 6:
            raise HTTPException(
                status_code=400, 
                detail="Password must be at least 6 characters long"
            )
        
        success = ner_keyword_manager.initialize_encryption(request.password)
        
        if success:
            stats = ner_keyword_manager.get_stats()
            return KeywordResponse(
                success=True,
                message="Encryption initialized successfully",
                data=stats
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize encryption"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initializing encryption: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ner-keywords/add", response_model=KeywordResponse)
async def add_keywords(
    request: AddKeywordsRequest,
    token_data: TokenData = Depends(get_token_data)
):
    """Add new user keywords with encryption"""
    try:
        if not request.keywords:
            raise HTTPException(status_code=400, detail="No keywords provided")
        
        if not request.password:
            raise HTTPException(status_code=400, detail="Password required")
        
        # Filter out empty keywords
        valid_keywords = [kw.strip() for kw in request.keywords if kw.strip()]
        if not valid_keywords:
            raise HTTPException(status_code=400, detail="No valid keywords provided")
        
        success = ner_keyword_manager.add_user_keywords(valid_keywords, request.password)
        
        if success:
            stats = ner_keyword_manager.get_stats()
            return KeywordResponse(
                success=True,
                message=f"Successfully added {len(valid_keywords)} keywords",
                data=stats
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to add keywords. Check password and try again."
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding keywords: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ner-keywords/remove", response_model=KeywordResponse)
async def remove_keywords(
    request: RemoveKeywordsRequest,
    token_data: TokenData = Depends(get_token_data)
):
    """Remove user keywords"""
    try:
        if not request.keywords:
            raise HTTPException(status_code=400, detail="No keywords provided")
        
        if not ner_keyword_manager.is_encryption_initialized():
            raise HTTPException(
                status_code=400, 
                detail="Encryption not initialized. Please initialize first."
            )
        
        success = ner_keyword_manager.remove_user_keywords(request.keywords)
        
        if success:
            stats = ner_keyword_manager.get_stats()
            return KeywordResponse(
                success=True,
                message=f"Successfully removed {len(request.keywords)} keywords",
                data=stats
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to remove keywords")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing keywords: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ner-keywords/user", response_model=KeywordResponse)
async def get_user_keywords(
    token_data: TokenData = Depends(get_token_data)
):
    """Get user-defined keywords (decrypted)"""
    try:
        if not ner_keyword_manager.is_encryption_initialized():
            return KeywordResponse(
                success=True,
                message="Encryption not initialized",
                data={"keywords": [], "count": 0}
            )
        
        keywords = ner_keyword_manager.get_user_keywords()
        return KeywordResponse(
            success=True,
            message="User keywords retrieved successfully",
            data={"keywords": keywords, "count": len(keywords)}
        )
    
    except Exception as e:
        logger.error(f"Error getting user keywords: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ner-keywords/default")
async def get_default_keywords(
    token_data: TokenData = Depends(get_token_data)
):
    """Get default keywords"""
    try:
        keywords = ner_keyword_manager.get_default_keywords()
        return KeywordResponse(
            success=True,
            message="Default keywords retrieved successfully",
            data={"keywords": keywords, "count": len(keywords)}
        )
    
    except Exception as e:
        logger.error(f"Error getting default keywords: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ner-keywords/stats")
async def get_keyword_stats(
    token_data: TokenData = Depends(get_token_data)
):
    """Get keyword statistics"""
    try:
        stats = ner_keyword_manager.get_stats()
        return KeywordResponse(
            success=True,
            message="Statistics retrieved successfully",
            data=stats
        )
    
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/ner-keywords/clear")
async def clear_user_keywords(
    token_data: TokenData = Depends(get_token_data)
):
    """Clear all user keywords"""
    try:
        if not ner_keyword_manager.is_encryption_initialized():
            raise HTTPException(
                status_code=400, 
                detail="Encryption not initialized"
            )
        
        success = ner_keyword_manager.clear_user_keywords()
        
        if success:
            stats = ner_keyword_manager.get_stats()
            return KeywordResponse(
                success=True,
                message="All user keywords cleared successfully",
                data=stats
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to clear keywords")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing keywords: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 