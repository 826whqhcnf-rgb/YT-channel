"""Orchestrates the full topic → video workflow."""
import json, os
from datetime import datetime


def _slug(text: str) -> str:
    keep = "".join(c if c.isalnum() or c == " " else "" for c in text)
    return "-".join(keep.lower().split())[:40] or "video"


def run(topic: str, cfg: dict, script_path: str | None = None, script_only: bool = False):
    from . import script as script_mod, voice, render

    # 1. Get the script: from a saved file, from Reddit, or AI-written.
    if script_path:
        print(f"[pipeline] Loading script from {script_path}")
        script = script_mod.Script.load(script_path)
    else:
        script = _make_script(topic, cfg, script_mod)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = os.path.join("output", f"{_slug(script.title)}-{ts}")
    os.makedirs(out_dir, exist_ok=True)
    script_file = os.path.join(out_dir, "script.json")
    script.save(script_file)
    print(f"[pipeline] Script saved → {script_file}")

    if script_only:
        print("\nOpen script.json to review/edit, then run:")
        print(f"  python run.py --script {script_file}")
        return

    # 2. Voiceover — hook first, then each story segment, then outro
    voice_cfg = cfg.get("voice", "en-US-AndrewNeural")
    texts = [script.hook] + [s.text for s in script.segments] + [script.outro]
    print(f"[pipeline] Synthesising {len(texts)} voice clips ({voice_cfg})...")
    clips = voice.synthesize(texts, os.path.join(out_dir, "audio"), voice_cfg)

    total_dur = sum(c.duration for c in clips)
    print(f"[pipeline] Estimated length: ~{total_dur:.0f}s")
    if total_dur < 60:
        print("[pipeline] ⚠️  Under 1 min — raise num_items/words_per_item in config.json")
    elif total_dur > 180:
        print("[pipeline] ⚠️  Over 3 min (YouTube Shorts cap) — lower num_items/words_per_item")

    # 3. Render
    out_video = os.path.join(out_dir, f"{_slug(script.title)}.mp4")
    render.build(script, clips, out_video, cfg)

    print(f"\n✅ Done!  →  {out_video}")
    print(f"   Folder: {out_dir}")
    return out_video


def _make_script(topic, cfg, script_mod):
    """Default source is real Reddit posts; fall back to AI, then offline."""
    source = cfg.get("source", "reddit")
    if source == "reddit":
        try:
            from . import reddit
            post = reddit.fetch_story(
                cfg.get("subreddits"),
                min_words=cfg.get("min_words", 150),
                max_words=cfg.get("max_words", 420),
            )
            if post:
                print(f"[pipeline] Reddit story from r/{post['subreddit']}: {post['title'][:60]}")
                return script_mod.from_reddit(post, cfg.get("words_per_item", 25))
            print("[pipeline] No fresh Reddit story found; falling back to AI writer.")
        except Exception as e:  # noqa: BLE001
            print(f"[pipeline] Reddit fetch failed ({e}); falling back to AI writer.")
    return script_mod.generate(topic, cfg)
