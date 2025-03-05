from dataclasses import dataclass
from typing import List, Sequence, Optional, Dict, Tuple, Set, Generator, Iterator

import ollama
from datetime import timedelta
import hashlib

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
        
        try:
            self.model_info = ollama.show(model_name)
        except Exception as e:
            if hasattr(e, 'status_code') and e.status_code == 404:
                ollama.pull(model_name)
                self.model_info = ollama.show(model_name)
            else:
                raise e
                
        self.minutes: List[MinutesSection] = []
        self._processed_segments = set()  # Track segment IDs we've already processed
        self._last_end_time = 0.0  # Track the end time of the last processed segment
    
    def _get_segment_id(self, segment):
        """Generate a unique ID for a segment based on its properties"""
        # Create a unique identifier for this segment using its properties
        unique_str = f"{segment.segment.start}_{segment.segment.end}_{segment.label}_{hash(segment.text)}"
        return hashlib.md5(unique_str.encode()).hexdigest()
    
    def _identify_new_segments(self, transcribed_segments):
        """Process transcribed segments and identify new ones that need summarization"""
        # Sort segments by start time
        sorted_segments = sorted(transcribed_segments, key=lambda x: x.segment.start)
        
        # Identify new segments that we haven't processed yet
        new_segments = []
        for segment in sorted_segments:
            segment_id = self._get_segment_id(segment)
            if segment_id not in self._processed_segments:
                new_segments.append((segment, segment_id))
        
        return new_segments
    
    def _is_new_topic(self, current_segments, new_segment):
        """Use the model to decide if a new segment should start a new topic"""
        if not current_segments:
            return False
            
        # Combine text from current segments
        current_text = " ".join([seg.text for seg, _ in current_segments if seg.text])
        
        # Get text from new segment
        new_text = new_segment.text if new_segment.text else ""
        
        # If either is empty, use timing-based decision
        if not current_text or not new_text:
            # If gap is more than 5 seconds, consider it a new topic
            return new_segment.segment.start - current_segments[-1][0].segment.end > 5.0
        
        # Ask the model if this is a new topic
        prompt = f"""
        You are analyzing conversation flow to determine topic transitions.
        Given the following two parts of a conversation, determine if the second part 
        represents a NEW TOPIC or a CONTINUATION of the current topic.
        Answer with only ONE WORD: either "NEW" or "CONTINUATION".
        
        CURRENT CONVERSATION:
        {current_text}
        
        NEW SEGMENT:
        {new_text}
        """
        
        response = ollama.chat(
            model=self.model_name, 
            messages=[{"role": "user", "content": prompt}],
        )
        
        result = response['message']['content'].strip().upper()
        return "NEW" in result
    
    def _form_topic_groups(self, new_segments_with_ids):
        """Group segments into topics using dynamic determination"""
        if not new_segments_with_ids:
            return []
            
        groups = []
        current_group = []
        
        for segment, segment_id in new_segments_with_ids:
            # If this is the first segment, start a new group
            if not current_group:
                current_group.append((segment, segment_id))
            else:
                # Check if this should be a new topic
                if self._is_new_topic(current_group, segment):
                    # Start a new group if we have enough segments
                    if len(current_group) >= 2:
                        groups.append(current_group)
                    current_group = [(segment, segment_id)]
                else:
                    # Add to current group
                    current_group.append((segment, segment_id))
        
        # Add the last group if it exists and has enough segments
        if current_group and len(current_group) >= 2:
            groups.append(current_group)
            
        return groups
    
    def _generate_section_title(self, group_segments):
        """Generate a title for a group of segments"""
        window_text = " ".join(segment.text for segment, _ in group_segments if segment.text)
        
        prompt = f"""
        Based on this conversation segment, provide a brief, descriptive title (5 words max) 
        for what's being discussed. Don't use quotes in your response:
        
        {window_text}
        """
        
        response = ollama.chat(model=self.model_name, messages=[
            {"role": "user", "content": prompt}
        ])
        topic_title = response['message']['content'].strip()
        
        # Limit to first 5 words if longer
        return " ".join(topic_title.split()[:5])
    
    def _generate_section_summary(self, group_segments):
        """Generate a summary for a group of segments"""
        segments_text = "\n".join([f"{segment.label}: {segment.text}" 
                                 for segment, _ in group_segments if segment.text])
        
        if not segments_text.strip():
            return "No transcription available for this segment."
        
        prompt = f"""
        Summarize the key points and decisions from this conversation segment in a professional manner.
        Include any decisions made, action items, or important information shared.
        Keep the summary concise (2-3 paragraphs maximum):
        
        {segments_text}
        """
        
        response = ollama.chat(model=self.model_name, messages=[
            {"role": "user", "content": prompt}
        ])
        
        return response['message']['content'].strip()
    
    def _generate_section_summary_streaming(self, group_segments) -> Generator[str, None, None]:
        """Generate a summary for a group of segments with streaming response"""
        segments_text = "\n".join([f"{segment.label}: {segment.text}" 
                                 for segment, _ in group_segments if segment.text])
        
        if not segments_text.strip():
            yield "No transcription available for this segment."
            return
        
        prompt = f"""
        Summarize the key points and decisions from this conversation segment in a professional manner.
        Include any decisions made, action items, or important information shared.
        Keep the summary concise (2-3 paragraphs maximum):
        
        {segments_text}
        """
        
        stream = ollama.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        
        for chunk in stream:
            if 'message' in chunk and 'content' in chunk['message']:
                yield chunk['message']['content']
    
    def _update_minutes(self, new_segments_with_ids):
        """Update minutes with new segments"""
        groups = self._form_topic_groups(new_segments_with_ids)
        
        for group in groups:
            segments, segment_ids = zip(*group) if group else ([], [])
            
            # Generate title and summary
            topic_title = self._generate_section_title(group)
            description = self._generate_section_summary(group)
            
            # Create minutes section
            section = MinutesSection(
                title=topic_title,
                description=description,
                speakers=list(set(segment.label for segment, _ in group)),
                start=segments[0].segment.start,
                end=segments[-1].segment.end,
                segment_ids=list(segment_ids)
            )
            
            self.minutes.append(section)
            
            # Mark segments as processed
            self._processed_segments.update(segment_ids)
            
            # Update last end time
            self._last_end_time = max(self._last_end_time, section.end)
        
        # Sort minutes by start time
        self.minutes.sort(key=lambda x: x.start)
    
    def __call__(self, transcribed_segments) -> List[MinutesSection]:
        """Process new segments and update minutes"""
        if not transcribed_segments:
            return self.minutes
        
        # Process segments to identify new ones
        new_segments_with_ids = self._identify_new_segments(transcribed_segments)
        
        # Update minutes with new segments
        self._update_minutes(new_segments_with_ids)
        
        return self.minutes
    
    def stream_minutes(self, transcribed_segments) -> Iterator[Dict]:
        """Stream minutes as they're being generated"""
        if not transcribed_segments:
            yield {"type": "complete", "data": self.minutes}
            return
            
        # Process segments to identify new ones
        new_segments_with_ids = self._identify_new_segments(transcribed_segments)
        
        # Group into topics
        groups = self._form_topic_groups(new_segments_with_ids)
        
        for group in groups:
            segments, segment_ids = zip(*group) if group else ([], [])
            
            # Generate title
            yield {"type": "status", "message": "Generating title..."}
            topic_title = self._generate_section_title(group)
            yield {"type": "title", "title": topic_title}
            
            # Generate summary with streaming
            yield {"type": "status", "message": "Generating summary..."}
            
            # Start a new section
            section = MinutesSection(
                title=topic_title,
                description="",  # Will be filled as we stream
                speakers=list(set(segment.label for segment, _ in group)),
                start=segments[0].segment.start,
                end=segments[-1].segment.end,
                segment_ids=list(segment_ids)
            )
            
            # Stream the summary generation
            full_summary = ""
            for summary_chunk in self._generate_section_summary_streaming(group):
                full_summary += summary_chunk
                yield {"type": "summary_chunk", "chunk": summary_chunk, "section_id": id(section)}
            
            # Complete the section with the full summary
            section.description = full_summary
            
            # Add to minutes
            self.minutes.append(section)
            
            # Mark segments as processed
            self._processed_segments.update(segment_ids)
            
            yield {"type": "section_complete", "section": section}
        
        # Sort minutes by start time
        self.minutes.sort(key=lambda x: x.start)
        
        # Signal completion
        yield {"type": "complete", "data": self.minutes}
    
    def format_minutes(self) -> str:
        """Format minutes into a readable text document."""
        if not self.minutes:
            return "No minutes available. Please process conversation data first."
            
        result = "# Meeting Minutes\n\n"
        
        for section in self.minutes:
            # Format time as MM:SS
            start_time = str(timedelta(seconds=int(section.start))).split(":", 1)[1]
            end_time = str(timedelta(seconds=int(section.end))).split(":", 1)[1]
            
            result += f"## {section.title} ({start_time} - {end_time})\n\n"
            result += f"**Participants**: {', '.join(section.speakers)}\n\n"
            result += section.description + "\n\n"
            
        return result
    
    def reset(self):
        """Reset the pipeline state."""
        self.minutes = []
        self._processed_segments = set()
        self._last_end_time = 0.0