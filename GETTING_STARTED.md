# Getting Started — the no-experience, Chromebook/iPad guide

This guide assumes you've **never used a terminal** and you're on a
**Chromebook or iPad**. You won't install anything on your device. Instead
you'll use a free "cloud computer" in your web browser called **GitHub
Codespaces**.

Total time the first time: about **30–40 minutes**. After that, making a new
video takes about **2 minutes**.

> 💡 What's a "cloud computer"? It's a real computer that lives on the internet.
> You control it through your browser. It can run the video software your
> Chromebook/iPad can't. When you're done, you download the finished video to
> your device.

---

## Part A — Open the project in a Codespace (one time, ~5 min)

1. In your browser, go to **https://github.com** and **sign in** with the same
   account that owns this project.
2. Go to your project page (the repository named **yt-channel**).
3. Click the green **`< > Code`** button near the top right.
4. In the little menu, click the **Codespaces** tab.
5. Click **Create codespace on `claude/faceless-youtube-channel-Pmbd4`**.
   - If it offers a different branch, click the branch name and pick
     `claude/faceless-youtube-channel-Pmbd4` first.
6. A new tab opens that looks like a code editor. **Wait** — at the bottom it
   will say it's "setting up". It's installing the video software for you. This
   takes **2–4 minutes** the first time. ☕
7. It's ready when the bottom activity stops and you see a **Terminal** panel at
   the bottom (a black box where you can type). If you don't see it, click the
   menu **☰ → Terminal → New Terminal**.

✅ **Checkpoint:** You have a code editor in your browser with a black terminal
box at the bottom. That terminal is where you'll type the commands below. To
"run" a command: click in the box, paste the text, press **Enter**.

---

## Part B — Get your free Pexels key (one time, ~2 min)

The video grabs free background clips from a site called Pexels. You need a free
"key" (a password-like code) so it's allowed to.

1. Go to **https://www.pexels.com/api/** and click **Get Started**.
2. Make a free account (email + password).
3. It shows you an **API Key** — a long string of letters and numbers. Copy it.
4. Back in the Codespace terminal, type this command **but paste your key
   between the quotes**, then press Enter:

   ```bash
   echo 'PEXELS_API_KEY=PASTE_YOUR_KEY_HERE' > .env
   ```

   Example of what it looks like filled in:
   `echo 'PEXELS_API_KEY=563492ad6f91700001000001abc...' > .env`

✅ **Checkpoint:** You've created a hidden settings file called `.env` with your
key in it. (You only do this once per Codespace.)

---

## Part B½ — Connect the AI writer (free, ~3 min)

Without this, the narration is fake placeholder text. This step gives you real
Top-10 facts. We'll use **Groq** because it's free and needs no credit card.

1. Go to **https://console.groq.com/keys** and sign in (Google login is fine).
2. Click **Create API Key**, give it any name, and **copy** the key (it starts
   with `gsk_`).
3. In the Codespace terminal, add it to your settings file by running these two
   lines (paste your key between the quotes on the second line):

   ```bash
   echo 'SCRIPT_PROVIDER=groq' >> .env
   echo 'SCRIPT_API_KEY=gsk_PASTE_YOUR_KEY_HERE' >> .env
   ```

   (Note the `>>` — that **adds** to the `.env` file without erasing your Pexels
   key from Part B.)

✅ **Checkpoint:** Your `.env` now has a Pexels key *and* a Groq key. Your videos
will now have real facts written by AI.

---

## Part C — Make your first video (~2–3 min)

In the terminal, type this and press Enter (change the topic to whatever you
like):

```bash
python main.py --topic "strangest deep sea creatures"
```

You'll see lots of text scroll by — that's normal. It's writing a script,
recording a voiceover, downloading clips, and stitching the video together.
When it's done it prints something like:

```
=== Done ===
Output folder: output/strangest-deep-sea-creatures-20260531-141500
  vertical  -> output/.../...-vertical.mp4
```

✅ **Checkpoint:** You made a video file! Next, let's watch it and save it to
your device.

---

## Part D — Watch and download your video (~1 min)

1. On the **left side** of the editor is a file list. Click the **`output`**
   folder to open it, then open the dated folder inside it.
2. You'll see a file ending in **`-vertical.mp4`**. Click it once to preview it,
   or **right-click it → Download** to save it to your Chromebook/iPad.

> 📝 **About the words:** If you did **Part B½**, the AI writer fills in real
> facts automatically — you're all set. If you skipped it, the narration is
> placeholder text and you have two options:
> - **Easiest:** open the `script.json` file in that output folder, and type
>   your own real facts over the placeholder text (just change the words inside
>   the quotes). Then re-make the video pointing at your edited script:
>   `python main.py --topic "deep sea" --script output/SomeFolder/script.json`
> - **Fancier (optional):** connect a free AI writer — see the main `README.md`
>   section "Better AI scripts."

---

## Part E — Post your video (the simple way, recommended to start)

For your first videos, **upload by hand**. It's the most reliable and there's
nothing technical to set up:

**YouTube (as a Short):**
1. On your phone, open the **YouTube** app and sign into your channel.
2. Tap the **➕** at the bottom → **Create a Short** / **Upload a video**.
3. Pick the `-vertical.mp4` you downloaded.
4. Title it, and **include the word `#Shorts`** in the title or description so
   YouTube treats it as a Short. Post it.

**TikTok:**
1. Open the **TikTok** app and sign in.
2. Tap **➕** → **Upload** (next to the record button).
3. Pick the same `-vertical.mp4`, add a caption, and post.

That's a complete, working channel workflow. 🎉 Do this a few times before
bothering with the automatic-upload setup below.

---

## Part F — Automatic uploading (optional, do this LATER)

Once you're making videos regularly and want them to post themselves, the
automatic uploaders are already built in. **Heads up: this part is fiddly**, and
TikTok in particular requires your developer app to be reviewed before it can
post publicly. Full step-by-step is in `README.md` under **"Uploading"**,
**"YouTube setup"**, and **"TikTok setup"**.

My honest advice: stay on **Part E (manual upload)** until posting by hand feels
like a chore. Then come back and we can set up automation together.

---

## Making more videos later

Your Codespace goes to sleep when you're not using it (so it doesn't waste your
free hours). To make another video:

1. Go to **https://github.com/codespaces** and click your existing Codespace to
   reopen it (your `.env` key is still there).
2. In the terminal, run `python main.py --topic "your new topic"`.
3. Download the new `-vertical.mp4` and post it.

---

## If something goes wrong

- **"command not found: python"** — the setup may still be finishing; wait a
  minute and try again, or run the setup by hand:
  `sudo apt-get update && sudo apt-get install -y ffmpeg && pip install -r requirements.txt`
- **No background clips / plain colored background** — your Pexels key in `.env`
  is missing or wrong. Redo Part B.
- **It mentions placeholder narration** — that's expected; see the note in
  Part D about editing `script.json` or connecting an AI writer.
- **Stuck?** Tell me exactly what the terminal said and I'll walk you through it.
