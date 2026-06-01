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

## Long-form finance explainers (mode: finance)

Make landscape 16:9 educational finance videos (plus an auto-cut vertical Short):
```bash
# AI drafts a script you can edit first (recommended for accuracy):
python run.py --mode finance --topic "how compound interest works" --script-only
#   ...open the printed script.json, fix/improve the text...
python run.py --mode finance --script output/.../script.json

# Or one shot, random finance topic:
python run.py --mode finance --random
```
- Each section shows an on-screen heading + key bullet points over B-roll, with
  word-synced captions in the lower third.
- A vertical Short teaser is auto-cut from the first sections (turn off with
  `"make_short": false` in config.json).
- Length knobs in config.json: `sections`, `words_per_section`.
- Needs your OpenRouter key (same one from setup). ⚠️ Always fact-check finance
  scripts before posting — it's educational content, not advice.

The Reddit story mode is unchanged — just leave off `--mode` (or use
`--mode reddit`).

---

## Autopilot (hands-off) 🤖

Make (and optionally post) a batch of videos with one command:
```bash
python autopilot.py                  # uses the "autopilot" block in config.json
python autopilot.py --count 3        # make 3 now
python autopilot.py --upload youtube # make + auto-post to YouTube
python autopilot.py --loop           # keep going on a schedule (every_hours)
python autopilot.py --mode finance   # long-form finance instead of stories
```
Configure defaults in `config.json` → `autopilot`:
`count` (videos per run), `mode` (reddit/finance), `upload` (["youtube"] etc. or
[] to just save), `every_hours` (loop interval), `stop_after_runs` (0 = forever).

The first YouTube post pauses once for the browser authorization; after that
it's fully unattended. Leave `python autopilot.py --loop` running and it keeps
your channel fed.

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
