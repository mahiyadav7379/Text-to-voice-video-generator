"""
Smart Dynamic Chunking Engine
Splits long Hindi / Hinglish / English text while preserving natural speech flow.
Priority: paragraph > sentence > Hindi punctuation > English punctuation > comma > word > char fallback.
"""

import re
from typing import List, Tuple

# Configurable limits
MIN_CHUNK_SIZE = 200
DEFAULT_CHUNK_SIZE = 600
MAX_CHUNK_SIZE = 900

# Hindi + English sentence terminators
HINDI_TERMINATORS = r'[।!?]'
ENGLISH_TERMINATORS = r'[.!?;:]'
ALL_TERMINATORS = r'[।!?.!;:]'
COMMA = r'[,،]'


def get_dynamic_chunk_size(text_length: int) -> int:
    """
    Intelligent chunk size based on total text length.
    Optimizes for TTS reliability, natural flow, memory and speed.
    """
    if text_length <= 1500:
        return min(MAX_CHUNK_SIZE, max(DEFAULT_CHUNK_SIZE, text_length // 2 or DEFAULT_CHUNK_SIZE))
    if text_length <= 8000:
        return DEFAULT_CHUNK_SIZE
    if text_length <= 25000:
        return 550
    # Very large (up to 50k)
    return 480


class SmartChunker:
    """Reusable smart text chunker for long stories."""

    def __init__(
        self,
        min_size: int = MIN_CHUNK_SIZE,
        default_size: int = DEFAULT_CHUNK_SIZE,
        max_size: int = MAX_CHUNK_SIZE,
    ):
        self.min_size = min_size
        self.default_size = default_size
        self.max_size = max_size

    def split(self, text: str, target_size: int = None) -> List[str]:
        """
        Split text into chunks respecting natural boundaries.
        Never cuts words in the middle when possible.
        """
        if not text or not text.strip():
            return []

        text = text.strip()
        target = target_size or get_dynamic_chunk_size(len(text))
        target = max(self.min_size, min(self.max_size, target))

        # Fast path for short text
        if len(text) <= target:
            return [text]

        # 1. Prefer paragraph boundaries
        paragraphs = re.split(r'\n\s*\n+', text)
        if len(paragraphs) > 1:
            chunks = self._merge_units(paragraphs, target, joiner='\n\n')
            if chunks and all(len(c) <= self.max_size * 1.4 for c in chunks):
                return [c.strip() for c in chunks if c.strip()]

        # 2. Sentence-level split (Hindi + English)
        sentences = self._split_sentences(text)
        if len(sentences) > 1:
            chunks = self._merge_units(sentences, target, joiner=' ')
            return [c.strip() for c in chunks if c.strip()]

        # 3. Comma / soft boundary
        soft_parts = re.split(r'([,،]\s*)', text)
        units = []
        buf = ''
        for part in soft_parts:
            if re.match(r'[,،]\s*', part):
                buf += part
                units.append(buf)
                buf = ''
            else:
                buf += part
        if buf:
            units.append(buf)
        if len(units) > 1:
            chunks = self._merge_units(units, target, joiner='')
            return [c.strip() for c in chunks if c.strip()]

        # 4. Word boundary (never mid-word)
        words = text.split()
        if len(words) > 1:
            chunks = []
            current = ''
            for w in words:
                candidate = (current + ' ' + w).strip() if current else w
                if len(candidate) <= target:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    # Single very long word → hard split as last resort
                    if len(w) > target:
                        chunks.extend(self._hard_split(w, target))
                        current = ''
                    else:
                        current = w
            if current:
                chunks.append(current)
            return chunks

        # 5. Absolute last resort – character split
        return self._hard_split(text, target)

    def _split_sentences(self, text: str) -> List[str]:
        """Split on Hindi danda, ?, !, ., ;, : while keeping delimiter."""
        # Keep the terminator attached to the sentence
        pattern = r'([^।!?.!;:]+[।!?.!;:]+)\s*'
        parts = re.findall(pattern, text)
        if not parts:
            return [text]
        # Append any trailing text without terminator
        last_end = 0
        for p in parts:
            idx = text.find(p, last_end)
            if idx >= 0:
                last_end = idx + len(p)
        remainder = text[last_end:].strip()
        if remainder:
            parts.append(remainder)
        return [p.strip() for p in parts if p.strip()]

    def _merge_units(self, units: List[str], target: int, joiner: str = ' ') -> List[str]:
        chunks = []
        current = ''
        for unit in units:
            unit = unit.strip()
            if not unit:
                continue
            candidate = (current + joiner + unit).strip() if current else unit
            if len(candidate) <= target:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                # Unit itself larger than target → recursive split
                if len(unit) > target:
                    sub = self.split(unit, target)
                    chunks.extend(sub[:-1])
                    current = sub[-1] if sub else ''
                else:
                    current = unit
        if current:
            chunks.append(current)
        return chunks

    def _hard_split(self, text: str, size: int) -> List[str]:
        """Character-level fallback – only when absolutely necessary."""
        return [text[i:i + size] for i in range(0, len(text), size)]


def smart_split(text: str, target_size: int = None) -> List[str]:
    """Convenience function."""
    return SmartChunker().split(text, target_size)
