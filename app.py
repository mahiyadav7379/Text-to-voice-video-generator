"""
AI Story Voice Studio – simplified single-voice system.
Gender (Male/Female) + Voice Preset for the entire story.
"""

from flask import Flask, render_template, request, jsonify, send_file
import sys
import os
import shutil
import platform
import time
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

if platform.system() == "Linux":
    os.environ["PATH"] = "/usr/bin:/usr/local/bin:" + os.environ.get("PATH", "")

app = Flask(__name__)

OUTPUT_FOLDER = "static/output"
TEMP_FOLDER = "temp_audio"
OUTPUT_VIDEO_FOLDER = "static/output_video"
TEMP_VIDEO_FOLDER = "temp_video"
MAX_CHARS = 50000

os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_VIDEO_FOLDER, exist_ok=True)
os.makedirs(TEMP_VIDEO_FOLDER, exist_ok=True)

import uuid
import threading
from engines.chunking import get_dynamic_chunk_size, smart_split
from engines.pipeline import StoryPipeline, PipelineConfig
from engines.tts_provider import get_provider
from engines.voice_mapper import (
    LEGACY_VOICE_MAP, VOICE_PRESETS, get_presets_for_gender, resolve_preset,
)
from engines.video_engine import VideoEngine, THEMES, RESOLUTIONS
from jobs.manager import JobManager

job_manager = JobManager(output_folder=OUTPUT_FOLDER, temp_folder=TEMP_FOLDER)
pipeline = StoryPipeline()
tts_provider = get_provider("edge")
video_engine = VideoEngine(output_dir=OUTPUT_VIDEO_FOLDER, temp_dir=TEMP_VIDEO_FOLDER)

video_jobs = {}
video_jobs_lock = threading.Lock()

VOICE_MAP = LEGACY_VOICE_MAP
SPEED_MAP = {"Slow": "-20%", "Normal": "+0%", "Fast": "+20%"}
DEFAULT_VOICE = "hi-IN-SwaraNeural"
PREVIEW_SAMPLE_TEXT = "यह आवाज़ नमूना है। कृपया सुनें।"


def check_ffmpeg():
    path = shutil.which("ffmpeg")
    if path:
        print(f"✅ FFmpeg found at: {path}")
        return path
    for p in ("/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if os.path.isfile(p):
            print(f"✅ FFmpeg found at: {p}")
            return p
    print("❌ FFmpeg not found!")
    return None


FFMPEG_PATH = check_ffmpeg()
try:
    from pydub import AudioSegment
    AudioSegment.converter = FFMPEG_PATH or shutil.which("ffmpeg")
    AudioSegment.ffprobe = shutil.which("ffprobe") or "/usr/bin/ffprobe"
except ImportError:
    pass


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config")
def api_config():
    return jsonify({
        "success": True,
        "max_chars": MAX_CHARS,
        "presets": {
            "male": get_presets_for_gender("male"),
            "female": get_presets_for_gender("female"),
        },
        "emotions": [
            "neutral", "happy", "sad", "angry", "surprised",
            "calm", "romantic", "concerned", "intense", "soft",
        ],
        "qualities": ["standard", "high", "ultra"],
        "modes": ["normal", "story"],
        "speed_modes": ["reliable", "balanced", "fast"],
        "ffmpeg": bool(FFMPEG_PATH),
    })


@app.route("/generate", methods=["POST"])
def generate():
    """Sync short text / preview – single voice preset."""
    try:
        data = request.json or {}
        text = (data.get("text") or "").strip()
        preview = bool(data.get("preview", False))
        gender = (data.get("voice_gender") or data.get("gender") or "female").lower()
        preset = data.get("voice_preset") or data.get("voice") or ""
        pitch = float(data.get("pitch", 0) or 0)
        quality = (data.get("quality") or "high").lower()
        speed = (data.get("speed") or "Normal").strip()

        if preview:
            text = text or PREVIEW_SAMPLE_TEXT
        else:
            if not text:
                return jsonify({"success": False, "error": "कृपया पाठ दर्ज करें"}), 400
            if len(text) > MAX_CHARS:
                return jsonify({"success": False, "error": f"पाठ {MAX_CHARS} वर्णों से अधिक नहीं हो सकता"}), 400
            if len(text) > 3000:
                return jsonify({
                    "success": False,
                    "error": "Long text detected. Please use the job API.",
                    "use_job_api": True,
                }), 400

        resolved = resolve_preset(preset, gender, legacy_voice=preset if preset in VOICE_MAP else "")
        voice = resolved["voice"]
        rate_num = int(resolved.get("rate", 0))
        if speed in SPEED_MAP:
            # SPEED_MAP is string like +0%; convert for edge
            rate_str = SPEED_MAP[speed]
        else:
            rate_str = f"{rate_num:+d}%"
        pitch_hz = int(max(-1.0, min(1.0, pitch)) * 20) + int(resolved.get("pitch", 0))
        pitch_str = f"{pitch_hz:+d}Hz"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        output_filename = f"hindi_tts_{timestamp}.mp3"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        chunks = smart_split(text, get_dynamic_chunk_size(len(text)))
        if not chunks:
            return jsonify({"success": False, "error": "पाठ को संसाधित नहीं किया जा सका"}), 400

        audio_chunks = []
        for i, chunk in enumerate(chunks):
            chunk_path = os.path.join(TEMP_FOLDER, f"chunk_{timestamp}_{i}.mp3")
            try:
                tts_provider.synthesize_sync(chunk, voice, rate_str, pitch_str, chunk_path)
                audio_chunks.append(chunk_path)
            except Exception as e:
                for p in audio_chunks:
                    try:
                        os.remove(p)
                    except Exception:
                        pass
                return jsonify({"success": False, "error": f"ऑडियो उत्पन्न करने में विफल: {str(e)}"}), 500

        bitrate = {"standard": "128k", "high": "192k", "ultra": "256k"}.get(quality, "192k")
        merge_ok = job_manager._merge_audio(audio_chunks, output_path, bitrate)
        for p in audio_chunks:
            try:
                os.remove(p)
            except Exception:
                pass

        if merge_ok:
            msg = "वॉइस प्रीव्यू तैयार है!" if preview else "ऑडियो सफलतापूर्वक उत्पन्न हुई!"
            return jsonify({
                "success": True,
                "message": msg,
                "filename": output_filename,
                "download_url": f"/download/{output_filename}",
            })
        return jsonify({"success": False, "error": "ऑडियो मर्ज नहीं हो सका"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": f"सर्वर त्रुटि: {str(e)}"}), 500


@app.route("/api/jobs", methods=["POST"])
def create_job():
    try:
        data = request.json or {}
        text = (data.get("text") or "").strip()
        if not text:
            return jsonify({"success": False, "error": "कृपया पाठ दर्ज करें"}), 400
        if len(text) > MAX_CHARS:
            return jsonify({"success": False, "error": f"पाठ {MAX_CHARS} वर्णों से अधिक नहीं हो सकता"}), 400

        gender = (data.get("voice_gender") or data.get("gender") or "female").lower()
        if gender not in ("male", "female"):
            gender = "female"
        preset = data.get("voice_preset") or data.get("voice") or f"{gender}_normal"

        config = {
            "mode": data.get("mode", "normal"),
            "max_chars": MAX_CHARS,
            "hinglish": bool(data.get("hinglish", False)),
            "voice_gender": gender,
            "voice_preset": preset,
            "global_emotion": data.get("global_emotion", data.get("emotion", "neutral")),
            "emotion_intensity": data.get("emotion_intensity", "medium"),
            "auto_emotion": bool(data.get("auto_emotion", True)),
            "speed": data.get("speed", "Normal"),
            "quality": data.get("quality", "high"),
            "pitch": float(data.get("pitch", 0) or 0),
            "voice": data.get("voice", ""),
            "speed_mode": data.get("speed_mode", "balanced"),
        }

        job = job_manager.create_job(text, config)
        started = job_manager.start_job(
            job.job_id,
            text,
            pipeline_fn=lambda t, c: pipeline.prepare(t, c),
            tts_provider=tts_provider,
        )
        if not started:
            return jsonify({"success": False, "error": "Could not start job"}), 500

        return jsonify({
            "success": True,
            "job_id": job.job_id,
            "status": job.status.value,
            "message": "Job started",
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    job = job_manager.get_job(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404
    return jsonify({"success": True, "job": job.to_dict()})


@app.route("/api/jobs/<job_id>/cancel", methods=["POST"])
def cancel_job(job_id):
    ok = job_manager.cancel_job(job_id)
    if not ok:
        return jsonify({"success": False, "error": "Cannot cancel job"}), 400
    return jsonify({"success": True, "message": "Job cancelled"})


@app.route("/api/analyze", methods=["POST"])
def analyze_story():
    """Emotion + text stats + chunk estimate (no character detection)."""
    try:
        data = request.json or {}
        text = (data.get("text") or "").strip()
        if not text:
            return jsonify({"success": False, "error": "Empty text"}), 400
        if len(text) > MAX_CHARS:
            return jsonify({"success": False, "error": f"Max {MAX_CHARS} chars"}), 400

        from engines.emotion import EmotionDetector
        from engines.hinglish import HinglishProcessor
        from engines.chunking import smart_split, get_dynamic_chunk_size

        emo = EmotionDetector()
        overall = emo.detect(text[:3000])
        _, hmeta = HinglishProcessor().process(text[:5000], enabled=True)
        cs = get_dynamic_chunk_size(len(text))
        chunks = smart_split(text, cs)
        words = len(text.split())
        gender = (data.get("voice_gender") or "female").lower()
        preset = data.get("voice_preset") or f"{gender}_normal"
        resolved = resolve_preset(preset, gender)

        return jsonify({
            "success": True,
            "emotion": {
                "detected": overall.emotion,
                "confidence": round(overall.confidence, 2),
            },
            "hinglish": hmeta,
            "voice": {
                "gender": resolved["gender"],
                "preset": preset,
                "label": resolved.get("label"),
                "provider_voice": resolved["voice"],
            },
            "stats": {
                "characters": len(text),
                "words": words,
                "estimated_chunks": len(chunks),
                "chunk_size": cs,
                "estimated_duration_min": max(1, int(words / 130)),
            },
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/draft", methods=["POST"])
def save_draft():
    return jsonify({"success": True, "message": "Draft acknowledged", "saved_at": time.time()})


@app.route("/download/<filename>")
def download(filename):
    try:
        if ".." in filename or "/" in filename or "\\" in filename:
            return "Invalid filename", 400
        file_path = os.path.join(OUTPUT_FOLDER, filename)
        if not os.path.exists(file_path):
            return "File not found", 404
        return send_file(file_path, as_attachment=True, download_name=filename, mimetype="audio/mpeg")
    except Exception as e:
        return f"Download error: {str(e)}", 500


@app.route("/api/video/themes")
def api_video_themes():
    return jsonify({
        "success": True,
        "themes": THEMES,
        "resolutions": list(RESOLUTIONS.keys()),
    })


@app.route("/api/video/generate", methods=["POST"])
def generate_video():
    try:
        data = request.json or {}
        text = (data.get("text") or "").strip()
        if not text:
            return jsonify({"success": False, "error": "कृपया पाठ दर्ज करें"}), 400

        job_id = uuid.uuid4().hex[:16]
        job_data = {
            "job_id": job_id,
            "status": "PROCESSING",
            "progress": 5,
            "stage": "Preparing Text to Video...",
            "error": None,
            "result": None,
            "created_at": time.time(),
        }

        with video_jobs_lock:
            video_jobs[job_id] = job_data

        def _run_video():
            def progress_cb(pct, stage_msg):
                with video_jobs_lock:
                    if job_id in video_jobs:
                        video_jobs[job_id]["progress"] = pct
                        video_jobs[job_id]["stage"] = stage_msg

            try:
                res = video_engine.generate_video(
                    text=text,
                    config=data,
                    tts_provider=tts_provider,
                    progress_callback=progress_cb,
                )
                with video_jobs_lock:
                    if job_id in video_jobs:
                        video_jobs[job_id]["status"] = "COMPLETED"
                        video_jobs[job_id]["progress"] = 100
                        video_jobs[job_id]["stage"] = "Video ready!"
                        video_jobs[job_id]["result"] = res
            except Exception as e:
                with video_jobs_lock:
                    if job_id in video_jobs:
                        video_jobs[job_id]["status"] = "FAILED"
                        video_jobs[job_id]["error"] = str(e)
                        video_jobs[job_id]["stage"] = f"Failed: {str(e)}"

        threading.Thread(target=_run_video, daemon=True).start()

        return jsonify({
            "success": True,
            "job_id": job_id,
            "message": "Video generation started",
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/video/jobs/<job_id>", methods=["GET"])
def get_video_job(job_id):
    with video_jobs_lock:
        job = video_jobs.get(job_id)
    if not job:
        return jsonify({"success": False, "error": "Video job not found"}), 404
    return jsonify({"success": True, "job": job})


@app.route("/download_video/<filename>")
def download_video(filename):
    try:
        if ".." in filename or "/" in filename or "\\" in filename:
            return "Invalid filename", 400
        file_path = os.path.join(OUTPUT_VIDEO_FOLDER, filename)
        if not os.path.exists(file_path):
            return "File not found", 404
        return send_file(file_path, as_attachment=True, download_name=filename, mimetype="video/mp4")
    except Exception as e:
        return f"Download error: {str(e)}", 500


@app.route("/install-ffmpeg")
def install_ffmpeg():
    return jsonify({
        "title": "FFmpeg Installation Guide",
        "message": "FFmpeg is required for audio merging.",
        "instructions": {
            "windows": {"command": "choco install ffmpeg"},
            "macos": {"command": "brew install ffmpeg"},
            "linux": {"command": "sudo apt-get install ffmpeg"},
        },
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🎙️ AI Story Voice Studio starting on port {port}")
    print(f"   MAX_CHARS={MAX_CHARS}  FFmpeg={FFMPEG_PATH}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
