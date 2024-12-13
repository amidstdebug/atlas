# app.py
import os
from collections import defaultdict
import torch

print('CUDA:', torch.cuda.is_available())
from flask import Flask, request, jsonify
from flask_cors import CORS
import io
import numpy as np
import soundfile as sf
import librosa
from scipy.signal import resample_poly
from funcs.model import load_model
from funcs.transcription import apply_custom_fixes
from funcs.lists import collated_list_string
import jwt
import datetime
from functools import wraps
import requests

# import sox
# Initialize the Flask application
app = Flask(__name__)
CORS(app)

# Load model and processor
model_name_or_path = './models/atco2_medium'
processor, model, device = load_model(model_name_or_path)
transcription_history = defaultdict(int)
pattern_history = defaultdict(lambda: {'count': 0, 'correct_format': ''})

# uri for local llm model
LLM_URI = "http://ollama:11434/api/chat"

# TODO : PUT THIS INTO AN ENV FILE
# Secret key for JWT encoding/decoding
JWT_SECRET = '***'
JWT_ALGORITHM = 'HS256'  # Recommended for JWT signing

OLLAMA_MODEL = "qwen2.5"


# Function to generate JWT token
def generate_jwt_token(user_id):
	payload = {
		'user_id': user_id,
		'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=0.1)  # Token expires in 1 hour
	}
	# Use PyJWT's encode method
	token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

	# PyJWT's encode in version 2.x returns bytes, so we decode it to a string if necessary
	return token if isinstance(token, str) else token.decode('utf-8')


# Decorator to protect routes with JWT authentication
def token_required(func):
	@wraps(func)
	def wrapper(*args, **kwargs):
		token = None
		# Check if the token is passed in the 'Authorization' header
		if 'Authorization' in request.headers:
			token = request.headers['Authorization'].split(" ")[1]  # Expecting Bearer <token>

		if not token:
			return jsonify({'error': 'Token is missing!'}), 401

		# TODO: FIX THIS SECURITY VULNERABILITY
		try:
			# Decode the token
			data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
			print(data)
		# You can access `data['user_id']` here to get user info, if needed
		except jwt.ExpiredSignatureError:
			return jsonify({'error': 'Token has expired!'}), 401
		except jwt.InvalidTokenError:
			return jsonify({'error': 'Invalid token!'}), 401

		return func(*args, **kwargs)

	return wrapper


# Route to get a JWT token with user_id and password validation
@app.route('/auth/login', methods=['POST'])
def login():
	# Get user_id and password from the request
	user_id = request.json.get('user_id')
	password = request.json.get('password')

	# Check if user_id and password are provided
	if not user_id or not password:
		return jsonify({'error': 'Missing user_id or password!'}), 400

	# Validate the user_id and password
	# TODO : FIX THIS SHIT
	if user_id == 'atlasuser' and password == 'passwordbearer2024':
		# Generate and return the token for the user
		token = generate_jwt_token(user_id)
		return jsonify({'token': token})
	else:
		# Return an error if the credentials are incorrect
		return jsonify({'error': 'Invalid user_id or password!'}), 401


@app.route('/auth/refresh', methods=['POST'])
def refresh_token():
	token = None

	# Check if the token is passed in the 'Authorization' header
	if 'Authorization' in request.headers:
		token = request.headers['Authorization'].split(" ")[1]  # Expecting Bearer <token>

	if not token:
		return jsonify({'error': 'Token is missing!'}), 401

	try:
		# Decode the token without verifying the expiration
		payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
		exp = datetime.datetime.utcfromtimestamp(payload['exp'])
		now = datetime.datetime.utcnow()

		# Check how long the token has been expired
		time_since_expiry = now - exp

		if time_since_expiry <= datetime.timedelta(hours=1):
			# Token expired less than an hour ago, so we can renew it
			new_payload = {
				'user_id': payload['user_id'],
				'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)  # Extend the expiration by 1 hour
			}
			new_token = jwt.encode(new_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
			return jsonify({'token': new_token if isinstance(new_token, str) else new_token.decode('utf-8')})

		else:
			# Token expired more than an hour ago, so it's no longer secure to renew it
			return jsonify(
				{'error': 'Token is no longer secure!'}), 403  # Using 403 Forbidden to indicate security issue

	except jwt.ExpiredSignatureError:
		# This should not happen as we are not verifying exp, but added for safety
		return jsonify({'error': 'Token has expired!'}), 401
	except jwt.InvalidTokenError:
		return jsonify({'error': 'Invalid token!'}), 401


@app.route('/transcribe', methods=['POST'])
@token_required
def transcribe_audio():
	try:
		if not os.path.exists('./misc/startup.wav'):
			print("File ./misc/startup.wav not found!")
			return
		audio_file = request.files['file']
		wav_io = io.BytesIO(audio_file.read())
		# Check if the file is empty
		if wav_io.getbuffer().nbytes == 0:
			return jsonify({"error": "No file data received"}), 400

		# Read the audio data and sample rate
		audio_data, original_sample_rate = sf.read(wav_io)

		# Convert to mono if necessary
		if audio_data.ndim > 1:
			audio_mono = librosa.to_mono(audio_data.T)
		else:
			audio_mono = audio_data

		# Remove DC offset
		audio_mono = audio_mono - np.mean(audio_mono)

		# Normalize the audio to prevent clipping
		max_val = np.max(np.abs(audio_mono))
		if max_val > 0:
			audio_mono = audio_mono / max_val * 0.99  # Scale to 99% to prevent clipping

		# Calculate the length of the audio in seconds
		audio_length_seconds = len(audio_mono) / original_sample_rate

		# Target length in seconds (30 seconds)
		target_length_seconds = 30
		target_sample_rate = 16000

		# If audio is shorter than 30 seconds, pad it with zeros
		if audio_length_seconds < target_length_seconds:
			padding_duration = target_length_seconds - audio_length_seconds
			padding_samples = int(padding_duration * original_sample_rate)
			audio_mono = np.pad(audio_mono, (0, padding_samples), 'constant')

		# Resample to target sample rate
		audio_resampled = resample_poly(audio_mono, up=target_sample_rate, down=original_sample_rate)
		# **Save the audio to a WAV file**
		sf.write('received_audio.wav', audio_resampled, target_sample_rate)

		# # Initialize SoX transformer
		# tfm = sox.Transformer()
		# target_sample_rate = 16000

		# # Use the rate function for proper downsampling with anti-aliasing
		# tfm.rate(samplerate=target_sample_rate, quality="h")  # High-quality resampling

		# # Apply the transformation to the numpy array (resampling with correct rate)
		# audio_resampled = tfm.build_array(input_array=audio_mono, sample_rate_in=original_sample_rate)

		# # Now, save the resampled audio for debugging or listening back
		# sf.write('received_audio.wav', audio_resampled, target_sample_rate)

		inputs = processor(
			audio_resampled,
			sampling_rate=target_sample_rate,
			return_tensors="pt",
			padding=True
		).to(device)

		with torch.no_grad():
			generated_ids = model.generate(inputs["input_features"])

		transcription = processor.batch_decode(
			generated_ids, skip_special_tokens=True
		)[0].strip()
		transcription = apply_custom_fixes(transcription)

		return jsonify({"transcription": transcription})

	except Exception as e:
		print('error,', e)
		return jsonify({"error": f"An error occurred: {str(e)}"}), 500


@app.route('/summary', methods=['POST'])
@token_required
def get_summary():
	try:
		# Get the transcription and previous_report from the POST request
		transcription = request.json.get('transcription')
		previous_report = request.json.get('previous_report')
		summary_mode = request.json.get('summary_mode')
		if not transcription:
			return jsonify({'error': 'Missing transcription in request'}), 400

		# Check if previous_report is provided and not None or empty
		if previous_report is not None and previous_report != '':
			# If previous_report is provided, adjust the content
			content = (
				f"This is the previous report:\n{previous_report}\n\n"
				f"and these are new transcriptions that just came in:\n{transcription}"
			)
		else:
			content = transcription
		# Construct the file path dynamically based on the variable
		file_path = f"./ollama_serve/Modelfile_{summary_mode}"

		# Read the contents of the file and assign it to the new variable
		with open(file_path, 'r') as file:
			system_prompt = file.read()

		# Define the payload to send to the external API
		payload = {
			"model": OLLAMA_MODEL,
			"options": {
				"temperature": 0.1
			},
			"messages": [
				{"role": "system", "content": system_prompt},
				{"role": "user", "content": content}
			],
			"stream": False
		}

		# Make the request to the external chat service
		response = requests.post(LLM_URI, json=payload)

		# If the external request fails, return an error
		if response.status_code != 200:
			return jsonify(
				{'error': 'Failed to query external service', 'details': response.text}
			), response.status_code

		# Return the response from the external service
		return jsonify(response.json())

	except Exception as e:
		return jsonify({"error": f"An error occurred: {str(e)}"}), 500


@app.route('/health', methods=['GET'])
@token_required
def health_check():
	return jsonify({"status": "healthy"}), 200


if __name__ == '__main__':
	# Function to transcribe ./narita.wav at startup
	def transcribe_startup_file():
		try:
			# Load the './narita.wav' file for transcription
			with open('./misc/startup.wav', 'rb') as f:
				audio_data, original_sample_rate = sf.read(f)

				# Convert to mono if necessary
				audio_mono = librosa.to_mono(audio_data.T)
				# Calculate the length of the audio in seconds
				audio_length_seconds = len(audio_mono) / original_sample_rate

				# Target length in seconds (30 seconds)
				target_length_seconds = 30
				target_sample_rate = 16000

				# If audio is shorter than 30 seconds, pad it with zeros
				if audio_length_seconds < target_length_seconds:
					padding_duration = target_length_seconds - audio_length_seconds
					padding_samples = int(padding_duration * original_sample_rate)
					audio_mono = np.pad(audio_mono, (0, padding_samples), 'constant')

				# Resample to target sample rate
				audio_resampled = resample_poly(audio_mono, up=target_sample_rate, down=original_sample_rate)

				# Process audio for transcription
				inputs = processor(audio_resampled, sampling_rate=target_sample_rate, return_tensors="pt",
				                   padding=True).to(device)

				# Perform transcription using the loaded model
				with torch.no_grad():
					generated_ids = model.generate(inputs["input_features"])

				transcription = processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
				transcription = apply_custom_fixes(transcription)

			# Log or print the transcription result
			# print(f"Transcription of './misc/startup.wav': {transcription}")

			return True  # Indicate success

		except Exception as e:
			print(f"Error transcribing './misc/startup.wav': {str(e)}")
			return False  # Indicate failure


	# Function to load model into memory via Ollama server
	def check_ollama_model_status():
		try:
			# Define a sample payload to send to Ollama server to load the model into memory
			payload = {
				"model": OLLAMA_MODEL,
				"messages": [
					{"role": "system", "content": "Load model into memory."}
				],
				"stream": False
			}

			# Send a POST request to Ollama server
			response = requests.post(LLM_URI, json=payload)

			# Log or print the response status
			if response.status_code == 200:
				print(f"Ollama model loaded successfully: {response.json()}")
				return True  # Indicate success
			else:
				print(f"Error loading Ollama model: {response.text}")
				return False  # Indicate failure

		except Exception as e:
			print(f"Error communicating with Ollama server: {str(e)}")
			return False  # Indicate failure


	# Run the Flask app
	print("Starting server and loading models...")

	# Step 1: Transcribe ./narita.wav upon startup
	transcribe_success = transcribe_startup_file()

	# Step 2: Send a request to Ollama server to load the model into memory
	ollama_success = check_ollama_model_status()

	# Step 3: Print success message if both steps succeeded
	if transcribe_success and ollama_success:
		print("All models loaded successfully. Server starting now.")
	else:
		print("Failed to load all models. Please check errors above.")

	# Step 4: Start the Flask application
	app.run(host='0.0.0.0', port=5000, debug=True)
