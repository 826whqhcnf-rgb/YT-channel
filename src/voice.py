"""Free neural TTS via edge-tts. Retries on network errors; falls back to silence."""
import asyncio, os, time
from dataclasses import dataclass
import edge_tts
from . import ffmpeg_runner as ff


@dataclass
class Clip:
    path: str
    duration: float


async def _synth(text: str, path: str, voice: str, rate: str):
    await edge_tts.Communicate(text, voice=voice, rate=rate).save(path)


def synthesize(texts: list[str], out_dir: str, voice: str, rate: str = "+8%") -> list[Clip]:
    os.makedirs(out_dir, exist_ok=True)
    clips = []
    for i, text in enumerate(texts):
        path = os.path.join(out_dir, f"seg_{i:02d}.mp3")
        ok = False
        for attempt in range(3):
            try:
                asyncio.run(_synth(text.strip(), path, voice, rate))
                if os.path.exists(path) and os.path.getsize(path) > 0:
                    ok = True
                    break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                else:
                    print(f"[voice] segment {i} failed ({e}); using silence.")
        if not ok:
            words = max(1, len(text.split()))
            ff.silent_audio(path, max(1.5, words / 2.5))
        clips.append(Clip(path=path, duration=ff.duration(path)))
    return clips
