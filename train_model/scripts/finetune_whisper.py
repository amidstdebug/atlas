import os
import torch
import torch.multiprocessing as mp
import librosa
import soundfile
import jiwer
import accelerate
import evaluate
from datasets import load_dataset, Audio
from transformers import (
	WhisperForConditionalGeneration,
	WhisperProcessor,
	Seq2SeqTrainingArguments,
	Seq2SeqTrainer,
	DataCollatorForSeq2Seq,
	DataCollatorWithPadding
)
from dataclasses import dataclass
from typing import Any, Dict, List, Union

# Load WER Metric
wer_metric = evaluate.load("wer")


class DataCollatorSpeechSeq2SeqWithPadding:
	def __init__(self, processor):
		self.processor = processor

	def __call__(self, features):
		# Separate input features (audio) and labels (text)
		input_features = [feature["input_features"] for feature in features]
		label_features = [feature["labels"] for feature in features]

		# The feature extractor expects a list of dictionaries with "input_features"
		input_features = [{"input_features": feat} for feat in input_features]

		# Pad input features and labels
		batch = {
			"input_features": self.processor.feature_extractor.pad(input_features, return_tensors="pt")[
				"input_features"],
			"labels": self.processor.tokenizer.pad({"input_ids": label_features}, return_tensors="pt").input_ids
		}
		return batch


class WhisperFineTuner:
	def __init__(self, model_name, data_dir, output_dir, final_dir):
		self.model_name = model_name
		self.data_dir = data_dir
		self.output_dir = output_dir
		self.final_dir = final_dir

		# Load the processor and model
		self.processor = WhisperProcessor.from_pretrained(self.model_name)
		# self.model = WhisperForConditionalGeneration.from_pretrained(self.model_name)
		self.model = WhisperForConditionalGeneration.from_pretrained(self.model_name).to(
			"cuda" if torch.cuda.is_available() else "cpu")

		# Freeze the encoder to speed up training and reduce memory usage
		self.model.freeze_encoder()

	def load_dataset(self):
		"""
		Loads the dataset from the given path and returns a Hugging Face Dataset object.
		Assumes the dataset is organized with 'train' and 'validation' directories containing audio files and a metadata JSON file.
		"""
		import os

		# Get the current directory where the script is located
		script_dir = os.path.dirname(os.path.realpath(__file__))

		# Construct the absolute path for the train and validation metadata.json
		train_data_path = os.path.abspath(os.path.join(script_dir, "../data/train_cleaned/metadata.json"))
		validation_data_path = os.path.abspath(os.path.join(script_dir, "../data/validation/metadata.json"))

		# Load the dataset using the resolved paths
		data_files = {
			"train": train_data_path,
			"validation": validation_data_path
		}

		# Use the paths in load_dataset
		dataset = load_dataset("json", data_files=data_files)

		# Cast the 'audio' column to Audio feature type
		dataset = dataset.cast_column("audio", Audio(sampling_rate=16000))
		return dataset

	def preprocess_dataset(self, dataset):
		"""
		Prepares the dataset by extracting input features and tokenizing the labels.
		Note that this assumes that the audio is already a .wav file with 30s padding.
		"""

		def prepare_dataset(batch):
			# Check if the batch is a list of audio samples (batched data)
			if isinstance(batch["audio"], list):
				# Iterate over each audio object in the batch
				batch["input_features"] = [
					self.processor.feature_extractor(audio["array"],
					                                 sampling_rate=audio["sampling_rate"]).input_features[0]
					for audio in batch["audio"]
				]
			else:
				# If it's a single example, handle it directly
				audio = batch["audio"]
				batch["input_features"] = self.processor.feature_extractor(
					audio["array"], sampling_rate=audio["sampling_rate"]
				).input_features[0]

			# Tokenize the text (labels)
			batch["labels"] = self.processor.tokenizer(batch["text"]).input_ids
			return batch

		# Remove unused columns to save memory
		dataset = dataset.map(
			prepare_dataset,
			remove_columns=dataset.column_names["train"],
			num_proc=1,  # Disable multiprocessing
			batched=True,
			batch_size=8
		)

		return dataset

	def compute_metrics(self, pred):
		"""
		Compute WER (Word Error Rate) and return it.
		"""
		pred_ids = pred.predictions
		label_ids = pred.label_ids

		# Replace -100 in the labels as we can't decode them
		label_ids[label_ids == -100] = self.processor.tokenizer.pad_token_id

		pred_str = self.processor.tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
		label_str = self.processor.tokenizer.batch_decode(label_ids, skip_special_tokens=True)

		# Compute WER
		wer = wer_metric.compute(predictions=pred_str, references=label_str)
		return {"wer": wer}

	def fine_tune(self):
		"""
		Fine-tunes the Whisper model with the specified dataset.
		"""
		# Load and preprocess the dataset
		dataset = self.load_dataset()
		dataset = self.preprocess_dataset(dataset)

		# Define training arguments
		training_args = Seq2SeqTrainingArguments(
			output_dir=self.output_dir,
			per_device_train_batch_size=16,  # Lower batch size
			gradient_accumulation_steps=2,  # Simulate larger batch size
			evaluation_strategy="steps",  # Evaluate more frequently
			eval_steps=500,  # Evaluate every 500 steps
			learning_rate=5e-6,  # Lower learning rate if needed
			num_train_epochs=20,
			warmup_steps=500,  # Gradual warmup
			predict_with_generate=True,
			generation_max_length=225,
			logging_dir="../logs/training",
			load_best_model_at_end=True,
			report_to=["tensorboard"],
			fp16=True,
			save_total_limit=2,
			save_strategy="steps",
			save_steps=500,  # Save every 500 steps
			metric_for_best_model="wer",
			greater_is_better=False,
			gradient_checkpointing=True,  # Enable gradient checkpointing for memory efficiency,
			remove_unused_columns=False,

		)

		# Create data collator
		data_collator = DataCollatorSpeechSeq2SeqWithPadding(self.processor)

		# Initialize the Trainer API
		trainer = Seq2SeqTrainer(
			model=self.model,
			args=training_args,
			train_dataset=dataset["train"],
			eval_dataset=dataset["validation"],
			data_collator=data_collator,  # Use custom data collator
			tokenizer=self.processor.tokenizer,
			compute_metrics=self.compute_metrics
		)

		# Start training
		trainer.train()
		# Save the fine-tuned model and processor
		self.model.save_pretrained(self.final_dir)
		self.processor.save_pretrained(self.final_dir)


if __name__ == "__main__":
	model_name = "jlvdoorn/whisper-medium.en-atco2-asr"
	data_dir = "../data"
	output_dir = "../models/output"
	final_dir = "../models/output/final_model_2"

	print(torch.cuda.is_available())  # This should return True if the GPU is available
	print(torch.cuda.device_count())  # Check how many GPUs are available
	# Fine-tune the Whisper model
	whisper_finetuner = WhisperFineTuner(model_name, data_dir, output_dir, final_dir)
	whisper_finetuner.fine_tune()
