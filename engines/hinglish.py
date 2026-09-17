"""
Hinglish Preprocessing Layer.
Detects mixed Hindi-English text and normalizes lightly for better TTS pronunciation
without aggressive replacement that would break meaning.
"""

import re
from typing import Tuple


# Common English words that edge-tts Hindi voices pronounce reasonably
# We keep them as-is. Only normalize obvious issues.

# Optional light transliteration helpers for very common office/tech terms
# (kept minimal – do not over-convert)
COMMON_KEEP = set()  # intentionally empty – preserve original


class HinglishProcessor:
    """
    Pipeline stage:
    Original → Detect mix → Light normalize → Return cleaned text + flags
    """

    def process(self, text: str, enabled: bool = True) -> Tuple[str, dict]:
        meta = {
            'is_hinglish': False,
            'hindi_ratio': 0.0,
            'english_ratio': 0.0,
            'changed': False,
        }
        if not text or not enabled:
            return text, meta

        # Character class stats
        hindi_chars = len(re.findall(r'[\u0900-\u097F]', text))
        latin_chars = len(re.findall(r'[A-Za-z]', text))
        total = hindi_chars + latin_chars or 1
        meta['hindi_ratio'] = hindi_chars / total
        meta['english_ratio'] = latin_chars / total
        meta['is_hinglish'] = 0.15 < meta['hindi_ratio'] < 0.85 and latin_chars > 5

        if not meta['is_hinglish']:
            return text, meta

        # Light normalization only
        cleaned = text
        # Normalize multiple spaces
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        # Ensure space after English punctuation when followed by Hindi
        cleaned = re.sub(r'([.!?])([\u0900-\u097F])', r'\1 \2', cleaned)
        # Ensure space before Hindi danda when missing
        cleaned = re.sub(r'([^\s])(।)', r'\1\2', cleaned)

        if cleaned != text:
            meta['changed'] = True
        return cleaned.strip(), meta
