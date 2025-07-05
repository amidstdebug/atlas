import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WhisperService:
	_instance = None

	def __new__(cls):
		if cls._instance is None:
			cls._instance = super(WhisperService, cls).__new__(cls)
			try:
				logger.info("Initializing Whisper model...")
				cls._instance.device = "cuda:0" if torch.cuda.is_available() else "cpu"
				torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

				# model_id = "openai/whisper-large-v3-turbo"
				model_id = "distil-whisper/distil-large-v3.5"

				cache_dir = "models"
				os.makedirs(cache_dir, exist_ok=True)

				model = AutoModelForSpeechSeq2Seq.from_pretrained(
					model_id, torch_dtype=torch_dtype, low_cpu_mem_usage=True, use_safetensors=True, cache_dir=cache_dir
				)
				model.to(cls._instance.device)

				processor = AutoProcessor.from_pretrained(model_id, cache_dir=cache_dir)

				cls._instance.pipe = pipeline(
					"automatic-speech-recognition",
					model=model,
					tokenizer=processor.tokenizer,
					feature_extractor=processor.feature_extractor,
					max_new_tokens=128,
					chunk_length_s=30,
					batch_size=16,
					return_timestamps=True,
					torch_dtype=torch_dtype,
					device=cls._instance.device,
				)
				logger.info("Whisper model initialized successfully.")
			except Exception as e:
				logger.error(f"Failed to initialize Whisper model: {e}")
				cls._instance = None
				raise
		return cls._instance

	def transcribe(self, audio_data: bytes):
		"""
		Transcribes a complete audio file provided as bytes.
		Used by the standard HTTP POST endpoint.
		"""
		if not self.pipe:
			raise RuntimeError("Whisper service is not initialized.")

		try:
			logger.info("Starting batch transcription...")
			result = self.pipe(audio_data)
			logger.info("Batch transcription completed.")
			return result
		except Exception as e:
			logger.error(f"Error during batch transcription: {e}")
			raise

	def transcribe_stream(self, audio_generator):
		"""
		Transcribes an audio stream from a generator.
		Used by the WebSocket endpoint for real-time processing.
		The pipeline will process the audio in chunks as it's yielded.
		"""
		if not self.pipe:
			raise RuntimeError("Whisper service is not initialized.")

		try:
			logger.info("Starting stream transcription...")
			# The pipeline can directly process a generator of audio chunks.
			for result in self.pipe(audio_generator):
				yield result
			logger.info("Stream transcription finished.")
		except Exception as e:
			logger.error(f"Error during stream transcription: {e}")
			# In a production scenario, you might want to handle this more gracefully,
			# potentially sending an error message over the WebSocket.
			raise


def get_whisper_service():
	"""
	Dependency injector for the WhisperService.
	Ensures a single instance is used across the application.
	"""
	return WhisperService()
