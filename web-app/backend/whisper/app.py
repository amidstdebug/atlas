from flask import Flask, request, jsonify
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
import torch
import soundfile as sf
import librosa
import numpy as np
import re
from collections import defaultdict
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

# Initialize the Flask application
app = Flask(__name__)

# Load model and processor
model_name_or_path = './local_model'
processor = AutoProcessor.from_pretrained(model_name_or_path)
model = AutoModelForSpeechSeq2Seq.from_pretrained(model_name_or_path)
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()

# Predefined lists and mappings
general = ['Air Traffic Control communications','1','2','3','4','5','6','7','8','9','0','90','180','270','360']
nato = [
	'Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf',
	'Hotel', 'India', 'Juliett', 'Kilo', 'Lima', 'Mike', 'November',
	'Oscar', 'Papa', 'Quebec', 'Romeo', 'Sierra', 'Tango', 'Uniform',
	'Victor', 'Whiskey', 'Xray', 'Yankee', 'Zulu'
]
atc_words = [
    "acknowledge", "affirmative","affirm", "altitude", "approach", "apron", "arrival",
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
    'line up and wait', 'unicom', 'cross runway', 'departure frequency',
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
    'wake turbulence category', 'X-ray cockpit security', 'yield to incoming aircraft', 'zero visibility takeoff','good day', 'no delay', 'fault'
]

collated_list = general + nato + atc_words
collated_list_string = ' '.join(collated_list)
# Define number mappings
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

# Define helper functions (apply_custom_fixes, etc.)

def apply_custom_fixes(transcription):
    # Track frequent patterns
    min_similarity_threshold = 90  # Adjust threshold as needed

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
                transcription = re.sub(rf'\b{word} \d{{1,5}}\b', correct_format, transcription)
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

    # Handle 'decimal' and 'point' to convert to numeric format with proper separation
    transcription = re.sub(r'(\d+)\s*(?:decimal|point)\s*(\d+)', r'\1.\2', transcription, flags=re.IGNORECASE)

    # Manually break off frequencies after the first decimal point
    transcription = re.sub(r'(\d+\.\d)(\d+)', r'\1 \2', transcription)

    return transcription

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    # Get the audio file from the request
    audio_file = request.files['file']
    audio, original_sample_rate = sf.read(audio_file)
    
    # Convert to mono and resample
    audio_mono = librosa.to_mono(audio.T)
    target_sample_rate = 16000
    audio = librosa.resample(audio_mono, orig_sr=original_sample_rate, target_sr=target_sample_rate, res_type='kaiser_fast')

    # Process each chunk
    chunk_duration_sec = 15
    padding_duration_sec = 30
    chunk_size = target_sample_rate * chunk_duration_sec
    padding_size = target_sample_rate * padding_duration_sec
    transcriptions = []

    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i + chunk_size]
        if len(chunk) < padding_size:
            chunk = np.pad(chunk, (0, padding_size - len(chunk)), mode='constant')

        inputs = processor(chunk, sampling_rate=target_sample_rate, return_tensors="pt", padding=True).to(device)

        with torch.no_grad():
            generated_ids = model.generate(inputs["input_features"], forced_decoder_ids=prompt_ids if prompt_ids is not None else None)

        transcription = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        transcription = re.sub(r'\s+', ' ', transcription).strip()

        for word, num in number_mapping.items():
            transcription = re.sub(word, num, transcription, flags=re.IGNORECASE)

        transcription = apply_custom_fixes(transcription)

        transcriptions.append(transcription)
        break  # Process only the first chunk
    return_data = jsonify({"transcription": transcriptions[0] if transcriptions else "No transcription available"})
    print('Sending: ', str(transcriptions),flush=True)
    # Return the transcription as a JSON response
    return return_data

        

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)