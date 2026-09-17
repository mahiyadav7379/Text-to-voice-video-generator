# 🎙️ AI Story Voice Studio

Upgraded Hindi Text-to-Speech project into a professional **AI Story Voice Studio**.

Supports long Hindi / Hinglish stories up to **50,000 characters** with dual male/female character voices, emotion mapping, smart chunking, and background job processing.

## Features

- **50,000 character support** with real-time counter
- **Smart dynamic chunking** (paragraph → sentence → punctuation → word)
- **Background job system** with progress %, ETA, cancel
- **Dual Character Mode** (Male + Female) with auto detection
- **Emotion detection & intensity** (mapped to rate/pitch for Edge TTS)
- **Pitch control** per character
- **Audio quality** Standard / High / Ultra (bitrate)
- **Story modes**: Normal · Story · Dual Character
- **Hinglish preprocessing**
- **Auto-save draft** (localStorage)
- **Light / Dark theme**
- **Responsive** mobile layout
- **Backward compatible** `/generate` for short text & preview

## Stack

- Flask + edge-tts + pydub + FFmpeg
- Vanilla JS / CSS (no React)
- Modular engines under `engines/`
- In-memory job manager under `jobs/`

## Run

```bash
pip install -r requirements.txt
# FFmpeg required
# Linux: sudo apt-get install ffmpeg
python app.py
# → http://localhost:5000
```

## APIs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/jobs` | Create generation job |
| GET | `/api/jobs/<id>` | Job status / progress |
| POST | `/api/jobs/<id>/cancel` | Cancel job |
| POST | `/generate` | Sync generate (short / preview) |
| POST | `/api/analyze` | Character + emotion preview |
| GET | `/download/<file>` | Download MP3 |
| GET | `/api/config` | Frontend config |

## Architecture

```
TEXT → Validate → Hinglish → Mode → Character Detect → Emotion Detect
    → Voice Mapper → Smart Chunk → Background Job → Edge TTS
    → Merge (pydub/ffmpeg) → Quality encode → Final MP3
```

## Limitations (Edge TTS)

- No native SSML emotion tags; emotion approximated via rate & pitch
- Two primary Hindi neural voices (Madhur male, Swara female)
- Rate limited by Microsoft service; long jobs take minutes
- Character detection is heuristic (manual names recommended for accuracy)

## Project layout

```
hindi-tts-studio/
├── app.py
├── engines/
│   ├── chunking.py
│   ├── character.py
│   ├── emotion.py
│   ├── hinglish.py
│   ├── voice_mapper.py
│   ├── tts_provider.py
│   └── pipeline.py
├── jobs/
│   └── manager.py
├── templates/index.html
├── static/{style.css,script.js,output/}
└── temp_audio/
```
