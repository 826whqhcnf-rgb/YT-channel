"""Orchestrates the full topic → video workflow."""
import json, os
from datetime import datetime


def _slug(text: str) -> str:
    keep = "".join(c if c.isalnum() or c == " " else "" for c in text)
    return "-".join(keep.lower().split())[:40] or "video"


def run(topic: str, cfg: dict, script_path: str | None = None,
        script_only: bool = False, mode: str = "reddit"):
    from . import script as script_mod, voice, render, render_long

    # 1. Get the script: from a saved file, from Reddit, or AI-written.
    if script_path:
        print(f"[pipeline] Loading script from {script_path}")
        script = script_mod.Script.load(script_path)
    else:
        script = _make_script(topic, cfg, script_mod, mode)

    if script is None:
        return None  # _make_script already explained why

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = os.path.join("output", f"{_slug(script.title)}-{ts}")
    os.makedirs(out_dir, exist_ok=True)
    script_file = os.path.join(out_dir, "script.json")
    script.save(script_file)
    print(f"[pipeline] Script saved → {script_file}")

    if script_only:
        print("\n📝 Draft saved. Open this file and edit the text, then render it:")
        print(f"     {script_file}")
        print(f"  python run.py --script {script_file}" +
              (" --mode finance" if mode == "finance" else ""))
        return

    # 2. Voiceover — hook first, then each segment, then outro
    voice_cfg = cfg.get("voice", "en-US-AndrewNeural")
    texts = [script.hook] + [s.text for s in script.segments] + [script.outro]
    print(f"[pipeline] Synthesising {len(texts)} voice clips ({voice_cfg})...")
    clips = voice.synthesize(texts, os.path.join(out_dir, "audio"), voice_cfg)

    total_dur = sum(c.duration for c in clips)
    mins = total_dur / 60
    print(f"[pipeline] Estimated length: ~{total_dur:.0f}s (~{mins:.1f} min)")

    # 3. Render — long-form 16:9 for finance, vertical 9:16 for reddit stories.
    out_video = os.path.join(out_dir, f"{_slug(script.title)}.mp4")
    if mode == "finance":
        render_long.build(script, clips, out_video, cfg)
        _maybe_make_short(script, clips, out_dir, ts, render, cfg)
    else:
        render.build(script, clips, out_video, cfg)

    # 4. Copy into a single, easy-to-find downloads/ folder
    final = _copy_to_downloads(out_video, script.title, ts)

    print(f"\n✅ Done!  →  {final}")
    print(f"   ⬇️  To save it: open the 'downloads' folder on the left,")
    print(f"      right-click '{os.path.basename(final)}' → Download.")

    # 5. Optional auto-post to YouTube / TikTok
    up = cfg.get("upload", {})
    if up.get("youtube") or up.get("tiktok"):
        from . import upload as upload_mod
        upload_mod.publish(final, script, cfg)

    return final


def _copy_to_downloads(video_path: str, title: str, ts: str) -> str:
    import shutil
    dl_dir = "downloads"
    os.makedirs(dl_dir, exist_ok=True)
    name = f"{_slug(title)}-{ts}.mp4"
    dest = os.path.join(dl_dir, name)
    try:
        shutil.copy2(video_path, dest)
        return dest
    except Exception as e:  # noqa: BLE001
        print(f"[pipeline] could not copy to downloads/ ({e})")
        return video_path


def _maybe_make_short(script, clips, out_dir, ts, render, cfg):
    """For finance mode, also cut a vertical Short from the intro+first sections."""
    if not cfg.get("make_short", True):
        return
    try:
        from . import script as script_mod
        # Use the hook + first 2-3 sections so the Short is a punchy teaser <60s.
        short = script_mod.Script(
            topic=script.topic, title=script.title, hook=script.hook,
            segments=script.segments[:3],
            outro="Full breakdown on the channel — follow for more.",
            description=script.description, tags=script.tags + ["shorts"],
        )
        n = 1 + len(short.segments)  # hook + sections
        short_clips = clips[:n] + [clips[-1]]
        out = os.path.join(out_dir, f"{_slug(script.title)}-short.mp4")
        print("[pipeline] Cutting a vertical Short teaser...")
        render.build(short, short_clips, out, cfg)
        _copy_to_downloads(out, script.title + " short", ts)
    except Exception as e:  # noqa: BLE001
        print(f"[pipeline] short cut skipped ({e}).")


def _make_script(topic, cfg, script_mod, mode="reddit"):
    """Build a script. Finance => AI explainer; otherwise Reddit (default).
    Returns None on failure (no silent fallback)."""
    if mode == "finance":
        from . import finance
        return finance.generate(topic, cfg)

    source = cfg.get("source", "reddit")
    if source == "ai":
        return script_mod.generate(topic, cfg)

    from . import reddit
    post = reddit.fetch_story(
        cfg.get("subreddits"),
        min_words=cfg.get("min_words", 120),
        max_words=cfg.get("max_words", 320),
    )
    if post:
        print(f"[pipeline] Reddit story from r/{post['subreddit']}: {post['title'][:60]}")
        return script_mod.from_reddit(post, cfg.get("words_per_item", 25))
    # No silent fallback to the AI/placeholder writer — stop and explain.
    print("\n[pipeline] ❌ Could not get a Reddit story. Nothing was generated.")
    print("  • If it says 'blocked', your network is refusing Reddit — try again,")
    print("    or tell me and I'll switch the source.")
    print("  • If you've used many stories, run:  python run.py --reset-stories")
    print("  • To use the AI writer instead, set \"source\": \"ai\" in config.json")
    return None
