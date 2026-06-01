"""
Auto-post finished videos to YouTube Shorts and TikTok.

Both platforms use YOUR OWN credentials, stored locally and gitignored:
  - YouTube: an OAuth client (client_secret.json) you authorize once in a
    browser; a reusable token is saved to youtube_token.json.
  - TikTok: an access token (with video.publish scope) you paste into
    config.json under upload.tiktok_token.

Nothing is ever shared with anyone else. You can revoke access any time.
See UPLOAD_SETUP.md for the one-time setup.
"""
from __future__ import annotations

import os
import time

# ---------------------------------------------------------------------------
# YouTube (Data API v3)
# ---------------------------------------------------------------------------
YT_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
YT_TOKEN = "youtube_token.json"


def _yt_service(client_secret: str):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(YT_TOKEN):
        creds = Credentials.from_authorized_user_file(YT_TOKEN, YT_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(client_secret):
                raise FileNotFoundError(
                    f"YouTube client secret not found at '{client_secret}'. "
                    "See UPLOAD_SETUP.md (YouTube section)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(client_secret, YT_SCOPES)
            # console flow works in a headless Codespace (prints a URL to visit)
            creds = flow.run_console() if hasattr(flow, "run_console") else flow.run_local_server(port=0)
        with open(YT_TOKEN, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload_youtube(video_path: str, title: str, description: str, tags: list[str],
                   cfg: dict) -> str | None:
    from googleapiclient.http import MediaFileUpload

    up = cfg.get("upload", {})
    client_secret = up.get("youtube_client_secret", "client_secret.json")
    privacy = up.get("youtube_privacy", "public")

    service = _yt_service(client_secret)
    # Shorts are signalled by vertical video + #Shorts in title/description.
    yt_title = title if "#shorts" in title.lower() else f"{title} #Shorts"
    body = {
        "snippet": {
            "title": yt_title[:100],
            "description": (description + "\n\n#Shorts").strip()[:5000],
            "tags": (tags + ["shorts"])[:30],
            "categoryId": up.get("youtube_category", "24"),  # 24 = Entertainment
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    req = service.videos().insert(part="snippet,status", body=body, media_body=media)

    print(f"[upload] YouTube: uploading '{yt_title}'...")
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"[upload]   {int(status.progress()*100)}%")
    vid = resp["id"]
    url = f"https://youtu.be/{vid}"
    print(f"[upload] ✅ YouTube: {url}")
    return url


# ---------------------------------------------------------------------------
# TikTok (Content Posting API — FILE_UPLOAD flow)
# ---------------------------------------------------------------------------
TT_INIT = "https://open.tiktokapis.com/v2/post/publish/video/init/"
TT_STATUS = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"


def upload_tiktok(video_path: str, title: str, cfg: dict) -> str | None:
    import requests

    up = cfg.get("upload", {})
    token = up.get("tiktok_token", "") or os.getenv("TIKTOK_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("No TikTok token. Set upload.tiktok_token in config.json "
                           "(see UPLOAD_SETUP.md, TikTok section).")
    privacy = up.get("tiktok_privacy", "SELF_ONLY")  # SELF_ONLY until app approved
    size = os.path.getsize(video_path)
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json; charset=UTF-8"}

    init_body = {
        "post_info": {
            "title": title[:2200],
            "privacy_level": privacy,
            "disable_comment": False, "disable_duet": False, "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD", "video_size": size,
            "chunk_size": size, "total_chunk_count": 1,
        },
    }
    print(f"[upload] TikTok: initializing ({size/1e6:.1f} MB)...")
    r = requests.post(TT_INIT, headers=headers, json=init_body, timeout=30)
    r.raise_for_status()
    data = r.json().get("data", {})
    publish_id, upload_url = data.get("publish_id"), data.get("upload_url")
    if not upload_url:
        raise RuntimeError(f"TikTok init failed: {r.text}")

    print("[upload] TikTok: uploading bytes...")
    with open(video_path, "rb") as f:
        put = requests.put(upload_url, timeout=300, data=f, headers={
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{size-1}/{size}",
        })
        put.raise_for_status()

    print("[upload] TikTok: processing...")
    for _ in range(40):
        s = requests.post(TT_STATUS, headers=headers,
                          json={"publish_id": publish_id}, timeout=30)
        status = s.json().get("data", {}).get("status")
        if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            print(f"[upload] ✅ TikTok: done (status={status}).")
            return publish_id
        if status == "FAILED":
            raise RuntimeError(f"TikTok publish failed: {s.text}")
        time.sleep(5)
    print(f"[upload] TikTok: still processing (publish_id={publish_id}).")
    return publish_id


# ---------------------------------------------------------------------------
# Dispatcher used by the pipeline
# ---------------------------------------------------------------------------
def publish(video_path: str, script, cfg: dict) -> None:
    up = cfg.get("upload", {})
    title = getattr(script, "title", "Story")
    description = getattr(script, "description", "")
    tags = list(getattr(script, "tags", []))

    if up.get("youtube"):
        try:
            upload_youtube(video_path, title, description, tags, cfg)
        except Exception as e:  # noqa: BLE001
            print(f"[upload] ❌ YouTube failed: {e}")

    if up.get("tiktok"):
        caption = (description or title) + " " + " ".join("#" + t for t in tags[:5])
        try:
            upload_tiktok(video_path, caption.strip(), cfg)
        except Exception as e:  # noqa: BLE001
            print(f"[upload] ❌ TikTok failed: {e}")
