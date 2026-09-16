from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow

from common import CONFIG_DIR, DATA_DIR, ensure_dir, load_environment, load_json, save_json, slugify

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def load_credentials() -> Credentials:
    token_path = Path(os.getenv("YOUTUBE_TOKEN_PATH", str(CONFIG_DIR / "token.json")))
    client_secret_path = Path(os.getenv("YOUTUBE_CLIENT_SECRET_PATH", str(CONFIG_DIR / "client_secret.json")))
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        ensure_dir(token_path.parent)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds
    if creds and creds.valid:
        return creds
    if os.getenv("CI"):
        raise RuntimeError("Missing or invalid OAuth token in CI. Save config/token.json into YOUTUBE_TOKEN_JSON.")
    if not client_secret_path.exists():
        raise RuntimeError(
            f"OAuth client secret file not found: {client_secret_path}. "
            "Download it from Google Cloud Console and save it to config/client_secret.json."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
    creds = flow.run_local_server(port=0)
    ensure_dir(token_path.parent)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def upload_video(script_payload: dict, slug: str) -> dict:
    creds = load_credentials()
    youtube = build("youtube", "v3", credentials=creds)
    video_path = DATA_DIR / "videos" / f"{slug}.mp4"
    thumbnail_path = DATA_DIR / "thumbnails" / f"{slug}.png"
    if not video_path.exists():
        raise RuntimeError(f"Video file not found: {video_path}")

    request_body = {
        "snippet": {
            "title": script_payload["title"],
            "description": script_payload["description"],
            "tags": script_payload.get("tags", []),
            "categoryId": os.getenv("YOUTUBE_CATEGORY_ID", "27"),
        },
        "status": {
            "privacyStatus": os.getenv("YOUTUBE_PRIVACY_STATUS", "unlisted"),
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response["id"]
    if thumbnail_path.exists():
        youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))).execute()

    playlist_id = os.getenv("YOUTUBE_PLAYLIST_ID")
    if playlist_id:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        ).execute()

    log_path = DATA_DIR / "upload_log.json"
    entries = load_json(log_path, default=[])
    entry = {
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "topic": script_payload["topic"],
        "slug": slug,
        "video_id": video_id,
        "privacy_status": request_body["status"]["privacyStatus"],
        "title": script_payload["title"],
    }
    entries.append(entry)
    save_json(log_path, entries)
    save_json(DATA_DIR / "latest_upload.json", entry)
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a generated YouTube video.")
    parser.add_argument("--topic", required=True, help="Topic title or slug")
    args = parser.parse_args()

    load_environment()
    slug = slugify(args.topic)
    script_payload = load_json(DATA_DIR / "scripts" / f"{slug}.json")
    if not script_payload:
        raise RuntimeError("Script JSON not found.")
    result = upload_video(script_payload, slug)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
