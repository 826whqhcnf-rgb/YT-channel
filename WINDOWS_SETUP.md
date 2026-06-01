# Run it locally on Windows (one-time setup, ~15 min)

Running on your own PC removes every cloud headache: the YouTube login becomes
one click, Reddit/YouTube stop IP-blocking you, and `autopilot.py --loop` can
run as long as your PC is on. Do this once.

> Throughout: when I say "open PowerShell", click Start, type **PowerShell**,
> press Enter. Copy a command, paste with **Ctrl+V** (or right-click), Enter.

---

## 1. Install the tools (Python, ffmpeg, git)

The fastest way is `winget` (built into Windows 10/11). In PowerShell, run these
one at a time:

```powershell
winget install --id Python.Python.3.12 -e
winget install --id Git.Git -e
winget install --id Gyan.FFmpeg -e
```

Then **CLOSE PowerShell and open a new one** (so it picks up the new programs).
Verify each works:

```powershell
python --version
git --version
ffmpeg -version
```

Each should print a version number. If `python` opens the Microsoft Store
instead, install from https://www.python.org/downloads/ and tick
**"Add python.exe to PATH"** during install.

> If `winget` isn't found, install the three manually:
> Python https://www.python.org/downloads/ (tick "Add to PATH"),
> Git https://git-scm.com/download/win,
> ffmpeg https://www.gyan.dev/ffmpeg/builds/ (get "ffmpeg-release-essentials",
> unzip, and add its `bin` folder to your PATH).

---

## 2. Download the project

Pick a folder (e.g. your Documents) and clone the repo:

```powershell
cd $HOME\Documents
git clone https://github.com/826whqhcnf-rgb/yt-channel.git
cd yt-channel
git checkout claude/faceless-youtube-channel-Pmbd4
```

---

## 3. Install the Python packages

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## 4. Set up your keys

```powershell
python setup.py
```
Paste your **OpenRouter** key (and Pexels key if you have one) when asked — the
wizard tests them. This writes `config.json`.

---

## 5. Add a gameplay background (optional)

```powershell
python get_gameplay.py
```
Downloads a free clip into `assets\gameplay\`. Or drop your own `.mp4` in that
folder.

---

## 6. Make your first video

```powershell
python run.py
```
The finished video + a copy-paste caption `.txt` land in the `downloads\` folder.

---

## 7. Turn on auto-posting to YouTube (the part that finally works locally)

1. Put your `client_secret.json` (from Google Cloud) in the project folder.
   (See `UPLOAD_SETUP.md` if you still need to create it.)
2. Run:
   ```powershell
   python run.py --upload youtube
   ```
3. Your **browser opens automatically** → sign in with your channel's Google
   account → "unverified app" → **Advanced → Go to (app) → Allow**. The page
   closes itself and the upload proceeds. ✅ One click, no copy-paste.
4. A `youtube_token.json` is saved, so you're never asked again.

> Tip: set `"youtube_privacy": "unlisted"` in `config.json` for the first test,
> confirm it lands on your channel, then switch to `"public"`.

---

## 8. Full autopilot

Once a single upload has worked:

```powershell
python autopilot.py --upload youtube --count 3   # make + post 3
python autopilot.py --loop                        # keep going on a schedule
```
Leave the `--loop` window open and it feeds your channel automatically. Set the
defaults (count, mode, interval) in `config.json` under `autopilot`.

---

## Daily use, after setup

```powershell
cd $HOME\Documents\yt-channel
git pull                 # get any updates
python autopilot.py      # make a batch
```

## Troubleshooting
- **`python` not recognised** → reinstall Python with "Add to PATH" ticked, new PowerShell.
- **`ffmpeg` not recognised** → the bundled `imageio-ffmpeg` is a fallback, but installing real ffmpeg (step 1) is faster.
- **Reddit/YouTube errors** → on a home connection these should be gone; if not, tell me the exact message.
