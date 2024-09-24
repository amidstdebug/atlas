# transcription.py

import re
import logging
from fuzzywuzzy import fuzz, process
from collections import defaultdict
from .lists import number_mapping, nato
# Set up logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

transcription_history = defaultdict(int)
pattern_history = defaultdict(lambda: {'count': 0, 'correct_format': ''})

# Function to log changes
def log_transcription_change(description, old_transcription, new_transcription):
    if old_transcription != new_transcription:
        logging.info(f"{description}: '{old_transcription}' -> '{new_transcription}'")

# Loop through and handle 'ident' patterns by looking to the left and right
def handle_ident_numbers(transcription):
    logging.info("Handling 'ident' numbers...")
    transcription_before = transcription
    # Define patterns for ident handling with a trailing space or end of string
    patterns = [
        r"0ident\b(?:\s|$)",          # Handles '0ident ' or '0ident' at end
        r"00ident_hundo\b(?:\s|$)",   # Handles '00ident_hundo ' or '00ident_hundo' at end
        r"000ident_thou\b(?:\s|$)"    # Handles '000ident_thou ' or '000ident_thou' at end
    ]
    
    # Replace all matching patterns with an empty string
    for pattern in patterns:
        transcription = re.sub(pattern, "", transcription)
    
    log_transcription_change("After handle_ident_numbers", transcription_before, transcription)
    return transcription

# Define helper functions (apply_custom_fixes, etc.)
def fix_decimal_followups(transcription):
    logging.info("Fixing decimal follow-ups...")
    transcription_before = transcription
    # Ensures proper handling of digits after a decimal point:
    # - Assume 1 digit after the decimal point by default.
    # - If 2 digits appear, check if the following sequence of numbers matches.
    pattern = r'(\d+\.\d{1,2})\s*(\d+)'  # Match sequences with 1 or 2 digits after decimal, followed by numbers
    matches = re.findall(pattern, transcription)
    
    for match in matches:
        full_number, follow_up = match
        # Check the digits after the decimal point
        decimal_part = full_number.split('.')[1]
        if len(decimal_part) == 1:
            # Default case: 1 digit after the decimal, keep it as is
            continue
        elif len(decimal_part) == 2:
            # Handle 2 digits after the decimal, check if the follow-up matches
            if follow_up.startswith(decimal_part):
                # If the next sequence starts with the same digits, keep the 2 digits after the decimal
                transcription = transcription.replace(f'{full_number} {follow_up}', f'{full_number}{follow_up[2:]}')
            else:
                # If no match, break after the first digit
                transcription = transcription.replace(f'{full_number} {follow_up}',
                                                      f'{full_number[:4]} {full_number[4]}')
    log_transcription_change("After fix_decimal_followups", transcription_before, transcription)
    return transcription

def apply_custom_fixes(transcription):
    logging.info(f"Original transcription: '{transcription}'")
    # Track frequent patterns
    min_similarity_threshold = 90  # Adjust threshold as needed

    # Apply custom word-to-number mapping
    for word_pattern, number in number_mapping.items():
        pattern = re.compile(word_pattern, flags=re.IGNORECASE)
        matches = pattern.findall(transcription)
        if matches:
            transcription_before = transcription
            transcription = pattern.sub(number, transcription)
            log_transcription_change(f"Applied number mapping '{word_pattern}' -> '{number}'", transcription_before, transcription)

    # Handle 'ident' patterns with adjacent digits
    transcription_before = transcription
    transcription = handle_ident_numbers(transcription)
    # Note: handle_ident_numbers already logs changes

    # Final cleanup: Remove any remaining 'ident' markers (just in case)
    transcription_before = transcription
    transcription = re.sub(r'ident', '', transcription, flags=re.IGNORECASE)
    log_transcription_change("Removed 'ident' markers", transcription_before, transcription)

    # # Apply custom word-to-letter mapping
    # for word_pattern, letter in nato_to_letter.items():
    #     pattern = re.compile(word_pattern, flags=re.IGNORECASE)
    #     matches = pattern.findall(transcription)
    #     if matches:
    #         transcription_before = transcription
    #         transcription = pattern.sub(letter, transcription)
    #         log_transcription_change(f"Applied NATO mapping '{word_pattern}' -> '{letter}'", transcription_before, transcription)

    # Find patterns like "word + digits" (e.g., "Singapore 638")
    pattern_matches = re.findall(r'\b([A-Z][a-z]*)\s(\d{1,5})\b', transcription)
    for match in pattern_matches:
        word, digits = match
        pattern = f"{word} {digits}"

        # Check against existing patterns in the history
        if pattern_history:
            closest_match, similarity = process.extractOne(pattern, pattern_history.keys(), scorer=fuzz.ratio)
            if similarity >= min_similarity_threshold:
                # If the pattern is similar to an existing pattern, use the most frequent correct format
                correct_format = pattern_history[closest_match]['correct_format']
                transcription_before = transcription
                transcription = re.sub(rf'\b{word} \d{{1,5}}\b', correct_format, transcription, flags=re.IGNORECASE)
                log_transcription_change(f"Replaced '{word} {digits}' with '{correct_format}' based on pattern history", transcription_before, transcription)
            else:
                # If no close match is found, store the new pattern
                pattern_history[pattern]['count'] += 1
                pattern_history[pattern]['correct_format'] = pattern
        else:
            # If no history exists, add the current pattern
            pattern_history[pattern]['count'] += 1
            pattern_history[pattern]['correct_format'] = pattern

    # Specific transformations
    transformations = [
        (r'\b(\d+)\s+left\b', r'\1L', "Transformed 'left' to 'L'"),
        (r'\b(\d+)\s+right\b', r'\1R', "Transformed 'right' to 'R'"),
        (r'\b(\d+)\s+centre\b', r'\1C', "Transformed 'centre' to 'C'"),
        (r'\b(\d+)\s+center\b', r'\1C', "Transformed 'center' to 'C'"),
        (r'(\d+)\s*(?:decimal|point)\s*(\d+)', r'\1.\2', "Transformed 'decimal' or 'point' to '.'"),
        # Add other transformations as needed
    ]

    for pattern, replacement, description in transformations:
        transcription_before = transcription
        transcription = re.sub(pattern, replacement, transcription, flags=re.IGNORECASE)
        log_transcription_change(description, transcription_before, transcription)

    # Manually break off frequencies after the first decimal point
    transcription_before = transcription
    transcription = fix_decimal_followups(transcription)
    # fix_decimal_followups logs changes internally

    # Combine adjacent digits that should form a single number
    patterns = [
        (r'\b(\d)\s+(\d)\s+(\d)\b', r'\1\2\3', "Combined three adjacent digits"),
        (r'\b(\d)\s+(\d)\b', r'\1\2', "Combined two adjacent digits"),
        (r'\b(\d)\s+(\d)([A-Z])\b', r'\1\2\3', "Combined digits and letter for runway designations"),
    ]

    for pattern, replacement, description in patterns:
        transcription_before = transcription
        transcription = re.sub(pattern, replacement, transcription, flags=re.IGNORECASE)
        log_transcription_change(description, transcription_before, transcription)

    # Removing whisper artifacts
    artifacts = [
        (r'thanks for watching', '', "Removed 'thanks for watching'"),
        (r'for watching', '', "Removed 'for watching'"),
    ]

    for pattern, replacement, description in artifacts:
        transcription_before = transcription
        transcription = re.sub(pattern, replacement, transcription, flags=re.IGNORECASE)
        log_transcription_change(description, transcription_before, transcription)

    # Change 'feet' to 'ft', 'knots' to 'kts'
    units = [
        (r'(\d+)\s+feet\b', r'\1ft', "Changed 'feet' to 'ft'"),
        (r'(\d+)\s+knots\b', r'\1kts', "Changed 'knots' to 'kts'"),
    ]

    for pattern, replacement, description in units:
        transcription_before = transcription
        transcription = re.sub(pattern, replacement, transcription, flags=re.IGNORECASE)
        log_transcription_change(description, transcription_before, transcription)

    # Combine numbers with 'ft' and 'kts'
    combinations = [
        (r'(\d{1,2})\s+(\d{2,3})\s*ft\b', r'\1\2ft', "Combined numbers with 'ft'"),
        (r'(\d{1,2})\s+(\d{2,3})\s*kts\b', r'\1\2kts', "Combined numbers with 'kts'"),
        (r'(\d{1,2})\s+(00|000)\b', r'\1\2', "Combined numbers with '00' or '000'"),
    ]

    for pattern, replacement, description in combinations:
        transcription_before = transcription
        transcription = re.sub(pattern, replacement, transcription, flags=re.IGNORECASE)
        log_transcription_change(description, transcription_before, transcription)

    # Handle squawk code recognition
    transcription_before = transcription
    transcription = re.sub(r'\bsquawk\s+(\d)\s*(\d)\s*(\d)\s*(\d)\b', r'squawk \1\2\3\4', transcription,
                           flags=re.IGNORECASE)
    log_transcription_change("Formatted squawk code", transcription_before, transcription)

    # Handle Flight Level
    transcription_before = transcription
    transcription = re.sub(r'\bflight level\s*(\d{3})(?=\s|$)', r'FL\1', transcription, flags=re.IGNORECASE)
    log_transcription_change("Formatted 'flight level'", transcription_before, transcription)

    # Ensure proper spacing between FLxxx and following digits
    transcription_before = transcription
    transcription = re.sub(r'(FL\d{3})(?=\d)', r'\1 ', transcription, flags=re.IGNORECASE)
    log_transcription_change("Ensured spacing after 'FLxxx'", transcription_before, transcription)

    # Capitalize NATO words
    transcription_before = transcription
    nato_pattern = r'\b(' + '|'.join(nato) + r')\b'
    transcription = re.sub(nato_pattern, lambda match: match.group(0).capitalize(), transcription, flags=re.IGNORECASE)
    log_transcription_change("Capitalized NATO words", transcription_before, transcription)

    # Capitalize first word
    transcription_before = transcription
    transcription = re.sub(r'^\w+', lambda match: match.group(0).capitalize(), transcription)
    log_transcription_change("Capitalized first word", transcription_before, transcription)

    # Ensure 3-digit callsigns
    transcription_before = transcription
    transcription = re.sub(r'\b(\d)\s*(\d)\s*(\d)\b', r'\1\2\3', transcription, flags=re.IGNORECASE)
    log_transcription_change("Ensured 3-digit callsigns", transcription_before, transcription)

    # Ensure 4-digit callsigns
    transcription_before = transcription
    transcription = re.sub(r'\b(\d)\s*(\d)\s*(\d)\s*(\d)\b', r'\1\2\3\4', transcription, flags=re.IGNORECASE)
    log_transcription_change("Ensured 4-digit callsigns", transcription_before, transcription)

    # Check for repeated words or numbers
    repeated_pattern = r'\b(\w+)(\s+\1){3,}\b'
    if (re.search(repeated_pattern, transcription) or transcription in ['You', 'Bye', '.', 'Bye bye', 'Thank you', 'Thank you.', 'Thank you very much..','Thank you very much.','Thank you so much', 'Thank you so much.'] or len(transcription.split()) == 1):
        logging.info(f"Transcription '{transcription}' identified as 'false activation'")
        transcription = "false activation"

    logging.info(f"Final transcription: '{transcription}'")
    return transcription
