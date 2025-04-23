import re
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

def apply_custom_fixes(transcription: str) -> str:
    """
    Apply custom fixes to the raw transcription output from the model.
    This is a simplified version that focuses on common patterns in meeting minutes.
    
    Args:
        transcription: Raw transcription text from the model
        
    Returns:
        str: Improved transcription with fixes applied
    """
    # Check if there's actually any transcription content
    if not transcription or len(transcription.strip()) == 0:
        return "No speech detected"
    
    # Early return for false activations (repeated words or very short phrases)
    word_count = len(transcription.split())
    if word_count < 3:
        return "False activation"  # Too short to be meaningful
    
    # Detect repeated words (indication of false activation)
    words = transcription.split()
    if len(words) > 3:
        unique_words = set(words)
        if len(unique_words) <= 2 and len(words) > 3:
            return "False activation"  # Repeated words
    
    # Remove Whisper artifacts
    artifacts = [
        r"\.? Thanks for watching\.", r"\.? Thank you for watching\.", 
        r"\.? Like and subscribe\.", r"\.? Please subscribe\."
    ]
    for pattern in artifacts:
        transcription = re.sub(pattern, ".", transcription)
    
    # Standardize units (Feet and Knots)
    # Convert "X feet" to "Xft"
    transcription = re.sub(r"(\d+)\s*feet", r"\1ft", transcription)
    transcription = re.sub(r"(\d+)\s*foot", r"\1ft", transcription)
    
    # Convert "X knots" to "Xkts"
    transcription = re.sub(r"(\d+)\s*knots", r"\1kts", transcription)
    transcription = re.sub(r"(\d+)\s*knot", r"\1kts", transcription)
    
    # Capitalize first word of the transcription
    if transcription and len(transcription) > 0:
        transcription = transcription[0].upper() + transcription[1:]
    
    # Standardize numerical expressions
    # Convert number words to digits for discussion clarity
    number_mapping = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
        'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
        'ten': '10', 'eleven': '11', 'twelve': '12', 'thirteen': '13',
        'fourteen': '14', 'fifteen': '15', 'sixteen': '16', 'seventeen': '17',
        'eighteen': '18', 'nineteen': '19', 'twenty': '20',
        'thirty': '30', 'forty': '40', 'fifty': '50',
        'sixty': '60', 'seventy': '70', 'eighty': '80', 'ninety': '90',
        'hundred': '00', 'thousand': '000'
    }
    
    # Convert specific patterns like "twenty five" to "25"
    for word_num, digit in number_mapping.items():
        # Ensure whole word replacement (with boundaries)
        transcription = re.sub(r'\b' + word_num + r'\b', digit, transcription, flags=re.IGNORECASE)
    
    # Handle common compound numbers like "twenty five" → "25"
    compound_patterns = [
        (r'\b(twenty)\s+(\d)\b', lambda m: '2' + m.group(2)),
        (r'\b(thirty)\s+(\d)\b', lambda m: '3' + m.group(2)),
        (r'\b(forty)\s+(\d)\b', lambda m: '4' + m.group(2)),
        (r'\b(fifty)\s+(\d)\b', lambda m: '5' + m.group(2)),
        (r'\b(sixty)\s+(\d)\b', lambda m: '6' + m.group(2)),
        (r'\b(seventy)\s+(\d)\b', lambda m: '7' + m.group(2)),
        (r'\b(eighty)\s+(\d)\b', lambda m: '8' + m.group(2)),
        (r'\b(ninety)\s+(\d)\b', lambda m: '9' + m.group(2))
    ]
    
    for pattern, replacement in compound_patterns:
        transcription = re.sub(pattern, replacement, transcription, flags=re.IGNORECASE)
    
    # Combine adjacent digits for clarity (e.g., "1 2 3" to "123")
    transcription = re.sub(r'(\d)\s+(\d)\s+(\d)\s+(\d)', r'\1\2\3\4', transcription)
    transcription = re.sub(r'(\d)\s+(\d)\s+(\d)', r'\1\2\3', transcription)
    transcription = re.sub(r'(\d)\s+(\d)', r'\1\2', transcription)
    
    # Capitalize NATO phonetic alphabet for clarity
    nato_words = [
        'Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf',
        'Hotel', 'India', 'Juliet', 'Kilo', 'Lima', 'Mike', 'November',
        'Oscar', 'Papa', 'Quebec', 'Romeo', 'Sierra', 'Tango', 'Uniform',
        'Victor', 'Whiskey', 'X-ray', 'Yankee', 'Zulu'
    ]
    
    for word in nato_words:
        # Capitalize whole words only
        transcription = re.sub(r'\b' + word + r'\b', word, transcription, flags=re.IGNORECASE)
    
    return transcription