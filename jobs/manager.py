"""
Background Job Processing System for long-form TTS (up to 50k chars).
In-memory job store + worker threads. Progress via polling.
"""

import os
import uuid
import time
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, List, Any, Callable
from pathlib import Path

# Quality → bitrate mapping (actual effect on final export)
QUALITY_BITRATE = {
    'standard': '128k',
    'high': '192k',
    'ultra': '256k',
}

# Bounded parallel TTS workers (provider-safe)
MAX_CONCURRENT_TTS = {
    'reliable': 1,
    'balanced': 3,
    'fast': 4,
}
DEFAULT_SPEED_MODE = 'balanced'
MAX_TTS_RETRIES = 3


class JobStatus(str, Enum):
    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    GENERATING_CHUNKS = 'GENERATING_CHUNKS'
    MERGING_AUDIO = 'MERGING_AUDIO'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'


@dataclass
class Job:
    job_id: str
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    current_chunk: int = 0
    total_chunks: int = 0
    stage: str = 'Preparing Text'
    message: str = ''
    error: str = ''
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    eta_seconds: Optional[float] = None
    output_filename: str = ''
    output_path: str = ''
    download_url: str = ''
    chunk_times: List[float] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    text_preview: str = ''
    cancelled: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d['status'] = self.status.value if isinstance(self.status, JobStatus) else self.status
        # Do not expose internal paths or full config secrets
        d.pop('output_path', None)
        d.pop('chunk_times', None)
        d.pop('cancelled', None)
        # Keep only safe config summary
        safe_cfg = {
            'mode': self.config.get('mode'),
            'quality': self.config.get('quality'),
            'hinglish': self.config.get('hinglish'),
            'voice_gender': self.config.get('voice_gender'),
            'voice_preset': self.config.get('voice_preset'),
        }
        d['config'] = safe_cfg
        return d


class JobManager:
    """
    Thread-safe in-memory job registry + background workers.
    Suitable for single-process Flask / gunicorn with threads.
    """

    def __init__(
        self,
        output_folder: str = 'static/output',
        temp_folder: str = 'temp_audio',
        max_workers: int = 2,
        job_ttl_seconds: int = 86400,
    ):
        self.output_folder = output_folder
        self.temp_folder = temp_folder
        self.max_workers = max_workers
        self.job_ttl = job_ttl_seconds
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.RLock()
        self._active_workers = 0
        self._ffmpeg = None
        self._pydub = None
        self._init_audio_tools()

        os.makedirs(output_folder, exist_ok=True)
        os.makedirs(temp_folder, exist_ok=True)

        # Background cleanup thread
        t = threading.Thread(target=self._cleanup_loop, daemon=True)
        t.start()

    def _init_audio_tools(self):
        import shutil as sh
        self._ffmpeg = sh.which('ffmpeg') or '/usr/bin/ffmpeg'
        try:
            from pydub import AudioSegment
            AudioSegment.converter = self._ffmpeg
            AudioSegment.ffprobe = sh.which('ffprobe') or '/usr/bin/ffprobe'
            self._pydub = AudioSegment
        except Exception:
            self._pydub = None

    # ---------- Public API ----------

    def create_job(self, text: str, config: dict) -> Job:
        job_id = uuid.uuid4().hex[:16]
        job = Job(
            job_id=job_id,
            status=JobStatus.PENDING,
            stage='Preparing Text',
            message='Job created',
            config=config,
            text_preview=text[:120] + ('…' if len(text) > 120 else ''),
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                return False
            job.cancelled = True
            job.status = JobStatus.CANCELLED
            job.message = 'Cancelled by user'
            job.finished_at = time.time()
            return True

    def start_job(self, job_id: str, text: str, pipeline_fn: Callable, tts_provider) -> bool:
        """Spawn a background worker for the job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status != JobStatus.PENDING:
                return False
            if self._active_workers >= self.max_workers:
                # Still accept – queue will wait inside thread
                pass
            job.status = JobStatus.PROCESSING
            job.started_at = time.time()
            job.stage = 'Analyzing Story'
            job.message = 'Starting analysis…'
            self._active_workers += 1

        def worker():
            try:
                self._run_job(job_id, text, pipeline_fn, tts_provider)
            finally:
                with self._lock:
                    self._active_workers = max(0, self._active_workers - 1)

        threading.Thread(target=worker, daemon=True).start()
        return True

    # ---------- Internal processing ----------

    def _run_job(self, job_id: str, text: str, pipeline_fn, tts_provider):
        job = self.get_job(job_id)
        if not job:
            return
        temp_dir = None
        try:
            from engines.pipeline import PipelineConfig

            cfg = job.config
            pipe_cfg = PipelineConfig(
                mode=cfg.get('mode', 'normal'),
                max_chars=cfg.get('max_chars', 50000),
                hinglish=cfg.get('hinglish', False),
                voice_gender=cfg.get('voice_gender', cfg.get('gender', 'female')),
                voice_preset=cfg.get('voice_preset', ''),
                global_emotion=cfg.get('global_emotion', 'neutral'),
                emotion_intensity=cfg.get('emotion_intensity', 'medium'),
                auto_emotion=cfg.get('auto_emotion', True),
                legacy_speed=cfg.get('speed', 'Normal'),
                quality=cfg.get('quality', 'high'),
                pitch=float(cfg.get('pitch', 0) or 0),
                voice=cfg.get('voice', ''),
            )

            self._update(job, stage='Detecting Characters', progress=5, message='Analyzing characters…')
            if job.cancelled:
                return

            prepared = pipeline_fn(text, pipe_cfg)
            total = len(prepared)
            job.total_chunks = total
            self._update(job, stage='Generating Audio', progress=8,
                         message=f'Preparing {total} chunks…', current_chunk=0)

            # Per-job temp directory
            temp_dir = os.path.join(self.temp_folder, f'job_{job_id}')
            os.makedirs(temp_dir, exist_ok=True)

            speed_mode = (cfg.get('speed_mode') or DEFAULT_SPEED_MODE).lower()
            concurrency = MAX_CONCURRENT_TTS.get(speed_mode, 3)
            concurrency = max(1, min(concurrency, total))

            # Pre-allocate ordered result slots
            audio_files: List[Optional[str]] = [None] * total
            completed_count = [0]
            lock = threading.Lock()

            def _synth_one(i, chunk):
                if job.cancelled:
                    return i, None, "cancelled"
                chunk_path = os.path.join(temp_dir, f"chunk_{i:04d}.mp3")
                params = chunk.voice_params
                # Backend debug log for voice routing verification
                print(
                    f"[Job {job_id}] Chunk {i+1}/{total} | "
                    f"preset={params.get('preset')} gender={params.get('gender')} "
                    f"voice={params.get('voice')} rate={params.get('rate')} pitch={params.get('pitch')} "
                    f"emotion={chunk.emotion}"
                )
                last_err = None
                for attempt in range(1, MAX_TTS_RETRIES + 1):
                    if job.cancelled:
                        return i, None, "cancelled"
                    try:
                        t0 = time.time()
                        tts_provider.synthesize_sync(
                            text=chunk.text,
                            voice=params["voice"],
                            rate=params["rate"],
                            pitch=params["pitch"],
                            output_path=chunk_path,
                        )
                        elapsed = time.time() - t0
                        with lock:
                            job.chunk_times.append(elapsed)
                            completed_count[0] += 1
                            done = completed_count[0]
                            self._update(
                                job,
                                status=JobStatus.GENERATING_CHUNKS,
                                stage="Processing Chunks",
                                current_chunk=done,
                                progress=8 + (done / max(total, 1)) * 75,
                                message=f"Generating chunk {done}/{total} ({params.get('label') or params.get('gender', '')})",
                            )
                            if job.chunk_times:
                                avg = sum(job.chunk_times) / len(job.chunk_times)
                                remaining = (total - done) * avg / max(concurrency, 1)
                                remaining += max(2.0, total * 0.05)
                                job.eta_seconds = remaining
                        return i, chunk_path, None
                    except Exception as e:
                        last_err = e
                        time.sleep(min(2 ** attempt, 8))
                return i, None, str(last_err)

            self._update(
                job, status=JobStatus.GENERATING_CHUNKS, stage="Processing Chunks",
                progress=8, message=f"Generating {total} chunks (concurrency={concurrency})…",
            )

            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                futures = {pool.submit(_synth_one, i, ch): i for i, ch in enumerate(prepared)}
                for fut in as_completed(futures):
                    if job.cancelled:
                        pool.shutdown(wait=False, cancel_futures=True)
                        self._update(job, status=JobStatus.CANCELLED, message="Cancelled")
                        return
                    i, path, err = fut.result()
                    if err and err != "cancelled":
                        raise RuntimeError(f"Chunk {i+1} TTS failed after retries: {err}")
                    if path:
                        audio_files[i] = path

            # Ensure order & completeness
            if any(p is None for p in audio_files):
                missing = [i for i, p in enumerate(audio_files) if p is None]
                raise RuntimeError(f"Missing audio for chunks: {missing}")
            # audio_files is already in chunk_id order

            if job.cancelled:
                return

            # Merge
            self._update(job, status=JobStatus.MERGING_AUDIO, stage='Merging Audio',
                         progress=90, message='Merging audio chunks…', eta_seconds=5)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
            filename = f'story_{timestamp}.mp3'
            output_path = os.path.join(self.output_folder, filename)
            bitrate = QUALITY_BITRATE.get(pipe_cfg.quality, '192k')

            ok = self._merge_audio(audio_files, output_path, bitrate)
            if not ok:
                raise RuntimeError('Audio merge failed')

            self._update(
                job,
                status=JobStatus.COMPLETED,
                stage='Completed',
                progress=100,
                message='Audio ready',
                output_filename=filename,
                output_path=output_path,
                download_url=f'/download/{filename}',
                finished_at=time.time(),
                eta_seconds=0,
            )

        except Exception as e:
            tb = traceback.format_exc()
            print(f'[Job {job_id}] FAILED: {e}\n{tb}')
            self._update(
                job,
                status=JobStatus.FAILED,
                stage='Failed',
                progress=job.progress,
                error=str(e),
                message=f'Error: {e}',
                finished_at=time.time(),
            )
        finally:
            # Safe temp cleanup (keep final output)
            if temp_dir and os.path.isdir(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

    def _merge_audio(self, chunk_paths: List[str], output_path: str, bitrate: str = '192k') -> bool:
        if not chunk_paths:
            return False

        # Method 1: pydub
        if self._pydub and self._ffmpeg:
            try:
                combined = self._pydub.empty()
                for p in chunk_paths:
                    combined += self._pydub.from_mp3(p)
                combined.export(output_path, format='mp3', bitrate=bitrate)
                if os.path.isfile(output_path) and os.path.getsize(output_path) > 500:
                    return True
            except Exception as e:
                print(f'pydub merge failed: {e}')

        # Method 2: ffmpeg concat
        if self._ffmpeg:
            try:
                concat_list = os.path.join(os.path.dirname(chunk_paths[0]), 'concat.txt')
                with open(concat_list, 'w', encoding='utf-8') as f:
                    for p in chunk_paths:
                        abs_p = os.path.abspath(p).replace('\\', '/')
                        f.write(f"file '{abs_p}'\n")
                import subprocess
                cmd = [
                    self._ffmpeg, '-f', 'concat', '-safe', '0',
                    '-i', concat_list, '-c', 'copy', '-y', output_path,
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                try:
                    os.remove(concat_list)
                except Exception:
                    pass
                if r.returncode == 0 and os.path.isfile(output_path):
                    return True
                print(f'ffmpeg merge failed: {r.stderr}')
            except Exception as e:
                print(f'ffmpeg direct failed: {e}')

        # Fallback: first chunk only
        try:
            shutil.copy(chunk_paths[0], output_path)
            return True
        except Exception:
            return False

    def _update(self, job: Job, **kwargs):
        with self._lock:
            # Do not overwrite a terminal cancelled state from the worker
            if job.cancelled and job.status == JobStatus.CANCELLED:
                if kwargs.get('status') not in (None, JobStatus.CANCELLED):
                    # Allow only progress/message updates that still reflect cancel
                    kwargs = {k: v for k, v in kwargs.items() if k not in ('status',)}
                    if not kwargs:
                        return
            for k, v in kwargs.items():
                if hasattr(job, k):
                    setattr(job, k, v)

    def _cleanup_loop(self):
        while True:
            time.sleep(1800)
            try:
                now = time.time()
                with self._lock:
                    expired = [
                        jid for jid, j in self._jobs.items()
                        if (j.finished_at or j.created_at) < now - self.job_ttl
                    ]
                    for jid in expired:
                        del self._jobs[jid]
                # Clean old output / temp files (>24h)
                for folder in (self.output_folder, self.temp_folder):
                    if not os.path.isdir(folder):
                        continue
                    for name in os.listdir(folder):
                        path = os.path.join(folder, name)
                        try:
                            if os.path.getmtime(path) < now - 86400:
                                if os.path.isfile(path):
                                    os.remove(path)
                                elif os.path.isdir(path):
                                    shutil.rmtree(path, ignore_errors=True)
                        except Exception:
                            pass
            except Exception:
                pass
