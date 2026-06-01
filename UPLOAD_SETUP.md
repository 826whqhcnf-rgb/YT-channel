# Auto-posting setup (YouTube + TikTok)

Auto-posting is **off by default**. When you turn it on, the tool posts each
finished video using **your own credentials**, which live only on your machine
(gitignored) and are never shared. You can revoke access any time.

Turn it on per run:
```bash
python run.py --upload youtube            # YouTube only
python run.py --upload tiktok             # TikTok only
python run.py --upload youtube,tiktok     # both
python run.py --batch 5 --upload youtube  # post a whole backlog
```
…or set `"upload": {"youtube": true}` in `config.json` to always post.

---

## YouTube (Shorts) — one-time setup (~10 min)

1. Go to https://console.cloud.google.com and create a project.
2. **APIs & Services → Library →** enable **"YouTube Data API v3"**.
3. **OAuth consent screen:** choose *External*, fill the basics, and under
   **Test users** add your own Google account (the channel's account).
4. **Credentials → Create credentials → OAuth client ID → type "Desktop app"**
   → **Download JSON**.
5. In your Codespace, upload that file and name it **`client_secret.json`**
   (right-click the file list → Upload), or set its path in `config.json` →
   `upload.youtube_client_secret`.
6. First post prints a Google URL — open it, sign in, approve the **upload**
   permission, paste the code back. A reusable `youtube_token.json` is saved,
   so you only authorize once.

Settings in `config.json` → `upload`:
- `youtube_privacy`: `public` | `unlisted` | `private` (start with `unlisted`
  to test, then switch to `public`).
- `youtube_category`: `24` = Entertainment, `27` = Education, etc.

Notes: new API projects have a daily upload quota (a handful of videos/day) and
may force uploads to private until Google verifies the project.

---

## TikTok — one-time setup

TikTok requires a developer app. **Before TikTok approves your app, posts are
limited to private (`SELF_ONLY`) and only to your registered test account.**

1. Create an app at https://developers.tiktok.com → add the **Content Posting
   API** product, with the `video.publish` scope.
2. Complete TikTok's app review when you're ready to post publicly.
3. Run the OAuth flow to get an **access token** for your account, and paste it
   into `config.json` → `upload.tiktok_token` (or set `TIKTOK_ACCESS_TOKEN`).
4. `upload.tiktok_privacy`: keep `SELF_ONLY` until your app is approved, then
   `PUBLIC_TO_EVERYONE`.

This uses TikTok's **official** API only — there's no scraping/unofficial path
(those violate TikTok's Terms and risk a ban).

---

## Safety

- `client_secret.json`, `youtube_token.json`, and `config.json` (which holds
  your TikTok token) are all gitignored — they never get pushed.
- Revoke YouTube access: https://myaccount.google.com/permissions
- Revoke TikTok access: TikTok app → Settings → Security → Apps.
- You are responsible for following each platform's Terms and AI-content /
  reused-content disclosure rules.
