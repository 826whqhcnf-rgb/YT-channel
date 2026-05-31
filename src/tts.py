"""
Text-to-speech using edge-tts (free Microsoft neural voices, no API key).

Hardened so a single failed segment never aborts the whole video:
  * empty text is skipped,
  * edge-tts is retried a few times,
  * if it still fails (e.g. transient network), a silent clip of an
    estimated length is generated so rendering can continue.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass

import edge_tts

from . import ffmpeg_tools


@dataclass
class VoiceClip:
    text: str
    path: str
    duration: float


async def _synthesize_one(text: str, path: str, voice: str, rate: str) -> None:
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    await communicate.save(path)


def _estimate_seconds(text: str) -> float:
    # ~2.5 words/second of speech; floor so very short lines still show.
    words = max(1, len(text.split()))
    return max(1.5, words / 2.5)


def synthesize(
    segments: list[str],
    out_dir: str,
    voice: str = "en-US-AndrewNeural",
    rate: str = "+0%",
    prefix: str = "seg",
    retries: int = 3,
) -> list[VoiceClip]:
    """Synthesize each text segment to its own MP3. Always returns a clip
    per segment (silent if speech synthesis failed)."""
    os.makedirs(out_dir, exist_ok=True)
    clips: list[VoiceClip] = []

    for i, raw in enumerate(segments):
        text = (raw or "").strip()
        path = os.path.join(out_dir, f"{prefix}_{i:02d}.mp3")
        ok = False

        if text:
            for attempt in range(retries):
                try:
                    asyncio.run(_synthesize_one(text, path, voice, rate))
                    if os.path.exists(path) and os.path.getsize(path) > 0:
                        ok = True
                        break
                except Exception as e:  # noqa: BLE001
                    if attempt == retries - 1:
                        print(f"[tts] segment {i} failed after {retries} tries ({e}).")
                    else:
                        time.sleep(2 * (attempt + 1))

        if not ok:
            print(f"[tts] Using silent fallback for segment {i}.")
            ffmpeg_tools.silent_audio(path, _estimate_seconds(text))

        clips.append(VoiceClip(text=text, path=path, duration=ffmpeg_tools.duration(path)))

    return clips
