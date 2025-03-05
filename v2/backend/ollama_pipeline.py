from dataclasses import dataclass
from typing import List, Sequence, Optional, Dict, Tuple, Set, Generator, Iterator, Callable
import logging
import ollama
from datetime import timedelta
import hashlib
import json

from prompts import (
    TOPICAL_SEGMENTATION_PROMPT,
    SECTION_TITLE_PROMPT,
    SECTION_SUMMARY_PROMPT
)

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
    
    def _get_segment_id(self, segment):
        """Generate a unique ID for a segment based on its properties"""
        # Create a unique identifier for this segment using its properties
        unique_str = f"{segment.segment.start}_{segment.segment.end}_{segment.label}_{hash(segment.text)}"
        return hashlib.md5(unique_str.encode()).hexdigest()
    
    def _identify_all_segments(self, transcribed_segments):
        """Process all transcribed segments"""
        logger.info(f"Identifying all segments from {len(transcribed_segments)} transcribed segments")
        
        # Sort segments by start time
        sorted_segments = sorted(transcribed_segments, key=lambda x: x.segment.start)
        
        # Generate IDs for all segments
        segments_with_ids = []
        for segment in sorted_segments:
            segment_id = self._get_segment_id(segment)
            segments_with_ids.append((segment, segment_id))
        
        logger.debug(f"Generated IDs for {len(segments_with_ids)} segments")
        return segments_with_ids
    
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
    
    def _topical_segmentation(self, segments_with_ids, progress_callback=None):
        """Group segments into coherent topics based on content analysis"""
        if not segments_with_ids:
            logger.warning("No segments provided for topical segmentation")
            return []
        
        if progress_callback:
            progress_callback({"type": "status", "message": "Analyzing conversation for topic segmentation..."})
            
        # Extract just the text for segmentation analysis
        segments_text = []
        for segment, _ in segments_with_ids:
            if segment.text and segment.text.strip():
                segments_text.append(segment.text)
        
        # If not enough text, just return all segments as one group
        if len(segments_text) < 3:
            logger.info("Not enough content for segmentation, treating as single topic")
            if progress_callback:
                progress_callback({"type": "status", "message": "Not enough content for segmentation, treating as single topic"})
            return [segments_with_ids]
            
        # Combine all text for the LLM to analyze
        full_text = "\n".join([f"{i+1}. {text}" for i, text in enumerate(segments_text)])
        
        # Ask the LLM to identify coherent topic segments
        prompt = TOPICAL_SEGMENTATION_PROMPT.format(full_text=full_text)
        
        if progress_callback:
            progress_callback({"type": "status", "message": "Analyzing transcript to identify distinct topics..."})
            
        # Use the helper method for model call with full logging
        logger.info(f"Sending topical segmentation prompt to model for {len(segments_text)} text segments")
        response = self._make_model_call(prompt, "topical_segmentation")
        
        result = response['message']['content'].strip()
        
        # Log the structured result for analysis
        logger.info(f"Model identified segment structure: {result}")
        
        # Parse the segmentation result
        topic_groups = []
        try:
            # Extract segment ranges from the response
            segments = []
            for line in result.split("\n"):
                if ":" in line and "-" in line:
                    try:
                        # Extract the segment number and range
                        segment_num = int(line.split(":", 1)[0].strip())
                        range_part = line.split(":", 1)[1].strip()
                        
                        # Handle different formats: "1-5" or "[1]-[5]"
                        if "[" in range_part:
                            # Handle "[start]-[end]" format
                            start_str = range_part.split("]-[")[0].strip("[")
                            end_str = range_part.split("]-[")[1].strip("]")
                            start, end = int(start_str), int(end_str)
                        else:
                            # Handle "start-end" format
                            start, end = map(int, range_part.split("-"))
                        
                        # Validate the range (must be reasonable)
                        if 1 <= start <= end <= len(segments_text) and end - start <= len(segments_text):
                            segments.append((start-1, end-1))  # Convert to 0-indexed
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Could not parse segment line: '{line}'. Error: {str(e)}")
                        continue
            
            # Check if the segments make sense
            if not segments:
                logger.warning("No valid segments parsed from model response")
                return [segments_with_ids]
                
            # Check if we just have tiny segments (model might be chunking arbitrarily)
            avg_segment_size = sum(end - start + 1 for start, end in segments) / len(segments)
            if len(segments) > 10 and avg_segment_size < 5:
                logger.warning(f"Detected potential arbitrary chunking: {len(segments)} segments with avg size {avg_segment_size}")
                
                # Try to merge small segments into larger logical groups
                # Simple approach: aim for 3-7 segments by merging adjacent ones
                target_segments = min(max(3, len(segments) // 5), 7)
                if len(segments) > target_segments and target_segments > 0:
                    logger.info(f"Merging {len(segments)} small segments into {target_segments} larger segments")
                    
                    # Group segments into target_segments groups
                    merged_segments = []
                    segments_per_group = len(segments) // target_segments
                    remainder = len(segments) % target_segments
                    
                    start_idx = 0
                    for i in range(target_segments):
                        # Add an extra segment to the first 'remainder' groups
                        count = segments_per_group + (1 if i < remainder else 0)
                        end_idx = start_idx + count - 1
                        
                        if end_idx < len(segments):
                            # Merge this group of segments
                            start = segments[start_idx][0]
                            end = segments[end_idx][1]
                            merged_segments.append((start, end))
                            
                        start_idx += count
                    
                    segments = merged_segments
                    logger.info(f"After merging: {len(segments)} segments")
            
            logger.info(f"Found {len(segments)} valid topic segments in conversation")
            if progress_callback:
                progress_callback({
                    "type": "status", 
                    "message": f"Found {len(segments)} topic segments in conversation"
                })
                
            # Map the segmented indices back to the original transcript segments
            current_text_index = 0
            text_to_segment_map = {}
            
            for i, (segment, _) in enumerate(segments_with_ids):
                if segment.text and segment.text.strip():
                    text_to_segment_map[current_text_index] = i
                    current_text_index += 1
            
            # Group the segments according to the segmentation
            for start_text, end_text in segments:
                group = []
                
                # Map text indices to segment indices
                start_idx = text_to_segment_map.get(start_text, 0)
                end_idx = text_to_segment_map.get(end_text, len(segments_with_ids)-1)
                
                # Add segments from this range
                for i in range(start_idx, min(end_idx+1, len(segments_with_ids))):
                    group.append(segments_with_ids[i])
                
                if group:
                    topic_groups.append(group)
            
            # If no groups were created, use the entire transcript
            if not topic_groups:
                logger.warning("No topic groups created from segmentation, treating as single topic")
                if progress_callback:
                    progress_callback({"type": "status", "message": "Segmentation failed, treating as single topic"})
                return [segments_with_ids]
                
            logger.info(f"Successfully created {len(topic_groups)} topic groups")
            return topic_groups
            
        except Exception as e:
            # If parsing fails, just return all segments as one group
            logger.error(f"Error in segmentation: {str(e)}, treating as single topic", exc_info=True)
            if progress_callback:
                progress_callback({"type": "status", "message": f"Error in segmentation: {str(e)}, treating as single topic"})
            return [segments_with_ids]
    
    def _generate_section_title(self, group_segments, progress_callback=None, index=0, total=1):
        """Generate a title for a group of segments"""
        if progress_callback:
            progress_callback({
                "type": "status", 
                "message": f"Generating title for section {index+1}/{total}..."
            })
        
        # Log input segment count and sample    
        logger.info(f"Generating title for section {index+1}/{total} with {len(group_segments)} segments")
        
        window_text = " ".join(segment.text for segment, _ in group_segments if segment.text)
        
        # Truncate window_text for logging to avoid huge log entries
        log_text = window_text[:500] + "..." if len(window_text) > 500 else window_text
        logger.debug(f"Section content sample: {log_text}")
        
        prompt = SECTION_TITLE_PROMPT.format(window_text=window_text)
        
        # Use the helper method for model call with full logging
        response = self._make_model_call(prompt, f"section_title_{index+1}")
        topic_title = response['message']['content'].strip()
        
        # Limit to first 5 words if longer
        title = " ".join(topic_title.split()[:5])
        logger.info(f"Generated title: {title}")
        
        if progress_callback:
            progress_callback({
                "type": "title_generated", 
                "title": title,
                "section_index": index
            })
            
        return title
        
    def _generate_section_summary(self, group_segments, progress_callback=None, index=0, total=1):
        """Generate a summary for a group of segments"""
        if progress_callback:
            progress_callback({
                "type": "status", 
                "message": f"Generating summary for section {index+1}/{total}..."
            })
            
        segments_text = "\n".join([f"{segment.label}: {segment.text}" 
                                 for segment, _ in group_segments if segment.text])
        
        if not segments_text.strip():
            logger.warning(f"No transcription available for section {index+1}")
            return "No transcription available for this segment."
        
        # Truncate segments_text for logging to avoid huge log entries
        log_text = segments_text[:500] + "..." if len(segments_text) > 500 else segments_text
        logger.debug(f"Section content to summarize (sample): {log_text}")
        
        prompt = SECTION_SUMMARY_PROMPT.format(segments_text=segments_text)
        
        logger.info(f"Generating summary for section {index+1}/{total}")
        
        # Use the helper method for model call with full logging
        response = self._make_model_call(prompt, f"section_summary_{index+1}")
        summary = response['message']['content'].strip()
        
        # Log a truncated version of the summary for debugging
        summary_preview = summary[:500] + "..." if len(summary) > 500 else summary
        logger.debug(f"Generated summary (preview): {summary_preview}")
        
        if progress_callback:
            progress_callback({
                "type": "summary_generated", 
                "summary": summary,
                "section_index": index
            })
            
        return summary
    
    def _create_minutes_sections(self, groups, progress_callback=None):
        """Create MinutesSection objects from topic groups"""
        sections = []
        total_groups = len(groups)
        
        logger.info(f"Creating {total_groups} minutes sections")
        
        if progress_callback:
            progress_callback({
                "type": "status", 
                "message": f"Generating content for {total_groups} sections..."
            })
        
        for i, group in enumerate(groups):
            segments, segment_ids = zip(*group) if group else ([], [])
            
            # Generate title and summary
            topic_title = self._generate_section_title(group, progress_callback, i, total_groups)
            description = self._generate_section_summary(group, progress_callback, i, total_groups)
            
            # Create minutes section
            section = MinutesSection(
                title=topic_title,
                description=description,
                speakers=list(set(segment.label for segment, _ in group)),
                start=segments[0].segment.start,
                end=segments[-1].segment.end,
                segment_ids=list(segment_ids)
            )
            
            sections.append(section)
            logger.info(f"Created section {i+1}/{total_groups}: {topic_title}")
            
            if progress_callback:
                progress_callback({
                    "type": "section_complete", 
                    "section": section,
                    "section_index": i,
                    "total_sections": total_groups,
                    "progress_percentage": ((i+1) / total_groups) * 100
                })
            
            # Mark segments as processed
            self._processed_segments.update(segment_ids)
            
            # Update last end time
            self._last_end_time = max(self._last_end_time, section.end)
        
        # Sort minutes by start time
        sections.sort(key=lambda x: x.start)
        logger.info(f"Completed creating and sorting {len(sections)} minutes sections")
        return sections
    
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
            
            # Group segments into topics
            topic_groups = self._topical_segmentation(segments_with_ids, progress_callback)
            
            # Create minutes sections
            self.minutes = self._create_minutes_sections(topic_groups, progress_callback)
            
            # Completion notification
            logger.info(f"Minutes generation complete - {len(self.minutes)} sections created")
            progress_callback({"type": "complete", "message": "Minutes generation complete"})
            
            return self.minutes
            
        except Exception as e:
            logger.error(f"Error generating minutes: {str(e)}", exc_info=True)
            progress_callback({"type": "error", "message": f"Error generating minutes: {str(e)}"})
            raise
    
    def __call__(self, transcribed_segments) -> List[MinutesSection]:
        """Process all segments to create minutes in one go"""
        if not transcribed_segments:
            logger.warning("No transcription data available for processing")
            return self.minutes
        
        logger.info(f"Processing {len(transcribed_segments)} transcript segments in one go")
        
        # Process all segments
        segments_with_ids = self._identify_all_segments(transcribed_segments)
        
        # Group segments into topics
        topic_groups = self._topical_segmentation(segments_with_ids)
        
        # Create minutes sections
        self.minutes = self._create_minutes_sections(topic_groups)
        
        logger.info(f"Generated {len(self.minutes)} minutes sections")
        return self.minutes
    
    def format_minutes(self) -> str:
        """Format minutes into a readable text document."""
        if not self.minutes:
            logger.warning("No minutes available for formatting")
            return "No minutes available. Please process conversation data first."
            
        logger.info("Formatting minutes for display")
        result = "# Meeting Minutes\n\n"
        
        for section in self.minutes:
            # Format time as MM:SS
            start_time = str(timedelta(seconds=int(section.start))).split(":", 1)[1]
            end_time = str(timedelta(seconds=int(section.end))).split(":", 1)[1]
            
            result += f"## {section.title} ({start_time} - {end_time})\n\n"
            result += f"**Participants**: {', '.join(section.speakers)}\n\n"
            result += section.description + "\n\n"
            
        logger.debug(f"Formatted minutes: {result[:500]}...")  # Log first 500 chars
        return result
    
    def reset(self):
        """Reset the pipeline state."""
        logger.info("Resetting pipeline state")
        self.minutes = []
        self._processed_segments = set()
        self._last_end_time = 0.0

    def log_model_response(self, model_response, prompt_type, truncate_length=10_000):
        """Helper method to log model responses in a consistent format."""
        try:
            # Extract content
            content = model_response['message']['content']
            
            # Truncate for logging if necessary
            if len(content) > truncate_length:
                content_log = content[:truncate_length] + "... [truncated]"
            else:
                content_log = content
                
            # Log in a structured way
            log_data = {
                "prompt_type": prompt_type,
                "model": self.model_name,
                "response_preview": content_log,
                "response_length": len(content),
                "total_tokens": model_response.get('total_tokens', None)
            }
            
            logger.info(f"Model response for {prompt_type}: {json.dumps(log_data)}")
            
        except Exception as e:
            logger.error(f"Error logging model response: {str(e)}")