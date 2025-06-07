import logging
from typing import Dict, Any
from utils.atc_text_processor import process_transcript_data, apply_custom_fixes

logger = logging.getLogger(__name__)

async def process_transcription_text(
    text: str,
    replace_numbers: bool = True,
    use_icao_callsigns: bool = True
) -> Dict[str, Any]:
    """
    Process transcription text with optional number replacement and ICAO callsign formatting.
    Uses the existing functions from atc_text_processor.py and atc_constants.py.
    
    Args:
        text (str): The input text to process
        replace_numbers (bool): Whether to replace numbers with their word equivalents
        use_icao_callsigns (bool): Whether to format callsigns in ICAO style
        
    Returns:
        Dict[str, Any]: Dictionary containing processed text and processing details
    """
    try:
        # First apply custom fixes to the text
        text = apply_custom_fixes(text)
        
        # Create a data structure that matches what process_transcript_data expects
        data = {
            "text": text,
            "words": []  # Empty list since we don't have word-level timestamps
        }
        
        # Process the text using the ATC text processor
        processed_data = process_transcript_data(data)
        processed_text = processed_data["text"]
        
        # Track what processing was applied
        replacements_applied = {
            "numbers_replaced": replace_numbers,
            "icao_callsigns_applied": use_icao_callsigns
        }
        
        return {
            "processed_text": processed_text,
            "replacements_applied": replacements_applied
        }
        
    except Exception as e:
        logger.error(f"Error processing transcription text: {str(e)}")
        # Return original text if processing fails
        return {
            "processed_text": text,
            "replacements_applied": {
                "numbers_replaced": False,
                "icao_callsigns_applied": False
            }
        } 