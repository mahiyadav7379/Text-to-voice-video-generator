"""
Story Processing Pipeline (simplified – single voice preset for entire story).
TEXT → Validate → Hinglish → Emotion → Voice Preset → Smart Chunk → TTS
"""

from typing import List, Dict, Any
from dataclasses import dataclass
from .chunking import SmartChunker, get_dynamic_chunk_size
from .emotion import EmotionDetector
from .hinglish import HinglishProcessor
from .voice_mapper import VoiceMapper, resolve_preset


@dataclass
class PipelineConfig:
    mode: str = "normal"  # normal | story
    max_chars: int = 50000
    hinglish: bool = False
    voice_gender: str = "female"  # male | female
    voice_preset: str = "female_normal"
    global_emotion: str = "neutral"
    emotion_intensity: str = "medium"
    auto_emotion: bool = True
    legacy_speed: str = "Normal"
    quality: str = "high"
    pitch: float = 0.0
    # legacy compat
    voice: str = ""


@dataclass
class PreparedChunk:
    text: str
    voice_params: Dict[str, Any]
    emotion: str
    index: int


class StoryPipeline:
    def __init__(self):
        self.chunker = SmartChunker()
        self.emotion_detector = EmotionDetector()
        self.hinglish = HinglishProcessor()
        self.voice_mapper = VoiceMapper()

    def prepare(self, text: str, config: PipelineConfig) -> List[PreparedChunk]:
        text = (text or "").strip()
        if not text:
            raise ValueError("Empty text")
        if len(text) > config.max_chars:
            raise ValueError(f"Text exceeds {config.max_chars} characters")

        text, _ = self.hinglish.process(text, enabled=config.hinglish)

        # Resolve single preset for entire story
        preset_key = config.voice_preset or ""
        if not preset_key and config.voice:
            preset_key = config.voice  # may be legacy label
        gender = config.voice_gender or "female"

        target_size = get_dynamic_chunk_size(len(text))
        raw_chunks = self.chunker.split(text, target_size)
        if not raw_chunks:
            raise ValueError("No processable chunks produced")

        prepared: List[PreparedChunk] = []
        for i, chunk_text in enumerate(raw_chunks):
            emotion = config.global_emotion
            if config.auto_emotion and config.mode == "story":
                detected = self.emotion_detector.detect(chunk_text, default=config.global_emotion)
                if detected.confidence >= 0.35:
                    emotion = detected.emotion

            params = self.voice_mapper.build_params(
                preset_key=preset_key,
                gender=gender,
                emotion=emotion,
                intensity=config.emotion_intensity,
                pitch_slider=config.pitch,
                legacy_voice=config.voice if config.voice else "",
                legacy_speed=config.legacy_speed if config.mode == "normal" else "",
            )
            prepared.append(PreparedChunk(
                text=chunk_text,
                voice_params=params,
                emotion=emotion,
                index=i,
            ))
        return prepared
