from __future__ import annotations

import argparse
import json
from datetime import date, timedelta

from googleapiclient.discovery import build

from common import DATA_DIR, load_environment, load_json, save_json, slugify
from upload_youtube import load_credentials


def fetch_video_analytics(video_id: str) -> dict:
    creds = load_credentials()
    analytics = build("youtubeAnalytics", "v2", credentials=creds)
    end_date = date.today()
    start_date = end_date - timedelta(days=1)
    response = analytics.reports().query(
        ids="channel==MINE",
        startDate=start_date.isoformat(),
        endDate=end_date.isoformat(),
        metrics="views,likes,comments,estimatedMinutesWatched,impressions,impressionsClickThroughRate",
        filters=f"video=={video_id}",
    ).execute()
    return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch 24-hour YouTube analytics for a video.")
    parser.add_argument("--topic", help="Topic title or slug")
    parser.add_argument("--latest", action="store_true", help="Use data/latest_upload.json")
    args = parser.parse_args()

    load_environment()
    if args.latest:
        upload_entry = load_json(DATA_DIR / "latest_upload.json", default={})
    elif args.topic:
        slug = slugify(args.topic)
        uploads = load_json(DATA_DIR / "upload_log.json", default=[])
        upload_entry = next((entry for entry in reversed(uploads) if entry["slug"] == slug), {})
    else:
        raise RuntimeError("Use --latest or --topic.")

    if not upload_entry:
        raise RuntimeError("No matching uploaded video entry found.")

    report = {
        "video_id": upload_entry["video_id"],
        "topic": upload_entry["topic"],
        "slug": upload_entry["slug"],
        "fetched_at": date.today().isoformat(),
        "report": fetch_video_analytics(upload_entry["video_id"]),
    }
    output_path = DATA_DIR / "analytics" / f"{upload_entry['slug']}.json"
    save_json(output_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

