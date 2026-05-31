"""
Assemble the final video with moviepy.

Text is rendered with PIL (Pillow) instead of moviepy's TextClip so there is
NO ImageMagick dependency — it works out of the box on a clean machine.

Per item:
  background visual (stock video looped/cropped, or photo with Ken Burns)
  + big rank/title overlay
  + optional burned-in caption (the narration text)
  + the narration audio (sets the segment duration)

Then: title card + items + outro card, with optional background music.
"""

from __future__ import annotations

import os
import textwrap

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
)
from moviepy.audio.fx.audio_loop import audio_loop

RESOLUTIONS = {
    "vertical": (1080, 1920),
    "landscape": (1920, 1080),
}


# --------------------------------------------------------------------------- #
# Fonts
# --------------------------------------------------------------------------- #
def _load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# Text rendering (PIL -> RGBA image -> ImageClip)
# --------------------------------------------------------------------------- #
def _text_image(
    lines: list[tuple[str, int]],
    size: tuple[int, int],
    align: str = "center",
    y_anchor: str = "center",
    pad: int = 60,
    stroke: int = 6,
) -> np.ndarray:
    """Render multi-size lines onto a transparent RGBA canvas."""
    W, H = size
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    rendered = []
    total_h = 0
    for text, fsize in lines:
        font = _load_font(fsize)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        rendered.append((text, font, w, h))
        total_h += h + 14

    if y_anchor == "center":
        y = (H - total_h) // 2
    elif y_anchor == "bottom":
        y = H - total_h - pad
    else:
        y = pad

    for text, font, w, h in rendered:
        if align == "center":
            x = (W - w) // 2
        elif align == "left":
            x = pad
        else:
            x = W - w - pad
        draw.text(
            (x, y),
            text,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=stroke,
            stroke_fill=(0, 0, 0, 255),
        )
        y += h + 14

    return np.array(img)


# --------------------------------------------------------------------------- #
# Backgrounds
# --------------------------------------------------------------------------- #
def _fit_cover(clip, size: tuple[int, int]):
    """Resize + center-crop a clip/image to exactly cover `size`."""
    W, H = size
    cw, ch = clip.size
    scale = max(W / cw, H / ch)
    clip = clip.resize(scale)
    cw, ch = clip.size
    x1 = (cw - W) // 2
    y1 = (ch - H) // 2
    return clip.crop(x1=x1, y1=y1, x2=x1 + W, y2=y1 + H)


def _gradient_bg(size: tuple[int, int], colors: list[str], duration: float):
    W, H = size
    top = np.array(_hex_to_rgb(colors[0]))
    bot = np.array(_hex_to_rgb(colors[-1]))
    grad = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        t = y / max(H - 1, 1)
        grad[y, :, :] = (top * (1 - t) + bot * t).astype(np.uint8)
    return ImageClip(grad).set_duration(duration)


def _background_for(
    path: str | None, kind: str, size: tuple[int, int], duration: float, colors: list[str]
):
    if kind == "video" and path:
        try:
            base = VideoFileClip(path).without_audio()
            base = _fit_cover(base, size)
            # Loop or trim to match the needed duration
            if base.duration < duration:
                n = int(duration / base.duration) + 1
                base = concatenate_videoclips([base] * n)
            return base.subclip(0, duration)
        except Exception as e:  # noqa: BLE001
            print(f"[assembler] video bg failed ({e}); using gradient.")
    elif kind == "photo" and path:
        try:
            img = ImageClip(path).set_duration(duration)
            img = _fit_cover(img, size)
            # Ken Burns: slow zoom from 1.0 -> 1.08
            img = img.resize(lambda t: 1.0 + 0.08 * (t / max(duration, 0.1)))
            img = _fit_cover(img, size)
            return img.set_duration(duration)
        except Exception as e:  # noqa: BLE001
            print(f"[assembler] photo bg failed ({e}); using gradient.")
    return _gradient_bg(size, colors, duration)


def _scrim(size: tuple[int, int], duration: float, opacity: float = 0.35):
    """Dark overlay so white text stays readable over any footage."""
    return (
        ColorClip(size, color=(0, 0, 0))
        .set_opacity(opacity)
        .set_duration(duration)
    )


# --------------------------------------------------------------------------- #
# Cards & segments
# --------------------------------------------------------------------------- #
def _caption_clip(text: str, size: tuple[int, int], duration: float):
    W, H = size
    wrap_chars = 26 if W < H else 48
    wrapped = textwrap.fill(text, wrap_chars)
    lines = [(ln, max(40, W // 22)) for ln in wrapped.split("\n")][:3]
    arr = _text_image(lines, (W, H), y_anchor="bottom", pad=int(H * 0.10))
    return ImageClip(arr).set_duration(duration)


def _title_card(title: str, size: tuple[int, int], duration: float, colors: list[str]):
    W, H = size
    bg = _gradient_bg(size, colors, duration)
    wrapped = textwrap.fill(title, 16 if W < H else 28)
    lines = [(ln, max(70, W // 12)) for ln in wrapped.split("\n")]
    arr = _text_image(lines, (W, H), y_anchor="center")
    return CompositeVideoClip([bg, ImageClip(arr).set_duration(duration)], size=size)


def _item_segment(
    item, audio: AudioFileClip, bg_path, bg_kind, size, colors, captions: bool
):
    duration = audio.duration + 0.4  # small tail so audio isn't clipped
    W, H = size
    bg = _background_for(bg_path, bg_kind, size, duration, colors)
    layers = [bg, _scrim(size, duration)]

    # Big "#rank" top + item title
    rank_lines = [(f"#{item.rank}", max(120, W // 7)), (item.title, max(54, W // 16))]
    arr = _text_image(rank_lines, (W, H), y_anchor="top", pad=int(H * 0.08))
    layers.append(ImageClip(arr).set_duration(duration))

    if captions:
        layers.append(_caption_clip(item.narration, size, duration))

    seg = CompositeVideoClip(layers, size=size).set_audio(audio.set_duration(duration))
    return seg.set_duration(duration)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def build_video(
    script,
    voice_clips,            # list of VoiceClip aligned to script.items
    intro_clip,             # VoiceClip for intro (or None)
    outro_clip,             # VoiceClip for outro (or None)
    orientation: str,
    out_path: str,
    cache_dir: str,
    pexels_key: str,
    visual_source: str,
    fallback_colors: list[str],
    fps: int = 30,
    title_seconds: float = 3.0,
    outro_seconds: float = 3.0,
    music_path: str | None = None,
    music_volume: float = 0.12,
    captions: bool = True,
) -> str:
    from . import visuals as visuals_mod

    size = RESOLUTIONS[orientation]
    segments = []

    # 1. Title card (with intro narration if available)
    title_dur = intro_clip.duration + 0.4 if intro_clip else title_seconds
    title = _title_card(script.title, size, title_dur, fallback_colors)
    if intro_clip:
        title = title.set_audio(
            AudioFileClip(intro_clip.path).set_duration(title_dur)
        )
    segments.append(title)

    # 2. Item segments
    for item, vc in zip(script.items, voice_clips):
        bg_path, bg_kind = visuals_mod.fetch(
            item.keyword or script.topic, visual_source, cache_dir, orientation, pexels_key
        )
        audio = AudioFileClip(vc.path)
        segments.append(
            _item_segment(item, audio, bg_path, bg_kind, size, fallback_colors, captions)
        )

    # 3. Outro card
    outro_dur = outro_clip.duration + 0.4 if outro_clip else outro_seconds
    outro = _title_card(script.outro or "Subscribe!", size, outro_dur, fallback_colors)
    if outro_clip:
        outro = outro.set_audio(AudioFileClip(outro_clip.path).set_duration(outro_dur))
    segments.append(outro)

    final = concatenate_videoclips(segments, method="compose")

    # 4. Background music (optional, ducked under narration)
    if music_path and os.path.exists(music_path):
        try:
            music = AudioFileClip(music_path).volumex(music_volume)
            music = audio_loop(music, duration=final.duration)
            final = final.set_audio(CompositeAudioClip([final.audio, music]))
        except Exception as e:  # noqa: BLE001
            print(f"[assembler] music mix skipped ({e}).")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    final.write_videofile(
        out_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        threads=os.cpu_count() or 2,
        preset="medium",
        logger=None,
    )
    final.close()
    return out_path
