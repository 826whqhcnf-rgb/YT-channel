"""
Assemble the final video from segments using ffmpeg + PIL overlays.
No moviepy. Each segment renders independently then gets concatenated.
"""
import os, shutil, textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from . import ffmpeg_runner as ff

SIZE = (1080, 1920)   # 9:16 vertical for Shorts/TikTok
W, H = SIZE
FPS = 30

GRAD_TOP = (15, 12, 41)     # deep purple-black
GRAD_BOT = (44, 9, 81)      # rich purple


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _gradient() -> np.ndarray:
    img = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        t = y / (H - 1)
        img[y] = tuple(int(GRAD_TOP[c]*(1-t) + GRAD_BOT[c]*t) for c in range(3))
    return img


_GRAD = None
def gradient_png(path: str) -> str:
    global _GRAD
    if _GRAD is None:
        _GRAD = _gradient()
    Image.fromarray(_GRAD, "RGB").save(path)
    return path


def _text_layer(lines: list[tuple[str, int]], y_anchor: str, pad: int) -> np.ndarray:
    """Render text lines onto transparent RGBA canvas."""
    img = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    rendered = []
    total_h = 0
    stroke = 5
    for text, fsize in lines:
        font = _font(fsize)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        rendered.append((text, font, tw, th))
        total_h += th + 10

    if y_anchor == "center":
        y = (H - total_h) // 2
    elif y_anchor == "bottom":
        y = H - total_h - pad
    else:  # top
        y = pad

    for text, font, tw, th in rendered:
        x = (W - tw) // 2
        draw.text((x, y), text, font=font, fill=(255,255,255,255),
                  stroke_width=stroke, stroke_fill=(0,0,0,200))
        y += th + 10

    return np.array(img)


def _save_png(arr: np.ndarray, path: str) -> str:
    Image.fromarray(arr, "RGBA").save(path)
    return path


def _title_banner(title: str) -> np.ndarray:
    """A persistent Reddit-style title banner near the top + a light scrim so
    captions stay readable. Caption TEXT is NOT baked in here — it is burned as
    word-synced subtitles in the final pass."""
    img = Image.new("RGBA", SIZE, (0, 0, 0, 70))   # light scrim
    draw = ImageDraw.Draw(img)

    # Rounded "card" behind the title
    title_font = _font(max(44, W // 24))
    lines = textwrap.fill(title, 26).split("\n")[:3]
    pad = 34
    line_h = title_font.size + 12
    box_h = len(lines) * line_h + pad
    box_top = int(H * 0.05)
    draw.rounded_rectangle(
        [70, box_top, W - 70, box_top + box_h], radius=28, fill=(20, 20, 24, 210)
    )
    ty = box_top + pad // 2 + line_h // 2
    for line in lines:
        draw.text((W // 2, ty), line, font=title_font, anchor="mm",
                  fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 220))
        ty += line_h
    return np.array(img)


def _scrim(alpha: int = 80) -> np.ndarray:
    return np.array(Image.new("RGBA", SIZE, (0, 0, 0, alpha)))


def _render_seg(bg: str, mode: str, overlay_png: str,
                audio: str, dur: float, out: str) -> None:
    """mode: 'video' (loop+cover), 'photo' (Ken Burns zoom), 'gradient' (still)."""
    if mode == "video":
        loop = ["-stream_loop", "-1"]
        bg_filter = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                     f"crop={W}:{H},setsar=1,fps={FPS}[bg]")
    elif mode == "photo":
        loop = ["-loop", "1"]
        frames = max(1, int(dur * FPS))
        # Slow Ken Burns zoom-in for life/motion on a still image.
        bg_filter = (
            f"[0:v]scale={W*2}:{H*2}:force_original_aspect_ratio=increase,"
            f"crop={W*2}:{H*2},"
            f"zoompan=z='min(zoom+0.0006,1.18)':d={frames}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},"
            f"setsar=1[bg]"
        )
    else:  # gradient / still color
        loop = ["-loop", "1"]
        bg_filter = f"[0:v]scale={W}:{H},setsar=1,fps={FPS}[bg]"

    ff.run([
        *loop, "-i", bg,
        "-loop", "1", "-i", overlay_png,
        "-i", audio,
        "-filter_complex",
        f"{bg_filter};[bg][1:v]overlay=0:0[v]",
        "-map", "[v]", "-map", "2:a",
        "-t", f"{dur:.2f}", "-r", str(FPS),
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-threads", "2",
        "-c:a", "aac", "-ar", "44100", "-b:a", "128k",
        out,
    ])


def build(script, voice_clips, out_path: str, cfg: dict) -> str:
    from . import footage, captions

    work = out_path + ".parts"
    os.makedirs(work, exist_ok=True)
    banner = _save_png(_title_banner(script.title), os.path.join(work, "banner.png"))

    gameplay = resolve_gameplay(cfg)
    if gameplay:
        print(f"[render] gameplay background: {os.path.basename(gameplay)}")
        return _build_gameplay(script, voice_clips, out_path, cfg, work, banner, gameplay)

    return _build_broll(script, voice_clips, out_path, cfg, work, banner)


def _build_gameplay(script, voice_clips, out_path, cfg, work, banner, gameplay):
    """Continuous gameplay clip behind the full narration (Subway Surfers /
    Minecraft parkour style) with word-synced captions burned on top."""
    from . import captions

    # 1. One narration track + caption offsets that match it exactly.
    narration = os.path.join(work, "narration.m4a")
    offsets, total = _concat_audio([vc.path for vc in voice_clips], narration, work)
    clip_words = [vc.words for vc in voice_clips]
    print(f"[render] narration {total:.0f}s; compositing gameplay + banner...")

    # 2. Gameplay looped/cropped to fill 9:16, banner on top, narration as audio.
    base = os.path.join(work, "base.mp4")
    ff.run([
        "-stream_loop", "-1", "-i", gameplay,
        "-loop", "1", "-i", banner,
        "-i", narration,
        "-filter_complex",
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},setsar=1,fps={FPS}[bg];"
        f"[bg][1:v]overlay=0:0[v]",
        "-map", "[v]", "-map", "2:a",
        "-t", f"{total:.2f}", "-r", str(FPS),
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-threads", "2",
        "-c:a", "aac", "-ar", "44100", "-b:a", "128k",
        base,
    ])

    return _finish(base, clip_words, offsets, out_path, cfg, work)


def _build_broll(script, voice_clips, out_path, cfg, work, banner):
    """Original path: fresh Pexels B-roll (or gradient) per segment."""
    from . import footage, captions

    pexels_key = cfg.get("pexels_key", "")
    cache = os.path.join("assets", "cache")
    grad = gradient_png(os.path.join(work, "grad.png"))
    scrim = _save_png(_scrim(80), os.path.join(work, "scrim.png"))
    parts = []

    total = len(script.segments) + 2
    offsets: list[float] = []
    clip_words: list[list] = []
    running = 0.0

    def add_clip(vc, tail=0.3):
        nonlocal running
        offsets.append(running)
        clip_words.append(vc.words)
        running += vc.duration + tail

    # --- Hook (different B-roll for the opening line) ---
    print(f"[render] [1/{total}] hook")
    hook_kw = footage.clean_keyword(script.segments[0].keyword if script.segments else script.topic)
    bg, mode = _bg_for(footage, hook_kw, cache, pexels_key, grad)
    _render_seg(bg, mode, scrim, voice_clips[0].path,
                voice_clips[0].duration + 0.3, os.path.join(work, "seg_00.mp4"))
    parts.append(os.path.join(work, "seg_00.mp4"))
    add_clip(voice_clips[0])

    # --- Story segments (fresh footage each one) ---
    for i, (seg_data, vc) in enumerate(zip(script.segments, voice_clips[1:])):
        print(f"[render] [{i+2}/{total}] {seg_data.text[:38].replace(chr(10),' ')}...")
        bg, mode = _bg_for(footage, seg_data.keyword or script.topic, cache, pexels_key, grad)
        seg = os.path.join(work, f"seg_{i+1:02d}.mp4")
        try:
            _render_seg(bg, mode, banner, vc.path, vc.duration + 0.3, seg)
        except Exception as e:
            print(f"[render]   footage failed ({e}); using gradient.")
            _render_seg(grad, "gradient", banner, vc.path, vc.duration + 0.3, seg)
        parts.append(seg)
        add_clip(vc)

    # --- Outro ---
    print(f"[render] [{total}/{total}] outro")
    outro_vc = voice_clips[-1]
    _render_seg(grad, "gradient", scrim, outro_vc.path,
                outro_vc.duration + 0.3, os.path.join(work, f"seg_{total:02d}.mp4"))
    parts.append(os.path.join(work, f"seg_{total:02d}.mp4"))
    add_clip(outro_vc)

    # --- Concatenate segments ---
    print(f"[render] concatenating {len(parts)} segments...")
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    concat = os.path.join(work, "concat.mp4")
    try:
        ff.run(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", concat])
    except Exception as e:
        print(f"[render] stream-copy failed ({e}); re-encoding.")
        ff.run(["-f", "concat", "-safe", "0", "-i", lst,
                "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                "-threads", "2", "-c:a", "aac", "-ar", "44100", concat])

    return _finish(concat, clip_words, offsets, out_path, cfg, work)


def _concat_audio(paths, out_audio, work):
    """Concatenate narration clips into one track. Returns (offsets, total)."""
    offsets, running = [], 0.0
    for p in paths:
        offsets.append(running)
        running += ff.duration(p) + 0.3
    lst = os.path.join(work, "audio_list.txt")
    with open(lst, "w") as f:
        for p in paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    # Re-encode to a uniform AAC track so concat is reliable across MP3s.
    ff.run(["-f", "concat", "-safe", "0", "-i", lst,
            "-af", "apad=pad_dur=0.3", "-c:a", "aac", "-ar", "44100", out_audio])
    return offsets, ff.duration(out_audio)


def _finish(base_video, clip_words, offsets, out_path, cfg, work):
    """Shared tail: burn word-synced captions, mix optional music, save."""
    from . import captions

    print("[render] burning word-synced captions...")
    ass = captions.build_ass(clip_words, offsets, os.path.join(work, "subs.ass"))
    captioned = os.path.join(work, "captioned.mp4")
    ass_path = ass.replace("\\", "/").replace(":", r"\:")
    try:
        ff.run(["-i", base_video, "-vf", f"subtitles='{ass_path}'",
                "-c:v", "libx264", "-preset", "veryfast", "-threads", "2",
                "-pix_fmt", "yuv420p", "-c:a", "copy", captioned])
        stage = captioned
    except Exception as e:
        print(f"[render] caption burn failed ({e}); continuing without word-sync.")
        stage = base_video

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    music = resolve_music(cfg)
    if music:
        vol = cfg.get("music_volume", 0.12)
        print(f"[render] mixing music: {os.path.basename(music)} (vol {vol})")
        try:
            ff.run(["-i", stage, "-stream_loop", "-1", "-i", music,
                    "-filter_complex",
                    f"[1:a]volume={vol}[m];"
                    f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]",
                    "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-shortest", out_path])
        except Exception as e:
            print(f"[render] music mix failed ({e}); narration only.")
            shutil.move(stage, out_path)
    else:
        shutil.move(stage, out_path)

    shutil.rmtree(work, ignore_errors=True)
    return out_path


def resolve_gameplay(cfg: dict) -> str | None:
    """Find a gameplay background clip. cfg['gameplay'] may be a file or a
    folder (a random clip is chosen). Returns None if none available."""
    import random
    g = cfg.get("gameplay", "assets/gameplay")
    if not g:
        return None
    if os.path.isfile(g):
        return g
    if os.path.isdir(g):
        clips = [os.path.join(g, f) for f in os.listdir(g)
                 if f.lower().endswith((".mp4", ".mov", ".mkv", ".webm"))]
        if clips:
            return random.choice(clips)
    return None


def _bg_for(footage, keyword, cache, pexels_key, grad):
    """Return (bg_path, mode) for a segment, defaulting to the gradient."""
    bg_path, kind = footage.fetch(keyword, cache, pexels_key)
    if bg_path and kind == "video":
        return bg_path, "video"
    if bg_path and kind == "photo":
        return bg_path, "photo"
    return grad, "gradient"


def resolve_music(cfg: dict) -> str | None:
    """Find a music track. cfg['music'] can be a file or a folder of tracks
    (a random one is chosen). Returns None if nothing is available."""
    import random
    m = cfg.get("music", "assets/music")
    if not m:
        return None
    if os.path.isfile(m):
        return m
    if os.path.isdir(m):
        tracks = [
            os.path.join(m, f) for f in os.listdir(m)
            if f.lower().endswith((".mp3", ".wav", ".m4a", ".ogg"))
        ]
        if tracks:
            return random.choice(tracks)
    return None
