"""Orchestrates the full topic → video workflow."""
import json, os
from datetime import datetime


def _slug(text: str) -> str:
    keep = "".join(c if c.isalnum() or c == " " else "" for c in text)
    return "-".join(keep.lower().split())[:40] or "video"


def run(topic: str, cfg: dict, script_path: str | None = None, script_only: bool = False):
    from . import script as script_mod, voice, render

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = os.path.join("output", f"{_slug(topic)}-{ts}")
    os.makedirs(out_dir, exist_ok=True)

    # 1. Script
    if script_path:
        print(f"[pipeline] Loading script from {script_path}")
        script = script_mod.Script.load(script_path)
    else:
        script = script_mod.generate(topic, cfg)
    script_file = os.path.join(out_dir, "script.json")
    script.save(script_file)
    print(f"[pipeline] Script saved → {script_file}")

    if script_only:
        print("\nOpen script.json to review/edit, then run:")
        print(f"  python run.py --topic \"{topic}\" --script {script_file}")
        return

    # 2. Voiceover — hook first, then items, then outro
    voice_cfg = cfg.get("voice", "en-US-AndrewNeural")
    texts = [script.hook] + [it.narration for it in script.items] + [script.outro]
    print(f"[pipeline] Synthesising {len(texts)} voice clips ({voice_cfg})...")
    clips = voice.synthesize(texts, os.path.join(out_dir, "audio"), voice_cfg)

    total_dur = sum(c.duration for c in clips)
    print(f"[pipeline] Estimated length: ~{total_dur:.0f}s")
    if total_dur > 170:
        print("[pipeline] ⚠️  Over 3 min — lower num_items or words_per_item in config.json")

    # 3. Render
    out_video = os.path.join(out_dir, f"{_slug(script.title)}.mp4")
    render.build(script, clips, out_video, cfg)

    print(f"\n✅ Done!  →  {out_video}")
    print(f"   Folder: {out_dir}")
    return out_video
