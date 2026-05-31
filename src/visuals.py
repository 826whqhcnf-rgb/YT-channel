"""
Fetch background visuals from Pexels (free API) with graceful fallbacks.

- video source: downloads short stock clips matching a keyword.
- photo source: downloads stills (the assembler applies a Ken Burns zoom).
- no key / no result: a gradient color clip is generated so the pipeline
  never hard-fails.
"""

from __future__ import annotations

import hashlib
import os
import random

import requests

PEXELS_VIDEO = "https://api.pexels.com/videos/search"
PEXELS_PHOTO = "https://api.pexels.com/v1/search"


def _cache_path(cache_dir: str, url: str, ext: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    h = hashlib.md5(url.encode()).hexdigest()[:16]
    return os.path.join(cache_dir, f"{h}.{ext}")


def _download(url: str, dest: str) -> str:
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
    return dest


def _pick_video_file(files: list[dict], orientation: str) -> dict | None:
    """Pick a ~1080p file. Avoid 4K sources — decoding them is the biggest
    memory hog and can get the process killed on small machines."""
    want_portrait = orientation == "vertical"
    candidates = []
    for f in files:
        w, h = f.get("width") or 0, f.get("height") or 0
        if not w or not h:
            continue
        is_portrait = h >= w
        if is_portrait == want_portrait:
            candidates.append(f)
    pool = candidates or [f for f in files if f.get("width") and f.get("height")]
    if not pool:
        return None

    # "short side" is what must cover the frame (width for vertical, height else).
    def short_side(f: dict) -> int:
        return min(f["width"], f["height"]) if want_portrait else f["height"]

    target = 1080
    # Prefer files whose short side is in [1080, 1440]; else the closest one.
    ideal = [f for f in pool if target <= short_side(f) <= 1440]
    if ideal:
        ideal.sort(key=lambda f: short_side(f))
        return ideal[0]
    pool.sort(key=lambda f: abs(short_side(f) - target))
    return pool[0]


def fetch_video(keyword: str, cache_dir: str, orientation: str, api_key: str) -> str | None:
    if not api_key:
        return None
    try:
        resp = requests.get(
            PEXELS_VIDEO,
            headers={"Authorization": api_key},
            params={
                "query": keyword,
                "per_page": 8,
                "orientation": "portrait" if orientation == "vertical" else "landscape",
            },
            timeout=30,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
        if not videos:
            return None
        video = random.choice(videos[: min(5, len(videos))])
        vf = _pick_video_file(video.get("video_files", []), orientation)
        if not vf:
            return None
        dest = _cache_path(cache_dir, vf["link"], "mp4")
        return _download(vf["link"], dest)
    except Exception as e:  # noqa: BLE001
        print(f"[visuals] Pexels video fetch failed for '{keyword}': {e}")
        return None


def fetch_photo(keyword: str, cache_dir: str, orientation: str, api_key: str) -> str | None:
    if not api_key:
        return None
    try:
        resp = requests.get(
            PEXELS_PHOTO,
            headers={"Authorization": api_key},
            params={
                "query": keyword,
                "per_page": 8,
                "orientation": "portrait" if orientation == "vertical" else "landscape",
            },
            timeout=30,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            return None
        photo = random.choice(photos[: min(5, len(photos))])
        src = photo["src"].get("large2x") or photo["src"].get("large") or photo["src"]["original"]
        dest = _cache_path(cache_dir, src, "jpg")
        return _download(src, dest)
    except Exception as e:  # noqa: BLE001
        print(f"[visuals] Pexels photo fetch failed for '{keyword}': {e}")
        return None


def fetch(keyword: str, source: str, cache_dir: str, orientation: str, api_key: str):
    """Return (path, kind) where kind is 'video', 'photo', or 'none'."""
    if source == "video":
        path = fetch_video(keyword, cache_dir, orientation, api_key)
        if path:
            return path, "video"
        # fall back to a photo before giving up
        path = fetch_photo(keyword, cache_dir, orientation, api_key)
        if path:
            return path, "photo"
    else:
        path = fetch_photo(keyword, cache_dir, orientation, api_key)
        if path:
            return path, "photo"
    return None, "none"
