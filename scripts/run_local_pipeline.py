from __future__ import annotations

import argparse
import subprocess
import sys

from common import DATA_DIR, REPO_ROOT, load_environment, pick_topic_argument, slugify


def run_command(command: list[str]) -> None:
    subprocess.run(command, check=True, cwd=REPO_ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local YouTube pipeline end-to-end.")
    parser.add_argument("--niche", default="образовательный контент про IT")
    parser.add_argument("--topic", help="Exact topic title or slug")
    parser.add_argument("--demo", action="store_true", help="Run with built-in demo data for previewing the pipeline.")
    parser.add_argument("--upload-dry-run", action="store_true", help="Also generate upload_dry_run.json after video assets are built.")
    args = parser.parse_args()

    load_environment()
    python = sys.executable
    demo_flag = ["--demo"] if args.demo else []

    run_command([python, "scripts/topic_research.py", "--niche", args.niche, *demo_flag])

    selected_topic = args.topic
    if not selected_topic:
        selected_topic = pick_topic_argument(None, DATA_DIR / "topics.json")["title"]

    run_command([python, "scripts/generate_script.py", "--topic", selected_topic, *demo_flag])
    run_command([python, "scripts/generate_tts.py", "--topic", selected_topic, *demo_flag])
    run_command([python, "scripts/build_video.py", "--topic", selected_topic])
    run_command([python, "scripts/generate_thumbnail.py", "--topic", selected_topic, *demo_flag])
    if args.upload_dry_run:
        run_command([python, "scripts/upload_youtube.py", "--topic", selected_topic, "--dry-run"])

    slug = slugify(selected_topic)
    print(f"Topic: {selected_topic}")
    print(f"Topics JSON: {DATA_DIR / 'topics.json'}")
    print(f"Script JSON: {DATA_DIR / 'scripts' / f'{slug}.json'}")
    print(f"Audio MP3: {DATA_DIR / 'audio' / f'{slug}.mp3'}")
    print(f"Video MP4: {DATA_DIR / 'videos' / f'{slug}.mp4'}")
    print(f"Thumbnail PNG: {DATA_DIR / 'thumbnails' / f'{slug}.png'}")
    if args.upload_dry_run:
        print(f"Upload dry run: {DATA_DIR / 'upload_dry_run.json'}")


if __name__ == "__main__":
    main()
