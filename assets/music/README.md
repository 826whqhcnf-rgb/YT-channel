# Background music

Drop one or more royalty-free tracks in this folder (`.mp3`, `.wav`, `.m4a`,
or `.ogg`). The renderer picks one **at random per video** and mixes it quietly
under the narration, so a folder of a few lo-fi tracks keeps your videos varied.

If this folder is empty, videos render with narration only — nothing breaks.

## Where to get free music (cleared for TikTok / YouTube)

- **YouTube Audio Library** — https://studio.youtube.com → *Audio Library*.
  Filter to "No copyright". Lo-fi / ambient / cinematic suit story videos.
- **Pixabay Music** — https://pixabay.com/music/ — free for commercial use,
  no attribution. Search "lofi", "ambient", "suspense".
- **Free Music Archive** — https://freemusicarchive.org — check each track's
  licence.

## Tips

- For Reddit-story videos, calm **lo-fi** or soft **suspense/ambient** beds work
  best — quiet enough that the voice stays clear.
- Adjust loudness in `config.json` → `"music_volume"` (0.12 is a good start;
  lower = quieter).
- Point `"music"` in `config.json` at a single file instead of this folder if
  you want the same track every time.

> ⚠️ Only use music you're licensed to use. Copyrighted songs can get videos
> muted, demonetised, or taken down.
