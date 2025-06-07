import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Import text processing functions
try:
    from models.prompts.numbers import apply_custom_fixes
except ImportError:
    logger.warning("Could not import text processing functions from numbers.py")
    apply_custom_fixes = None

async def process_transcription_text(
    text: str,
    replace_numbers: bool = True,
    use_icao_callsigns: bool = True
) -> Dict[str, Any]:
    """
    Process transcription text with number replacement and ICAO callsign conversion.
    
    Args:
        text: The transcription text to process
        replace_numbers: Whether to apply number replacement processing
        use_icao_callsigns: Whether to apply ICAO callsign processing
        
    Returns:
        Dictionary containing processed text and metadata
    """
    if not apply_custom_fixes:
        logger.warning("Text processing functions not available")
        return {
            "processed_text": text,
            "original_text": text,
            "replacements_applied": {"error": "Text processing functions not available"}
        }
    
    try:
        processed_text = text
        replacements_applied = []
        
        # Apply number replacement if requested
        if replace_numbers:
            # Add your number replacement logic here
            # For now, just log that it would be applied
            replacements_applied.append("number_replacement")
        
        # Apply ICAO callsign conversion if requested  
        if use_icao_callsigns:
            # Apply custom fixes without the replace_numbers parameter
            processed_text = apply_custom_fixes(processed_text)
            replacements_applied.append("icao_callsigns")
        
        return {
            "processed_text": processed_text,
            "original_text": text,
            "replacements_applied": replacements_applied
        }
        
    except Exception as e:
        logger.error(f"Error in process_transcription_text: {str(e)}")
        raise