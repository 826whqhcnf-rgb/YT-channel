"""Download stock footage/photos from Pexels. Returns None gracefully if no key."""
import hashlib, os, random, requests


def fetch(keyword: str, cache_dir: str, pexels_key: str) -> tuple[str | None, str]:
    """Returns (local_path, kind) where kind is 'video', 'photo', or 'none'."""
    if not pexels_key:
        return None, "none"
    os.makedirs(cache_dir, exist_ok=True)

    # Try video first, fall back to photo
    path = _video(keyword, cache_dir, pexels_key) or _photo(keyword, cache_dir, pexels_key)
    if path:
        kind = "video" if path.endswith(".mp4") else "photo"
        return path, kind
    return None, "none"


def _download(url: str, dest: str) -> str | None:
    if os.path.exists(dest) and os.path.getsize(dest) > 512:
        return dest
    try:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
        return dest
    except Exception as e:
        print(f"[footage] download failed ({e})")
        return None


def _cache(cache_dir: str, url: str, ext: str) -> str:
    h = hashlib.md5(url.encode()).hexdigest()[:12]
    return os.path.join(cache_dir, f"{h}.{ext}")


def _video(keyword: str, cache_dir: str, key: str) -> str | None:
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": key},
            params={"query": keyword, "per_page": 6, "orientation": "portrait"},
            timeout=15,
        )
        r.raise_for_status()
        videos = r.json().get("videos", [])
        if not videos:
            return None
        video = random.choice(videos[:4])
        files = video.get("video_files", [])
        # Pick ~1080p portrait, never 4K
        portrait = [f for f in files if f.get("height", 0) >= f.get("width", 1)
                    and f.get("height", 9999) <= 1920]
        if not portrait:
            portrait = files
        portrait.sort(key=lambda f: abs((f.get("height") or 0) - 1080))
        best = portrait[0] if portrait else None
        if not best:
            return None
        return _download(best["link"], _cache(cache_dir, best["link"], "mp4"))
    except Exception as e:
        print(f"[footage] video search failed ({e})")
        return None


def _photo(keyword: str, cache_dir: str, key: str) -> str | None:
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": key},
            params={"query": keyword, "per_page": 6, "orientation": "portrait"},
            timeout=15,
        )
        r.raise_for_status()
        photos = r.json().get("photos", [])
        if not photos:
            return None
        photo = random.choice(photos[:4])
        url = photo["src"].get("large2x") or photo["src"]["large"]
        return _download(url, _cache(cache_dir, url, "jpg"))
    except Exception as e:
        print(f"[footage] photo search failed ({e})")
        return None
