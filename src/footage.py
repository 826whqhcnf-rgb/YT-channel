"""
Download stock footage/photos from Pexels, tuned for vertical story videos:
- prefers HD vertical *video* clips, with smart fallbacks to a related search
  and then a photo, so each segment gets relevant, good-looking B-roll.
- returns None gracefully if no key / nothing found (caller uses a gradient).
"""
import hashlib, os, random, re, requests

# Generic words that make stock searches worse — strip them from keywords.
_STOP = {
    "the", "a", "an", "and", "or", "but", "my", "your", "his", "her", "their",
    "our", "of", "to", "in", "on", "for", "with", "at", "by", "from", "is",
    "was", "were", "are", "be", "it", "this", "that", "so", "i", "me", "we",
}


def clean_keyword(raw: str, fallback: str = "dramatic cinematic background") -> str:
    """Turn a freeform phrase into a tight 1-3 word stock-search query."""
    words = re.findall(r"[a-zA-Z]+", (raw or "").lower())
    words = [w for w in words if w not in _STOP and len(w) > 2]
    if not words:
        return fallback
    return " ".join(words[:3])


def fetch(keyword: str, cache_dir: str, pexels_key: str) -> tuple[str | None, str]:
    """Returns (local_path, kind) where kind is 'video', 'photo', or 'none'."""
    if not pexels_key:
        return None, "none"
    os.makedirs(cache_dir, exist_ok=True)

    q = clean_keyword(keyword)
    # 1) vertical video on the cleaned keyword
    # 2) vertical video on just the first word (broader)
    # 3) photo on the cleaned keyword
    broad = q.split()[0] if q else q
    path = (
        _video(q, cache_dir, pexels_key)
        or (_video(broad, cache_dir, pexels_key) if broad != q else None)
        or _photo(q, cache_dir, pexels_key)
    )
    if path:
        return path, ("video" if path.endswith(".mp4") else "photo")
    return None, "none"


def _download(url: str, dest: str) -> str | None:
    if os.path.exists(dest) and os.path.getsize(dest) > 512:
        return dest
    try:
        with requests.get(url, stream=True, timeout=90) as r:
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
            params={"query": keyword, "per_page": 15, "orientation": "portrait",
                    "size": "medium"},
            timeout=20,
        )
        r.raise_for_status()
        videos = r.json().get("videos", [])
        # Keep clips that are long enough to fill a segment and truly vertical.
        good = [v for v in videos
                if v.get("duration", 0) >= 4
                and v.get("height", 0) >= v.get("width", 1)]
        pool = good or videos
        if not pool:
            return None
        video = random.choice(pool[:8])
        files = video.get("video_files", [])
        # Prefer a vertical file whose short side is ~1080 (HD, not 4K).
        portrait = [f for f in files
                    if f.get("height", 0) >= f.get("width", 1) and f.get("width")]
        portrait = portrait or files
        portrait.sort(key=lambda f: abs((f.get("width") or 0) - 1080))
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
            params={"query": keyword, "per_page": 15, "orientation": "portrait"},
            timeout=20,
        )
        r.raise_for_status()
        photos = r.json().get("photos", [])
        if not photos:
            return None
        photo = random.choice(photos[:8])
        src = photo["src"]
        url = src.get("portrait") or src.get("large2x") or src.get("large")
        return _download(url, _cache(cache_dir, url, "jpg"))
    except Exception as e:
        print(f"[footage] photo search failed ({e})")
        return None
