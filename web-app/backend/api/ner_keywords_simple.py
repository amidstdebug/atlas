from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
import json
from services.auth.jwt import get_token_data
from models.AuthType import TokenData
from services.ner_keywords.simple_manager import simple_ner_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# Request/Response models
class UpdateKeywordsRequest(BaseModel):
    raw_text: str

class ImportRequest(BaseModel):
    data: Dict[str, Any]

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

@router.get("/ner-keywords/data")
async def get_keywords_data(
    token_data: TokenData = Depends(get_token_data)
):
    """Get keywords data including raw text for editing"""
    try:
        data = {
            "raw_text": simple_ner_manager.get_raw_text(),
            "categories": simple_ner_manager.get_categories(),
            "keywords_by_category": simple_ner_manager.get_keywords_by_category(),
            "stats": simple_ner_manager.get_stats()
        }
        return ApiResponse(
            success=True,
            message="Keywords data retrieved successfully",
            data=data
        )
    except Exception as e:
        logger.error(f"Error getting keywords data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ner-keywords/update")
async def update_keywords(
    request: UpdateKeywordsRequest,
    token_data: TokenData = Depends(get_token_data)
):
    """Update keywords from raw text format"""
    try:
        success = simple_ner_manager.update_from_raw_text(request.raw_text)
        
        if success:
            return ApiResponse(
                success=True,
                message="Keywords updated successfully",
                data={
                    "stats": simple_ner_manager.get_stats(),
                    "keywords_by_category": simple_ner_manager.get_keywords_by_category()
                }
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to update keywords")
    
    except Exception as e:
        logger.error(f"Error updating keywords: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ner-keywords/export")
async def export_keywords(
    token_data: TokenData = Depends(get_token_data)
):
    """Export keywords data as JSON"""
    try:
        data = simple_ner_manager.export_data()
        
        return ApiResponse(
            success=True,
            message="Keywords exported successfully",
            data=data
        )
    
    except Exception as e:
        logger.error(f"Error exporting keywords: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ner-keywords/import")
async def import_keywords(
    request: ImportRequest,
    token_data: TokenData = Depends(get_token_data)
):
    """Import keywords data from JSON"""
    try:
        success = simple_ner_manager.import_data(request.data)
        
        if success:
            return ApiResponse(
                success=True,
                message="Keywords imported successfully",
                data={
                    "raw_text": simple_ner_manager.get_raw_text(),
                    "stats": simple_ner_manager.get_stats()
                }
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to import keywords")
    
    except Exception as e:
        logger.error(f"Error importing keywords: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ner-keywords/import-file")
async def import_keywords_file(
    file: UploadFile = File(...),
    token_data: TokenData = Depends(get_token_data)
):
    """Import keywords from uploaded JSON file"""
    try:
        # Read and parse file content
        content = await file.read()
        data = json.loads(content.decode('utf-8'))
        
        success = simple_ner_manager.import_data(data)
        
        if success:
            return ApiResponse(
                success=True,
                message=f"File '{file.filename}' imported successfully",
                data={
                    "raw_text": simple_ner_manager.get_raw_text(),
                    "stats": simple_ner_manager.get_stats()
                }
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to import keywords from file")
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        logger.error(f"Error importing file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ner-keywords/stats")
async def get_stats(
    token_data: TokenData = Depends(get_token_data)
):
    """Get keyword statistics"""
    try:
        stats = simple_ner_manager.get_stats()
        return ApiResponse(
            success=True,
            message="Statistics retrieved successfully",
            data=stats
        )
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 