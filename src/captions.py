"""
Build an ASS subtitle file with word-by-word reveal (TikTok-style):
each word pops in exactly when the narrator says it, grouped into short
phrases that stay readable on a phone screen.
"""
from __future__ import annotations

W, H = 1080, 1920
WORDS_PER_PHRASE = 3   # how many words visible on screen at once (kept short to fit)


def _ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def _header() -> str:
    # Big bold centred captions with a thick outline — readable over any footage.
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Base,DejaVu Sans,82,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,3,5,140,140,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _dialogue(start: float, end: float, text: str, style: str = "Base") -> str:
    return f"Dialogue: 0,{_ts(start)},{_ts(end)},{style},,0,0,0,,{text}\n"


def build_ass(clip_words, segment_offsets: list[float], path: str) -> str:
    """
    clip_words: list (per audio clip) of Word(text,start,end) lists.
    segment_offsets: absolute start time (s) of each clip in the final video.
    Writes word-synced phrases; the currently-spoken word is highlighted.
    """
    lines = [_header()]

    for words, base in zip(clip_words, segment_offsets):
        if not words:
            continue
        # group words into phrases of WORDS_PER_PHRASE
        for i in range(0, len(words), WORDS_PER_PHRASE):
            group = words[i:i + WORDS_PER_PHRASE]
            g_start = base + group[0].start
            g_end = base + group[-1].end
            # one Dialogue line per spoken word: rebuild the phrase, highlight
            # the active word by wrapping it in the Hi colour via inline tag.
            for j, w in enumerate(group):
                w_start = base + w.start
                w_end = base + (group[j + 1].start if j + 1 < len(group) else w.end)
                parts = []
                for k, gw in enumerate(group):
                    token = _esc(gw.text)
                    if k == j:
                        parts.append(r"{\c&H00F0FF&}" + token + r"{\c&HFFFFFF&}")
                    else:
                        parts.append(token)
                text = " ".join(parts)
                lines.append(_dialogue(w_start, max(w_end, w_start + 0.05), text, "Base"))

    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(lines))
    return path
