import os
import torch
import torch.multiprocessing as mp
import librosa
import soundfile
import jiwer
import accelerate
import evaluate
from datasets import load_dataset, Audio, DatasetDict, concatenate_datasets
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
        self.model = WhisperForConditionalGeneration.from_pretrained(self.model_name).to(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        # Freeze the encoder to speed up training and reduce memory usage
        self.model.freeze_encoder()

    def load_dataset(self):
        """
        Loads the dataset from the given path and the ATCO2 datasets, combines them, and returns a Hugging Face Dataset object.
        """
        # Get the current directory where the script is located
        script_dir = os.path.dirname(os.path.realpath(__file__))

        # Construct the absolute path for the train and validation metadata.json
        train_data_path = os.path.abspath(os.path.join(script_dir, "../data/train_cleaned/metadata.json"))
        validation_data_path = os.path.abspath(os.path.join(script_dir, "../data/validation/metadata.json"))

        # Load your existing dataset
        data_files = {
            "train": train_data_path,
            "validation": validation_data_path
        }
        existing_dataset = load_dataset("json", data_files=data_files)

        # Load the new ATCO2 dataset which has both 'train' and 'validation' splits
        atco2_atcosim_asr = load_dataset("jlvdoorn/atco2-asr-atcosim")

        # Cast the 'audio' column to Audio feature type with the desired sampling rate
        existing_dataset = existing_dataset.cast_column("audio", Audio(sampling_rate=16000))
        atco2_atcosim_asr = atco2_atcosim_asr.cast_column("audio", Audio(sampling_rate=16000))  # New dataset

        # Check and assign 'train' split
        if "train" in atco2_atcosim_asr:
            atco2_asr_train = atco2_atcosim_asr["train"]
        else:
            # If only 'test' split exists, use it as 'train'
            atco2_asr_train = atco2_atcosim_asr["test"]

        # Check and assign 'validation' split
        if "validation" in atco2_atcosim_asr:
            atco2_asr_validation = atco2_atcosim_asr["validation"]
        else:
            # If only 'test' split exists, use it as 'validation'
            atco2_asr_validation = atco2_atcosim_asr["test"]

        # Combine the 'train' splits using concatenate_datasets
        train_dataset = concatenate_datasets([existing_dataset["train"], atco2_asr_train])

        # Combine the 'validation' splits using concatenate_datasets
        validation_dataset = concatenate_datasets([existing_dataset["validation"], atco2_asr_validation])

        # Create a new DatasetDict with combined splits
        dataset = DatasetDict({
            "train": train_dataset,
            "validation": validation_dataset
        })

        return dataset

    def preprocess_dataset(self, dataset):
        """
        Prepares the dataset by extracting input features and tokenizing the labels.
        """

        def prepare_dataset(batch):
            # Process audio
            audio = batch["audio"]
            batch["input_features"] = self.processor.feature_extractor(
                audio["array"], sampling_rate=audio["sampling_rate"]
            ).input_features[0]

            # Tokenize the text (labels)
            batch["labels"] = self.processor.tokenizer(batch["text"]).input_ids
            return batch

        # Process each split separately
        processed_dataset = DatasetDict()
        for split in dataset.keys():
            processed_split = dataset[split].map(
                prepare_dataset,
                remove_columns=dataset[split].column_names,
                num_proc=1,  # Adjust based on your system's capabilities
                batched=False,
            )
            processed_dataset[split] = processed_split

        return processed_dataset

    def compute_metrics(self, pred):
        """
        Compute WER (Word Error Rate) and return it.
        """
        pred_ids = pred.predictions
        label_ids = pred.label_ids

        # Replace -100 in the labels as we can't decode them
        label_ids[label_ids == -100] = self.processor.tokenizer.pad_token_id

        # Decode predictions and labels
        pred_str = self.processor.tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
        label_str = self.processor.tokenizer.batch_decode(label_ids, skip_special_tokens=True)

        # Optionally, clean up the decoded strings
        pred_str = [pred.strip() for pred in pred_str]
        label_str = [label.strip() for label in label_str]

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
            per_device_train_batch_size=64,  # Adjust based on your GPU memory
            gradient_accumulation_steps=4,  # Simulate larger batch size
            evaluation_strategy="epoch",  # Evaluate at the end of each epoch
            learning_rate=5e-5,  # Adjust learning rate if needed
            num_train_epochs=10,  # Train for 10 epochs
            warmup_steps=500,  # Gradual warmup
            predict_with_generate=True,
            generation_max_length=225,
            logging_dir="../logs/training",
            load_best_model_at_end=True,
            report_to=["tensorboard"],
            fp16=True,
            save_total_limit=2,
            save_strategy="epoch",  # Save at the end of each epoch
            metric_for_best_model="wer",
            greater_is_better=False,
            gradient_checkpointing=False,
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
            data_collator=data_collator,
            tokenizer=self.processor.tokenizer,
            compute_metrics=self.compute_metrics,
        )

        # Start training
        trainer.train()

        # Save the fine-tuned model and processor
        self.model.save_pretrained(self.final_dir)
        self.processor.save_pretrained(self.final_dir)


if __name__ == "__main__":
    model_name = "distil-whisper/distil-medium.en"
    data_dir = "../data"
    output_dir = "../models/output"
    final_dir = "../models/output/distil_medium_justin_retrained"

    print(f"CUDA Available: {torch.cuda.is_available()}")
    print(f"Number of GPUs: {torch.cuda.device_count()}")

    # Fine-tune the Whisper model
    whisper_finetuner = WhisperFineTuner(model_name, data_dir, output_dir, final_dir)
    whisper_finetuner.fine_tune()
