"""
Upload a finished MP4 to YouTube via the YouTube Data API v3.

Auth model (important): YOU authorize the app once via Google OAuth in your
own browser. The resulting token is stored locally in token.json and reused.
No password is ever shared — the app only gets the scopes you approve, and
you can revoke access anytime at https://myaccount.google.com/permissions.

Setup (see README "YouTube setup"):
  1. Create a Google Cloud project, enable "YouTube Data API v3".
  2. Configure an OAuth consent screen (External, add yourself as a test user).
  3. Create an OAuth client ID of type "Desktop app", download the JSON.
  4. Point YOUTUBE_CLIENT_SECRET (in .env) at that JSON file.
"""

from __future__ import annotations

import os

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = "token.json"


def _get_service(client_secret: str):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(client_secret):
                raise FileNotFoundError(
                    f"OAuth client secret not found at '{client_secret}'. "
                    "See README 'YouTube setup'."
                )
            flow = InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)
            # Opens a browser locally; falls back to console code if headless.
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    privacy: str = "private",
    category_id: str = "27",
    client_secret: str | None = None,
) -> str | None:
    from googleapiclient.http import MediaFileUpload

    client_secret = client_secret or os.getenv("YOUTUBE_CLIENT_SECRET", "client_secret.json")
    service = _get_service(client_secret)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:30],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    print(f"[youtube] Uploading '{title}'...")
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[youtube]   {int(status.progress() * 100)}%")
    vid = response["id"]
    print(f"[youtube] Done: https://youtu.be/{vid}")
    return vid
