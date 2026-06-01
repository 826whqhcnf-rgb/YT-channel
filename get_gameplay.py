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
    print("Downloading gameplay clip... (this can take a minute)")
    print("⚠️  Make sure this video is licensed for reuse (no-copyright / CC).")

    # YouTube blocks datacenter IPs (Codespaces) with "confirm you're not a bot".
    # Some client APIs slip past this, so try several before giving up. If the
    # user exported cookies to cookies.txt, use them (most reliable).
    clients = ["tv", "ios", "web_safari", "android", "mweb"]
    base = [sys.executable, "-m", "yt_dlp", "-f", fmt,
            "--merge-output-format", "mp4", "-o", outtmpl]
    if os.path.exists("cookies.txt"):
        base += ["--cookies", "cookies.txt"]
        print("Using cookies.txt for authentication.")

    rc = 1
    for client in clients:
        print(f"\n→ Trying YouTube client: {client}")
        rc = subprocess.run(
            base + ["--extractor-args", f"youtube:player_client={client}", url]
        ).returncode
        if rc == 0:
            break

    if rc != 0:
        print("\n❌ Download failed — YouTube is blocking this datacenter IP.")
        print("   Fixes, easiest first:")
        print("   1. Try a different no-copyright gameplay video (some work, some don't).")
        print("   2. Download the clip on your OWN computer, then drag-and-drop the")
        print("      .mp4 into the assets/gameplay folder on the left.")
        print("   3. Export YouTube cookies to a file named cookies.txt in this")
        print("      folder (see yt-dlp wiki) and run this command again.")
        return rc

    clips = [f for f in os.listdir(DEST_DIR) if f.lower().endswith(".mp4")]
    print(f"\n✅ Done. Gameplay clips now in {DEST_DIR}/: {', '.join(clips)}")
    print("   Make a video:  python run.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
