"""
Text-to-speech using edge-tts (free Microsoft neural voices, no API key).

Produces one MP3 per narration segment and reports its duration so the
assembler can sync visuals to the voiceover.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import edge_tts


@dataclass
class VoiceClip:
    text: str
    path: str
    duration: float


def _probe_duration(path: str) -> float:
    """Get audio duration via moviepy (ffmpeg under the hood)."""
    from moviepy.editor import AudioFileClip

    clip = AudioFileClip(path)
    d = float(clip.duration)
    clip.close()
    return d


async def _synthesize_one(text: str, path: str, voice: str, rate: str) -> None:
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    await communicate.save(path)


def synthesize(
    segments: list[str],
    out_dir: str,
    voice: str = "en-US-AndrewNeural",
    rate: str = "+0%",
    prefix: str = "seg",
) -> list[VoiceClip]:
    """Synthesize each text segment to its own MP3. Returns clips in order."""
    os.makedirs(out_dir, exist_ok=True)
    clips: list[VoiceClip] = []

    async def run_all() -> None:
        for i, text in enumerate(segments):
            path = os.path.join(out_dir, f"{prefix}_{i:02d}.mp3")
            await _synthesize_one(text, path, voice, rate)
            clips.append(VoiceClip(text=text, path=path, duration=0.0))

    asyncio.run(run_all())

    for clip in clips:
        clip.duration = _probe_duration(clip.path)
    return clips
