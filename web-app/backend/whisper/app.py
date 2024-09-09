import os

from flask import Flask, request, jsonify
import torch
import soundfile as sf
import librosa
import numpy as np
import re
from collections import defaultdict
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import io
from flask_cors import CORS
from scipy.signal import resample_poly
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq

# Initialize the Flask application
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Load model and processor
model_name_or_path = 'local_model_medium'
processor = AutoProcessor.from_pretrained(model_name_or_path)
model = AutoModelForSpeechSeq2Seq.from_pretrained(model_name_or_path)
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print('Running on', device)
model.to(device)
model.eval()
# Predefined lists and mappings
general = ['Air Traffic Control communications', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '90', '180', '270',
           '360']
nato = [
	'Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf',
	'Hotel', 'India', 'Juliett', 'Kilo', 'Lima', 'Mike', 'November',
	'Oscar', 'Papa', 'Quebec', 'Romeo', 'Sierra', 'Tango', 'Uniform',
	'Victor', 'Whiskey', 'Xray', 'Yankee', 'Zulu'
]
atc_words = [
	"acknowledge", "affirmative", "affirm", "altitude", "approach", "apron", "arrival",
	"bandbox", "base", "bearing", "cleared", "climb", "contact", "control",
	"crosswind", "cruise", "descend", "departure", "direct", "disregard",
	"downwind", "estimate", "final", "flight", "frequency", "go around",
	"heading", "hold", "identified", "immediate", "information", "instruct",
	"intentions", "land", "level", "maintain", "mayday", "message", "missed",
	"navigation", "negative", "obstruction", "option", "orbit", "pan-pan",
	"pattern", "position", "proceed", "radar", "readback", "received",
	"report", "request", "required", "runway", "squawk", "standby", "takeoff",
	"taxi", "threshold", "traffic", "transit", "turn", "vector", "visual",
	"waypoint", "weather", "wilco", "wind", "with you", "speed",
	"heavy", "light", "medium", "emergency", "fuel", "identifier",
	"limit", "monitor", "notice", "operation", "permission", "relief",
	"route", "signal", "stand", "system", "terminal", "test", "track",
	"understand", "verify", "vertical", "warning", "zone", "no", "yes", "unable",
	"clearance", "conflict", "coordination", "cumulonimbus", "deviation", "enroute",
	"fix", "glideslope", "handoff", "holding", "IFR", "jetstream", "knots",
	"localizer", "METAR", "NOTAM", "overfly", "pilot", "QNH", "radial",
	"sector", "SID", "STAR", "tailwind", "transition", "turbulence", "uncontrolled",
	"VFR", "wake turbulence", "X-wind", "yaw", "Zulu time", "airspace",
	"briefing", "checkpoint", "elevation", "FL",
	"ground control", "hazard", "ILS", "jetway", "kilo", "logbook", "missed approach",
	"nautical mile", "offset", "profile", "quadrant", "RVR",
	"static", "touchdown", "upwind", "variable", "wingtip", "Yankee", "zoom climb",
	"airspeed", "backtrack", "ETOPS", "gate", "holding pattern",
	"jumpseat", "minimums", "pushback", "RNAV", "slot time", "taxiway", "TCAS",
	"wind shear", "zero fuel weight", "ETA",
	"flight deck", "ground proximity warning system", "jet route",
	"landing clearance", "Mach number", "NDB", "obstacle clearance",
	"PAPI", "QFE", "radar contact",
	'ATC', 'pilot', 'call sign', 'altitude', 'heading', 'speed', 'climb to', 'descend to',
	'maintain', 'tower', 'ground', 'runway', 'taxi', 'takeoff', 'landing',
	'flight level', 'traffic', 'hold short', 'cleared for',
	'roger', 'visibility', 'weather', 'wind', 'gusts',
	'icing conditions', 'deicing', 'VFR', 'IFR', 'no-fly zone',
	'restricted airspace', 'flight path', 'direct route', 'vector', 'frequency change',
	'final approach', 'initial climb to', 'contact approach', 'FIR', 'control zone', 'TMA',
	'missed approach', 'minimum safe altitude', 'transponder',
	'reduce speed to', 'increase speed to',
	'flight conditions', 'clear of conflict', 'resume own navigation', 'request altitude change',
	'request route change', 'flight visibility', 'ceiling', 'severe weather', 'convective SIGMET',
	'AIRMET', 'QNH', 'QFE', 'transition altitude', 'transition level',
	'NOSIG', 'TFR', 'special use airspace',
	'MOA', 'IAP', 'visual approach',
	'NDB', 'VOR',
	'ATIS', 'engine start clearance',
	'line up and wait', 'UNICOM', 'cross runway', 'departure frequency',
	'arrival frequency', 'go-ahead', 'hold position', 'check gear down',
	'touch and go', 'circuit pattern', 'climb via SID',
	'descend via STAR', 'speed restriction', 'flight following', 'radar service terminated', 'squawk VFR',
	'change to advisory frequency', 'report passing altitude', 'report position',
	'ATD', 'block altitude', 'cruise climb', 'direct to', 'execute missed approach',
	'in-flight refueling', 'joining instructions', 'lost communications', 'MEA', 'next waypoint', 'OCH',
	'procedure turn', 'radar vectoring', 'radio failure', 'short final', 'standard rate turn',
	'TRSA', 'undershoot', 'VMC',
	'wide-body aircraft', 'yaw damper', 'zulu time conversion', 'RNAV',
	'RNP', 'barometric pressure', 'control tower handover', 'datalink communication',
	'ELT', 'FDR', 'GCI',
	'hydraulic failure', 'IMC', 'knock-it-off',
	'LVO', 'MAP', 'NAVAIDS',
	'oxygen mask deployment', 'PAR', 'QRA',
	'runway incursion', 'SAR', 'tail strike', 'upwind leg', 'vertical speed',
	'wake turbulence category', 'X-ray cockpit security', 'yield to incoming aircraft', 'zero visibility takeoff',
	'good day', 'no delay', 'fault'
]

collated_list = general + nato + atc_words
collated_list_string = ' '.join(collated_list)

# Number mappings to handle numbers like twenty, thirty, etc.
number_mapping = {
	r'\bzero\b': '0',
	r'\bone\b': '1',
	r'\btwo\b': '2',
	r'\bthree\b': '3',
	r'\bfour\b': '4',
	r'\bfive\b': '5',
	r'\bsix\b': '6',
	r'\bseven\b': '7',
	r'\beight\b': '8',
	r'\bnine\b': '9',
	r'\bten\b': '10',
	r'\beleven\b': '11t',
	r'\btwelve\b': '12',
	r'\bthirteen\b': '13',
	r'\bfourteen\b': '14',
	r'\bfifteen\b': '15',
	r'\bsixteen\b': '16',
	r'\bseventeen\b': '17',
	r'\beighteen\b': '18',
	r'\bnineteen\b': '19',
	r'\btwenty\b': '20ident',
	r'\bthirty\b': '30ident',
	r'\bforty\b': '40ident',
	r'\bfifty\b': '50ident',
	r'\bsixty\b': '60ident',
	r'\bseventy\b': '70ident',
	r'\beighty\b': '80ident',
	r'\bninety\b': '90ident',
	r'\bhundred\b': '00',
	r'\bthousand\b': '000'
}

# Prepare prompt for the model (convert it to tokens)
if collated_list_string:
	prompt_ids = processor(text=collated_list_string, return_tensors="pt").input_ids.to(device)
else:
	prompt_ids = None

transcription_history = defaultdict(int)
pattern_history = defaultdict(lambda: {'count': 0, 'correct_format': ''})


# Loop through and handle 'ident' patterns by looking to the left and right
def handle_ident_numbers(transcription):
	pattern = r"0ident "
	new_transcription = re.sub(pattern, "", transcription)

	return new_transcription

# Define helper functions (apply_custom_fixes, etc.)
def fix_decimal_followups(transcription):
	"""
	Ensures proper handling of digits after a decimal point:
	- Assume 1 digit after the decimal point by default.
	- If 2 digits appear, check if the following sequence of numbers matches.
	"""
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

	return transcription


def apply_custom_fixes(transcription):
	# Track frequent patterns
	min_similarity_threshold = 90  # Adjust threshold as needed

	# Apply custom word-to-number mapping
	for word_pattern, number in number_mapping.items():
		transcription = re.sub(word_pattern, number, transcription, flags=re.IGNORECASE)
		
	# Handle 'ident' patterns with adjacent digits
	transcription = handle_ident_numbers(transcription)

	# Final cleanup: Remove any remaining 'ident' markers (just in case)
	transcription = re.sub(r'ident', '', transcription, flags=re.IGNORECASE)

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
				transcription = re.sub(rf'\b{word} \d{{1,5}}\b', correct_format, transcription, flags=re.IGNORECASE)
			else:
				# If no close match is found, store the new pattern
				pattern_history[pattern]['count'] += 1
				pattern_history[pattern]['correct_format'] = pattern
		else:
			# If no history exists, add the current pattern
			pattern_history[pattern]['count'] += 1
			pattern_history[pattern]['correct_format'] = pattern

	# Specific transformation: "placeholder left" to "placeholderL" and "placeholder right" to "placeholderR"
	transcription = re.sub(r'\b(\d+)\s+left\b', r'\1L', transcription, flags=re.IGNORECASE)
	transcription = re.sub(r'\b(\d+)\s+right\b', r'\1R', transcription, flags=re.IGNORECASE)
	transcription = re.sub(r'\b(\d+)\s+centre\b', r'\1C', transcription, flags=re.IGNORECASE)
	transcription = re.sub(r'\b(\d+)\s+center\b', r'\1C', transcription, flags=re.IGNORECASE)

	# Handle 'decimal' and 'point' to convert to numeric format with proper separation
	transcription = re.sub(r'(\d+)\s*(?:decimal|point)\s*(\d+)', r'\1.\2', transcription, flags=re.IGNORECASE)

	# Manually break off frequencies after the first decimal point
	transcription = fix_decimal_followups(transcription)

	# Combine adjacent digits that should form a single number
	transcription = re.sub(r'\b(\d)\s+(\d)\s+(\d)\b', r'\1\2\3', transcription, flags=re.IGNORECASE)
	transcription = re.sub(r'\b(\d)\s+(\d)\b', r'\1\2', transcription, flags=re.IGNORECASE)

	# Specific rule to handle runway designations like "1 6L" to "16L"
	transcription = re.sub(r'\b(\d)\s+(\d)([A-Z])\b', r'\1\2\3', transcription, flags=re.IGNORECASE)

	# removing whisper shit
	transcription = re.sub(r'thanks for watching', '', transcription, flags=re.IGNORECASE)
	transcription = re.sub(r'for watching', '', transcription, flags=re.IGNORECASE)

	# Change feet to ft
	transcription = re.sub(r'(\d+)\s+feet\b', r'\1ft', transcription, flags=re.IGNORECASE)

	# Change knots to kts
	transcription = re.sub(r'(\d+)\s+knots\b', r'\1kts', transcription, flags=re.IGNORECASE)

	# Combine numbers with ft (able to handle spaces in numbers)
	transcription = re.sub(r'(\d{1,2})\s+(\d{2,3})\s*ft\b', r'\1\2ft', transcription, flags=re.IGNORECASE)

	# Combine numbers with kts (able to handle spaces in numbers)
	transcription = re.sub(r'(\d{1,2})\s+(\d{2,3})\s*kts\b', r'\1\2kts', transcription, flags=re.IGNORECASE)

	# Combine numbers followed by "00" (hundred) or "000" (thousand) into a single number
	transcription = re.sub(r'(\d{1,2})\s+(00|000)\b', r'\1\2', transcription, flags=re.IGNORECASE)

	# Handle squawk code recognition: ensure squawk code is always a 4-digit number
	transcription = re.sub(r'\bsquawk\s+(\d)\s*(\d)\s*(\d)\s*(\d)\b', r'squawk \1\2\3\4', transcription,
	                       flags=re.IGNORECASE)
	# Handle Flight Level: Prevent flight levels from concatenating with other numbers like time references
	transcription = re.sub(r'\bflight level\s*(\d{3})(?=\s|$)', r'FL\1', transcription, flags=re.IGNORECASE)

	# Ensure proper spacing between FLxxx and any following digits or text (e.g., "FL150 10 minutes")
	transcription = re.sub(r'(FL\d{3})(?=\d)', r'\1 ', transcription, flags=re.IGNORECASE)

	# capitalise NATO words if found
	nato_pattern = r'\b(' + '|'.join(nato) + r')\b'
	transcription = re.sub(nato_pattern, lambda match: match.group(0).capitalize(), transcription, flags=re.IGNORECASE)

	# Capitalise first word
	transcription = re.sub(r'^\w+', lambda match: match.group(0).capitalize(), transcription)

	# Ensure 3-digit callsigns like "7 59" are captured correctly
	transcription = re.sub(r'\b(\d)\s*(\d)\s*(\d)\b', r'\1\2\3', transcription, flags=re.IGNORECASE)

	# Ensure 4-digit callsigns like "4407" are captured correctly
	transcription = re.sub(r'\b(\d)\s*(\d)\s*(\d)\s*(\d)\b', r'\1\2\3\4', transcription, flags=re.IGNORECASE)
	repeated_pattern = r'\b(\w+)(\s+\1){3,}\b'

	# Check for repeated words or numbers
	if (re.search(repeated_pattern,
	              transcription) or transcription == 'You' or transcription == 'Bye' or transcription == '.' \
			or transcription == 'Bye bye' or transcription == 'Thank you' or transcription == 'Thank you very much..' or len(
				transcription.split()) == 1):
		transcription = "false activation"

	return transcription


@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
	try:
		# Get the audio file from the request
		audio_file = request.files['file']

		# Read the WAV file directly
		wav_io = io.BytesIO(audio_file.read())
		if wav_io.getbuffer().nbytes == 0:
			return jsonify({"error": "No file data received"}), 400

		# Read the WAV data using soundfile
		audio_data, original_sample_rate = sf.read(wav_io)

		# Convert to mono (you can still use librosa for this step)
		audio_mono = librosa.to_mono(audio_data.T)
		target_sample_rate = 16000

		# Resample using scipy
		audio = resample_poly(audio_mono, up=target_sample_rate, down=original_sample_rate)

		# Padding if necessary
		padding_duration_sec = 30
		padding_size = target_sample_rate * padding_duration_sec
		if len(audio) < padding_size:
			audio = np.pad(audio, (0, padding_size - len(audio)), mode='constant')

		# Process the audio
		inputs = processor(audio, sampling_rate=target_sample_rate, return_tensors="pt", padding=True).to(device)

		with torch.no_grad():
			generated_ids = model.generate(inputs["input_features"])

		transcription = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
		transcription = re.sub(r'\s+', ' ', transcription).strip()

		# Apply any custom word-to-number mapping
		number_mapping = {}  # Define the custom mappings
		for word, num in number_mapping.items():
			transcription = re.sub(word, num, transcription, flags=re.IGNORECASE)

		transcription = apply_custom_fixes(transcription)

		print('Transcribed:', transcription)
		return jsonify({"transcription": transcription})

	except Exception as e:
		return jsonify({"error": f"An error occurred: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
	return jsonify({"status": "healthy"}), 200


if __name__ == '__main__':
	app.run(host='0.0.0.0', port=5000, debug=True)
