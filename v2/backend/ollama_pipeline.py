from dataclasses import dataclass
from typing import List, Sequence, Optional, Dict, Tuple, Set, Generator, Iterator, Callable
import logging
import ollama
from datetime import timedelta
import hashlib
import json


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("minutes_pipeline.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MinutesPipeline")

@dataclass
class MinutesSection:
    title: str
    description: str
    speakers: List[str]
    start: float
    end: float
    segment_ids: List[str]  # Store IDs of segments included in this section

def get_segment_id(segment):
	"""Generate a unique ID for a segment based on its properties"""
	# Create a unique identifier for this segment using its properties
	unique_str = f"{segment.segment.start}_{segment.segment.end}_{segment.label}_{hash(segment.text)}"
	return hashlib.md5(unique_str.encode()).hexdigest()

class MinutesPipeline:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model_info = None
        
        logger.info(f"Initializing MinutesPipeline with model: {model_name}")
        
        try:
            self.model_info = ollama.show(model_name)
            logger.info(f"Model info: {self.model_info}")
        except Exception as e:
            if hasattr(e, 'status_code') and e.status_code == 404:
                logger.warning(f"Model {model_name} not found. Pulling it now...")
                ollama.pull(model_name)
                self.model_info = ollama.show(model_name)
                logger.info(f"Model pulled successfully. Info: {self.model_info}")
            else:
                logger.error(f"Error initializing model: {str(e)}")
                raise e
                
        self.minutes: List[MinutesSection] = []
        self._processed_segments = set()  # Track segment IDs we've already processed
        self._last_end_time = 0.0  # Track the end time of the last processed segment
    
    def _identify_all_segments(self, transcribed_segments):
        """Process all transcribed segments"""
        logger.info(f"Identifying all segments from {len(transcribed_segments)} transcribed segments")
        
        # Sort segments by start time
        sorted_segments = sorted(transcribed_segments, key=lambda x: x.segment.start)
        
        # Generate IDs for all segments
        segments_with_ids = [(segment, get_segment_id(segment)) for segment in sorted_segments]
        
        logger.debug(f"Generated IDs for {len(segments_with_ids)} segments")
        return segments_with_ids
    
    def generate_minutes_with_progress(self, transcribed_segments, progress_callback: Callable) -> List[MinutesSection]:
        """Process all segments to create minutes with progress updates"""
        if not transcribed_segments:
            logger.error("No transcription data available")
            progress_callback({"type": "error", "message": "No transcription data available"})
            return self.minutes
        
        try:
            # Log start time and segment count
            segment_count = len(transcribed_segments)
            logger.info(f"Starting minutes generation with progress tracking for {segment_count} segments")
            
            # Inform about starting the process
            progress_callback({"type": "status", "message": "Starting minutes generation..."})
            
            # Process all segments
            progress_callback({"type": "status", "message": "Processing transcript segments..."})
            segments_with_ids = self._identify_all_segments(transcribed_segments)
                        
            # Completion notification
            logger.info(f"Minutes generation complete - {len(self.minutes)} sections created")
            progress_callback({"type": "complete", "message": "Minutes generation complete"})
            
            return self.minutes
            
        except Exception as e:
            logger.error(f"Error generating minutes: {str(e)}", exc_info=True)
            progress_callback({"type": "error", "message": f"Error generating minutes: {str(e)}"})
            raise
			
    def _make_model_call(self, prompt, prompt_type, log_input=True, truncate_input=1000):
        """Make a model call with proper logging of inputs and outputs"""
        # Log the input prompt (optionally truncated)
        if log_input:
            log_prompt = prompt
            if len(log_prompt) > truncate_input:
                log_prompt = log_prompt[:truncate_input] + "... [truncated]"
            logger.info(f"Model input for {prompt_type}: {log_prompt}")
        
        # Make the actual model call
        try:
            response = ollama.chat(
                model=self.model_name, 
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Log the response details
            self.log_model_response(response, prompt_type)
            
            return response
        except Exception as e:
            logger.error(f"Error in model call for {prompt_type}: {str(e)}", exc_info=True)
            raise
			
    def __call__(self, transcribed_segments) -> List[MinutesSection]:
        """Process all segments to create minutes in one go."""
        pass
    
    def format_minutes(self) -> str:
        """Format minutes into a readable text document."""
        pass
    
    def reset(self):
        """Reset the pipeline state."""
        self.minutes = []
        self._processed_segments = set()
        self._last_end_time = 0.0