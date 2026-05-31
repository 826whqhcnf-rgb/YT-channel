"""
Thin wrapper around the ffmpeg/ffprobe binaries.

Prefers the system ffmpeg (installed via apt in the devcontainer). If that's
missing for any reason, it falls back to the binary bundled with the
`imageio-ffmpeg` pip package, so rendering works even on a bare machine.
"""

from __future__ import annotations

import re
import shutil
import subprocess


def _resolve_ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return "ffmpeg"  # last resort; will error clearly if absent


FFMPEG = _resolve_ffmpeg()
FFPROBE = shutil.which("ffprobe")  # may be None (imageio bundle has no ffprobe)


def run(args: list[str]) -> None:
    """Run ffmpeg with the given args. Raises RuntimeError with stderr on failure."""
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *args]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip()[-1500:]
        raise RuntimeError("ffmpeg failed:\n  " + " ".join(cmd) + "\n" + tail)


def duration(path: str) -> float:
    """Media duration in seconds. Uses ffprobe if available, else parses ffmpeg."""
    if FFPROBE:
        out = subprocess.run(
            [
                FFPROBE,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nokey=1:noprint_wrappers=1",
                path,
            ],
            capture_output=True,
            text=True,
        )
        try:
            return float(out.stdout.strip())
        except (ValueError, AttributeError):
            pass
    proc = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", proc.stderr or "")
    if m:
        h, mm, s = m.groups()
        return int(h) * 3600 + int(mm) * 60 + float(s)
    return 0.0


def silent_audio(path: str, seconds: float) -> None:
    """Generate a silent MP3 of the given length (used as a TTS fallback)."""
    run(
        [
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            f"{max(seconds, 0.5):.2f}",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "9",
            path,
        ]
    )
