"""
Free neural TTS via edge-tts, capturing per-WORD timings so captions can be
synced to the narration. Retries on network errors; falls back to silence.
"""
import asyncio, os, time
from dataclasses import dataclass, field

import edge_tts
from . import ffmpeg_runner as ff


@dataclass
class Word:
    text: str
    start: float   # seconds from the start of this clip
    end: float


@dataclass
class Clip:
    path: str
    duration: float
    words: list[Word] = field(default_factory=list)


async def _synth_with_marks(text: str, path: str, voice: str, rate: str) -> list[Word]:
    """Synthesize one segment and collect WordBoundary timings."""
    words: list[Word] = []
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    with open(path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 10_000_000          # 100ns ticks -> s
                dur = chunk["duration"] / 10_000_000
                words.append(Word(text=chunk["text"], start=start, end=start + dur))
    return words


def _even_split(text: str, total: float) -> list[Word]:
    """Fallback timing: spread words evenly across the clip duration."""
    toks = text.split()
    if not toks:
        return []
    per = total / len(toks)
    return [Word(t, i * per, (i + 1) * per) for i, t in enumerate(toks)]


def synthesize(texts: list[str], out_dir: str, voice: str, rate: str = "+8%") -> list[Clip]:
    os.makedirs(out_dir, exist_ok=True)
    clips: list[Clip] = []
    for i, text in enumerate(texts):
        text = (text or "").strip()
        path = os.path.join(out_dir, f"seg_{i:02d}.mp3")
        words: list[Word] = []
        ok = False
        for attempt in range(3):
            try:
                words = asyncio.run(_synth_with_marks(text, path, voice, rate))
                if os.path.exists(path) and os.path.getsize(path) > 0:
                    ok = True
                    break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                else:
                    print(f"[voice] segment {i} failed ({e}); using silence.")
        if not ok:
            n = max(1, len(text.split()))
            ff.silent_audio(path, max(1.5, n / 2.5))
        dur = ff.duration(path)
        # If timings are missing (older edge-tts / silence), spread evenly.
        if not words:
            words = _even_split(text, dur)
        clips.append(Clip(path=path, duration=dur, words=words))
    return clips
