from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from common import DATA_DIR, REPO_ROOT, load_environment, slugify


def run_command(command: list[str]) -> None:
    subprocess.run(command, check=True, cwd=REPO_ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the free scenario pipeline from a saved JSON scenario.")
    parser.add_argument("--scenario-file", required=True, help="Path to a scenario JSON file.")
    parser.add_argument("--demo", action="store_true", help="Use placeholder scene images instead of remote generation.")
    parser.add_argument("--upload-dry-run", action="store_true", help="Also generate upload_dry_run.json after video assets are built.")
    args = parser.parse_args()

    load_environment()
    scenario_path = Path(args.scenario_file).expanduser().resolve()
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    topic = str(scenario.get("title", "")).strip()
    if not topic:
        raise RuntimeError("Scenario is missing title.")

    python = sys.executable
    demo_flag = ["--demo"] if args.demo else []
    run_command([python, "scripts/prepare_scenario.py", "--scenario-file", str(scenario_path)])
    run_command([python, "scripts/generate_tts.py", "--topic", topic, *demo_flag])
    run_command([python, "scripts/generate_scene_images.py", "--topic", topic, *demo_flag])
    run_command([python, "scripts/build_video.py", "--topic", topic])
    run_command([python, "scripts/generate_thumbnail.py", "--topic", topic, *demo_flag])
    if args.upload_dry_run:
        run_command([python, "scripts/upload_youtube.py", "--topic", topic, "--dry-run"])

    slug = slugify(topic)
    print(f"Topic: {topic}")
    print(f"Script JSON: {DATA_DIR / 'scripts' / f'{slug}.json'}")
    print(f"Audio MP3: {DATA_DIR / 'audio' / f'{slug}.mp3'}")
    print(f"Scene images: {DATA_DIR / 'images' / slug}")
    print(f"Video MP4: {DATA_DIR / 'videos' / f'{slug}.mp4'}")
    print(f"Thumbnail PNG: {DATA_DIR / 'thumbnails' / f'{slug}.png'}")
    if args.upload_dry_run:
        print(f"Upload dry run: {DATA_DIR / 'upload_dry_run.json'}")


if __name__ == "__main__":
    main()
