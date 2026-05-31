"""Thin wrapper around ffmpeg. Prefers system binary; falls back to imageio-ffmpeg bundle."""
import re, shutil, subprocess


def _find_ffmpeg() -> str:
    sys_ff = shutil.which("ffmpeg")
    if sys_ff:
        return sys_ff
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


FF = _find_ffmpeg()
FP = shutil.which("ffprobe")


def run(args: list[str]) -> None:
    cmd = [FF, "-y", "-hide_banner", "-loglevel", "error", *args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{(r.stderr or '').strip()[-800:]}")


def duration(path: str) -> float:
    if FP:
        r = subprocess.run(
            [FP, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nokey=1:noprint_wrappers=1", path],
            capture_output=True, text=True,
        )
        try:
            return float(r.stdout.strip())
        except ValueError:
            pass
    r = subprocess.run([FF, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", r.stderr or "")
    if m:
        h, mm, s = m.groups()
        return int(h) * 3600 + int(mm) * 60 + float(s)
    return 1.0


def silent_audio(path: str, secs: float) -> None:
    run(["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
         "-t", f"{secs:.2f}", "-c:a", "libmp3lame", "-q:a", "9", path])
