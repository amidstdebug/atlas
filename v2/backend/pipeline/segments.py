from dataclasses import dataclass
import hashlib

from pyannote.core import Segment

@dataclass
class TranscribedSegment:
    segment: Segment
    label: str
    track: str
    text: str
    deprecated: bool = False

    @property
    def id(self):    
    	unique_str = f"{self.segment.start}_{self.segment.end}_{self.label}_{hash(self.text)}"
    	return hashlib.md5(unique_str.encode()).hexdigest()
