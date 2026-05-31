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


SYSTEM_PROMPT = """You are a scriptwriter for a faceless "Top 10" YouTube/TikTok channel.
Write punchy, factual, engaging narration. No filler, no "in this video".
Hook the viewer in the first sentence. Each item must be a self-contained,
surprising fact. Return STRICT JSON only, no markdown fences."""


def _llm_generate(topic: str, num_items: int, words_per_item: int) -> Script | None:
    base = os.getenv("SCRIPT_API_BASE", "").strip()
    key = os.getenv("SCRIPT_API_KEY", "").strip()
    model = os.getenv("SCRIPT_MODEL", "gpt-4o-mini").strip()
    if not base or not key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        print("[script] openai package not installed; using offline generator.")
        return None

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
        f"Topic: {topic}\n"
        f"Make exactly {num_items} items, ranked from {num_items} down to 1 "
        f"(most interesting is #1).\n"
        f"Return JSON matching this shape:\n{json.dumps(schema)}"
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            temperature=0.8,
        )
        raw = resp.choices[0].message.content
        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        data = json.loads(raw)
        data["topic"] = topic
        for i, it in enumerate(data.get("items", [])):
            it.setdefault("keyword", it.get("title", topic))
            it["rank"] = int(it.get("rank", num_items - i))
        print(f"[script] Generated via LLM ({model}).")
        return Script.from_dict(data)
    except Exception as e:  # noqa: BLE001
        print(f"[script] LLM generation failed ({e}); using offline generator.")
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
