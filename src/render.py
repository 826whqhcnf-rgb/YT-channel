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


def _overlay_for_item(rank: int, title: str, narration: str) -> np.ndarray:
    # Semi-transparent scrim
    img = Image.new("RGBA", SIZE, (0, 0, 0, 100))
    draw = ImageDraw.Draw(img)

    # Big rank number (top-centre)
    rank_font = _font(max(180, W // 5))
    draw.text((W//2, int(H*0.12)), f"#{rank}", font=rank_font,
              fill=(255,220,0,255), anchor="mm",
              stroke_width=6, stroke_fill=(0,0,0,220))

    # Item title (below rank)
    title_font = _font(max(64, W // 14))
    wrapped = textwrap.fill(title, 18)
    ty = int(H * 0.24)
    for line in wrapped.split("\n"):
        draw.text((W//2, ty), line, font=title_font,
                  fill=(255,255,255,255), anchor="mm",
                  stroke_width=4, stroke_fill=(0,0,0,200))
        ty += title_font.size + 8

    # Caption (bottom)
    cap_font = _font(max(42, W // 22))
    wrapped_cap = textwrap.fill(narration, 28)
    cy = int(H * 0.72)
    for line in wrapped_cap.split("\n")[:4]:
        draw.text((W//2, cy), line, font=cap_font,
                  fill=(240,240,240,255), anchor="mm",
                  stroke_width=3, stroke_fill=(0,0,0,200))
        cy += cap_font.size + 6

    return np.array(img)


def _overlay_for_card(text: str) -> np.ndarray:
    img = Image.new("RGBA", SIZE, (0, 0, 0, 60))
    draw = ImageDraw.Draw(img)
    font = _font(max(72, W // 11))
    wrapped = textwrap.fill(text, 16)
    cy = H // 2 - (wrapped.count("\n") + 1) * (font.size + 10) // 2
    for line in wrapped.split("\n"):
        draw.text((W//2, cy), line, font=font,
                  fill=(255,255,255,255), anchor="mm",
                  stroke_width=5, stroke_fill=(0,0,0,200))
        cy += font.size + 10
    return np.array(img)


def _render_seg(bg: str, bg_is_video: bool, overlay_png: str,
                audio: str, dur: float, out: str) -> None:
    loop = ["-stream_loop", "-1"] if bg_is_video else ["-loop", "1"]
    ff.run([
        *loop, "-i", bg,
        "-loop", "1", "-i", overlay_png,
        "-i", audio,
        "-filter_complex",
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},setsar=1,fps={FPS}[bg];"
        f"[bg][1:v]overlay=0:0[v]",
        "-map", "[v]", "-map", "2:a",
        "-t", f"{dur:.2f}", "-r", str(FPS),
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-threads", "2",
        "-c:a", "aac", "-ar", "44100", "-b:a", "128k",
        out,
    ])


def build(script, voice_clips, out_path: str, cfg: dict) -> str:
    from . import footage

    work = out_path + ".parts"
    os.makedirs(work, exist_ok=True)
    pexels_key = cfg.get("pexels_key", "")
    cache = os.path.join("assets", "cache")
    grad = gradient_png(os.path.join(work, "grad.png"))
    parts = []

    total = len(script.items) + 2

    # --- Hook card ---
    print(f"[render] [1/{total}] hook card")
    ov = _save_png(_overlay_for_card(script.hook), os.path.join(work, "hook_ov.png"))
    hook_dur = voice_clips[0].duration + 0.3
    _render_seg(grad, False, ov, voice_clips[0].path, hook_dur,
                os.path.join(work, "seg_00.mp4"))
    parts.append(os.path.join(work, "seg_00.mp4"))

    # --- Item segments (voice_clips[1] .. voice_clips[N]) ---
    for i, (item, vc) in enumerate(zip(script.items, voice_clips[1:])):
        print(f"[render] [{i+2}/{total}] #{item.rank}: {item.title}")
        bg_path, bg_kind = footage.fetch(item.keyword or script.topic, cache, pexels_key)
        ov = _save_png(
            _overlay_for_item(item.rank, item.title, item.narration),
            os.path.join(work, f"item_{i:02d}_ov.png"),
        )
        seg = os.path.join(work, f"seg_{i+1:02d}.mp4")
        dur = vc.duration + 0.3
        try:
            if bg_path:
                _render_seg(bg_path, bg_kind == "video", ov, vc.path, dur, seg)
            else:
                _render_seg(grad, False, ov, vc.path, dur, seg)
        except Exception as e:
            print(f"[render]   footage failed ({e}); using gradient.")
            _render_seg(grad, False, ov, vc.path, dur, seg)
        parts.append(seg)

    # --- Outro card ---
    print(f"[render] [{total}/{total}] outro")
    ov = _save_png(_overlay_for_card(script.outro), os.path.join(work, "outro_ov.png"))
    outro_vc = voice_clips[-1]
    outro_dur = outro_vc.duration + 0.3
    outro_seg = os.path.join(work, f"seg_{total:02d}.mp4")
    _render_seg(grad, False, ov, outro_vc.path, outro_dur, outro_seg)
    parts.append(outro_seg)

    # --- Concatenate ---
    print(f"[render] concatenating {len(parts)} segments...")
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    try:
        ff.run(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out_path])
    except Exception as e:
        print(f"[render] stream-copy failed ({e}); re-encoding.")
        ff.run([
            "-f", "concat", "-safe", "0", "-i", lst,
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-threads", "2", "-c:a", "aac", "-ar", "44100", out_path,
        ])

    shutil.rmtree(work, ignore_errors=True)
    return out_path
