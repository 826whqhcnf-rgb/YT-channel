#!/usr/bin/env python3
"""
First-time setup wizard.
Run this once: python setup.py
It tests every key before saving so you know it works.
"""
import json, os, sys, requests

CONFIG = "config.json"

def ask(prompt, default=""):
    val = input(prompt).strip()
    return val if val else default

def check_openrouter(key):
    """Returns (status, message). status: 'ok' | 'valid_busy' | 'bad'."""
    try:
        from openai import OpenAI
    except ImportError:
        return "bad", "openai package not installed (run: pip install -r requirements.txt)"

    try:
        from src.script import choose_models
        models = choose_models(key)
    except Exception:
        models = ["meta-llama/llama-3.3-70b-instruct:free"]

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    last = ""
    auth_passed = False
    for model in models[:4]:
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with the single word: working"}],
                max_tokens=5,
            )
            return "ok", (r.choices[0].message.content or "").strip()
        except Exception as e:
            last = str(e)
            low = last.lower()
            # Only a genuine auth error means the key is bad.
            if "401" in last or "no auth" in low or "invalid api key" in low or "user not found" in low:
                return "bad", last
            # 404 / 429 / busy all mean the key authenticated fine.
            auth_passed = True
            continue
    if auth_passed:
        return "valid_busy", last
    return "bad", last

def check_pexels(key):
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": key},
            params={"query": "ocean", "per_page": 1},
            timeout=10,
        )
        r.raise_for_status()
        return True, "ok"
    except Exception as e:
        return False, str(e)

def main():
    print("\n=== Faceless Video Channel — Setup ===\n")

    existing = {}
    if os.path.exists(CONFIG):
        with open(CONFIG) as f:
            existing = json.load(f)
        print("Found existing config.json — press Enter to keep current values.\n")

    cfg = dict(existing)

    # --- OpenRouter ---
    print("STEP 1: OpenRouter (free AI writer)")
    print("  → Sign up at https://openrouter.ai (free, no credit card)")
    print("  → Go to https://openrouter.ai/keys → Create Key → copy it\n")
    current = cfg.get("openrouter_key", "")
    hint = f" (current ends …{current[-6:]})" if current else ""
    key = ask(f"Paste your OpenRouter key{hint}: ", current)
    if key and key != current:
        print("  Testing key...", end=" ", flush=True)
        status, msg = check_openrouter(key)
        if status == "ok":
            print(f"✅ Works! (model replied: '{msg}')")
        elif status == "valid_busy":
            print("✅ Key is valid! (the free models are just busy right now — "
                  "that's normal and it'll work when you make a video.)")
        else:
            print(f"❌ Key looks invalid: {msg}")
            ans = ask("Save it anyway? Type y to keep, n to re-enter (y/n): ").lower()
            if ans != "y":
                print("  Not saved. Re-run 'python setup.py' to try again.")
                sys.exit(1)
    elif key == current and current:
        print("  Keeping existing key.")
    cfg["openrouter_key"] = key

    # --- Pexels ---
    print("\nSTEP 2: Pexels (free background footage)")
    print("  → Sign up at https://www.pexels.com/api (free)")
    print("  → Your key appears on that page after signing up\n")
    current = cfg.get("pexels_key", "")
    hint = f" (current ends …{current[-6:]})" if current else ""
    key = ask(f"Paste your Pexels key{hint} (or Enter to skip): ", current)
    if key and key != current:
        print("  Testing key...", end=" ", flush=True)
        ok, msg = check_pexels(key)
        if ok:
            print("✅ Works!")
        else:
            print(f"⚠️  Warning: {msg}")
    elif not key:
        print("  Skipped — videos will use plain colour backgrounds.")
    cfg["pexels_key"] = key

    # --- Voice ---
    print("\nSTEP 3: Voice (using free Microsoft neural voices — no key needed)")
    voices = [
        "en-US-AndrewNeural",
        "en-US-BrianNeural",
        "en-GB-RyanNeural",
        "en-AU-WilliamNeural",
    ]
    current = cfg.get("voice", voices[0])
    print("  Options:")
    for i, v in enumerate(voices):
        mark = " ← current" if v == current else ""
        print(f"    {i+1}. {v}{mark}")
    choice = ask(f"  Pick a number (Enter for current): ", "")
    if choice.isdigit() and 1 <= int(choice) <= len(voices):
        cfg["voice"] = voices[int(choice)-1]
    else:
        cfg["voice"] = current
    print(f"  Using: {cfg['voice']}")

    # --- Defaults ---
    cfg.setdefault("source", "reddit")     # "reddit" = copy real posts, "ai" = AI-written
    cfg.setdefault("num_items", 12)        # number of story caption segments (AI source)
    cfg.setdefault("words_per_item", 25)   # words per caption segment
    cfg.setdefault("min_words", 120)       # shortest Reddit story to accept
    cfg.setdefault("max_words", 320)       # longer stories are truncated to this
    cfg.setdefault("music", "assets/music")  # folder of music tracks (random pick)
    cfg.setdefault("music_volume", 0.12)     # quiet bed under the narration
    cfg.setdefault("gameplay", "assets/gameplay")  # gameplay clip behind video (if any)
    cfg.setdefault("fps", 30)
    cfg.setdefault("upload", {})
    up = cfg["upload"]
    up.setdefault("youtube", False)               # auto-post to YouTube Shorts
    up.setdefault("tiktok", False)                # auto-post to TikTok
    up.setdefault("youtube_client_secret", "client_secret.json")
    up.setdefault("youtube_privacy", "public")    # public | unlisted | private
    up.setdefault("youtube_category", "24")       # 24 = Entertainment
    up.setdefault("tiktok_token", "")             # paste your TikTok access token
    up.setdefault("tiktok_privacy", "SELF_ONLY")  # SELF_ONLY until app approved

    with open(CONFIG, "w") as f:
        json.dump(cfg, f, indent=2)

    print("\n✅ Setup complete! Config saved to config.json")
    print("\nNext steps:")
    if not cfg.get("openrouter_key"):
        print("  ⚠️  No AI writer key — scripts will use placeholder text.")
    print("  Make a video: python run.py --topic \"strangest deep sea creatures\"")
    print("  Random topic: python run.py --random\n")

if __name__ == "__main__":
    main()
