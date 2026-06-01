"""
Financial / educational explainer scripts for long-form YouTube.

Produces a Script whose segments carry an on-screen heading + key bullet points
(for clean slides) plus narration and a B-roll keyword. AI-drafted via the same
OpenRouter setup; you can edit the saved script.json before rendering.
"""
from __future__ import annotations

import json

from .script import Script, Segment, _extract_json, choose_models


SYSTEM = """You are a scriptwriter for a faceless, high-trust YouTube channel that
explains FINANCE and ECONOMICS clearly (think well-researched explainer channels).
The audience is smart beginners who want to actually understand the concept.

Rules:
- Be accurate and concrete. Use real definitions, simple examples, and round,
  illustrative numbers. NEVER invent fake statistics or cite fake sources; if a
  precise figure isn't certain, phrase it generally ("roughly", "on average").
- This is EDUCATIONAL, not financial advice. No "buy X", no hype, no guarantees.
- Strong hook that frames why the concept matters to the viewer's money/life.
- Logical flow: define it → why it matters → how it works (with an example) →
  common mistakes / nuance → quick recap.
- Conversational but precise. Short sentences. Explain jargon the moment you use it.
- For each section give a short on-screen HEADING and 2-4 punchy KEY POINTS
  (a few words each) that will appear as on-screen text while you narrate.
- "keyword" is a concrete, filmable stock scene (e.g. "stock market screen",
  "stack of coins", "city financial district", "person budgeting").
- Return STRICT JSON only — no markdown, no code fences, nothing outside the JSON."""


USER_TEMPLATE = """Write a long-form YouTube explainer script about this finance topic: {topic}

Target about {total_words} words total (~{est_minutes} minutes spoken).
Break it into {n} sections, each ~{wps} words of narration, in a logical teaching order.

Return JSON with exactly this shape:
{{
  "title": "a clear, clickable YouTube title (<=70 chars)",
  "hook": "the spoken opening 2-3 sentences: why this concept matters to the viewer",
  "segments": [
    {{
      "heading": "short on-screen section heading (2-5 words)",
      "points": ["key point", "key point", "key point"],
      "text": "~{wps} words of clear narration for this section",
      "keyword": "concrete stock-footage scene for this section"
    }}
    // exactly {n} sections: define -> why it matters -> how it works (example)
    // -> nuance/mistakes -> recap
  ],
  "outro": "1-2 sentences: recap + invite to like/subscribe for more finance explainers",
  "description": "a YouTube description: 2-3 sentence summary + a short '00:00 Intro' style note + 5-8 hashtags",
  "tags": ["10-15 lowercase finance tags"]
}}"""


def generate(topic: str, cfg: dict) -> Script | None:
    key = cfg.get("openrouter_key", "")
    if not key:
        print("[finance] No OpenRouter key set — run python setup.py first.")
        return None

    n = max(int(cfg.get("sections", 7)), 4)
    wps = max(int(cfg.get("words_per_section", 90)), 50)
    total_words = n * wps
    est_minutes = round(total_words / 150, 1)  # ~150 spoken words/min

    try:
        from openai import OpenAI
    except ImportError:
        print("[finance] openai package not installed.")
        return None

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    user = USER_TEMPLATE.format(topic=topic, n=n, wps=wps,
                                total_words=total_words, est_minutes=est_minutes)

    for model in choose_models(key):
        print(f"[finance] Writing with {model}...", end=" ", flush=True)
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": user}],
                temperature=0.6, max_tokens=4000,
            )
            data = _extract_json(resp.choices[0].message.content or "")
            if not data:
                print("bad JSON; trying next model.")
                continue
            segs = []
            for s in data.get("segments", []):
                text = str(s.get("text", "")).strip()
                if not text:
                    continue
                segs.append(Segment(
                    text=text,
                    keyword=str(s.get("keyword", topic)),
                    heading=str(s.get("heading", "")),
                    points=[str(p) for p in s.get("points", [])][:4],
                ))
            if not segs:
                print("no sections; trying next model.")
                continue
            print(f"✅ {len(segs)} sections.")
            return Script(
                topic=topic,
                title=str(data.get("title", topic.title())),
                hook=str(data.get("hook", "")),
                segments=segs,
                outro=str(data.get("outro", "Subscribe for more finance explainers.")),
                description=str(data.get("description", "")),
                tags=[str(t) for t in data.get("tags", [])] or ["finance", "money", "investing"],
            )
        except Exception as e:  # noqa: BLE001
            low = str(e).lower()
            if "401" in low or "invalid api key" in low or "user not found" in low:
                print("\n[finance] OpenRouter key invalid. Run: python setup.py")
                return None
            print("busy/unavailable; trying next model.")
            continue

    print("[finance] All models were busy. Try again in a minute.")
    return None
