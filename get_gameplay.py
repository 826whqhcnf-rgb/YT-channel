#!/usr/bin/env python3
"""
Download a gameplay background clip from YouTube into assets/gameplay/.

  python get_gameplay.py "https://youtu.be/VIDEO_ID"
  python get_gameplay.py "https://youtu.be/VIDEO_ID" --name subway1

The renderer then plays it (looped, cropped to 9:16) behind your stories.

⚠️  Only download videos you are allowed to use ("no copyright" / "free to use"
    / Creative Commons gameplay). Using copyrighted footage can get your videos
    muted, demonetised, or removed.
"""
import argparse
import os
import re
import subprocess
import sys

DEST_DIR = os.path.join("assets", "gameplay")


def main():
    p = argparse.ArgumentParser(description="Download a gameplay background clip")
    p.add_argument("url", help="YouTube URL of a no-copyright gameplay video")
    p.add_argument("--name", help="Filename (without extension) to save as")
    p.add_argument("--max-height", type=int, default=1920,
                   help="Cap resolution to keep the file small (default 1920)")
    args = p.parse_args()

    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        print("yt-dlp is not installed. Run:  pip install -r requirements.txt")
        return 1

    # Strip stray wrapping that often comes from pasting (angle brackets, quotes,
    # zero-width/whitespace) so "<https://...>" still works.
    url = args.url.strip().strip("<>\"' \t​")

    os.makedirs(DEST_DIR, exist_ok=True)
    name = args.name or "%(title).50s-%(id)s"
    # keep filenames filesystem-safe
    outtmpl = os.path.join(DEST_DIR, re.sub(r"[^\w%().\-]", "_", name) + ".%(ext)s")

    fmt = f"bestvideo[height<={args.max_height}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", fmt,
        "--merge-output-format", "mp4",
        "-o", outtmpl,
        url,
    ]
    print("Downloading gameplay clip... (this can take a minute)")
    print("⚠️  Make sure this video is licensed for reuse (no-copyright / CC).")
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        print("\nDownload failed. Check the URL, or try a different clip.")
        return rc

    clips = [f for f in os.listdir(DEST_DIR) if f.lower().endswith(".mp4")]
    print(f"\n✅ Done. Gameplay clips now in {DEST_DIR}/: {', '.join(clips)}")
    print("   Make a video:  python run.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
