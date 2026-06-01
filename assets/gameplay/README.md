# Gameplay background (Subway Surfers / Minecraft parkour style)

Drop one or more gameplay clips here (`.mp4`, `.mov`, `.mkv`, or `.webm`) and
the renderer will run gameplay **continuously behind the whole video**, with the
word-synced captions on top — the classic Reddit-story look.

- If this folder has a clip, gameplay is used automatically (one is picked at
  random per video) and Pexels B-roll is skipped.
- If it's empty, videos fall back to relevant stock B-roll / gradient.

## How to add a clip (in your Codespace)

1. Find a long, **no-copyright / royalty-free** gameplay video (vertical 9:16 is
   ideal, but any aspect works — it gets cropped to fill the screen). Good
   searches on YouTube: "subway surfers gameplay no copyright vertical",
   "minecraft parkour gameplay copyright free", "satisfying gameplay 10 minutes".
2. Download it to your computer (e.g. with a YouTube downloader you're allowed
   to use), then **drag-and-drop the file into this `assets/gameplay` folder**
   in the Codespace file explorer on the left.
3. That's it — run `python run.py` and the gameplay plays behind your story.

A single 5-10 minute clip is plenty; the renderer loops it if a video is longer
than the clip, and starts wherever it needs to.

## Options (config.json)

- `"gameplay": "assets/gameplay"` — folder (random clip) or a single file path.
- Set `"gameplay": ""` (empty) to force stock B-roll instead.

> ⚠️ Only use gameplay footage you're licensed to use. "No copyright" /
> "copyright free" / Creative Commons clips are safest. Using copyrighted
> gameplay can get videos muted, demonetised, or taken down.
