"""
Emotion Detection + Mapping Engine.
Maps detected / selected emotions to TTS parameters (rate, pitch, pause hints).
Edge-TTS has no native emotion tags – we approximate via rate & pitch.
"""

import re
from dataclasses import dataclass
from typing import Dict, Tuple, Optional


# Supported emotion categories
EMOTIONS = [
    'neutral', 'happy', 'sad', 'angry', 'surprised',
    'calm', 'romantic', 'concerned', 'intense', 'soft',
]

# Keyword → emotion (Hindi + English / Hinglish)
EMOTION_KEYWORDS: Dict[str, list] = {
    'happy': [
        r'खुश', r'खुशी', r'हँसी', r'मुस्कुरा', r'आनंद', r'मज़ा', r'उत्साह',
        r'happy', r'joy', r'smile', r'laugh', r'excited', r'glad', r'wonderful',
        r'बहुत अच्छा', r'शानदार', r'वाह',
    ],
    'sad': [
        r'उदास', r'दुखी', r'रोने', r'आँसू', r'दर्द', r'गम', r'निराश',
        r'sad', r'cry', r'tear', r'pain', r'sorrow', r'depressed', r'lonely',
        r'मुझे बुरा', r'तोड़ दिया',
    ],
    'angry': [
        r'गुस्सा', r'क्रोध', r'चिढ़', r'नाराज़', r'झगड़ा', r'चिल्ला',
        r'angry', r'mad', r'furious', r'rage', r'hate', r'annoyed',
        r'क्यों', r'झूठ', r'धोखा',
    ],
    'surprised': [
        r'हैरान', r'आश्चर्य', r'चौंक', r'अचानक', r'वाकई', r'सच\?',
        r'surprised', r'wow', r'amazing', r'shocked', r'really\?',
    ],
    'calm': [
        r'शांत', r'आराम', r'धीमा', r'सुकून', r'प्रशांत',
        r'calm', r'peaceful', r'relax', r'quiet',
    ],
    'romantic': [
        r'प्यार', r'मोहब्बत', r'इश्क', r'दिल', r'रोमांस', r'याद करती', r'याद करता',
        r'love', r'romantic', r'heart', r'miss you', r'beautiful', r'खूबसूरत',
        r'तुमसे मिलकर', r'तुम्हें चाहता', r'तुम्हें चाहती',
    ],
    'concerned': [
        r'चिंता', r'डर', r'फिक्र', r'परेशान', r'डर लग',
        r'worried', r'afraid', r'scared', r'concern', r'anxious', r'fear',
    ],
    'intense': [
        r'तीव्र', r'जोर', r'तेज़', r'गंभीर', r'जोरदार',
        r'intense', r'serious', r'strong', r'powerful',
    ],
    'soft': [
        r'नरम', r'कोमल', r'धीरे', r'हल्के',
        r'soft', r'gentle', r'tender', r'whisper',
    ],
}


@dataclass
class EmotionResult:
    emotion: str
    confidence: float
    intensity: str = 'medium'  # low | medium | high


# Mapping: emotion → (rate_delta %, pitch_delta Hz-ish, style_hint)
# Values are relative adjustments applied on top of base voice settings.
EMOTION_MAP: Dict[str, Dict] = {
    'neutral':   {'rate': 0,   'pitch': 0,   'style': 'normal'},
    'happy':     {'rate': 8,   'pitch': 15,  'style': 'conversational'},
    'sad':       {'rate': -12, 'pitch': -20, 'style': 'soft'},
    'angry':     {'rate': 12,  'pitch': 10,  'style': 'intense'},
    'surprised': {'rate': 15,  'pitch': 25,  'style': 'emotional'},
    'calm':      {'rate': -8,  'pitch': -5,  'style': 'soft'},
    'romantic':  {'rate': -6,  'pitch': 5,   'style': 'emotional'},
    'concerned': {'rate': -5,  'pitch': -10, 'style': 'soft'},
    'intense':   {'rate': 10,  'pitch': 8,   'style': 'narrative'},
    'soft':      {'rate': -10, 'pitch': -8,  'style': 'soft'},
}

INTENSITY_SCALE = {
    'low': 0.4,
    'medium': 1.0,
    'high': 1.6,
}


class EmotionDetector:
    """Keyword + pattern based emotion detection with confidence."""

    def detect(self, text: str, default: str = 'neutral') -> EmotionResult:
        if not text or not text.strip():
            return EmotionResult(emotion=default, confidence=0.0)

        scores: Dict[str, float] = {e: 0.0 for e in EMOTIONS if e != 'neutral'}
        lower = text.lower()

        for emotion, patterns in EMOTION_KEYWORDS.items():
            for pat in patterns:
                matches = re.findall(pat, lower, re.IGNORECASE)
                if matches:
                    scores[emotion] += len(matches) * 0.35

        # Light punctuation boosts only when keywords already present
        has_signal = any(v > 0 for v in scores.values())
        if has_signal:
            if '!' in text:
                scores['happy'] += 0.1
                scores['surprised'] += 0.1
                scores['angry'] += 0.05
            if '?' in text and len(text) < 80:
                scores['surprised'] += 0.1
                scores['concerned'] += 0.08

        best = max(scores, key=scores.get)
        conf = min(0.95, scores[best])

        # Require keyword signal + min confidence (punctuation alone is not enough)
        if conf < 0.35 or not has_signal:
            return EmotionResult(emotion=default, confidence=conf)
        return EmotionResult(emotion=best, confidence=conf)


class EmotionMapper:
    """
    Converts emotion + intensity into concrete TTS parameter deltas.
    Keeps output natural – never extreme.
    """

    def map(
        self,
        emotion: str,
        intensity: str = 'medium',
        base_rate: int = 0,
        base_pitch: int = 0,
    ) -> Dict[str, int]:
        emotion = (emotion or 'neutral').lower()
        if emotion not in EMOTION_MAP:
            emotion = 'neutral'
        intensity = (intensity or 'medium').lower()
        scale = INTENSITY_SCALE.get(intensity, 1.0)

        m = EMOTION_MAP[emotion]
        rate_delta = int(m['rate'] * scale)
        pitch_delta = int(m['pitch'] * scale)

        # Clamp to safe ranges for edge-tts neural voices
        final_rate = max(-30, min(30, base_rate + rate_delta))
        final_pitch = max(-40, min(40, base_pitch + pitch_delta))

        return {
            'rate': final_rate,
            'pitch': final_pitch,
            'style': m['style'],
            'emotion': emotion,
            'intensity': intensity,
        }
