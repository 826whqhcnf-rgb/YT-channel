"""
Generate a Top-10 style script.

Two modes:
  1. LLM mode  — if SCRIPT_API_BASE + SCRIPT_API_KEY are set, uses any
                 OpenAI-compatible endpoint (OpenAI, Ollama, LM Studio, etc.).
  2. Offline   — a deterministic template generator so the pipeline works
                 with zero API keys. It produces a coherent (if generic)
                 script you can hand-edit, or feed your own facts via a
                 topics .txt/.json file.

The output is a `Script` dataclass consumed by the rest of the pipeline.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict


@dataclass
class Item:
    rank: int
    title: str
    narration: str
    # Search keyword used to pull stock visuals for this item
    keyword: str = ""


@dataclass
class Script:
    topic: str
    title: str
    intro: str
    items: list[Item] = field(default_factory=list)
    outro: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @staticmethod
    def from_dict(d: dict) -> "Script":
        items = [Item(**it) for it in d.get("items", [])]
        return Script(
            topic=d["topic"],
            title=d["title"],
            intro=d.get("intro", ""),
            items=items,
            outro=d.get("outro", ""),
            description=d.get("description", ""),
            tags=d.get("tags", []),
        )


SYSTEM_PROMPT = """You are the head writer for a fast-paced, faceless "Top 10"
YouTube Shorts / TikTok channel. Your job: write a countdown that keeps viewers
watching to #1.

Rules:
- Every item is ONE genuinely surprising, TRUE, verifiable fact. No fluff,
  no "in this video", no "did you know", no repeating the item title.
- First sentence is a strong hook that creates curiosity.
- Narration is punchy and spoken-word (short sentences, active voice).
- Build toward #1 being the most jaw-dropping item.
- "keyword" must be a concrete, filmable visual phrase (2-3 words) that stock
  footage would actually have (e.g. "anglerfish glowing", "lightning storm"),
  NOT an abstract idea.
- Do NOT invent fake statistics. If unsure, keep the claim general.
Return STRICT JSON only — no markdown, no code fences, no commentary."""

# provider -> (default base_url, default model). All are OpenAI-compatible.
PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.0-flash"),
    "openrouter": ("https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct:free"),
    "ollama": ("http://localhost:11434/v1", "llama3.1"),
}


def _resolve_provider() -> tuple[str, str, str]:
    """Figure out base URL / key / model from SCRIPT_PROVIDER + overrides."""
    provider = os.getenv("SCRIPT_PROVIDER", "").strip().lower()
    base = os.getenv("SCRIPT_API_BASE", "").strip()
    key = os.getenv("SCRIPT_API_KEY", "").strip()
    model = os.getenv("SCRIPT_MODEL", "").strip()

    if provider in PROVIDERS:
        p_base, p_model = PROVIDERS[provider]
        base = base or p_base
        model = model or p_model
        if provider == "ollama" and not key:
            key = "ollama"  # Ollama ignores the key but the client requires one
    return base, key, model or "gpt-4o-mini"


def _llm_generate(topic: str, num_items: int, words_per_item: int) -> Script | None:
    base, key, model = _resolve_provider()
    if not base or not key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        print("[script] openai package not installed; using offline generator.")
        return None

    print(f"[script] Writing with provider {base} (model={model})...")
    client = OpenAI(base_url=base, api_key=key)
    schema = {
        "title": "string, catchy, <=70 chars",
        "intro": "1-2 sentence hook",
        "items": [
            {
                "rank": "int (10 down to 1)",
                "title": "short item name",
                "narration": f"~{words_per_item} words of narration",
                "keyword": "2-3 word stock-footage search phrase",
            }
        ],
        "outro": "1 sentence call to subscribe",
        "description": "YouTube description, 2-3 sentences",
        "tags": ["8-12 lowercase tags"],
    }
    user = (
        f'Write a "Top {num_items}" countdown video script about: {topic}\n'
        f"- Title should read like 'Top {num_items} {topic.strip().rstrip('?.!').title()}'.\n"
        f"- Exactly {num_items} items, ranked from {num_items} down to 1 "
        f"(save the most jaw-dropping for #1).\n"
        f"- Each narration is about {words_per_item} words so the whole video "
        f"stays under 3 minutes for YouTube Shorts.\n"
        f"Return JSON matching this shape:\n{json.dumps(schema)}"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]

    def _call(use_json_mode: bool):
        kwargs = {"model": model, "messages": messages, "temperature": 0.8}
        if use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        return client.chat.completions.create(**kwargs)

    raw = None
    try:
        # JSON mode (supported by Groq/OpenAI) forces a parseable reply. Some
        # providers reject it, so fall back to a plain call if needed.
        try:
            resp = _call(use_json_mode=True)
        except Exception as e:  # noqa: BLE001
            print(f"[script] JSON mode unavailable ({e}); retrying without it.")
            resp = _call(use_json_mode=False)
        raw = resp.choices[0].message.content or ""
    except Exception as e:  # noqa: BLE001
        print(f"[script] LLM request failed ({type(e).__name__}: {e}).")
        print("[script] Falling back to the offline template.")
        return None

    data = _extract_json(raw)
    if data is None:
        print("[script] Could not parse JSON from the model reply; first 200 chars:")
        print("   " + raw.strip()[:200].replace("\n", " "))
        print("[script] Falling back to the offline template.")
        return None

    try:
        data["topic"] = topic
        data.setdefault("title", f"Top {num_items} {topic.title()}")
        data.setdefault("intro", "")
        data.setdefault("outro", "")
        data.setdefault("description", data.get("title", ""))
        data.setdefault("tags", [])
        items = data.get("items", [])
        for i, it in enumerate(items):
            it.setdefault("title", f"{topic} #{i + 1}")
            it.setdefault("narration", it.get("title", ""))
            it.setdefault("keyword", it.get("title", topic))
            it["rank"] = int(it.get("rank", num_items - i))
        if not items:
            raise ValueError("model returned zero items")
        print(f"[script] Generated via LLM ({model}): {len(items)} items.")
        return Script.from_dict(data)
    except Exception as e:  # noqa: BLE001
        print(f"[script] LLM reply had unexpected shape ({e}); using offline template.")
        return None


def _extract_json(raw: str) -> dict | None:
    """Pull a JSON object out of a model reply, tolerating code fences / prose."""
    if not raw:
        return None
    text = raw.strip()
    # Strip ``` / ```json fences if present.
    text = re.sub(r"```(?:json)?", "", text).strip()
    # Try the whole thing, then the first {...last} span.
    for candidate in (text, _brace_span(text)):
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _brace_span(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return None


def _offline_generate(topic: str, num_items: int, words_per_item: int) -> Script:
    """Deterministic placeholder script. Edit the JSON or wire up an LLM
    for real content. Designed so the full pipeline runs with no keys."""
    clean = topic.strip().rstrip("?.!")
    title = f"Top {num_items} {clean}"
    intro = (
        f"Here are the top {num_items} {clean.lower()} — and number one "
        f"might genuinely surprise you. Let's count them down."
    )
    items: list[Item] = []
    for rank in range(num_items, 0, -1):
        idx = num_items - rank + 1
        # Short placeholder so the default video fits the Shorts limit. Replace
        # with a real fact (edit script.json) or connect an AI writer.
        narration = (
            f"Number {rank}: a fascinating example of {clean.lower()}. "
            f"Swap this placeholder for a real fact, or connect an AI writer."
        )
        items.append(
            Item(rank=rank, title=f"{clean} #{idx}", narration=narration, keyword=clean)
        )
    outro = "If you learned something new, subscribe for a new countdown every day."
    description = (
        f"{title}. A faceless countdown of the most interesting {clean.lower()}. "
        f"New videos daily — subscribe and turn on notifications!"
    )
    tags = list({w.lower() for w in re.findall(r"[A-Za-z]+", clean)})[:8]
    print("[script] Generated via offline template (no LLM configured).")
    return Script(topic, title, intro, items, outro, description, tags)


def load_script(path: str) -> Script:
    """Load a previously generated/edited script JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return Script.from_dict(json.load(f))


def generate(topic: str, num_items: int = 10, words_per_item: int = 35) -> Script:
    return _llm_generate(topic, num_items, words_per_item) or _offline_generate(
        topic, num_items, words_per_item
    )
