from transformers import WhisperForConditionalGeneration, WhisperProcessor

# Define the model path where all your files are stored
model_path = "../models/output/final_model"

# Load the processor (tokenizer and feature extractor)
processor = WhisperProcessor.from_pretrained(model_path)

# Load the model (weights and config)
model = WhisperForConditionalGeneration.from_pretrained(model_path)

# Use the model for inference
input_features = processor("../data/train_cleaned/wsss11_chunk1_cleaned.wav", return_tensors="pt").input_features
generated_ids = model.generate(input_features)

# Decode the transcription
transcription = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
print(transcription)
