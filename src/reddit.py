"""
Fetch real stories straight from Reddit's public JSON (no API key needed).

Pulls top text posts from story subreddits, skips ones already used, cleans the
markdown, and returns a post dict. Tracks used IDs so batches don't repeat.
"""
from __future__ import annotations

import html
import os
import random
import re

import requests

# A descriptive User-Agent is required or Reddit returns 429/403.
USER_AGENT = "python:faceless-story-generator:1.0 (personal use)"

# Best-performing story subreddits.
DEFAULT_SUBREDDITS = [
    "AmItheAsshole",
    "tifu",
    "ProRevenge",
    "MaliciousCompliance",
    "pettyrevenge",
    "entitledparents",
    "relationship_advice",
    "TrueOffMyChest",
]

# Mood-matching B-roll keywords per subreddit (cycled across segments).
MOODS = {
    "AmItheAsshole": ["tense conversation", "family dinner argument", "person thinking"],
    "tifu": ["awkward moment", "busy office", "city street day"],
    "ProRevenge": ["dramatic storm clouds", "city skyline night", "person walking away"],
    "MaliciousCompliance": ["office desk paperwork", "workplace", "clock ticking"],
    "pettyrevenge": ["rainy window", "city street night", "smirking person"],
    "entitledparents": ["shopping mall", "parking lot", "crowded store"],
    "relationship_advice": ["couple silhouette sunset", "sad person window", "rainy street night"],
    "TrueOffMyChest": ["person alone window", "moody sky", "quiet room"],
}
DEFAULT_MOOD = ["dramatic clouds", "city street night", "rainy window", "moody sunset"]

USED_FILE = os.path.join("data", "used_reddit.txt")


def _load_used() -> set[str]:
    if os.path.exists(USED_FILE):
        with open(USED_FILE, encoding="utf-8") as f:
            return {ln.strip() for ln in f if ln.strip()}
    return set()


def _mark_used(post_id: str) -> None:
    os.makedirs(os.path.dirname(USED_FILE), exist_ok=True)
    with open(USED_FILE, "a", encoding="utf-8") as f:
        f.write(post_id + "\n")


def _clean(text: str) -> str:
    text = html.unescape(text or "")
    text = text.replace("​", " ").replace("&#x200B;", " ")
    # markdown links [label](url) -> label
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # bare URLs
    text = re.sub(r"https?://\S+", "", text)
    # drop "Edit:" / "Update:" / "TL;DR" trailers
    text = re.split(r"\n+\s*(?:edit|update|tl;?dr)\b", text, flags=re.IGNORECASE)[0]
    # strip markdown symbols
    text = re.sub(r"[*_>#`~]", "", text)
    # collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _top_posts(subreddit: str, time_filter: str, limit: int) -> list[dict]:
    last_err = ""
    for host in ("https://www.reddit.com", "https://old.reddit.com"):
        try:
            url = f"{host}/r/{subreddit}/top.json?t={time_filter}&limit={limit}"
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
            r.raise_for_status()
            return [c["data"] for c in r.json()["data"]["children"]]
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            continue
    if last_err:
        print(f"[reddit]   r/{subreddit} fetch error ({last_err})")
    return []


def _truncate_words(text: str, max_words: int) -> str:
    """Trim to <= max_words, ending on a sentence boundary where possible."""
    words = text.split()
    if len(words) <= max_words:
        return text
    clipped = " ".join(words[:max_words])
    # back up to the last sentence end so it doesn't cut mid-thought
    m = list(re.finditer(r"[.!?]", clipped))
    if m and m[-1].end() > len(clipped) * 0.5:
        return clipped[: m[-1].end()]
    return clipped + "..."


def fetch_story(
    subreddits: list[str] | None = None,
    min_words: int = 120,
    max_words: int = 320,
    time_filter: str = "month",
    limit: int = 80,
) -> dict | None:
    """Return a usable story post dict, or None if nothing suitable was found.

    Long stories are truncated to max_words (not rejected). Tries several time
    windows so a channel that has used up recent posts still finds material.
    """
    subs = list(subreddits or DEFAULT_SUBREDDITS)
    random.shuffle(subs)
    used = _load_used()

    time_windows = [time_filter] + [t for t in ("year", "all", "week") if t != time_filter]
    seen_any = False
    too_short = too_long_ok = used_count = 0

    for tf in time_windows:
        for sub in subs:
            posts = _top_posts(sub, tf, limit)
            if posts:
                seen_any = True
            random.shuffle(posts)
            for p in posts:
                if p.get("id") in used:
                    used_count += 1
                    continue
                if p.get("over_18") or p.get("stickied") or p.get("is_video"):
                    continue
                body = _clean(p.get("selftext", ""))
                wc = len(body.split())
                if wc < min_words:
                    too_short += 1
                    continue
                if wc > max_words:
                    body = _truncate_words(body, max_words)
                    too_long_ok += 1
                _mark_used(p["id"])
                return {
                    "id": p["id"],
                    "title": _clean(p.get("title", "")),
                    "body": body,
                    "subreddit": sub,
                    "url": "https://reddit.com" + p.get("permalink", ""),
                }
        # nothing in this window; widen to the next one

    if not seen_any:
        print("[reddit] Could not reach Reddit (network blocked or rate-limited).")
    else:
        print(f"[reddit] No new story matched filters "
              f"(skipped: {used_count} already-used, {too_short} too short). "
              f"Try lowering 'min_words' in config.json, or clear data/used_reddit.txt.")
    return None


def mood_keywords(subreddit: str) -> list[str]:
    return MOODS.get(subreddit, DEFAULT_MOOD)
