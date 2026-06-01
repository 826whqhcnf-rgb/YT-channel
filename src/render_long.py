"""
Long-form 16:9 renderer for finance / educational explainers.

Each section = subtle motion/B-roll background + a clean slide overlay
(section heading + key bullet points) + narration, with word-synced captions
in the lower third. Produces a landscape 1920x1080 MP4.
"""
import os, shutil, textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from . import ffmpeg_runner as ff
from . import render as R  # reuse fonts, music/gameplay resolve, _bg_for, etc.

SIZE = (1920, 1080)
W, H = SIZE
FPS = 30

# Brand palette (deep navy -> teal), professional finance look.
BRAND_TOP = (8, 18, 36)
BRAND_BOT = (12, 40, 58)
ACCENT = (0, 220, 170)   # teal-green accent for headings/bullets


def _font(size: int):
    return R._font(size)


def _gradient_png(path: str) -> str:
    img = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        t = y / (H - 1)
        img[y] = tuple(int(BRAND_TOP[c]*(1-t) + BRAND_BOT[c]*t) for c in range(3))
    Image.fromarray(img, "RGB").save(path)
    return path


def _slide_overlay(title: str, heading: str, points: list, idx: int) -> np.ndarray:
    """Left-side heading + bullet points panel; subtle scrim over the B-roll."""
    img = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Darken the left ~60% so text is readable while B-roll shows on the right.
    panel = Image.new("RGBA", (int(W*0.62), H), (6, 14, 28, 205))
    img.paste(panel, (0, 0), panel)

    # Small channel title top-left
    tf = _font(34)
    draw.text((70, 50), title[:60], font=tf, fill=(150, 200, 220, 255))

    # Accent bar + heading
    hy = 230
    if heading:
        draw.rectangle([70, hy, 88, hy + 70], fill=ACCENT + (255,))
        hf = _font(64)
        for line in textwrap.fill(heading, 24).split("\n")[:2]:
            draw.text((110, hy), line, font=hf, fill=(255, 255, 255, 255))
            hy += 76

    # Key points as bullets
    py = max(hy + 40, 360)
    pf = _font(46)
    for p in points[:4]:
        draw.ellipse([74, py + 18, 98, py + 42], fill=ACCENT + (255,))
        for k, line in enumerate(textwrap.fill(p, 34).split("\n")[:2]):
            draw.text((120, py), line, font=pf, fill=(235, 240, 245, 255))
            py += 56
        py += 18

    return np.array(img)


def _render_section(bg, mode, overlay_png, audio, dur, out):
    """One section: B-roll (or gradient) under the slide overlay + narration."""
    if mode == "video":
        loop = ["-stream_loop", "-1"]
        bgf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
               f"crop={W}:{H},setsar=1,fps={FPS}[bg]")
    elif mode == "photo":
        loop = ["-loop", "1"]
        frames = max(1, int(dur * FPS))
        bgf = (f"[0:v]scale={W*2}:{H*2}:force_original_aspect_ratio=increase,"
               f"crop={W*2}:{H*2},zoompan=z='min(zoom+0.0004,1.12)':d={frames}:"
               f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},setsar=1[bg]")
    else:
        loop = ["-loop", "1"]
        bgf = f"[0:v]scale={W}:{H},setsar=1,fps={FPS}[bg]"

    ff.run([
        *loop, "-i", bg,
        "-loop", "1", "-i", overlay_png,
        "-i", audio,
        "-filter_complex", f"{bgf};[bg][1:v]overlay=0:0[v]",
        "-map", "[v]", "-map", "2:a",
        "-t", f"{dur:.2f}", "-r", str(FPS), "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-threads", "2",
        "-c:a", "aac", "-ar", "44100", "-b:a", "128k", out,
    ])


def _title_card(title: str, path: str) -> np.ndarray:
    img = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([W//2 - 200, H - 250, W//2 + 200, H - 244], fill=ACCENT + (255,))
    f = _font(96)
    lines = textwrap.fill(title, 22).split("\n")[:3]
    y = H//2 - len(lines) * 60
    for line in lines:
        draw.text((W//2, y), line, font=f, anchor="mm",
                  fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 200))
        y += 120
    return np.array(img)


def build(script, voice_clips, out_path: str, cfg: dict) -> str:
    from . import footage, captions

    work = out_path + ".parts"
    os.makedirs(work, exist_ok=True)
    pexels_key = cfg.get("pexels_key", "")
    cache = os.path.join("assets", "cache")
    grad = _gradient_png(os.path.join(work, "grad.png"))
    parts, offsets, clip_words, running = [], [], [], 0.0

    def add_clip(vc, tail=0.3):
        nonlocal running
        offsets.append(running); clip_words.append(vc.words)
        running += vc.duration + tail

    total = len(script.segments) + 2

    # --- Intro title card (over gradient) with the hook narration ---
    print(f"[long] [1/{total}] intro")
    ov = R._save_png(_title_card(script.title, ""), os.path.join(work, "intro_ov.png"))
    _render_section(grad, "gradient", ov, voice_clips[0].path,
                    voice_clips[0].duration + 0.3, os.path.join(work, "seg_00.mp4"))
    parts.append(os.path.join(work, "seg_00.mp4")); add_clip(voice_clips[0])

    # --- Section slides ---
    for i, (seg, vc) in enumerate(zip(script.segments, voice_clips[1:])):
        print(f"[long] [{i+2}/{total}] {(seg.heading or seg.text[:30])}...")
        bg, mode = R._bg_for(footage, seg.keyword or script.topic, cache, pexels_key, grad)
        ov = R._save_png(
            _slide_overlay(script.title, seg.heading, seg.points, i),
            os.path.join(work, f"sec_{i:02d}.png"))
        out = os.path.join(work, f"seg_{i+1:02d}.mp4")
        try:
            _render_section(bg, mode, ov, vc.path, vc.duration + 0.3, out)
        except Exception as e:
            print(f"[long]   bg failed ({e}); gradient.")
            _render_section(grad, "gradient", ov, vc.path, vc.duration + 0.3, out)
        parts.append(out); add_clip(vc)

    # --- Outro card ---
    print(f"[long] [{total}/{total}] outro")
    ov = R._save_png(_title_card(script.outro or "Subscribe", ""), os.path.join(work, "outro_ov.png"))
    ovc = voice_clips[-1]
    _render_section(grad, "gradient", ov, ovc.path, ovc.duration + 0.3,
                    os.path.join(work, f"seg_{total:02d}.mp4"))
    parts.append(os.path.join(work, f"seg_{total:02d}.mp4")); add_clip(ovc)

    # --- Concat ---
    print(f"[long] concatenating {len(parts)} sections...")
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    concat = os.path.join(work, "concat.mp4")
    try:
        ff.run(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", concat])
    except Exception as e:
        print(f"[long] copy concat failed ({e}); re-encoding.")
        ff.run(["-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264",
                "-preset", "veryfast", "-pix_fmt", "yuv420p", "-threads", "2",
                "-c:a", "aac", "-ar", "44100", concat])

    # --- Captions (lower-third for landscape) ---
    print("[long] burning captions...")
    ass = captions.build_ass(clip_words, offsets, os.path.join(work, "subs.ass"), size=SIZE)
    ap = ass.replace("\\", "/").replace(":", r"\:")
    captioned = os.path.join(work, "captioned.mp4")
    try:
        ff.run(["-i", concat, "-vf", f"subtitles='{ap}'", "-c:v", "libx264",
                "-preset", "veryfast", "-threads", "2", "-pix_fmt", "yuv420p",
                "-c:a", "copy", captioned])
        stage = captioned
    except Exception as e:
        print(f"[long] caption burn failed ({e}).")
        stage = concat

    # --- Optional music ---
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    music = R.resolve_music(cfg)
    if music:
        vol = cfg.get("music_volume", 0.08)  # quieter under spoken explainer
        print(f"[long] mixing music: {os.path.basename(music)} (vol {vol})")
        try:
            ff.run(["-i", stage, "-stream_loop", "-1", "-i", music, "-filter_complex",
                    f"[1:a]volume={vol}[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                    "-shortest", out_path])
        except Exception as e:
            print(f"[long] music mix failed ({e}).")
            shutil.move(stage, out_path)
    else:
        shutil.move(stage, out_path)

    shutil.rmtree(work, ignore_errors=True)
    return out_path
