"""
Upload a finished MP4 to TikTok via the official Content Posting API.

Auth model: you create a TikTok for Developers app, get it approved for the
Content Posting API, and obtain an OAuth access token for your account with
the `video.upload` (and/or `video.publish`) scope. Put it in TIKTOK_ACCESS_TOKEN.
No password is shared; revoke anytime in TikTok app settings.

IMPORTANT — read the README "TikTok setup":
  * Until your app passes TikTok's audit, posts are restricted to private
    ("SELF_ONLY") and only to the developer/test accounts you registered.
  * There is no unofficial/scraping path here — automating via the official
    API is the only approach that complies with TikTok's Terms of Service.

This uses the FILE_UPLOAD flow:
  1. POST /v2/post/publish/video/init/   -> get publish_id + upload_url
  2. PUT the bytes to upload_url
  3. Poll  /v2/post/publish/status/fetch/ until the post is processed.
"""

from __future__ import annotations

import os
import time

import requests

INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"


def upload(
    video_path: str,
    caption: str,
    privacy: str = "SELF_ONLY",
    access_token: str | None = None,
    poll_seconds: int = 5,
    max_polls: int = 60,
) -> str | None:
    access_token = access_token or os.getenv("TIKTOK_ACCESS_TOKEN", "")
    if not access_token:
        raise RuntimeError(
            "TIKTOK_ACCESS_TOKEN is not set. See README 'TikTok setup'."
        )

    size = os.path.getsize(video_path)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    # 1. init — single-chunk upload
    init_body = {
        "post_info": {
            "title": caption[:2200],
            "privacy_level": privacy,
            "disable_comment": False,
            "disable_duet": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": size,
            "total_chunk_count": 1,
        },
    }
    print(f"[tiktok] Initializing upload ({size/1e6:.1f} MB)...")
    r = requests.post(INIT_URL, headers=headers, json=init_body, timeout=30)
    r.raise_for_status()
    data = r.json().get("data", {})
    publish_id = data.get("publish_id")
    upload_url = data.get("upload_url")
    if not upload_url or not publish_id:
        raise RuntimeError(f"TikTok init failed: {r.text}")

    # 2. upload the bytes
    print("[tiktok] Uploading video bytes...")
    with open(video_path, "rb") as f:
        put_headers = {
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{size - 1}/{size}",
        }
        pr = requests.put(upload_url, headers=put_headers, data=f, timeout=300)
        pr.raise_for_status()

    # 3. poll status
    print("[tiktok] Processing...")
    for _ in range(max_polls):
        sr = requests.post(
            STATUS_URL, headers=headers, json={"publish_id": publish_id}, timeout=30
        )
        sr.raise_for_status()
        status = sr.json().get("data", {}).get("status")
        if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            print(f"[tiktok] Done (status={status}). publish_id={publish_id}")
            return publish_id
        if status == "FAILED":
            raise RuntimeError(f"TikTok publish failed: {sr.text}")
        time.sleep(poll_seconds)

    print(f"[tiktok] Still processing after timeout. publish_id={publish_id}")
    return publish_id
