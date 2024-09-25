# transcription.py
import pandas as pd
import re
import logging
from fuzzywuzzy import fuzz, process
from collections import defaultdict
from .lists import nato  # Removed number_mapping import

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

# History trackers
transcription_history = defaultdict(int)
pattern_history = defaultdict(lambda: {'count': 0, 'correct_format': ''})


# Function to log changes
def log_transcription_change(description, old_transcription, new_transcription):
	if old_transcription != new_transcription:
		logging.info(f"{description}: '{old_transcription}' -> '{new_transcription}'")


# ============================
# Number Parsing Utilities
# ============================

units = {
	'zero': 0, 'oh': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
	'six': 6, 'seven': 7, 'eight': 8, 'nine': 9
}
teens = {
	'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14,
	'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19
}
tens = {
	'twenty': 20, 'thirty': 30, 'forty': 40, 'fourty': 40, 'fifty': 50,
	'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90
}
scales = {'hundred': 100, 'thousand': 1000}
number_words = set(units.keys()) | set(teens.keys()) | set(tens.keys()) | set(scales.keys())


def parse_number(text):
	words = text.lower().split()
	has_scales = any(word in scales for word in words)

	if has_scales:
		total = 0
		number_str = ''
		i = 0
		while i < len(words):
			word = words[i]
			if word == 'and':
				i += 1  # Skip 'and'
			elif word in units:
				number_str += str(units[word])
				i += 1
			elif word in teens:
				number_str += str(teens[word])
				i += 1
			elif word in tens:
				if i + 1 < len(words) and words[i + 1] in units:
					number = tens[word] + units[words[i + 1]]
					number_str += str(number)
					i += 2
				else:
					number_str += str(tens[word])
					i += 1
			elif word in scales:
				scale = scales[word]
				if number_str == '':
					current = 1
				else:
					current = int(number_str)
				current *= scale
				total += current
				number_str = ''
				i += 1
			else:
				i += 1
		if number_str != '':
			total += int(number_str)
		return str(total)
	else:
		number_str = ''
		i = 0
		while i < len(words):
			word = words[i]
			if word in units:
				number_str += str(units[word])
				i += 1
			elif word in teens:
				number_str += str(teens[word])
				i += 1
			elif word in tens:
				if i + 1 < len(words) and words[i + 1] in units:
					number = tens[word] + units[words[i + 1]]
					number_str += str(number)
					i += 2
				else:
					number_str += str(tens[word])
					i += 1
			else:
				i += 1
		if number_str.lstrip('0') == '':
			return '0'
		else:
			return number_str


def replace_number_words(transcription):
	logging.info("Replacing number words with digits...")
	number_words_pattern = r'\b(?:' + '|'.join(number_words) + r')\b(?:\s+\b(?:' + '|'.join(number_words) + r')\b)*'
	pattern = re.compile(number_words_pattern, flags=re.IGNORECASE)

	def replace_match(match):
		text = match.group(0)
		number = parse_number(text)
		return str(number)

	transcription_before = transcription
	transcription = pattern.sub(replace_match, transcription)
	# log_transcription_change("Replaced number words with digits", transcription_before, transcription)
	return transcription


def remove_and_between_number_words(transcription):
	logging.info("Removing 'and' between number words...")
	number_word_pattern = r'\b(?:' + '|'.join(number_words) + r')\b'
	pattern = re.compile(rf'({number_word_pattern})\s+and\s+({number_word_pattern})', flags=re.IGNORECASE)
	transcription_before = transcription
	transcription = pattern.sub(r'\1 \2', transcription)
	# log_transcription_change("Removed 'and' between number words", transcription_before, transcription)
	return transcription


# ============================
# 1. Initial Cleanup
# ============================

def remove_whisper_artifacts(transcription):
	logging.info("Removing whisper artifacts...")
	artifacts = [
		(r'\bthanks for watching\b[\.\!\?]?', '', "Removed 'thanks for watching'"),
		(r'\bfor watching\b[\.\!\?]?', '', "Removed 'for watching'"),
	]
	for pattern, replacement, description in artifacts:
		transcription_before = transcription
		transcription = re.sub(pattern, replacement, transcription, flags=re.IGNORECASE)
	# log_transcription_change(description, transcription_before, transcription)

	transcription = re.sub(r'\s*\.\s*$', '.', transcription)
	transcription = re.sub(r'\.\.', '.', transcription)
	transcription = transcription.strip()

	return transcription


# ============================
# 2. Standardize Units and Directions
# ============================

def standardize_units(transcription):
	logging.info("Standardizing units...")

	# Replace ' feet' with 'ft'
	transcription_before = transcription
	transcription = transcription.replace(' feet', 'ft')
	# log_transcription_change("Changed 'feet' to 'ft'", transcription_before, transcription)

	# Replace ' knots' with 'kts'
	transcription_before = transcription
	transcription = transcription.replace(' knots', 'kts')
	# log_transcription_change("Changed 'knots' to 'kts'", transcription_before, transcription)

	return transcription


def standardize_directions(transcription):
	logging.info("Standardizing directional terms...")
	transformations = [
		(r'\b(\d+)\s+left\b', r'\1L', "Transformed 'left' to 'L'"),
		(r'\b(\d+)\s+right\b', r'\1R', "Transformed 'right' to 'R'"),
		(r'\b(\d+)\s+centre\b', r'\1C', "Transformed 'centre' to 'C'"),
		(r'\b(\d+)\s+center\b', r'\1C', "Transformed 'center' to 'C'"),
	]
	for pattern, replacement, description in transformations:
		transcription_before = transcription
		transcription = re.sub(pattern, replacement, transcription, flags=re.IGNORECASE)
	# log_transcription_change(description, transcription_before, transcription)

	transcription = re.sub(r'(\d+)\s+([LRC])\b', r'\1\2', transcription, flags=re.IGNORECASE)
	return transcription


# ============================
# 3. Specific Patterns and Mappings
# ============================

def capitalize_nato_and_first_word(transcription):
	logging.info("Capitalizing NATO words and the first word...")
	nato_pattern = r'\b(' + '|'.join(nato) + r')\b'
	transcription_before = transcription
	transcription = re.sub(
		nato_pattern,
		lambda match: match.group(0).capitalize(),
		transcription,
		flags=re.IGNORECASE
	)
	# log_transcription_change("Capitalized NATO words", transcription_before, transcription)
	return transcription


def replace_zulu_with_z(transcription):
	logging.info("Replacing 'Zulu' with 'Z' and concatenating...")
	transcription_before = transcription
	transcription = re.sub(
		r'\b(\d+)\s*Zulu\b',
		r'\1Z',
		transcription,
		flags=re.IGNORECASE
	)
	# log_transcription_change("Replaced 'Zulu' with 'Z' and concatenated", transcription_before, transcription)
	return transcription


# ============================
# 4. Number Handling and Formatting
# ============================

def combine_adjacent_digits_for_callsigns(transcription):
	logging.info("Combining adjacent digits for callsigns...")
	digit_patterns = [
		(r'\b(\d)\s+(\d)\s+(\d)\s+(\d)\b', r'\1\2\3\4', "Combined four adjacent digits"),
		(r'\b(\d)\s+(\d)\s+(\d)(?=\s|$|[A-Za-z])', r'\1\2\3', "Combined three adjacent digits"),
	]
	for pattern, replacement, description in digit_patterns:
		transcription_before = transcription
		transcription = re.sub(pattern, replacement, transcription, flags=re.IGNORECASE)
	# log_transcription_change(description, transcription_before, transcription)
	return transcription


def combine_letter_and_number(transcription):
	logging.info("Combining letter and number patterns...")
	transcription_before = transcription
	transcription = re.sub(r'\b([A-Z])\s+(\d+)\b', r'\1\2', transcription, flags=re.IGNORECASE)
	# log_transcription_change("Combined letter and number patterns", transcription_before, transcription)
	return transcription


def handle_flight_levels(transcription):
	logging.info("Handling flight levels...")
	transcription_before = transcription
	transcription = re.sub(
		r'\bflight level\s*(\d{3})(?=\s|\.|,|$)',
		r'FL\1',
		transcription,
		flags=re.IGNORECASE
	)
	# log_transcription_change("Formatted 'flight level'", transcription_before, transcription)

	transcription_before = transcription
	transcription = re.sub(
		r'(FL\d{3})(?=\d)',
		r'\1 ',
		transcription,
		flags=re.IGNORECASE
	)
	# log_transcription_change("Ensured spacing after 'FLxxx'", transcription_before, transcription)
	return transcription


def handle_squawk_codes(transcription):
	logging.info("Handling squawk codes...")
	transcription_before = transcription
	transcription = re.sub(
		r'\bsquawk\s+(\d)\s*(\d)\s*(\d)\s*(\d)\b',
		r'squawk \1\2\3\4',
		transcription,
		flags=re.IGNORECASE
	)
	# log_transcription_change("Formatted squawk code", transcription_before, transcription)
	return transcription


def combine_numbers_with_units(transcription):
	logging.info("Combining numbers with units...")
	combinations = [
		(r'(\d{1,2})\s+(\d{2,3})\s*ft\b', r'\1\2ft', "Combined numbers with 'ft'"),
		(r'(\d{1,2})\s+(\d{2,3})\s*kts\b', r'\1\2kts', "Combined numbers with 'kts'"),
		(r'(\d{1,2})\s+(00|000)\b', r'\1\2', "Combined numbers with '00' or '000'"),
	]
	for pattern, replacement, description in combinations:
		transcription_before = transcription
		transcription = re.sub(pattern, replacement, transcription, flags=re.IGNORECASE)
	# log_transcription_change(description, transcription_before, transcription)
	return transcription


def replace_point_or_decimal(transcription):
	logging.info("Replacing 'point' or 'decimal' with '.' ...")
	transcription_before = transcription
	transcription = re.sub(r'\s*(point|decimal)\s*', '.', transcription, flags=re.IGNORECASE)
	# log_transcription_change("Replaced 'point' or 'decimal' with '.'", transcription_before, transcription)
	return transcription


def handle_decimal_followups(transcription):
	logging.info("Fixing decimal follow-ups...")
	transcription_before = transcription
	pattern = r'(\d+\.\d{1,2})\s*(\d+)'
	matches = re.findall(pattern, transcription)

	for match in matches:
		full_number, follow_up = match
		decimal_part = full_number.split('.')[1]
		if len(decimal_part) == 1:
			continue
		elif len(decimal_part) == 2:
			if follow_up.startswith(decimal_part):
				transcription = transcription.replace(
					f'{full_number} {follow_up}',
					f'{full_number}{follow_up[2:]}'
				)
			else:
				transcription = transcription.replace(
					f'{full_number} {follow_up}',
					f'{full_number[:4]} {full_number[4:]}'
				)
	# log_transcription_change("After fix_decimal_followups", transcription_before, transcription)
	return transcription


# ============================
# 5. General Number and Pattern Handling
# ============================


def combine_remaining_adjacent_digits(transcription):
	logging.info("Combining remaining adjacent digits...")
	patterns = [
		(r'\b(\d)\s+(\d+)\b', r'\1\2', "Combined single digit with multi-digit number"),
		(r'\b(\d)\s+(\d)([A-Z])\b', r'\1\2\3', "Combined digits and letter for runway designations"),
	]
	for pattern, replacement, description in patterns:
		transcription_before = transcription
		transcription = re.sub(pattern, replacement, transcription, flags=re.IGNORECASE)
	# log_transcription_change(description, transcription_before, transcription)
	return transcription


# ============================
# 6. Final Cleanup and Validation
# ============================

def validate_transcription(transcription):
	logging.info("Validating transcription for false activations...")
	repeated_pattern = r'\b(\w+)(\s+\1){3,}\b'
	if (re.search(repeated_pattern, transcription) or
			transcription.lower() in [
				'you', 'bye', '.', 'bye bye', 'thank you',
				'thank you.', 'thank you very much', 'thank you very much..',
				'thank you very much.', 'thank you so much',
				'thank you so much.'
			] or
			(len(transcription.split()) == 1 and 'FL' not in transcription)):
		logging.info(f"Transcription '{transcription}' identified as 'false activation'")
		return "false activation"
	return transcription


def handle_icao_callsign(transcription):
	parquet_file = './aircraft_callsign.parquet'
	df = pd.read_parquet(parquet_file)

	def replace_callsign_with_icao(text: str, df: pd.DataFrame) -> str:
		# Create a dictionary mapping callsigns to ICAO codes
		callsign_to_icao = dict(zip(df['Callsign'], df['ICAO']))

		# Replace callsigns with ICAO codes in the text
		for callsign, icao in callsign_to_icao.items():
			# Use regex to replace callsign followed by a space and a number with ICAO followed by the number
			pattern = r'\b' + re.escape(callsign) + r'\b\s*(\d+)'
			replacement = icao + r'\1'
			text = re.sub(pattern, replacement, text)

		return text

	transcription = replace_callsign_with_icao(transcription, df)

	return transcription

def capitalize_first_word(transcription):
	transcription_before = transcription
	if transcription:
		transcription = transcription[0].upper() + transcription[1:]
	# log_transcription_change("Capitalized first word", transcription_before, transcription)
	return transcription


# ============================
# Main Transformation Function
# ============================

def apply_custom_fixes(transcription):
	logging.info(f"Original transcription: '{transcription}'")

	# 1. Initial Cleanup
	transcription = remove_whisper_artifacts(transcription)
	transcription = replace_point_or_decimal(transcription)
	# Remove 'and' between number words
	transcription = remove_and_between_number_words(transcription)
	transcription = replace_number_words(transcription)  # Updated function
	transcription = handle_decimal_followups(transcription)
	transcription = combine_remaining_adjacent_digits(transcription)

	# 3. Specific Patterns
	transcription = capitalize_nato_and_first_word(transcription)

	# 4. Number Handling
	transcription = combine_adjacent_digits_for_callsigns(transcription)
	transcription = combine_letter_and_number(transcription)
	transcription = combine_numbers_with_units(transcription)

	# 5. General Number and Pattern Handling
	transcription = handle_flight_levels(transcription)
	transcription = handle_squawk_codes(transcription)

	# 2. Standardize Units and Directions
	transcription = standardize_units(transcription)
	transcription = standardize_directions(transcription)
	transcription = replace_zulu_with_z(transcription)

	# 6. Final Cleanup and Validation
	transcription = validate_transcription(transcription)
	transcription = capitalize_first_word(transcription)

	# 7. Handle Aircraft Callsign
	transcription = handle_icao_callsign(transcription)
	logging.info(f"Final transcription: '{transcription}'")
	return transcription
