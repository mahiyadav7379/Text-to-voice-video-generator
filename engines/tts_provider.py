"""
TTS Provider Abstraction Layer.
BaseTTSProvider → EdgeTTSProvider (current).
Future providers can be added without touching story / job logic.
"""

import asyncio
import os
from abc import ABC, abstractmethod
from typing import Optional


class BaseTTSProvider(ABC):
    """Abstract TTS interface."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: str,
        rate: str = '+0%',
        pitch: str = '+0Hz',
        output_path: str = '',
    ) -> str:
        """Generate audio file and return path."""
        pass

    def synthesize_sync(self, text: str, voice: str, rate: str = '+0%', pitch: str = '+0Hz', output_path: str = '') -> str:
        """Synchronous wrapper."""
        try:
            return asyncio.run(self.synthesize(text, voice, rate, pitch, output_path))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(self.synthesize(text, voice, rate, pitch, output_path))
            finally:
                loop.close()


class EdgeTTSProvider(BaseTTSProvider):
    """Microsoft Edge neural TTS (edge-tts)."""

    def __init__(self):
        try:
            import edge_tts
            self._edge = edge_tts
        except ImportError as e:
            raise RuntimeError('edge-tts is required') from e

    async def synthesize(
        self,
        text: str,
        voice: str,
        rate: str = '+0%',
        pitch: str = '+0Hz',
        output_path: str = '',
    ) -> str:
        if not text or not text.strip():
            raise ValueError('Empty text for TTS')
        if not output_path:
            raise ValueError('output_path required')

        # edge-tts Communicate supports rate & pitch
        communicate = self._edge.Communicate(
            text.strip(),
            voice=voice,
            rate=rate,
            pitch=pitch,
        )
        await communicate.save(output_path)
        if not os.path.isfile(output_path) or os.path.getsize(output_path) < 100:
            raise RuntimeError(f'Edge-TTS produced empty or invalid file: {output_path}')
        return output_path


def get_provider(name: str = 'edge') -> BaseTTSProvider:
    if name == 'edge':
        return EdgeTTSProvider()
    raise ValueError(f'Unknown TTS provider: {name}')
