"""
Character system removed. Stub kept for safe imports only.
"""
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Segment:
    text: str
    speaker: str = "narrator"
    character_name: Optional[str] = None
    emotion: str = "neutral"
    confidence: float = 1.0

@dataclass
class CharacterProfile:
    name: str = ""
    gender: str = "unknown"

class CharacterDetector:
    def __init__(self, *args, **kwargs):
        pass
    def analyze(self, text: str) -> List[Segment]:
        return [Segment(text=text or "", speaker="narrator")]
