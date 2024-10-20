from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
import torch
import soundfile as sf
import librosa
import numpy as np
import datetime
import re
from collections import defaultdict


# Initialize CUDA (optional)
torch.cuda.init()

# Define the model path or Hugging Face model ID
# model_name_or_path = "jlvdoorn/whisper-small-atco2-asr"
model_name_or_path = 'jlvdoorn/whisper-medium-atco2-asr'

# Load the processor and model
processor = AutoProcessor.from_pretrained(model_name_or_path)
model = AutoModelForSpeechSeq2Seq.from_pretrained(model_name_or_path)

# # Save the processor and model to a local directory
processor.save_pretrained("../models/atco2_medium")
model.save_pretrained("../models/atco2_medium")

# Move model to GPU if available
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print(device)
model.to(device)
model.eval()
#
# Load your audio file (e.g., WAV file)
audio_input = "./startup.wav"
audio, original_sample_rate = sf.read(audio_input)
print(f"Audio data shape: {audio.shape}")

# # Convert to mono
# audio_mono = librosa.to_mono(audio.T)
#
# # Resample audio to 16000 Hz
# target_sample_rate = 16000
# audio = librosa.resample(audio_mono, orig_sr=original_sample_rate, target_sr=target_sample_rate, res_type='kaiser_fast')
#
# # Define chunk size (10 seconds) and padding duration (30 seconds)
# chunk_duration_sec = 15
# padding_duration_sec = 30
# chunk_size = target_sample_rate * chunk_duration_sec
# padding_size = target_sample_rate * padding_duration_sec
#
# # Define lists of relevant terms
# general = ['Air Traffic Control communications','1','2','3','4','5','6','7','8','9','0','90','180','270','360']
# nato = [
# 	'Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf',
# 	'Hotel', 'India', 'Juliett', 'Kilo', 'Lima', 'Mike', 'November',
# 	'Oscar', 'Papa', 'Quebec', 'Romeo', 'Sierra', 'Tango', 'Uniform',
# 	'Victor', 'Whiskey', 'Xray', 'Yankee', 'Zulu'
# ]
# atc_words = [
#     "acknowledge", "affirmative","affirm", "altitude", "approach", "apron", "arrival",
#     "bandbox", "base", "bearing", "cleared", "climb", "contact", "control",
#     "crosswind", "cruise", "descend", "departure", "direct", "disregard",
#     "downwind", "estimate", "final", "flight", "frequency", "go around",
#     "heading", "hold", "identified", "immediate", "information", "instruct",
#     "intentions", "land", "level", "maintain", "mayday", "message", "missed",
#     "navigation", "negative", "obstruction", "option", "orbit", "pan-pan",
#     "pattern", "position", "proceed", "radar", "readback", "received",
#     "report", "request", "required", "runway", "squawk", "standby", "takeoff",
#     "taxi", "threshold", "traffic", "transit", "turn", "vector", "visual",
#     "waypoint", "weather", "wilco", "wind", "with you", "speed",
#     "heavy", "light", "medium", "emergency", "fuel", "identifier",
#     "limit", "monitor", "notice", "operation", "permission", "relief",
#     "route", "signal", "stand", "system", "terminal", "test", "track",
#     "understand", "verify", "vertical", "warning", "zone", "no", "yes", "unable",
#     "clearance", "conflict", "coordination", "cumulonimbus", "deviation", "enroute",
#     "fix", "glideslope", "handoff", "holding", "IFR", "jetstream", "knots",
#     "localizer", "METAR", "NOTAM", "overfly", "pilot", "QNH", "radial",
#     "sector", "SID", "STAR", "tailwind", "transition", "turbulence", "uncontrolled",
#     "VFR", "wake turbulence", "X-wind", "yaw", "Zulu time", "airspace",
#     "briefing", "checkpoint", "elevation", "FL",
#     "ground control", "hazard", "ILS", "jetway", "kilo", "logbook", "missed approach",
#     "nautical mile", "offset", "profile", "quadrant", "RVR",
#     "static", "touchdown", "upwind", "variable", "wingtip", "Yankee", "zoom climb",
#     "airspeed", "backtrack", "ETOPS", "gate", "holding pattern",
#     "jumpseat", "minimums", "pushback", "RNAV", "slot time", "taxiway", "TCAS",
#     "wind shear", "zero fuel weight", "ETA",
#     "flight deck", "ground proximity warning system", "jet route",
#     "landing clearance", "Mach number", "NDB", "obstacle clearance",
#     "PAPI", "QFE", "radar contact",
#     'ATC', 'pilot', 'call sign', 'altitude', 'heading', 'speed', 'climb to', 'descend to',
#     'maintain', 'tower', 'ground', 'runway', 'taxi', 'takeoff', 'landing',
#     'flight level', 'traffic', 'hold short', 'cleared for',
#     'roger', 'visibility', 'weather', 'wind', 'gusts',
#     'icing conditions', 'deicing', 'VFR', 'IFR', 'no-fly zone',
#     'restricted airspace', 'flight path', 'direct route', 'vector', 'frequency change',
#     'final approach', 'initial climb to', 'contact approach', 'FIR', 'control zone', 'TMA',
#     'missed approach', 'minimum safe altitude', 'transponder',
#     'reduce speed to', 'increase speed to',
#     'flight conditions', 'clear of conflict', 'resume own navigation', 'request altitude change',
#     'request route change', 'flight visibility', 'ceiling', 'severe weather', 'convective SIGMET',
#     'AIRMET', 'QNH', 'QFE', 'transition altitude', 'transition level',
#     'NOSIG', 'TFR', 'special use airspace',
#     'MOA', 'IAP', 'visual approach',
#     'NDB', 'VOR',
#     'ATIS', 'engine start clearance',
#     'line up and wait', 'unicom', 'cross runway', 'departure frequency',
#     'arrival frequency', 'go-ahead', 'hold position', 'check gear down',
#     'touch and go', 'circuit pattern', 'climb via SID',
#     'descend via STAR', 'speed restriction', 'flight following', 'radar service terminated', 'squawk VFR',
#     'change to advisory frequency', 'report passing altitude', 'report position',
#     'ATD', 'block altitude', 'cruise climb', 'direct to', 'execute missed approach',
#     'in-flight refueling', 'joining instructions', 'lost communications', 'MEA', 'next waypoint', 'OCH',
#     'procedure turn', 'radar vectoring', 'radio failure', 'short final', 'standard rate turn',
#     'TRSA', 'undershoot', 'VMC',
#     'wide-body aircraft', 'yaw damper', 'zulu time conversion', 'RNAV',
#     'RNP', 'barometric pressure', 'control tower handover', 'datalink communication',
#     'ELT', 'FDR', 'GCI',
#     'hydraulic failure', 'IMC', 'knock-it-off',
#     'LVO', 'MAP', 'NAVAIDS',
#     'oxygen mask deployment', 'PAR', 'QRA',
#     'runway incursion', 'SAR', 'tail strike', 'upwind leg', 'vertical speed',
#     'wake turbulence category', 'X-ray cockpit security', 'yield to incoming aircraft', 'zero visibility takeoff','good day', 'no delay', 'fault'
# ]
#
# collated_list = general + nato + atc_words
# collated_list_string = ' '.join(collated_list)
#
# # Prepare prompt for the model (convert it to tokens)
# if collated_list_string:
#     prompt_ids = processor(text=collated_list_string, return_tensors="pt").input_ids.to(device)
# else:
#     prompt_ids = None
#
# # Define number mappings
# number_mapping = {
#     r'\bzero\b': '0',
#     r'\bone\b': '1',
#     r'\btwo\b': '2',
#     r'\bthree\b': '3',
#     r'\bfour\b': '4',
#     r'\bfive\b': '5',
#     r'\bsix\b': '6',
#     r'\bseven\b': '7',
#     r'\beight\b': '8',
#     r'\bnine\b': '9',
#     r'\bten\b': '10',
#     r'\bhundred\b': '00',
#     r'\bthousand\b': '000'
# }
#
# # Dictionary to maintain history of transcriptions and patterns
# transcription_history = defaultdict(int)
# pattern_history = defaultdict(lambda: {'count': 0, 'correct_format': ''})
#
# from fuzzywuzzy import fuzz
# from fuzzywuzzy import process
#
# def apply_custom_fixes(transcription):
#     # Track frequent patterns
#     min_similarity_threshold = 90  # Adjust threshold as needed
#
#     # Find patterns like "word + digits" (e.g., "Singapore 638")
#     pattern_matches = re.findall(r'\b([A-Z][a-z]*)\s(\d{1,5})\b', transcription)
#     for match in pattern_matches:
#         word, digits = match
#         pattern = f"{word} {digits}"
#
#         # Check against existing patterns in the history
#         if pattern_history:
#             closest_match, similarity = process.extractOne(pattern, pattern_history.keys(), scorer=fuzz.ratio)
#
#             if similarity >= min_similarity_threshold:
#                 # If the pattern is similar to an existing pattern, use the most frequent correct format
#                 correct_format = pattern_history[closest_match]['correct_format']
#                 transcription = re.sub(rf'\b{word} \d{{1,5}}\b', correct_format, transcription)
#             else:
#                 # If no close match is found, store the new pattern
#                 pattern_history[pattern]['count'] += 1
#                 pattern_history[pattern]['correct_format'] = pattern
#         else:
#             # If no history exists, add the current pattern
#             pattern_history[pattern]['count'] += 1
#             pattern_history[pattern]['correct_format'] = pattern
#
#     # Specific transformation: "placeholder left" to "placeholderL" and "placeholder right" to "placeholderR"
#     transcription = re.sub(r'\b(\d+)\s+left\b', r'\1L', transcription, flags=re.IGNORECASE)
#     transcription = re.sub(r'\b(\d+)\s+right\b', r'\1R', transcription, flags=re.IGNORECASE)
#
#     # Handle 'decimal' and 'point' to convert to numeric format with proper separation
#     transcription = re.sub(r'(\d+)\s*(?:decimal|point)\s*(\d+)', r'\1.\2', transcription, flags=re.IGNORECASE)
#
#     # Manually break off frequencies after the first decimal point
#     transcription = re.sub(r'(\d+\.\d)(\d+)', r'\1 \2', transcription)
#
#     return transcription
#
#
#
#
# # Process each chunk
# for i in range(0, len(audio), chunk_size):
#     chunk = audio[i:i + chunk_size]
#
#     # Pad the chunk to 30 seconds
#     if len(chunk) < padding_size:
#         chunk = np.pad(chunk, (0, padding_size - len(chunk)), mode='constant')
#
#     # Compute the timestamp for the chunk (accurate timing)
#     start_time = str(datetime.timedelta(seconds=i // target_sample_rate))
#     end_time = str(datetime.timedelta(seconds=(i + len(chunk)) // target_sample_rate))
#
#     # Preprocess the chunk
#     inputs = processor(chunk, sampling_rate=target_sample_rate, return_tensors="pt", padding=True).to(device)
#
#     # Transcribe the chunk
#     with torch.no_grad():
#         generated_ids = model.generate(inputs["input_features"], forced_decoder_ids=prompt_ids if prompt_ids is not None else None)
#
#     # Decode the generated tokens to text
#     transcription = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
#
#     # Remove unnecessary spaces
#     transcription = re.sub(r'\s+', ' ', transcription).strip()
#
#     # Replace numbers and specific words in the transcription
#     for word, num in number_mapping.items():
#         transcription = re.sub(word, num, transcription, flags=re.IGNORECASE)
#
#     # Combine sequences of digits into single numbers
#     transcription = re.sub(r'(\d)\s+(?=\d)', r'\1', transcription)
#
#     # Handle 'decimal' and 'point' to convert to numeric format
#     transcription = re.sub(r'(\d+)\s*(?:decimal|point)\s*(\d+)', r'\1.\2', transcription, flags=re.IGNORECASE)
#
#     # Apply custom regex fixes for common aviation typos
#     transcription = apply_custom_fixes(transcription)
#
#     # Update transcription history
#     transcription_history[transcription] += 1
#
#     # Print the transcription with accurate start and end timestamps
#     print(f"[{start_time} - {end_time}] {transcription}")
#
# print("Transcription complete.")
#
# # Display the most common phrases and patterns (for debugging/inspection)
# print("\nMost common phrases:")
# for phrase, count in transcription_history.items():
#     if count > 1:
#         print(f"'{phrase}' occurred {count} times.")
#
# print("\nMost common word + digits patterns:")
# for pattern, data in pattern_history.items():
#     if data['count'] > 1:
#         print(f"'{pattern}' occurred {data['count']} times, stored as '{data['correct_format']}'")