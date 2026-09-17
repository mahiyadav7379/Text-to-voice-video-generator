"""
Text-to-Video Synthesis Engine for AI Story Voice Studio.
Renders high-definition MP4 videos from story scripts with Hindi text,
custom visual themes, aspect ratios (16:9, 9:16, 1:1), subtitles, audio visualizers,
and Edge-TTS voice synchronization.
"""

import os
import sys
import shutil
import time
import math
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Theme palette definitions: (BgStart, BgEnd, AccentColor, CardBg, TextColor, SubtitleBg)
THEMES = {
    "cinematic": {
        "name": "Cinematic Dark",
        "bg_start": (15, 12, 29),
        "bg_end": (35, 25, 60),
        "accent": (245, 197, 24),
        "card_bg": (25, 20, 45, 220),
        "text_color": (255, 255, 255),
        "subtitle_bg": (10, 8, 20, 210),
        "particle_color": (245, 197, 24, 60),
    },
    "cyberpunk": {
        "name": "Cyberpunk Neon",
        "bg_start": (10, 10, 26),
        "bg_end": (5, 30, 50),
        "accent": (0, 240, 255),
        "card_bg": (15, 15, 35, 220),
        "text_color": (255, 255, 255),
        "subtitle_bg": (5, 5, 20, 220),
        "particle_color": (255, 0, 128, 80),
    },
    "storybook": {
        "name": "Storybook Gold",
        "bg_start": (38, 20, 12),
        "bg_end": (75, 45, 20),
        "accent": (255, 200, 100),
        "card_bg": (55, 30, 18, 230),
        "text_color": (255, 248, 230),
        "subtitle_bg": (25, 12, 6, 220),
        "particle_color": (255, 215, 0, 70),
    },
    "anime": {
        "name": "Anime Sunset",
        "bg_start": (45, 15, 50),
        "bg_end": (90, 30, 80),
        "accent": (255, 110, 180),
        "card_bg": (60, 20, 65, 220),
        "text_color": (255, 255, 255),
        "subtitle_bg": (30, 10, 35, 220),
        "particle_color": (255, 182, 193, 70),
    },
    "nature": {
        "name": "Nature Emerald",
        "bg_start": (10, 28, 20),
        "bg_end": (20, 55, 40),
        "accent": (72, 239, 173),
        "card_bg": (15, 40, 30, 220),
        "text_color": (240, 255, 245),
        "subtitle_bg": (5, 20, 14, 220),
        "particle_color": (72, 239, 173, 60),
    },
    "minimal": {
        "name": "Minimal Obsidian",
        "bg_start": (18, 18, 20),
        "bg_end": (35, 35, 40),
        "accent": (220, 220, 230),
        "card_bg": (28, 28, 32, 230),
        "text_color": (255, 255, 255),
        "subtitle_bg": (12, 12, 15, 220),
        "particle_color": (200, 200, 220, 50),
    },
}

# Resolutions per aspect ratio
RESOLUTIONS = {
    "16:9": (1920, 1080),  # Landscape / YouTube
    "9:16": (1080, 1920),  # Portrait / Shorts / Reels
    "1:1": (1080, 1080),   # Square
}


class VideoEngine:
    """
    Renders videos from story text & audio chunks using Pillow + FFmpeg.
    """

    def __init__(self, output_dir: str = "static/output_video", temp_dir: str = "temp_video"):
        self.output_dir = output_dir
        self.temp_dir = temp_dir
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        self.ffmpeg_path = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
        self.font_path = self._find_hindi_font()

    @staticmethod
    def _find_hindi_font() -> Optional[str]:
        """Locates best available Hindi-supporting TTF/TTC font."""
        candidates = [
            "C:/Windows/Fonts/Nirmala.ttc",
            "C:/Windows/Fonts/mangald.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return None

    def _get_font(self, size: int) -> ImageFont.ImageFont:
        """Loads TTF/TTC font with specified size."""
        if self.font_path:
            try:
                # Pillow supports ttc index=0
                return ImageFont.truetype(self.font_path, size, index=0)
            except Exception:
                try:
                    return ImageFont.truetype(self.font_path, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    def split_into_scenes(self, text: str) -> List[str]:
        """Splits full text into logical video scenes (approx 1-3 sentences per scene)."""
        import re
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        paragraphs = []
        for line in lines:
            # Split by Hindi danda (।) or sentence punctuation
            raw_sentences = re.split(r'([।!?\n]+)', line)
            combined = []
            for i in range(0, len(raw_sentences), 2):
                sent = raw_sentences[i].strip()
                punct = raw_sentences[i+1] if i+1 < len(raw_sentences) else ""
                if sent:
                    combined.append(sent + punct)
            if combined:
                paragraphs.extend(combined)
            else:
                paragraphs.append(line)

        # Merge short sentences into scenes of 80-250 chars
        scenes = []
        curr = ""
        for s in paragraphs:
            if not curr:
                curr = s
            elif len(curr) + len(s) < 180:
                curr += " " + s
            else:
                scenes.append(curr.strip())
                curr = s
        if curr.strip():
            scenes.append(curr.strip())

        return scenes or [text]

    def _draw_radial_gradient(self, draw: ImageDraw.ImageDraw, width: int, height: int, theme: dict):
        """Creates a smooth dark atmospheric gradient background."""
        c1 = theme["bg_start"]
        c2 = theme["bg_end"]
        
        # Vertical linear-radial mix
        for y in range(height):
            ratio = y / height
            r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
            g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
            b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

    def _wrap_text(self, text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
        """Wraps text into lines that fit within max_width."""
        words = text.split()
        if not words:
            return [""]
        lines = []
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            try:
                bbox = draw.textbbox((0, 0), test_line, font=font)
                w = bbox[2] - bbox[0]
            except AttributeError:
                w, _ = draw.textsize(test_line, font=font)

            if w <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
                    current_line = []
        if current_line:
            lines.append(" ".join(current_line))
        return lines

    def render_scene_frame(
        self,
        scene_index: int,
        total_scenes: int,
        scene_text: str,
        title: str,
        aspect_ratio: str = "16:9",
        theme_key: str = "cinematic",
        watermark: str = "AI Story Voice Studio",
    ) -> str:
        """
        Renders a crisp 1080p image frame for a single scene with Hindi text,
        visual background, theme styling, and visualizer elements.
        """
        width, height = RESOLUTIONS.get(aspect_ratio, (1920, 1080))
        theme = THEMES.get(theme_key, THEMES["cinematic"])

        # Base Image
        img = Image.new("RGB", (width, height), theme["bg_start"])
        draw = ImageDraw.Draw(img)

        # 1. Background Gradient
        self._draw_radial_gradient(draw, width, height, theme)

        # 2. Decorative Particles / Stars / Accent Waves
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ol_draw = ImageDraw.Draw(overlay)

        # Subtle glowing circles/particles
        import random
        random.seed(scene_index * 1337)
        for _ in range(35):
            px = random.randint(50, width - 50)
            py = random.randint(50, height - 50)
            pr = random.randint(4, 25)
            p_color = theme["particle_color"]
            ol_draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=p_color)

        # Decorative neon corner accents
        accent = theme["accent"]
        accent_rgba = (accent[0], accent[1], accent[2], 180)
        margin = int(width * 0.04)

        # Top border accent bar
        ol_draw.rectangle([margin, margin, width - margin, margin + 6], fill=accent_rgba)

        # Composite particle overlay
        img = Image.alpha_composite(img.convert("RGBA"), overlay)
        draw = ImageDraw.Draw(img)

        # Fonts scale based on height/width
        header_font_size = int(height * 0.035)
        text_font_size = int(height * 0.048)
        footer_font_size = int(height * 0.024)

        header_font = self._get_font(header_font_size)
        text_font = self._get_font(text_font_size)
        footer_font = self._get_font(footer_font_size)

        # 3. Header Badge ("🎬 SCENE 1 / 4 • STORY VOICE")
        header_text = f"🎬 SCENE {scene_index + 1} OF {total_scenes}"
        if title:
            header_text += f" • {title.upper()}"
        
        header_y = int(height * 0.08)
        draw.text((margin + 15, header_y), header_text, fill=accent, font=header_font)

        # 4. Main Subtitle / Script Text Box
        max_box_width = int(width * 0.85)
        wrapped_lines = self._wrap_text(scene_text, text_font, max_box_width, draw)

        # Calculate line heights
        line_height = int(text_font_size * 1.5)
        total_text_h = len(wrapped_lines) * line_height

        # Card position centered vertically
        card_w = int(width * 0.88)
        card_h = total_text_h + int(height * 0.12)
        card_x = (width - card_w) // 2
        card_y = (height - card_h) // 2

        # Draw translucent card background
        card_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_overlay)
        card_bg = theme["card_bg"]
        card_draw.rounded_rectangle(
            [card_x, card_y, card_x + card_w, card_y + card_h],
            radius=20,
            fill=card_bg,
            outline=accent_rgba,
            width=2,
        )
        img = Image.alpha_composite(img, card_overlay)
        draw = ImageDraw.Draw(img)

        # Render Text lines inside Card
        text_start_y = card_y + (card_h - total_text_h) // 2
        for i, line in enumerate(wrapped_lines):
            try:
                bbox = draw.textbbox((0, 0), line, font=text_font)
                lw = bbox[2] - bbox[0]
            except AttributeError:
                lw, _ = draw.textsize(line, font=text_font)
            
            lx = (width - lw) // 2
            ly = text_start_y + (i * line_height)

            # Drop shadow for ultra high contrast reading
            draw.text((lx + 3, ly + 3), line, fill=(0, 0, 0, 240), font=text_font)
            draw.text((lx, ly), line, fill=theme["text_color"], font=text_font)

        # 5. Audio Waveform Visualizer Animation bars at bottom
        wave_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        wave_draw = ImageDraw.Draw(wave_overlay)
        wave_y = height - int(height * 0.12)
        bar_count = 32
        bar_width = int(width * 0.7) // bar_count
        start_x = (width - (bar_count * bar_width)) // 2

        for b in range(bar_count):
            # Dynamic bar height formula per scene
            phase = (b * 0.3) + (scene_index * 1.5)
            b_height = int((math.sin(phase) * 0.4 + 0.5) * (height * 0.06)) + 8
            bx = start_x + (b * bar_width)
            by1 = wave_y - (b_height // 2)
            by2 = wave_y + (b_height // 2)
            wave_draw.rounded_rectangle(
                [bx + 2, by1, bx + bar_width - 2, by2],
                radius=4,
                fill=accent_rgba,
            )
        img = Image.alpha_composite(img, wave_overlay)
        draw = ImageDraw.Draw(img)

        # 6. Watermark Footer
        footer_text = f"🎙️ {watermark} | AI Text to Video"
        footer_y = height - int(height * 0.05)
        draw.text((margin + 15, footer_y), footer_text, fill=(200, 200, 220), font=footer_font)

        # Save frame PNG
        frame_filename = f"frame_{scene_index:03d}.png"
        frame_path = os.path.join(self.temp_dir, frame_filename)
        img.convert("RGB").save(frame_path, quality=95)
        return frame_path

    def get_audio_duration(self, audio_path: str) -> float:
        """Measures exact duration in seconds of an audio file using ffprobe/pydub."""
        if not os.path.isfile(audio_path):
            return 3.0
        try:
            from pydub import AudioSegment
            seg = AudioSegment.from_file(audio_path)
            return len(seg) / 1000.0
        except Exception:
            pass

        # Fallback ffprobe
        ffprobe = shutil.which("ffprobe") or "/usr/bin/ffprobe"
        if ffprobe:
            try:
                cmd = [
                    ffprobe, "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    audio_path
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                val = float(res.stdout.strip())
                if val > 0:
                    return val
            except Exception:
                pass
        return 4.0

    def generate_video(
        self,
        text: str,
        config: dict,
        tts_provider,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Complete end-to-end Text-to-Video generation process.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        job_temp_dir = os.path.join(self.temp_dir, f"video_job_{timestamp}")
        os.makedirs(job_temp_dir, exist_ok=True)

        try:
            aspect_ratio = config.get("aspect_ratio", "16:9")
            theme_key = config.get("theme", "cinematic")
            voice_gender = config.get("voice_gender", "female")
            voice_preset = config.get("voice_preset", f"{voice_gender}_normal")
            speed = config.get("speed", "Normal")
            pitch = float(config.get("pitch", 0) or 0)

            # Resolve TTS parameters
            from engines.voice_mapper import resolve_preset
            resolved = resolve_preset(voice_preset, voice_gender)
            voice = resolved["voice"]
            rate_str = "+0%" if speed == "Normal" else ("-20%" if speed == "Slow" else "+20%")
            pitch_hz = int(max(-1.0, min(1.0, pitch)) * 20) + int(resolved.get("pitch", 0))
            pitch_str = f"{pitch_hz:+d}Hz"

            if progress_callback:
                progress_callback(10, "Splitting story into video scenes…")

            scenes = self.split_into_scenes(text)
            total_scenes = len(scenes)

            scene_clips = []

            for idx, scene_text in enumerate(scenes):
                if progress_callback:
                    pct = 15 + int((idx / total_scenes) * 65)
                    progress_callback(pct, f"Rendering scene {idx + 1}/{total_scenes} audio & visual frame…")

                # 1. Synthesize Audio for scene
                scene_audio_path = os.path.join(job_temp_dir, f"audio_{idx:03d}.mp3")
                tts_provider.synthesize_sync(scene_text, voice, rate_str, pitch_str, scene_audio_path)

                # 2. Get exact duration
                duration = self.get_audio_duration(scene_audio_path)

                # 3. Render Visual Frame image
                frame_img_path = self.render_scene_frame(
                    scene_index=idx,
                    total_scenes=total_scenes,
                    scene_text=scene_text,
                    title=config.get("title", "AI Story"),
                    aspect_ratio=aspect_ratio,
                    theme_key=theme_key,
                )

                # 4. Render Scene MP4 Video clip using FFmpeg
                scene_mp4_path = os.path.join(job_temp_dir, f"clip_{idx:03d}.mp4")
                cmd = [
                    self.ffmpeg_path, "-y",
                    "-loop", "1", "-i", frame_img_path,
                    "-i", scene_audio_path,
                    "-c:v", "libx264", "-tune", "stillimage",
                    "-c:a", "aac", "-b:a", "192k",
                    "-pix_fmt", "yuv420p",
                    "-t", str(duration),
                    scene_mp4_path
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if res.returncode != 0:
                    raise RuntimeError(f"FFmpeg failed for scene {idx + 1}: {res.stderr}")

                scene_clips.append(scene_mp4_path)

            if progress_callback:
                progress_callback(85, "Stitching final MP4 Video…")

            # Concatenate all scene MP4 clips
            output_filename = f"video_{timestamp}.mp4"
            final_video_path = os.path.join(self.output_dir, output_filename)

            if len(scene_clips) == 1:
                shutil.copy(scene_clips[0], final_video_path)
            else:
                concat_list_path = os.path.join(job_temp_dir, "concat_list.txt")
                with open(concat_list_path, "w", encoding="utf-8") as f:
                    for clip in scene_clips:
                        abs_clip = os.path.abspath(clip).replace("\\", "/")
                        f.write(f"file '{abs_clip}'\n")

                concat_cmd = [
                    self.ffmpeg_path, "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", concat_list_path,
                    "-c", "copy",
                    final_video_path
                ]
                res = subprocess.run(concat_cmd, capture_output=True, text=True, timeout=300)
                if res.returncode != 0:
                    raise RuntimeError(f"FFmpeg concat failed: {res.stderr}")

            if progress_callback:
                progress_callback(100, "Video completed successfully!")

            file_size_mb = round(os.path.getsize(final_video_path) / (1024 * 1024), 2)
            total_duration = sum(self.get_audio_duration(c) for c in scene_clips)

            return {
                "success": True,
                "filename": output_filename,
                "output_path": final_video_path,
                "download_url": f"/download_video/{output_filename}",
                "aspect_ratio": aspect_ratio,
                "resolution": RESOLUTIONS.get(aspect_ratio, (1920, 1080)),
                "theme": THEMES.get(theme_key, {}).get("name", theme_key),
                "total_scenes": total_scenes,
                "duration_seconds": round(total_duration, 1),
                "file_size_mb": file_size_mb,
            }

        finally:
            # Clean up job temp files
            if os.path.isdir(job_temp_dir):
                try:
                    shutil.rmtree(job_temp_dir, ignore_errors=True)
                except Exception:
                    pass
