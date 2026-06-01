#!/usr/bin/env python3
"""
Get a gameplay background clip into assets/gameplay/.

  python get_gameplay.py                       # auto: find a free clip on Archive.org
  python get_gameplay.py --search "minecraft parkour"
  python get_gameplay.py "https://youtu.be/VIDEO_ID"   # from YouTube (often IP-blocked on cloud)
  python get_gameplay.py "https://.../clip.mp4"         # any direct .mp4 link

The renderer then plays it (looped, cropped to 9:16) behind your stories.

⚠️  Only use footage you are allowed to ("no copyright" / "free to use" / public
    domain / Creative Commons). Archive.org's auto mode prefers such items, but
    you are responsible for what you publish.
"""
import argparse
import os
import re
import subprocess
import sys

DEST_DIR = os.path.join("assets", "gameplay")


def main():
    p = argparse.ArgumentParser(description="Get a gameplay background clip")
    p.add_argument("url", nargs="?", help="YouTube or direct .mp4 URL (optional)")
    p.add_argument("--search", help="Search Archive.org for this gameplay and download one")
    p.add_argument("--name", help="Filename (without extension) to save as")
    p.add_argument("--max-height", type=int, default=1920,
                   help="Cap resolution to keep the file small (default 1920)")
    args = p.parse_args()

    # No URL given (or --search): auto-fetch a free clip from Archive.org.
    if not args.url or args.search:
        return _from_archive(args.search or "subway surfers gameplay")

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

    print("Downloading gameplay clip... (this can take a minute)")
    print("⚠️  Make sure this video is licensed for reuse (no-copyright / CC).")

    # Direct stream URL (e.g. googlevideo.com/videoplayback...) bypasses YouTube's
    # bot check entirely — just fetch the file straight with requests.
    if "googlevideo.com/videoplayback" in url or "/videoplayback?" in url:
        return _download_direct(url)

    fmt = f"bestvideo[height<={args.max_height}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

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


def _from_archive(query: str) -> int:
    """Search Archive.org for a gameplay video and download a clip from it.

    Archive.org hosts lots of gameplay (Subway Surfers, Minecraft parkour, etc.)
    and serves direct file downloads with NO bot check / IP lock — so this works
    from a Codespace where YouTube does not.
    """
    import requests

    UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"}
    os.makedirs(DEST_DIR, exist_ok=True)
    print(f"Searching Archive.org for: {query}")

    # 1. Find candidate items (movies mediatype).
    try:
        r = requests.get(
            "https://archive.org/advancedsearch.php",
            params={"q": f'({query}) AND mediatype:(movies)',
                    "fl[]": "identifier", "rows": "25", "output": "json"},
            headers=UA, timeout=40,
        )
        r.raise_for_status()
        ids = [d["identifier"] for d in r.json()["response"]["docs"]]
    except Exception as e:  # noqa: BLE001
        print(f"❌ Archive.org search failed ({e}).")
        print("   Your network may be blocking it. Try the manual upload method")
        print("   in assets/gameplay/README.md.")
        return 1

    if not ids:
        print("No results. Try a different --search term (e.g. 'minecraft parkour').")
        return 1

    # 2. For each item, find a reasonably-sized .mp4 file and download it.
    for ident in ids:
        try:
            meta = requests.get(f"https://archive.org/metadata/{ident}",
                                headers=UA, timeout=40).json()
        except Exception:
            continue
        files = meta.get("files", [])
        mp4s = []
        for f in files:
            name = f.get("name", "")
            if not name.lower().endswith(".mp4"):
                continue
            size = int(f.get("size", 0) or 0)
            # 5 MB .. 600 MB: big enough to be real gameplay, small enough to fetch.
            if 5_000_000 <= size <= 600_000_000:
                mp4s.append((size, name))
        if not mp4s:
            continue
        mp4s.sort()
        _size, fname = mp4s[len(mp4s) // 2]  # middle = decent length, not huge
        url = f"https://archive.org/download/{ident}/{requests.utils.quote(fname)}"
        print(f"Found: {ident} → {fname} ({_size//1_000_000} MB)")
        dest = os.path.join(DEST_DIR, "gameplay.mp4")
        if _stream_to(url, dest, UA):
            print(f"\n✅ Done. Saved {dest} ({os.path.getsize(dest)//1_000_000} MB).")
            print(f"   Source: https://archive.org/details/{ident}")
            print("   ⚠️  Check that item's license before publishing widely.")
            print("   Make a video:  python run.py")
            return 0
        print("   (that file failed; trying another item...)")

    print("❌ Could not download any clip. Try a different --search term, or the")
    print("   manual upload method in assets/gameplay/README.md.")
    return 1


def _stream_to(url: str, dest: str, headers: dict) -> bool:
    import requests
    try:
        with requests.get(url, headers=headers, stream=True, timeout=180,
                          allow_redirects=True) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length", 0))
            done = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        print(f"\r  {done*100//total:3d}%  ({done//1_000_000} MB)",
                              end="", flush=True)
        print()
        return os.path.getsize(dest) > 100_000
    except Exception as e:  # noqa: BLE001
        print(f"\n  download error ({e})")
        return False


def _download_direct(url: str) -> int:
    """Fetch a direct video stream URL (googlevideo videoplayback link)."""
    import requests

    os.makedirs(DEST_DIR, exist_ok=True)
    dest = os.path.join(DEST_DIR, "gameplay.mp4")
    print("Detected a direct stream URL — downloading the file directly.")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                             "AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/124.0.0.0 Safari/537.36"}
    try:
        with requests.get(url, headers=headers, stream=True, timeout=120) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length", 0))
            done = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 20):  # 1 MB
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = done * 100 // total
                        print(f"\r  {pct:3d}%  ({done//1_000_000} MB)", end="", flush=True)
        print()
    except Exception as e:  # noqa: BLE001
        print(f"\n❌ Direct download failed ({e}).")
        return 1

    size = os.path.getsize(dest)
    if size < 100_000:
        print(f"❌ Downloaded file is too small ({size} bytes) — the link may have "
              "expired. Direct googlevideo links only last a few hours; grab a fresh one.")
        return 1
    print(f"\n✅ Done. Saved {dest} ({size//1_000_000} MB).")
    print("   Make a video:  python run.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
