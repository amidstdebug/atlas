import torch
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq

model_name_or_path = 'JoeTan/whisper-small-atco2'
local_directory = './local_model_joe/'

try:
	# Load the processor and model
	print("Loading processor...")
	processor = AutoProcessor.from_pretrained(model_name_or_path)
	print("Processor loaded successfully.")

	print("Loading model...")
	model = AutoModelForSpeechSeq2Seq.from_pretrained(model_name_or_path)
	print("Model loaded successfully.")

	# Save the processor and model locally
	processor.save_pretrained(local_directory)
	model.save_pretrained(local_directory)
	print(f"Model and processor saved locally to {local_directory}.")

	# Print the model architecture
	print("Model architecture:")
	print(model)

except Exception as e:
	print(f"An error occurred: {e}")
