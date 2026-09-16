from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from common import DATA_DIR, load_environment, save_json, slugify


def shorten_text(value: str, *, words: int = 5) -> str:
    tokens = value.strip().split()
    if not tokens:
        return "Сцена"
    shortened = " ".join(tokens[:words]).rstrip(".,;:!?")
    return shortened + ("..." if len(tokens) > words else "")


def normalize_string_list(value: object, *, limit: int) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        raise RuntimeError("Expected a list of strings.")
    return [str(item).strip() for item in items if str(item).strip()][:limit]


def normalize_scenes(raw_scenes: object) -> list[dict]:
    if not isinstance(raw_scenes, list):
        raise RuntimeError("Scenario field 'scenes' must be an array.")
    scenes = []
    for index, scene in enumerate(raw_scenes, start=1):
        if not isinstance(scene, dict):
            raise RuntimeError(f"Scene {index} must be an object.")
        narration = str(scene.get("narration", "")).strip()
        image_prompt = str(scene.get("image_prompt", "")).strip()
        if not narration:
            raise RuntimeError(f"Scene {index} is missing narration.")
        if not image_prompt:
            raise RuntimeError(f"Scene {index} is missing image_prompt.")
        scenes.append(
            {
                "index": index,
                "title": str(scene.get("title") or shorten_text(narration, words=6)),
                "narration": narration,
                "image_prompt": image_prompt,
            }
        )
    if not scenes:
        raise RuntimeError("Scenario must contain at least one scene.")
    return scenes


def build_payload(scenario: dict) -> dict:
    title = str(scenario.get("title", "")).strip()
    description = str(scenario.get("description", "")).strip()
    if not title:
        raise RuntimeError("Scenario is missing title.")
    if not description:
        raise RuntimeError("Scenario is missing description.")

    scenes = normalize_scenes(scenario.get("scenes") or [])
    slug = slugify(title)
    middle_scenes = scenes[1:-1]
    thumbnail_text = str(scenario.get("thumbnail_text") or shorten_text(title, words=4)).upper()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topic": title,
        "slug": slug,
        "demo_mode": False,
        "source": "scenario_file",
        "hook": scenes[0]["narration"],
        "outline": [{"heading": scene["title"], "talking_points": []} for scene in middle_scenes],
        "cta": scenes[-1]["narration"],
        "title": title,
        "description": description,
        "thumbnail_text": thumbnail_text,
        "tags": normalize_string_list(scenario.get("tags"), limit=15),
        "title_options": normalize_string_list(scenario.get("title_options"), limit=2),
        "thumbnail_text_options": [option.upper() for option in normalize_string_list(scenario.get("thumbnail_text_options"), limit=2)],
        "scenes": scenes,
        "tts_text": "\n".join(scene["narration"] for scene in scenes),
        "scenario_source_path": "",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize an externally generated scenario JSON into pipeline format.")
    parser.add_argument("--scenario-file", required=True, help="Path to a JSON file with title, description, tags and scenes.")
    args = parser.parse_args()

    load_environment()
    scenario_path = Path(args.scenario_file).expanduser().resolve()
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    payload = build_payload(scenario)
    payload["scenario_source_path"] = str(scenario_path)

    output_path = DATA_DIR / "scripts" / f"{payload['slug']}.json"
    save_json(output_path, payload)
    print(f"Saved scenario script to {output_path}")


if __name__ == "__main__":
    main()
