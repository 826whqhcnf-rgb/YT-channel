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
# Specific topic
python run.py --topic "strangest deep sea creatures"

# Random topic from data/topics.txt
python run.py --random

# Check the script before rendering
python run.py --topic "haunted places" --script-only
```

Videos save to the `output/` folder. Download them and post to TikTok/YouTube Shorts.

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
