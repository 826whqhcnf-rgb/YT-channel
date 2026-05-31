# Faceless Top-10 Channel — YouTube + TikTok Pipeline

Turn a single topic into a finished, faceless **Top-10 facts** video and
(optionally) auto-publish it to **YouTube** and **TikTok** — using free,
local-first tools.

```
topic  →  AI script  →  neural voiceover  →  stock visuals  →  MP4(s)  →  upload
          (optional)      (edge-tts, free)    (Pexels, free)   9:16 + 16:9
```

- **No face, no camera, no microphone.**
- **Free to start:** voiceover via `edge-tts` (no key), visuals via Pexels (free key).
- **Renders both** vertical (1080×1920 for Shorts/TikTok) and landscape (1920×1080).
- **Captions burned in**, big rank/title overlays, optional background music.
- **Robust**: assembled with `ffmpeg` directly (no moviepy); a failed voice
  segment or stock clip falls back gracefully instead of crashing the run.
- **Optional AI scripts** via any OpenAI-compatible endpoint (OpenAI or local Ollama).
- **Optional auto-upload** to YouTube (Data API v3) and TikTok (Content Posting API).

> ⚠️ This tool **creates and uploads** videos. It does **not** create the
> channel/account itself, and it can't bypass platform sign-up or review.
> See **"What you have to do yourself"** below.

---

## Quick start

```bash
# 1. Install system dependency: ffmpeg
#    macOS:  brew install ffmpeg
#    Ubuntu: sudo apt-get install -y ffmpeg
#    Windows: https://www.gyan.dev/ffmpeg/builds/  (add to PATH)

# 2. Python deps
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure secrets
cp .env.example .env
#    Add your free PEXELS_API_KEY (https://www.pexels.com/api/).
#    Everything else is optional to start.

# 4. Make your first video (no uploads, just local MP4s)
python main.py --topic "strangest deep sea creatures"
```

Outputs land in `output/<topic>-<timestamp>/`:
- `script.json` — the generated script (editable)
- `*-vertical.mp4` and `*-landscape.mp4`

### Editing the script before rendering
```bash
python main.py --topic "ancient inventions" --script-only   # writes script.json
#   ...edit script.json by hand (better facts, tighter narration)...
python main.py --topic "ancient inventions" --script script.json
```

---

## AI script writer (recommended)

Without a writer, the offline generator only makes *placeholder* text. To get
real, interesting Top-10 facts, plug in an AI writer — it speaks the standard
OpenAI-compatible API, so you just pick a provider and paste one key in `.env`.

**Free, no credit card — Groq (recommended):**
1. Get a free key at https://console.groq.com/keys
2. In `.env`:
   ```env
   SCRIPT_PROVIDER=groq
   SCRIPT_API_KEY=gsk_your_key_here
   ```
3. Test it: `python main.py --topic "haunted places" --script-only` and open
   `script.json` — you should see real facts, not placeholders.

**Other providers** — just change `SCRIPT_PROVIDER` and `SCRIPT_API_KEY`:

| `SCRIPT_PROVIDER` | Cost  | Get a key |
|-------------------|-------|-----------|
| `groq`            | free  | https://console.groq.com/keys |
| `gemini`          | free  | https://aistudio.google.com/apikey |
| `openrouter`      | free* | https://openrouter.ai/keys (use free models) |
| `openai`          | paid  | https://platform.openai.com/api-keys |
| `ollama`          | local | run https://ollama.com (no key needed) |

Override the model with `SCRIPT_MODEL` if you like; sensible defaults are built in.

> Always sanity-check AI-generated "facts" before publishing.

### Topic ideas / batching
`data/topics.txt` holds a bank of Top-10 ideas. Run with no topic (or
`--random-topic`) to pick one at random — handy for cranking out a general
"Top 10s" channel:
```bash
python main.py --random-topic
```

---

## Uploading

Uploading is **off by default**. Enable per run:

```bash
python main.py --topic "black holes" --upload youtube          # YouTube only
python main.py --topic "black holes" --upload youtube,tiktok   # both
```
…or flip `upload.youtube.enabled` / `upload.tiktok.enabled` in `config.yaml`.

### YouTube setup (one-time, ~10 min)
1. Go to https://console.cloud.google.com → create a project.
2. **APIs & Services → Library →** enable **"YouTube Data API v3"**.
3. **OAuth consent screen:** type *External*, add your own Google account as a **Test user**.
4. **Credentials → Create credentials → OAuth client ID → Desktop app.** Download the JSON.
5. Save it as `client_secret.json` in this folder (or set `YOUTUBE_CLIENT_SECRET` in `.env`).
6. First upload opens a browser to approve **only the upload scope**; a reusable
   `token.json` is then saved locally.

Notes: new API projects start in a test state where uploads are forced to
**private** until you request verification. Set `upload.youtube.privacy`
accordingly. Daily upload quota is limited (a handful of uploads/day).

### TikTok setup (requires app approval)
1. Create an app at https://developers.tiktok.com → add the **Content Posting API**.
2. Complete TikTok's app review/audit. **Before approval**, posts are limited to
   **private (`SELF_ONLY`)** and to your registered test accounts.
3. Run the OAuth flow to get an **access token** with `video.upload`/`video.publish`
   scope; put it in `TIKTOK_ACCESS_TOKEN` in `.env`.

> The TikTok module uses **only the official API**. There is no scraping /
> unofficial path here — that would violate TikTok's Terms of Service and risk
> a ban. Keep `privacy: SELF_ONLY` until your app is approved.

---

## What you have to do yourself

This software automates **content creation and the upload API calls**. By
design it cannot (and should not) do these for you:

| Step | Why it's on you |
|------|-----------------|
| Create the YouTube channel / Google account | Requires human sign-up + phone verification. |
| Create the TikTok account | Same — anti-bot sign-up. |
| Approve API access (OAuth) | You log in **in your own browser**; the app receives only a scoped token you can revoke. |
| Provide your own API keys/tokens | Stored locally in `.env`/`token.json`, never committed. |
| Verify facts & follow each platform's AI-content disclosure rules | Compliance is the channel owner's responsibility. |

**On giving an AI agent your account access:** don't hand over your passwords.
The correct, safe mechanism is exactly what this repo uses — **scoped OAuth
tokens and API keys that live in your own machine's `.env`**, which you can
revoke at any time. That way the automation can post on your behalf without
ever holding your login, and nothing sensitive is stored in the repo.

---

## Configuration reference

See `config.yaml` — voice, items per video, resolutions to render, music,
captions, and upload/privacy settings are all there.

## Project layout
```
main.py                 CLI entry point
config.yaml             All tunable settings
.env.example            Secrets template (copy to .env)
src/
  script_generator.py   LLM or offline Top-10 script
  tts.py                edge-tts voiceover (retries + silent fallback)
  visuals.py            Pexels stock fetch + fallbacks
  ffmpeg_tools.py       ffmpeg/ffprobe wrapper (system or bundled binary)
  assembler.py          ffmpeg + PIL video assembly
  upload_youtube.py     YouTube Data API v3
  upload_tiktok.py      TikTok Content Posting API
  pipeline.py           Orchestrates the whole run
assets/music/           Put bg.mp3 here (optional)
```

## Disclaimer
You are responsible for the content you publish, for complying with YouTube's
and TikTok's Terms of Service and AI-disclosure policies, and for the licensing
of any media and music you use.
