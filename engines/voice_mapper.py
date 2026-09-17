"""
Voice Preset System – single voice for the entire story.
Edge TTS Hindi: hi-IN-MadhurNeural (male), hi-IN-SwaraNeural (female).
Presets vary rate/pitch/style; not fake native voices.
"""

from typing import Dict, List
from .emotion import EmotionMapper


# Actual provider voice IDs
MALE_VOICE_ID = "hi-IN-MadhurNeural"
FEMALE_VOICE_ID = "hi-IN-SwaraNeural"

# Configurable presets: gender + style via rate/pitch
VOICE_PRESETS: Dict[str, Dict] = {
    # Male presets (all use Madhur)
    "male_normal": {
        "gender": "male",
        "label": "Male Normal",
        "voice": MALE_VOICE_ID,
        "rate": 0,
        "pitch": 0,
        "style": "normal",
    },
    "male_soft": {
        "gender": "male",
        "label": "Male Soft",
        "voice": MALE_VOICE_ID,
        "rate": -8,
        "pitch": -5,
        "style": "soft",
    },
    "male_deep": {
        "gender": "male",
        "label": "Male Deep",
        "voice": MALE_VOICE_ID,
        "rate": -5,
        "pitch": -12,
        "style": "storytelling",
    },
    "male_mature": {
        "gender": "male",
        "label": "Male Mature",
        "voice": MALE_VOICE_ID,
        "rate": -6,
        "pitch": -8,
        "style": "narrative",
    },
    # Female presets (all use Swara)
    "female_normal": {
        "gender": "female",
        "label": "Female Normal",
        "voice": FEMALE_VOICE_ID,
        "rate": 0,
        "pitch": 0,
        "style": "normal",
    },
    "female_soft": {
        "gender": "female",
        "label": "Female Soft",
        "voice": FEMALE_VOICE_ID,
        "rate": -8,
        "pitch": -3,
        "style": "soft",
    },
    "female_sweet": {
        "gender": "female",
        "label": "Female Sweet",
        "voice": FEMALE_VOICE_ID,
        "rate": 2,
        "pitch": 10,
        "style": "emotional",
    },
    "female_mature": {
        "gender": "female",
        "label": "Female Mature",
        "voice": FEMALE_VOICE_ID,
        "rate": -5,
        "pitch": -6,
        "style": "narrative",
    },
}

# Backward-compatible legacy labels → preset keys
LEGACY_VOICE_TO_PRESET = {
    "Deep Male": "male_deep",
    "Natural Male": "male_normal",
    "Professional Male": "male_mature",
    "Soft Female": "female_soft",
    "Natural Female": "female_normal",
    "Professional Female": "female_mature",
}

# Keep for /generate short path
LEGACY_VOICE_MAP = {
    "Deep Male": MALE_VOICE_ID,
    "Natural Male": MALE_VOICE_ID,
    "Professional Male": MALE_VOICE_ID,
    "Soft Female": FEMALE_VOICE_ID,
    "Natural Female": FEMALE_VOICE_ID,
    "Professional Female": FEMALE_VOICE_ID,
}

VOICE_CATALOG = {
    "male": {"default": MALE_VOICE_ID},
    "female": {"default": FEMALE_VOICE_ID},
}


def get_presets_for_gender(gender: str) -> List[Dict]:
    g = (gender or "female").lower()
    return [
        {"key": k, "label": v["label"], "gender": v["gender"]}
        for k, v in VOICE_PRESETS.items()
        if v["gender"] == g
    ]


def resolve_preset(preset_key: str = "", gender: str = "", legacy_voice: str = "") -> Dict:
    """Resolve to a concrete preset dict."""
    if preset_key and preset_key in VOICE_PRESETS:
        return dict(VOICE_PRESETS[preset_key])
    if legacy_voice and legacy_voice in LEGACY_VOICE_TO_PRESET:
        return dict(VOICE_PRESETS[LEGACY_VOICE_TO_PRESET[legacy_voice]])
    g = (gender or "female").lower()
    default_key = "male_normal" if g == "male" else "female_normal"
    return dict(VOICE_PRESETS[default_key])


class VoiceMapper:
    """Maps preset + emotion → TTS rate/pitch/voice for the whole story."""

    def __init__(self):
        self.emotion_mapper = EmotionMapper()

    def build_params(
        self,
        preset_key: str = "female_normal",
        gender: str = "female",
        emotion: str = "neutral",
        intensity: str = "medium",
        pitch_slider: float = 0.0,
        legacy_voice: str = "",
        legacy_speed: str = "",
    ) -> Dict:
        preset = resolve_preset(preset_key, gender, legacy_voice)
        base_rate = int(preset.get("rate", 0))
        base_pitch = int(preset.get("pitch", 0))

        if legacy_speed:
            speed_map = {"Slow": -20, "Normal": 0, "Fast": 20}
            # Only override if normal mode speed selected explicitly
            if legacy_speed in speed_map and legacy_speed != "Normal":
                base_rate = speed_map[legacy_speed]

        slider_pitch = int(max(-1.0, min(1.0, float(pitch_slider or 0))) * 20)
        base_pitch += slider_pitch

        emo = self.emotion_mapper.map(emotion, intensity, base_rate, base_pitch)
        rate = max(-40, min(40, emo["rate"]))
        pitch = max(-50, min(50, emo["pitch"]))

        return {
            "voice": preset["voice"],
            "rate": f"{rate:+d}%",
            "pitch": f"{pitch:+d}Hz",
            "rate_num": rate,
            "pitch_num": pitch,
            "style": preset.get("style", "normal"),
            "emotion": emotion,
            "preset": preset_key or preset.get("label", ""),
            "gender": preset["gender"],
            "label": preset.get("label", ""),
        }
