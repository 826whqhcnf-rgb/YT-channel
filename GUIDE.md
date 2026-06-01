# Quick Start Guide

## First time only (~5 min)

### 1. Install dependencies (Codespace does this automatically)
```bash
pip install -r requirements.txt
```

### 2. Run the setup wizard
```bash
python setup.py
```

This walks you through getting two free keys:
- **OpenRouter** (AI writer): https://openrouter.ai/keys — free, no credit card
- **Pexels** (stock footage): https://www.pexels.com/api — free

The wizard **tests both keys** before saving them, so you'll know immediately if they work.

---

## Make a video

```bash
# Make a video from a real trending Reddit story (default)
python run.py

# Make a BACKLOG of 5 videos from 5 different Reddit stories
python run.py --batch 5

# Check the script before rendering
python run.py --script-only
```

Videos save to the `output/` folder. Download them and post to TikTok/YouTube Shorts.

### Where the stories come from
By default the tool pulls **real top posts** from story subreddits
(r/AmItheAsshole, r/tifu, r/ProRevenge, r/MaliciousCompliance, and more) — no AI
key needed. It remembers which posts it used so a batch never repeats.

- Change the subreddits or word limits in `config.json`:
  `"subreddits": ["AmItheAsshole","tifu",...]`, `"min_words"`, `"max_words"`.
- Prefer AI-written original stories instead? Set `"source": "ai"` in
  `config.json` (needs your OpenRouter key).

---

## Background music (optional)

Drop royalty-free `.mp3` tracks into the **`assets/music/`** folder. The
renderer mixes one in (at random) quietly under the narration. If the folder is
empty, videos play with narration only. See `assets/music/README.md` for free,
TikTok-safe music sources. Adjust loudness with `"music_volume"` in `config.json`.

---

## Auto-posting (optional)

Post finished videos straight to YouTube Shorts / TikTok with your own account:
```bash
python run.py --upload youtube,tiktok
python run.py --batch 5 --upload youtube   # post a whole backlog
```
One-time credential setup (your keys stay on your machine) is in
**`UPLOAD_SETUP.md`**.

---

## Post the video

**TikTok:** Open TikTok app → + → Upload → pick the .mp4

**YouTube Shorts:** Open YouTube app → + → Create a Short → Upload → add **#Shorts** to the title

---

## Troubleshooting

**Script is placeholder text?** → Run `python setup.py` and enter your OpenRouter key.

**No background footage?** → Run `python setup.py` and enter your Pexels key.

**Video terminated / crashed?** → Run `python run.py --topic "..." --script-only` to test just the script first.

**Still stuck?** → The error message in the terminal tells you exactly what's wrong.
