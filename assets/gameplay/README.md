# Gameplay background (Subway Surfers / Minecraft parkour style)

Drop one or more gameplay clips here (`.mp4`, `.mov`, `.mkv`, or `.webm`) and
the renderer will run gameplay **continuously behind the whole video**, with the
word-synced captions on top — the classic Reddit-story look.

- If this folder has a clip, gameplay is used automatically (one is picked at
  random per video) and Pexels B-roll is skipped.
- If it's empty, videos fall back to relevant stock B-roll / gradient.

## How to add a clip (in your Codespace)

**Easiest — download straight from YouTube:**
```bash
python get_gameplay.py "https://youtu.be/VIDEO_ID"
```
This saves the clip into this folder automatically. Use a **no-copyright /
free-to-use** gameplay video (check the video's description). Example:
```bash
python get_gameplay.py "https://youtu.be/zZ7AimPACzc"
```

**Or manually (most reliable):**
1. Download a long, **no-copyright / royalty-free** gameplay video on your OWN
   computer (any YouTube downloader / browser extension you're allowed to use).
2. **Drag-and-drop the file into this `assets/gameplay` folder** in the
   Codespace file explorer on the left.

> ⚠️ Note: YouTube often blocks downloads from cloud servers (Codespaces) with
> a "confirm you're not a bot" error. `get_gameplay.py` automatically tries
> several YouTube clients to get around it, but it doesn't always work. If it
> keeps failing, use the manual drag-and-drop method above — it always works.

A single 5-10 minute clip is plenty; the renderer loops it if a video is longer
than the clip, and starts wherever it needs to.

## Options (config.json)

- `"gameplay": "assets/gameplay"` — folder (random clip) or a single file path.
- Set `"gameplay": ""` (empty) to force stock B-roll instead.

> ⚠️ Only use gameplay footage you're licensed to use. "No copyright" /
> "copyright free" / Creative Commons clips are safest. Using copyrighted
> gameplay can get videos muted, demonetised, or taken down.
