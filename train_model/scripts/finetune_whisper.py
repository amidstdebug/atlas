import torch
from transformers import (
    WhisperForConditionalGeneration,
    WhisperProcessor,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer
)
from optimum.bettertransformer import BetterTransformer
from datasets import load_dataset, Audio
import evaluate
import os

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
            "input_features": self.processor.feature_extractor.pad(input_features, return_tensors="pt")["input_features"],
            "labels": self.processor.tokenizer.pad({"input_ids": label_features}, return_tensors="pt").input_ids
        }
        return batch


class WhisperFineTuner:
    def __init__(self, model_name, data_dir, output_dir, final_dir, use_better_transformer=False, backend='inductor'):
        self.model_name = model_name
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.final_dir = final_dir
        self.use_better_transformer = use_better_transformer
        self.backend = backend  # Specify the backend

        # Load the processor and model
        self.processor = WhisperProcessor.from_pretrained(self.model_name)
        self.model = WhisperForConditionalGeneration.from_pretrained(self.model_name).to(
            "cuda" if torch.cuda.is_available() else "cpu")

        # Convert to BetterTransformer if requested
        if self.use_better_transformer:
            self.model = BetterTransformer.transform(self.model)

        # Freeze the encoder to speed up training and reduce memory usage
        self.model.freeze_encoder()

    def load_dataset(self):
        """
        Loads the dataset from the given path and returns a Hugging Face Dataset object.
        Assumes the dataset is organized with 'train_cleaned' and 'validation' directories containing metadata.json.
        """
        # Construct the absolute path for the train and validation metadata.json
        train_data_path = os.path.join(self.data_dir, "train_cleaned", "metadata.json")
        validation_data_path = os.path.join(self.data_dir, "validation", "metadata.json")

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
            # Extract input features using the processor
            input_features = self.processor.feature_extractor(
                batch["audio"]["array"],
                sampling_rate=batch["audio"]["sampling_rate"],
                return_tensors="pt"
            ).input_features[0]  # Remove batch dimension

            # Tokenize the labels
            with self.processor.as_target_processor():
                labels = self.processor.tokenizer(batch["text"], return_tensors="pt").input_ids[0]

            batch["input_features"] = input_features
            batch["labels"] = labels
            return batch

        # Remove unused columns to save memory
        dataset = dataset.map(
            prepare_dataset,
            remove_columns=dataset.column_names["train"],
            num_proc=4,  # Adjust based on CPU cores
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
            per_device_train_batch_size=16,  # Adjust based on GPU memory
            per_device_eval_batch_size=16,
            gradient_accumulation_steps=2,  # To simulate larger batch sizes
            evaluation_strategy="steps",
            eval_steps=500,  # Evaluate every 500 steps
            save_steps=500,  # Save every 500 steps
            learning_rate=5e-5,
            num_train_epochs=20,
            warmup_steps=500,
            predict_with_generate=True,
            generation_max_length=225,
            logging_dir=os.path.join(self.output_dir, "logs"),  # Save logs to output_dir/logs
            load_best_model_at_end=True,
            report_to=["tensorboard", "wandb"],  # Report to TensorBoard and WandB
            fp16=True,
            save_total_limit=2,
            save_strategy="steps",
            metric_for_best_model="wer",
            greater_is_better=False,
            gradient_checkpointing=True,  # Enable gradient checkpointing for memory efficiency
            remove_unused_columns=False,
            # Specify the backend for torch.compile if needed
            # This might not be directly supported in Seq2SeqTrainingArguments
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

        # Optionally compile the model with torch.compile for further optimizations
        # Note: This requires PyTorch 2.0 or higher
        try:
            import torch._dynamo as dynamo
            from torch._dynamo.backends.inductor import config as inductor_config

            # Set the backend to 'inductor'
            dynamo.config.backend = 'inductor'

            # Optionally, adjust inductor configurations if needed
            # For example:
            # inductor_config.compile_only = True

            # Compile the model
            self.model = torch.compile(self.model, backend='inductor')
            print("Model compiled with Inductor backend.")
        except Exception as e:
            print(f"Error compiling the model with Inductor: {e}")

        # Start training
        trainer.train()


        # Save the fine-tuned model and processor
        self.model.save_pretrained(self.final_dir)
        self.processor.save_pretrained(self.final_dir)


if __name__ == "__main__":
    model_name = "distil-whisper/distil-large-v3"  # Use the distil-large-v3 model
    data_dir = "../data"  # Base data directory
    output_dir = "../models/output"  # Output directory for training artifacts
    final_dir = "../models/output/final_model"  # Directory to save the final model

    use_better_transformer = True  # Set to True to enable BetterTransformer optimizations
    backend = 'inductor'  # Specify the backend

    print(f"CUDA Available: {torch.cuda.is_available()}")  # This should return True if the GPU is available
    print(f"CUDA Device Count: {torch.cuda.device_count()}")  # Check how many GPUs are available

    # Fine-tune the Whisper model
    whisper_finetuner = WhisperFineTuner(model_name, data_dir, output_dir, final_dir, use_better_transformer, backend)
    whisper_finetuner.fine_tune()
