"""
AI script writer — uses OpenRouter (free models, no credit card).
Falls back to a short offline template if no key is set.
"""
import json, os, re
import requests
from dataclasses import dataclass, field, asdict


# Preferred free models, in priority order. We only use the ones OpenRouter
# currently lists as free (fetched live), so a retired model never breaks us.
PREFERRED_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "meta-llama/llama-3.1-70b-instruct:free",
    "mistralai/mistral-small-3.2-24b-instruct:free",
    "google/gemma-2-9b-it:free",
    "meta-llama/llama-3.1-8b-instruct:free",
]


def fetch_free_models(key: str | None = None) -> list[str]:
    """Ask OpenRouter which models are free *right now* (pricing == 0)."""
    try:
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        r = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=15)
        r.raise_for_status()
        free = []
        for m in r.json().get("data", []):
            pr = m.get("pricing", {})
            if str(pr.get("prompt", "x")) in ("0", "0.0") and str(pr.get("completion", "x")) in ("0", "0.0"):
                free.append(m["id"])
        return free
    except Exception:
        return []


def choose_models(key: str | None = None) -> list[str]:
    """Return an ordered list of usable free models (live list ∩ preferences)."""
    free = set(fetch_free_models(key))
    if not free:
        return PREFERRED_MODELS  # offline/unknown: try the static list anyway
    ordered = [m for m in PREFERRED_MODELS if m in free]
    extras = [m for m in free if m not in PREFERRED_MODELS
              and (":free" in m and any(t in m for t in ("instruct", "chat", "it")))]
    result = ordered + extras
    return (result or list(free))[:6]



@dataclass
class Segment:
    text: str
    keyword: str = ""
    heading: str = ""          # on-screen section heading (finance/explainer slides)
    points: list = field(default_factory=list)  # bullet key-points for the slide


@dataclass
class Script:
    topic: str
    title: str
    hook: str
    segments: list[Segment] = field(default_factory=list)
    outro: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    @staticmethod
    def load(path: str) -> "Script":
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        segments = [Segment(**s) for s in d.pop("segments", [])]
        return Script(**d, segments=segments)


SYSTEM = """You are a viral short-form STORYTELLER for TikTok, YouTube Shorts and Reels —
the faceless "Reddit story" format (think r/AmItheAsshole, r/TIFU, r/ProRevenge,
r/MaliciousCompliance, r/relationship_advice, r/nosleep). A calm voice narrates
a gripping first-person story over background video while captions appear on screen.

What makes these go viral — follow ALL of it:
- HOOK FIRST: the opening line must stop the scroll in 3 seconds. Drop the listener
  straight into conflict, betrayal, or a shocking statement. NO "so basically", NO
  "story time", NO throat-clearing.
- First person ("I", "my"), conversational, present-tense urgency, like a real person venting.
- Specific vivid details (names, places, exact things said) make it feel real.
- Build tension → a turning point → a satisfying twist, payoff, or revenge near the end.
- End on a CLIFFHANGER or a question that begs comments ("Was I wrong?", "Part 2?").
- Believable and PG-13: drama, revenge, embarrassment, mild creepiness are great.
  NO explicit gore, sexual content, slurs, hate, or real private data.
- "keyword" for each part is a concrete, mood-matching scene a stock site would have
  (e.g. "wedding reception", "rainy city street night", "person crying", "empty office").
- Return STRICT JSON only — no markdown, no code fences, nothing outside the JSON object."""


USER_TEMPLATE = """Write a viral first-person story video script based on this prompt: {topic}

Make it about {total_words} words total (a {est_seconds}-second video) so it runs over a minute.
Break the story into exactly {n} caption segments of roughly {wpw} words each, in order.

Return JSON with exactly this shape:
{{
  "title": "the on-screen post-style title, e.g. 'AITA for ruining my sister's wedding?' (≤70 chars)",
  "hook": "the spoken opening 1-2 sentences — the single most important, scroll-stopping line",
  "segments": [
    {{"text": "~{wpw} words continuing the story", "keyword": "concrete mood-matching B-roll scene"}},
    ... exactly {n} segments that tell the full story in order, ending with the twist/payoff
  ],
  "outro": "a cliffhanger + call to action, e.g. 'Was I wrong? Follow for part 2.'",
  "description": "a TikTok/YouTube caption with 3-5 relevant hashtags",
  "tags": ["8 to 12 lowercase tags"]
}}"""


def _extract_json(text: str) -> dict | None:
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    for candidate in (text, text[text.find("{"):text.rfind("}")+1]):
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


def from_reddit(post: dict, words_per_item: int = 25) -> Script:
    """Turn a fetched Reddit post into a narratable Script (no AI needed)."""
    from . import reddit as reddit_mod

    title = post.get("title", "").strip()
    body = post.get("body", "").strip()
    sub = post.get("subreddit", "")
    moods = reddit_mod.mood_keywords(sub)

    # Split body into sentences, then group into ~words_per_item-word captions.
    sentences = re.split(r"(?<=[.!?])\s+", body)
    segments: list[Segment] = []
    cur: list[str] = []
    count = 0

    def flush():
        if not cur:
            return
        chunk = " ".join(cur)
        # Content-accurate B-roll: pull a salient noun phrase from THIS chunk,
        # falling back to the subreddit mood so footage matches what's said.
        kw = _segment_keyword(chunk) or moods[len(segments) % len(moods)]
        segments.append(Segment(text=chunk, keyword=kw))

    for s in sentences:
        s = s.strip()
        if not s:
            continue
        cur.append(s)
        count += len(s.split())
        if count >= words_per_item:
            flush()
            cur, count = [], 0
    flush()

    short_title = title if len(title) <= 70 else title[:67] + "..."
    tags = ["reddit", "story", "storytime", "redditstories", sub.lower(), "fyp", "viral"]
    description = (
        f"{title}\n\n"
        "😱 Reddit's wildest stories, read out loud. Would YOU have done the same?\n"
        "👇 Drop your verdict in the comments — and FOLLOW for a new story every day!\n\n"
        "#reddit #redditstories #storytime #aita #tifu #fyp #shorts #drama #storytelling"
    )
    return Script(
        topic=title,
        title=short_title,
        hook=title,
        segments=segments,
        outro="Was the OP wrong? Comment below — and follow for more stories.",
        description=description,
        tags=tags,
    )


# Concrete, filmable nouns we're happy to search stock footage for.
_VISUAL_NOUNS = {
    "wedding", "car", "house", "money", "phone", "dog", "cat", "school",
    "office", "hospital", "police", "kitchen", "restaurant", "store", "road",
    "rain", "storm", "city", "beach", "forest", "night", "party", "dinner",
    "court", "letter", "computer", "baby", "ring", "door", "window", "train",
    "airport", "hotel", "garden", "fire", "snow", "mountain", "river", "bar",
    "gym", "park", "church", "graveyard", "mirror", "clock", "key", "gift",
}


def _segment_keyword(text: str) -> str | None:
    """Find a concrete, filmable noun in the segment to drive B-roll search."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    for w in words:
        base = w.rstrip("s") if w.endswith("s") and w[:-1] in _VISUAL_NOUNS else w
        if base in _VISUAL_NOUNS:
            return base
    return None


def generate(topic: str, cfg: dict) -> Script:
    key = cfg.get("openrouter_key", "")
    # num_items / words_per_item now mean: number of caption segments and words each.
    # Floors keep the story over a minute even if an old config has small values.
    n = max(cfg.get("num_items", 12), 10)
    wpw = max(cfg.get("words_per_item", 25), 22)

    if key:
        result = _llm_generate(topic, n, wpw, key)
        if result:
            return result

    return _offline(topic, n, wpw)


def _llm_generate(topic, n, wpw, key) -> Script | None:
    try:
        from openai import OpenAI
    except ImportError:
        print("[script] openai not installed.")
        return None

    total_words = n * wpw
    est_seconds = round(total_words / 2.5)
    models = choose_models(key)
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    user_msg = USER_TEMPLATE.format(
        topic=topic, n=n, wpw=wpw, total_words=total_words, est_seconds=est_seconds
    )

    for model in models:
        print(f"[script] Writing with {model}...", end=" ", flush=True)
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.9,
                max_tokens=2600,
            )
            raw = resp.choices[0].message.content or ""
            data = _extract_json(raw)
            if not data:
                print(f"bad JSON (first 100 chars: {raw[:100]}); trying next model.")
                continue
            segments = []
            for s in data.get("segments", []):
                text = str(s.get("text", "")).strip()
                if text:
                    segments.append(Segment(text=text, keyword=str(s.get("keyword", topic))))
            if not segments:
                print("no story segments returned; trying next model.")
                continue
            print(f"✅ story with {len(segments)} parts.")
            return Script(
                topic=topic,
                title=str(data.get("title", topic.title())),
                hook=str(data.get("hook", "")),
                segments=segments,
                outro=str(data.get("outro", "Was I wrong? Follow for part 2.")),
                description=str(data.get("description", "")),
                tags=list(data.get("tags", [])),
            )
        except Exception as e:
            err = str(e)
            low = err.lower()
            if "401" in err or "no auth" in low or "invalid api key" in low or "user not found" in low:
                print("\n[script] Your OpenRouter key is invalid. Run: python setup.py")
                return None
            if any(t in low for t in ("rate", "quota", "limit", "429", "404", "not found", "no endpoints")):
                print("busy/unavailable; trying next model.")
                continue
            print(f"error: {e}; trying next model.")
            continue

    print("[script] All free models were busy. Try again in a minute "
          "(using offline template for now).")
    return None


def _offline(topic: str, n: int, wpw: int) -> Script:
    print("[script] Using offline template — run python setup.py to add an AI writer key.")
    clean = topic.strip().rstrip("?.!")
    segments = [
        Segment(
            text=f"Part {i+1} of the story about {clean.lower()}. "
                 f"Replace this placeholder with the real story by adding an AI writer key.",
            keyword=clean,
        )
        for i in range(n)
    ]
    return Script(
        topic=topic,
        title=clean.title(),
        hook=f"You won't believe what happened with {clean.lower()}.",
        segments=segments,
        outro="Was I wrong? Follow for part 2.",
        description=f"{clean}. #story #reddit #storytime",
        tags=[w.lower() for w in clean.split()][:8] + ["story", "storytime", "reddit"],
    )
