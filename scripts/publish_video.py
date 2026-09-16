from __future__ import annotations

import argparse
import json

from googleapiclient.discovery import build

from common import DATA_DIR, load_environment, load_json
from upload_youtube import load_credentials


def main() -> None:
    parser = argparse.ArgumentParser(description="Update privacy status for an uploaded video.")
    parser.add_argument("--video-id")
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--privacy-status", default="public", choices=["public", "unlisted", "private"])
    args = parser.parse_args()

    load_environment()
    if args.latest:
        latest = load_json(DATA_DIR / "latest_upload.json", default={})
        video_id = latest.get("video_id")
    else:
        video_id = args.video_id
    if not video_id:
        raise RuntimeError("Pass --video-id or --latest.")

    youtube = build("youtube", "v3", credentials=load_credentials())
    current = youtube.videos().list(part="status", id=video_id).execute()
    items = current.get("items", [])
    if not items:
        raise RuntimeError(f"Video not found: {video_id}")
    status = items[0].get("status", {})
    status["privacyStatus"] = args.privacy_status
    status["selfDeclaredMadeForKids"] = False

    response = youtube.videos().update(
        part="status",
        body={
            "id": video_id,
            "status": status,
        },
    ).execute()
    print(json.dumps(response, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
