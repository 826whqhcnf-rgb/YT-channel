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
class Item:
    rank: int
    title: str
    narration: str
    keyword: str = ""


@dataclass
class Script:
    topic: str
    title: str
    hook: str
    items: list[Item] = field(default_factory=list)
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
        items = [Item(**it) for it in d.pop("items", [])]
        return Script(**d, items=items)


SYSTEM = """You write scripts for a viral TikTok / YouTube Shorts channel that posts
Top-N countdown videos. The audience is general, curious, and easily bored.

Rules:
- HOOK: the very first sentence must shock or intrigue — no "in this video", no "welcome".
- Each item is ONE true, verifiable, surprising fact. No filler words.
- Narration is punchy spoken-word: short sentences, active voice, present tense.
- Build excitement toward #1 (the most jaw-dropping).
- "keyword" is a concrete 2-3 word phrase a stock footage site would have (e.g. "deep ocean floor", "lava erupting", "crowd cheering"). Never abstract.
- Return STRICT JSON — no markdown, no code fences, nothing outside the JSON object."""


USER_TEMPLATE = """Write a Top {n} countdown video script about: {topic}

Return JSON with exactly this shape:
{{
  "title": "Top {n} {title_hint} (catchy, ≤60 chars)",
  "hook": "1-2 sentence opening that grabs attention immediately",
  "items": [
    {{"rank": {n}, "title": "short name", "narration": "~{wpw} spoken words — one surprising fact", "keyword": "2-3 word footage search"}},
    ... down to rank 1 (most jaw-dropping last)
  ],
  "outro": "1 punchy sentence — tell them to follow/subscribe for more",
  "description": "YouTube/TikTok description, 2-3 sentences + relevant hashtags",
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


def generate(topic: str, cfg: dict) -> Script:
    key = cfg.get("openrouter_key", "")
    n = cfg.get("num_items", 7)
    wpw = cfg.get("words_per_item", 18)
    title_hint = topic.strip().rstrip("?.!").title()

    if key:
        result = _llm_generate(topic, n, wpw, title_hint, key)
        if result:
            return result

    return _offline(topic, n)


def _llm_generate(topic, n, wpw, title_hint, key) -> Script | None:
    try:
        from openai import OpenAI
    except ImportError:
        print("[script] openai not installed.")
        return None

    models = choose_models(key)
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    user_msg = USER_TEMPLATE.format(n=n, topic=topic, title_hint=title_hint, wpw=wpw)

    for model in models:
        print(f"[script] Writing with {model}...", end=" ", flush=True)
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.85,
                max_tokens=2000,
            )
            raw = resp.choices[0].message.content or ""
            data = _extract_json(raw)
            if not data:
                print(f"bad JSON (first 100 chars: {raw[:100]}); trying next model.")
                continue
            items = []
            for i, it in enumerate(data.get("items", [])):
                items.append(Item(
                    rank=int(it.get("rank", n - i)),
                    title=str(it.get("title", "")),
                    narration=str(it.get("narration", "")),
                    keyword=str(it.get("keyword", topic)),
                ))
            if not items:
                print("no items returned; trying next model.")
                continue
            print(f"✅ {len(items)} items.")
            return Script(
                topic=topic,
                title=str(data.get("title", f"Top {n} {topic.title()}")),
                hook=str(data.get("hook", "")),
                items=items,
                outro=str(data.get("outro", "Follow for more!")),
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


def _offline(topic: str, n: int) -> Script:
    print("[script] Using offline template — run python setup.py to add an AI writer key.")
    clean = topic.strip().rstrip("?.!")
    items = [
        Item(rank=r, title=f"{clean} #{n-r+1}",
             narration=f"Number {r}: a surprising fact about {clean.lower()}. Replace this with a real fact.",
             keyword=clean)
        for r in range(n, 0, -1)
    ]
    return Script(
        topic=topic,
        title=f"Top {n} {clean.title()}",
        hook=f"Here are the top {n} {clean.lower()} — and number one will genuinely shock you.",
        items=items,
        outro="Follow for a new countdown every day!",
        description=f"Top {n} {clean}. New videos daily — follow and turn on notifications!",
        tags=[w.lower() for w in clean.split()][:8],
    )
