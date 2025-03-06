import os
import json
import time
import logging
import argparse
from pathlib import Path

import numpy as np
import torch
import torchaudio

from diart_pipeline import OnlinePipeline, OnlinePipelineConfig, LD_LIBRARY_PATH
from ollama_pipeline import MinutesPipeline

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("audio_processing.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("audio_processor")

class AudioFileProcessor:
    def __init__(self, model_name="phi4:latest"):
        logger.info("Initializing AudioFileProcessor")
        start_time = time.time()
        
        # Initialize the diarization pipeline
        config = OnlinePipelineConfig()
        self.pipeline = OnlinePipeline(config)
        
        # Initialize the minutes pipeline
        self.minutes_pipeline = MinutesPipeline(model_name)
        
        # Default parameters
        self.chunk_size = 2 * 16000  # 2 seconds at 16kHz
        
        logger.info(f"AudioFileProcessor initialized in {time.time() - start_time:.2f}s")
    
    def process_audio_file(self, audio_file_path, chunk_size_seconds=2, simulate_streaming=True):
        """
        Process an audio file and generate meeting minutes.
        
        Args:
            audio_file_path: Path to the audio file
            chunk_size_seconds: Size of each chunk in seconds
            simulate_streaming: If True, process the audio in chunks to simulate streaming
        
        Returns:
            Generated meeting minutes
        """
        logger.info(f"Processing audio file: {audio_file_path}")
        start_time = time.time()
        
        # Load the audio file
        waveform, sample_rate = torchaudio.load(audio_file_path)
        
        # Convert to mono if needed
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        
        # Resample if needed
        target_sample_rate = self.pipeline.pipeline.config.sample_rate
        if sample_rate != target_sample_rate:
            logger.info(f"Resampling audio from {sample_rate}Hz to {target_sample_rate}Hz")
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=target_sample_rate)
            waveform = resampler(waveform)
            sample_rate = target_sample_rate
        
        # Convert to numpy array
        waveform_np = waveform.squeeze().numpy()
        
        logger.info(f"Audio loaded: {len(waveform_np) / sample_rate:.2f} seconds at {sample_rate}Hz")
        
        # Reset pipeline for fresh processing
        self.pipeline.reset()
        
        # Process audio in chunks (to simulate streaming) or all at once
        if simulate_streaming:
            chunk_size = int(chunk_size_seconds * sample_rate)
            num_chunks = int(np.ceil(len(waveform_np) / chunk_size))
            
            logger.info(f"Processing audio in {num_chunks} chunks of {chunk_size_seconds}s each")
            
            for i in range(num_chunks):
                start_idx = i * chunk_size
                end_idx = min(start_idx + chunk_size, len(waveform_np))
                chunk = waveform_np[start_idx:end_idx]
                
                # Process the chunk
                chunk_start_time = time.time()
                # Add channel dimension
                chunk = np.expand_dims(chunk, 1)
                self.pipeline(chunk, sample_rate)
                
                # Transcribe periodically as in the streaming version
                if (i + 1) % 2 == 0 or i == num_chunks - 1:  # Every 2 chunks or at the end
                    self.pipeline.transcribe()
                
                logger.info(f"Processed chunk {i+1}/{num_chunks} in {time.time() - chunk_start_time:.2f}s")
        else:
            # Process the entire audio at once
            logger.info("Processing the entire audio at once")
            waveform_np = np.expand_dims(waveform_np, 1)
            self.pipeline(waveform_np, sample_rate)
            self.pipeline.transcribe()
        
        # Get the final transcription
        transcripts = self.pipeline.get_transcription()
        logger.info(f"Found {len(transcripts)} transcript segments")
        
        if not transcripts:
            logger.warning("No transcripts found. Cannot generate minutes.")
            return None
        
        # Display transcript for debugging
        for t in transcripts:
            logger.info(f"Speaker {t.label}: {t.segment.start:.2f}s-{t.segment.end:.2f}s: {t.text}")
        
        # Generate minutes
        logger.info("Generating meeting minutes...")
        minutes_start_time = time.time()
        
        # Progress callback function
        def progress_callback(update):
            logger.info(f"Minutes progress: {update.get('type', 'unknown')} - {update.get('message', '')}")
        
        self.minutes_pipeline.generate_minutes_with_progress(transcripts, progress_callback)
        
        logger.info(f"Minutes generated in {time.time() - minutes_start_time:.2f}s")
        
        # Format the minutes
        minutes_text = self.minutes_pipeline.format_minutes()
        
        # Format JSON output
        minutes_data = {
            "minutes_text": minutes_text,
            "sections": [
                {
                    "title": section.title,
                    "description": section.description,
                    "speakers": section.speakers,
                    "start": section.start,
                    "end": section.end
                }
                for section in self.minutes_pipeline.minutes
            ],
            "processing_time": time.time() - start_time
        }
        
        logger.info(f"Audio processing complete in {time.time() - start_time:.2f}s")
        return minutes_data
    
    def save_minutes(self, minutes_data, output_path):
        """Save the generated minutes to a file."""
        output_file = Path(output_path)
        
        # Save as JSON
        with open(output_file.with_suffix('.json'), 'w') as f:
            json.dump(minutes_data, f, indent=2)
        
        # Save as text
        with open(output_file.with_suffix('.txt'), 'w') as f:
            f.write(minutes_data["minutes_text"])
        
        logger.info(f"Minutes saved to {output_file.with_suffix('.json')} and {output_file.with_suffix('.txt')}")

def main():
    print(LD_LIBRARY_PATH)
    os.environ["LD_LIBRARY_PATH"] = LD_LIBRARY_PATH
    time.sleep(5)
    
    parser = argparse.ArgumentParser(description="Process an audio file and generate meeting minutes")
    parser.add_argument("audio_file", help="Path to the audio file to process")
    parser.add_argument("--output", "-o", default="meeting_minutes", help="Base filename for output files")
    parser.add_argument("--chunk-size", "-c", type=float, default=2.0, help="Chunk size in seconds")
    parser.add_argument("--model", "-m", default="phi4:latest", help="Model name for the minutes generation")
    parser.add_argument("--no-streaming", action="store_true", help="Process the entire audio at once instead of simulating streaming")
    
    args = parser.parse_args()
    
    try:
        # Initialize the processor
        processor = AudioFileProcessor(model_name=args.model)
        
        # Process the audio file
        minutes_data = processor.process_audio_file(
            args.audio_file,
            chunk_size_seconds=args.chunk_size,
            simulate_streaming=not args.no_streaming
        )
        
        if minutes_data:
            # Save the minutes
            processor.save_minutes(minutes_data, args.output)
            
            # Print a summary
            print("\n===== Meeting Minutes Summary =====")
            print(f"Total sections: {len(minutes_data['sections'])}")
            for i, section in enumerate(minutes_data['sections']):
                print(f"\nSection {i+1}: {section['title']}")
                print(f"  Speakers: {', '.join(section['speakers'])}")
                print(f"  Timespan: {section['start']:.2f}s - {section['end']:.2f}s")
            
            print(f"\nFull minutes saved to {args.output}.txt")
            print(f"JSON data saved to {args.output}.json")
        else:
            print("Failed to generate minutes: no transcripts found")
    
    except Exception as e:
        logger.error(f"Error processing audio file: {e}", exc_info=True)
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()