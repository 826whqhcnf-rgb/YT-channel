"""
End-to-end orchestration: topic -> script -> voiceover -> visuals -> video(s)
-> optional upload to YouTube and/or TikTok.
"""

from __future__ import annotations

import os
from datetime import datetime

from . import assembler, script_generator, tts


def _slug(text: str) -> str:
    keep = "".join(c if c.isalnum() or c in " -" else "" for c in text)
    return "-".join(keep.lower().split())[:50] or "video"


def run(cfg: dict, topic: str, script_path: str | None = None) -> dict:
    out_root = os.path.join("output", f"{_slug(topic)}-{datetime.now():%Y%m%d-%H%M%S}")
    work = os.path.join(out_root, "work")
    cache = os.path.join("assets", "cache")
    os.makedirs(work, exist_ok=True)

    pexels_key = os.getenv("PEXELS_API_KEY", "")

    # 1. Script
    if script_path:
        script = script_generator.load_script(script_path)
        print(f"[pipeline] Loaded script from {script_path}")
    else:
        script = script_generator.generate(
            topic,
            num_items=cfg["content"]["num_items"],
            words_per_item=cfg["content"]["words_per_item"],
        )
    script.tags = list(dict.fromkeys(script.tags + cfg["channel"]["tags"]))
    with open(os.path.join(out_root, "script.json"), "w", encoding="utf-8") as f:
        f.write(script.to_json())

    # 2. Voiceover (intro, each item, outro)
    voice = cfg["content"]["voice"]
    rate = cfg["content"]["rate"]
    print(f"[pipeline] Synthesizing {len(script.items) + 2} voice clips ({voice})...")
    intro_clip = tts.synthesize([script.intro], work, voice, rate, "intro")[0]
    item_clips = tts.synthesize(
        [it.narration for it in script.items], work, voice, rate, "item"
    )
    outro_clip = tts.synthesize([script.outro], work, voice, rate, "outro")[0]

    # 2b. Shorts duration guard. Cards add ~0.4s tails; this closely matches the
    # final runtime. Warn if it would exceed the Shorts limit.
    limit = cfg["video"].get("shorts_max_seconds", 180)
    est = (
        intro_clip.duration
        + outro_clip.duration
        + sum(c.duration + 0.4 for c in item_clips)
        + 0.8
    )
    print(f"[pipeline] Estimated runtime ~{est:.0f}s (Shorts limit {limit}s).")
    if "vertical" in cfg["video"]["render"] and est > limit:
        print(
            f"[pipeline] WARNING: ~{est:.0f}s exceeds the {limit}s YouTube Shorts "
            f"limit. Lower content.num_items or content.words_per_item in config.yaml."
        )

    # 3. Render each requested orientation
    rendered: dict[str, str] = {}
    for orientation in cfg["video"]["render"]:
        out_path = os.path.join(out_root, f"{_slug(script.title)}-{orientation}.mp4")
        print(f"[pipeline] Rendering {orientation} -> {out_path}")
        assembler.build_video(
            script=script,
            voice_clips=item_clips,
            intro_clip=intro_clip,
            outro_clip=outro_clip,
            orientation=orientation,
            out_path=out_path,
            cache_dir=cache,
            pexels_key=pexels_key,
            visual_source=cfg["visuals"]["source"],
            fallback_colors=cfg["visuals"]["fallback_colors"],
            fps=cfg["video"]["fps"],
            title_seconds=cfg["video"]["title_card_seconds"],
            outro_seconds=cfg["video"]["outro_seconds"],
            music_path=cfg["video"].get("music"),
            music_volume=cfg["video"]["music_volume"],
            captions=cfg["video"]["captions"],
        )
        rendered[orientation] = out_path

    result = {"script": script, "out_dir": out_root, "videos": rendered}

    # 4. Optional uploads
    _maybe_upload(cfg, script, rendered)
    return result


def _maybe_upload(cfg: dict, script, rendered: dict[str, str]) -> None:
    yt = cfg["upload"]["youtube"]
    if yt.get("enabled"):
        from . import upload_youtube

        # We publish as YouTube Shorts: use the vertical render and add the
        # #Shorts signal so YouTube classifies it as a Short. Shorts must be
        # vertical/square and <= 3 minutes long.
        path = rendered.get("vertical") or next(iter(rendered.values()))
        title = script.title if "#shorts" in script.title.lower() else f"{script.title} #Shorts"
        description = script.description.rstrip() + "\n\n#Shorts"
        tags = list(dict.fromkeys(script.tags + ["shorts"]))
        try:
            upload_youtube.upload(
                video_path=path,
                title=title,
                description=description,
                tags=tags,
                privacy=yt.get("privacy", "private"),
                category_id=yt.get("category_id", "27"),
            )
        except Exception as e:  # noqa: BLE001
            print(f"[pipeline] YouTube upload failed: {e}")

    tk = cfg["upload"]["tiktok"]
    if tk.get("enabled"):
        from . import upload_tiktok

        # TikTok requires vertical.
        path = rendered.get("vertical") or next(iter(rendered.values()))
        caption = f"{script.title} {' '.join('#' + t for t in script.tags[:5])}"
        try:
            upload_tiktok.upload(
                video_path=path,
                caption=caption,
                privacy=tk.get("privacy", "SELF_ONLY"),
            )
        except Exception as e:  # noqa: BLE001
            print(f"[pipeline] TikTok upload failed: {e}")
