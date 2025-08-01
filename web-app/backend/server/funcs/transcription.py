import pandas as pd
import re
import logging
from fuzzywuzzy import fuzz, process
from collections import defaultdict
import difflib
from .lists import nato  # Removed number_mapping import

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

# Define ANSI escape codes for colors
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"

# History trackers
transcription_history = defaultdict(int)
pattern_history = defaultdict(lambda: {'count': 0, 'correct_format': ''})

# ============================
# Number Parsing Utilities
# ============================
units = {
	'zero': 0, 'oh': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
	'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'niner': 9
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
	number_words_pattern = r'\b(?:' + '|'.join(number_words) + r')\b(?:\s+\b(?:' + '|'.join(number_words) + r')\b)*'
	pattern = re.compile(number_words_pattern, flags=re.IGNORECASE)

	def replace_match(match):
		text = match.group(0)
		number = parse_number(text)
		return str(number)

	transcription_before = transcription
	transcription = pattern.sub(replace_match, transcription)
	return transcription


def remove_and_between_number_words(transcription):
	number_word_pattern = r'\b(?:' + '|'.join(number_words) + r')\b'
	pattern = re.compile(rf'({number_word_pattern})\s+and\s+({number_word_pattern})', flags=re.IGNORECASE)
	transcription_before = transcription
	transcription = pattern.sub(r'\1 \2', transcription)
	return transcription


# ============================
# 1. Initial Cleanup
# ============================
def remove_whisper_artifacts(transcription):
	artifacts = [
		(r'\bthanks for watching\b[\.\!\?]?', '', "Removed 'thanks for watching'"),
		(r'\bfor watching\b[\.\!\?]?', '', "Removed 'for watching'"),
		# Ignore transcripts that are only 'so', 'so.', 'okay', or 'okay.' regardless of capitalization.
		(r'^(so|so\.|okay|okay\.)$', '', "Removed trivial artifact ('so', 'okay', etc.)")
	]
	for pattern, replacement, description in artifacts:
		transcription_before = transcription
		transcription = re.sub(pattern, replacement, transcription, flags=re.IGNORECASE)
	transcription = re.sub(r'\s*\.\s*$', '.', transcription)
	transcription = re.sub(r'\.\.', '.', transcription)
	transcription = transcription.strip()
	return transcription


# ============================
# 2. Standardize Units and Directions
# ============================
def standardize_units(transcription):
	transcription_before = transcription
	transcription = transcription.replace(' feet', 'ft')
	transcription = transcription.replace(' knots', 'kts')
	return transcription


def standardize_directions(transcription):
	transformations = [
		(r'\b(\d+)\s+left\b', r'\1L', "Transformed 'left' to 'L'"),
		(r'\b(\d+)\s+right\b', r'\1R', "Transformed 'right' to 'R'"),
		(r'\b(\d+)\s+centre\b', r'\1C', "Transformed 'centre' to 'C'"),
		(r'\b(\d+)\s+center\b', r'\1C', "Transformed 'center' to 'C'"),
	]
	for pattern, replacement, description in transformations:
		transcription_before = transcription
		transcription = re.sub(pattern, replacement, transcription, flags=re.IGNORECASE)
	transcription = re.sub(r'(\d+)\s+([LRC])\b', r'\1\2', transcription, flags=re.IGNORECASE)
	return transcription


# ============================
# 3. Specific Patterns and Mappings
# ============================
def capitalize_nato_and_first_word(transcription):
	nato_pattern = r'\b(' + '|'.join(nato) + r')\b'
	transcription_before = transcription
	transcription = re.sub(
		nato_pattern,
		lambda match: match.group(0).capitalize(),
		transcription,
		flags=re.IGNORECASE
	)
	return transcription


def replace_zulu_with_z(transcription):
	transcription_before = transcription
	transcription = re.sub(
		r'\b(\d+)\s*Zulu\b',
		r'\1Z',
		transcription,
		flags=re.IGNORECASE
	)
	return transcription


def handle_gocat(transcription):
	transcription_before = transcription
	transcription = re.sub(r'\bgocat\s*(\d+)\b', r'TGW\1', transcription, flags=re.IGNORECASE)
	transcription = re.sub(r'\bgocad\s*(\d+)\b', r'TGW\1', transcription, flags=re.IGNORECASE)

	return transcription


# ============================
# 4. Number Handling and Formatting
# ============================
def combine_adjacent_digits_for_callsigns(transcription):
	digit_patterns = [
		(r'\b(\d)\s+(\d)\s+(\d)\s+(\d)\b', r'\1\2\3\4', "Combined four adjacent digits"),
		(r'\b(\d)\s+(\d)\s+(\d)(?=\s|$|[A-Za-z])', r'\1\2\3', "Combined three adjacent digits"),
	]
	for pattern, replacement, description in digit_patterns:
		transcription_before = transcription
		transcription = re.sub(pattern, replacement, transcription, flags=re.IGNORECASE)
	return transcription


def combine_letter_and_number(transcription):
	transcription_before = transcription
	transcription = re.sub(r'\b([A-Z])\s+(\d+)\b', r'\1\2', transcription, flags=re.IGNORECASE)
	return transcription


def handle_flight_levels(transcription):
	transcription_before = transcription
	transcription = re.sub(
		r'\bflight level\s*(\d{3})(?=\s|\.|,|$)',
		r'FL\1',
		transcription,
		flags=re.IGNORECASE
	)
	transcription_before = transcription
	transcription = re.sub(
		r'(FL\d{3})(?=\d)',
		r'\1 ',
		transcription,
		flags=re.IGNORECASE
	)
	return transcription


def handle_squawk_codes(transcription):
	transcription_before = transcription
	transcription = re.sub(
		r'\bsquawk\s+(\d)\s*(\d)\s*(\d)\s*(\d)\b',
		r'squawk \1\2\3\4',
		transcription,
		flags=re.IGNORECASE
	)
	return transcription


def combine_numbers_with_units(transcription):
	combinations = [
		(r'(\d{1,2})\s+(\d{2,3})\s*ft\b', r'\1\2ft', "Combined numbers with 'ft'"),
		(r'(\d{1,2})\s+(\d{2,3})\s*kts\b', r'\1\2kts', "Combined numbers with 'kts'"),
		(r'(\d{1,2})\s+(00|000)\b', r'\1\2', "Combined numbers with '00' or '000'"),
	]
	for pattern, replacement, description in combinations:
		transcription_before = transcription
		transcription = re.sub(pattern, replacement, transcription, flags=re.IGNORECASE)
	return transcription


def replace_point_or_decimal(transcription):
	transcription_before = transcription
	transcription = re.sub(r'\s*(point|decimal)\s*', '.', transcription, flags=re.IGNORECASE)
	return transcription


def handle_decimal_followups(transcription):
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
	return transcription


# ============================
# 5. General Number and Pattern Handling
# ============================
def combine_remaining_adjacent_digits(transcription):
	patterns = [
		(r'\b(\d)\s+(\d+)\b', r'\1\2', "Combined single digit with multi-digit number"),
		(r'\b(\d)\s+(\d)([A-Z])\b', r'\1\2\3', "Combined digits and letter for runway designations"),
	]
	for pattern, replacement, description in patterns:
		transcription_before = transcription
		transcription = re.sub(pattern, replacement, transcription, flags=re.IGNORECASE)
	return transcription


# ============================
# 6. Final Cleanup and Validation
# ============================
def validate_transcription(transcription):
	repeated_pattern = r'\b(\w+)(\s+\1){3,}\b'
	if (re.search(repeated_pattern, transcription) or
			transcription.lower() in [
				'you', 'bye', '.', 'bye bye', 'thank you',
				'thank you.', 'thank you very much', 'thank you very much..',
				'thank you very much.', 'thank you so much', 'thank you so much.',
				'so', 'so.', 'okay', 'okay.'
			] or
			(len(transcription.split()) == 1 and 'FL' not in transcription)):
		return "false activation"
	return transcription


def handle_icao_callsign(transcription):
	parquet_file = './server/funcs/aircraft_callsign.parquet'
	df = pd.read_parquet(parquet_file)

	def replace_callsign_with_icao(text: str, df: pd.DataFrame) -> str:
		callsign_to_icao = dict(zip(df['Callsign'], df['ICAO']))
		for callsign, icao in callsign_to_icao.items():
			pattern = r'\b' + re.escape(callsign) + r'\b\s*(\d+)'
			replacement = icao + r'\1'
			text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
		return text

	transcription = replace_callsign_with_icao(transcription, df)
	return transcription


def capitalize_first_word(transcription):
	transcription_before = transcription
	if transcription:
		transcription = transcription[0].upper() + transcription[1:]
	return transcription


def validate_atc_transcription(transcription):
	misheard_words = {
		"soles": "souls",
		"rodger": "roger",
		"Everett": "Emirates",
		"tree": "three",
	}
	words = transcription.split()
	corrected_words = []
	for word in words:
		corrected_words.append(misheard_words.get(word, word))
	transcription = ' '.join(corrected_words)
	return transcription


# ============================
# Main Transformation Function
# ============================
def apply_custom_fixes(transcription):
	logging.info(f"Original transcription: {YELLOW}'{transcription}'{RESET}")

	# 1. Initial Cleanup
	transcription = remove_whisper_artifacts(transcription)
	transcription = replace_point_or_decimal(transcription)
	transcription = remove_and_between_number_words(transcription)
	transcription = replace_number_words(transcription)
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
	transcription = handle_gocat(transcription)

	# 2. Standardize Units and Directions
	transcription = standardize_units(transcription)
	transcription = standardize_directions(transcription)
	transcription = replace_zulu_with_z(transcription)

	# 6. Final Cleanup and Validation
	transcription = validate_transcription(transcription)
	transcription = capitalize_first_word(transcription)
	transcription = validate_atc_transcription(transcription)
	# 7. Handle Aircraft Callsign
	transcription = handle_icao_callsign(transcription)
	logging.info(f"Final transcription: {GREEN}'{transcription}'{RESET}")
	return transcription


# ============================================
# New Functions to Update Timestamped Transcripts
# ============================================
def update_words_with_final_transcript(original_words, final_transcript):
	"""
	Update the "words" list (each with its own timestamps) so that their 'text' values match
	the final transcript produced by apply_custom_fixes. This function uses difflib to
	align the original tokens (from the words list) with the final tokens.
	"""
	orig_tokens = [w['text'] for w in original_words]
	final_tokens = final_transcript.split()

	# If token counts match, update each word directly.
	if len(orig_tokens) == len(final_tokens):
		for i in range(len(original_words)):
			original_words[i]['text'] = final_tokens[i]
		return original_words

	new_words = []
	matcher = difflib.SequenceMatcher(None, orig_tokens, final_tokens)
	for tag, i1, i2, j1, j2 in matcher.get_opcodes():
		if tag == 'equal':
			for orig_idx, final_idx in zip(range(i1, i2), range(j1, j2)):
				new_word = original_words[orig_idx].copy()
				new_word['text'] = final_tokens[final_idx]
				new_words.append(new_word)
		elif tag == 'replace':
			# Merge the original tokens from i1 to i2 to form a block.
			if i1 < len(original_words):
				start_time = original_words[i1]['start']
			else:
				start_time = 0
			if i2 - 1 < len(original_words):
				end_time = original_words[i2 - 1]['end']
			else:
				end_time = start_time
			block_duration = end_time - start_time
			num_new = j2 - j1
			# Distribute the time interval among the new tokens.
			for k, final_token in enumerate(final_tokens[j1:j2]):
				token_start = start_time + (block_duration * k / num_new)
				token_end = start_time + (block_duration * (k + 1) / num_new)
				new_word = {
					'text': final_token,
					'start': token_start,
					'end': token_end,
					'duration': token_end - token_start
				}
				new_words.append(new_word)
		elif tag == 'insert':
			# For inserted tokens, assign a timestamp equal to the end time of the previous token.
			prev_end = new_words[-1]['end'] if new_words else (original_words[0]['start'] if original_words else 0)
			for final_token in final_tokens[j1:j2]:
				new_word = {
					'text': final_token,
					'start': prev_end,
					'end': prev_end,
					'duration': 0
				}
				new_words.append(new_word)
		elif tag == 'delete':
			# Skip deleted tokens.
			continue
	return new_words


def process_transcript_data(data):
	"""
	Given a transcript data dictionary (with keys like "text" and "words"), this function:
	  1. Extracts the transcript from data["text"]
	  2. Applies the custom fixes to it via apply_custom_fixes()
	  3. Replaces the old transcript with the new one in data["text"]
	  4. Updates the "words" list so that each word's "text" reflects the modifications,
		 while keeping the original timestamps unchanged (or merged appropriately).

	Also checks if the transcript is empty (or just whitespace). In that case, returns "false activation".
	"""
	original_transcript = data.get("text", "").strip()

	# Check if text is empty; if so, return false activation
	if not original_transcript:
		final_transcript = "false activation"
		data["text"] = final_transcript
		if "words" in data:
			data["words"] = update_words_with_final_transcript(data["words"], final_transcript)
		return data

	final_transcript = apply_custom_fixes(original_transcript)
	data["text"] = final_transcript
	if "words" in data:
		data["words"] = update_words_with_final_transcript(data["words"], final_transcript)
	return data