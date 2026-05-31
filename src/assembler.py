"""
Assemble the final video with ffmpeg (no moviepy — avoids its install/numpy
breakage and uses far less memory).

Text overlays are drawn with PIL into transparent PNGs, then composited over
the background by ffmpeg. Each segment is rendered to its own MP4 and the
segments are concatenated; a bad stock clip falls back to a gradient rather
than killing the whole render.

Per item:
  background (stock video looped/cropped, or photo, or gradient)
  + dark scrim for legibility
  + big rank/title (top) and optional caption (bottom)
  + the narration audio (sets the segment length)
"""

from __future__ import annotations

import os
import shutil
import textwrap

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import ffmpeg_tools

RESOLUTIONS = {
    "vertical": (1080, 1920),
    "landscape": (1920, 1080),
}


# --------------------------------------------------------------------------- #
# Fonts & helpers
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


def _save_png(arr: np.ndarray, path: str) -> str:
    Image.fromarray(arr, "RGBA").save(path)
    return path


# --------------------------------------------------------------------------- #
# Text rendering -> RGBA arrays
# --------------------------------------------------------------------------- #
def _draw_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[tuple[str, int]],
    size: tuple[int, int],
    y_anchor: str,
    pad: int,
    stroke: int = 6,
) -> None:
    W, H = size
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
        x = (W - w) // 2
        draw.text(
            (x, y),
            text,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=stroke,
            stroke_fill=(0, 0, 0, 255),
        )
        y += h + 14


def _segment_overlay(size: tuple[int, int], rank: int, title: str, caption: str | None) -> np.ndarray:
    """Scrim + top rank/title + optional bottom caption, on a transparent canvas."""
    W, H = size
    img = Image.new("RGBA", (W, H), (0, 0, 0, 90))  # ~35% dark scrim
    draw = ImageDraw.Draw(img)

    top_lines = [(f"#{rank}", max(120, W // 7)), (title, max(54, W // 16))]
    _draw_lines(draw, top_lines, size, y_anchor="top", pad=int(H * 0.08))

    if caption:
        wrap_chars = 26 if W < H else 48
        wrapped = textwrap.fill(caption, wrap_chars).split("\n")[:3]
        cap_lines = [(ln, max(40, W // 22)) for ln in wrapped]
        _draw_lines(draw, cap_lines, size, y_anchor="bottom", pad=int(H * 0.10))

    return np.array(img)


def _card_overlay(size: tuple[int, int], title: str) -> np.ndarray:
    W, H = size
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    wrapped = textwrap.fill(title, 16 if W < H else 28).split("\n")
    lines = [(ln, max(70, W // 12)) for ln in wrapped]
    _draw_lines(draw, lines, size, y_anchor="center", pad=0)
    return np.array(img)


def _gradient_png(size: tuple[int, int], colors: list[str], path: str) -> str:
    W, H = size
    top = np.array(_hex_to_rgb(colors[0]))
    bot = np.array(_hex_to_rgb(colors[-1]))
    grad = np.zeros((H, W, 4), dtype=np.uint8)
    grad[:, :, 3] = 255
    for y in range(H):
        t = y / max(H - 1, 1)
        grad[y, :, :3] = (top * (1 - t) + bot * t).astype(np.uint8)
    return _save_png(grad, path)


# --------------------------------------------------------------------------- #
# Segment rendering
# --------------------------------------------------------------------------- #
def _render_segment(
    bg_path: str,
    bg_is_video: bool,
    overlay_png: str,
    audio_path: str,
    dur: float,
    size: tuple[int, int],
    fps: int,
    out_path: str,
) -> None:
    W, H = size
    loop_bg = ["-stream_loop", "-1"] if bg_is_video else ["-loop", "1"]
    args = [
        *loop_bg, "-i", bg_path,
        "-loop", "1", "-i", overlay_png,
        "-i", audio_path,
        "-filter_complex",
        (
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setsar=1,fps={fps}[bg];"
            f"[bg][1:v]overlay=0:0[v]"
        ),
        "-map", "[v]", "-map", "2:a",
        "-t", f"{dur:.2f}",
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "veryfast",
        "-threads", "2",  # bound CPU/memory on small (2-core) machines
        "-c:a", "aac", "-ar", "44100", "-b:a", "128k",
        out_path,
    ]
    ffmpeg_tools.run(args)


def _render_with_fallback(
    bg_path, bg_kind, overlay_png, audio_path, dur, size, fps, out_path, gradient_png
):
    """Try the chosen background; on any ffmpeg error fall back to the gradient."""
    if bg_path:
        try:
            _render_segment(
                bg_path, bg_kind == "video", overlay_png, audio_path, dur, size, fps, out_path
            )
            return
        except Exception as e:  # noqa: BLE001
            print(f"[assembler] background failed ({e}); using gradient.")
    _render_segment(gradient_png, False, overlay_png, audio_path, dur, size, fps, out_path)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def build_video(
    script,
    voice_clips,
    intro_clip,
    outro_clip,
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
    parts_dir = out_path + ".parts"
    os.makedirs(parts_dir, exist_ok=True)

    gradient_png = _gradient_png(size, fallback_colors, os.path.join(parts_dir, "gradient.png"))
    seg_paths: list[str] = []

    def seg_file(name: str) -> str:
        return os.path.join(parts_dir, name)

    total = len(script.items) + 2

    # 1. Title card
    print(f"[assembler] [1/{total}] title card")
    title_ov = _save_png(_card_overlay(size, script.title), seg_file("title_ov.png"))
    title_dur = (intro_clip.duration if intro_clip else title_seconds) + 0.4
    title_out = seg_file("seg_title.mp4")
    _render_segment(
        gradient_png, False, title_ov, intro_clip.path, title_dur, size, fps, title_out
    )
    seg_paths.append(title_out)

    # 2. Item segments
    for idx, (item, vc) in enumerate(zip(script.items, voice_clips)):
        print(f"[assembler] [{idx + 2}/{total}] item #{item.rank}: {item.title}")
        bg_path, bg_kind = visuals_mod.fetch(
            item.keyword or script.topic, visual_source, cache_dir, orientation, pexels_key
        )
        ov = _save_png(
            _segment_overlay(size, item.rank, item.title, item.narration if captions else None),
            seg_file(f"item_{idx:02d}_ov.png"),
        )
        out_seg = seg_file(f"seg_item_{idx:02d}.mp4")
        dur = vc.duration + 0.4
        _render_with_fallback(
            bg_path, bg_kind, ov, vc.path, dur, size, fps, out_seg, gradient_png
        )
        seg_paths.append(out_seg)

    # 3. Outro card
    print(f"[assembler] [{total}/{total}] outro card")
    outro_text = script.outro or "Subscribe!"
    outro_ov = _save_png(_card_overlay(size, outro_text), seg_file("outro_ov.png"))
    outro_dur = (outro_clip.duration if outro_clip else outro_seconds) + 0.4
    outro_out = seg_file("seg_outro.mp4")
    _render_segment(
        gradient_png, False, outro_ov, outro_clip.path, outro_dur, size, fps, outro_out
    )
    seg_paths.append(outro_out)

    # 4. Concatenate. All segments share identical codec params, so try a
    # cheap stream-copy first (no re-encode = far less CPU/memory). Fall back
    # to a re-encode only if copy produces bad timestamps.
    print(f"[assembler] concatenating {len(seg_paths)} segments")
    list_file = seg_file("concat.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for p in seg_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    concat_out = seg_file("concat.mp4")
    try:
        ffmpeg_tools.run(
            ["-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", concat_out]
        )
    except Exception as e:  # noqa: BLE001
        print(f"[assembler] stream-copy concat failed ({e}); re-encoding.")
        ffmpeg_tools.run(
            [
                "-f", "concat", "-safe", "0", "-i", list_file,
                "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                "-threads", "2", "-c:a", "aac", "-ar", "44100",
                concat_out,
            ]
        )

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    # 5. Optional background music (looped, ducked under narration)
    if music_path and os.path.exists(music_path):
        try:
            ffmpeg_tools.run(
                [
                    "-i", concat_out,
                    "-stream_loop", "-1", "-i", music_path,
                    "-filter_complex",
                    f"[1:a]volume={music_volume}[m];"
                    f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]",
                    "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-shortest",
                    out_path,
                ]
            )
        except Exception as e:  # noqa: BLE001
            print(f"[assembler] music mix skipped ({e}).")
            shutil.move(concat_out, out_path)
    else:
        shutil.move(concat_out, out_path)

    # 6. Clean up intermediate parts
    shutil.rmtree(parts_dir, ignore_errors=True)
    return out_path
