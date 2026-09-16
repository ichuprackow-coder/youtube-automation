from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from common import DATA_DIR, extract_keywords, llm_chat_json, load_environment, load_json, pick_topic_argument, save_json, slugify, youtube_api_get


def collect_youtube_tag_hints(topic: str) -> list[str]:
    response = youtube_api_get(
        "search",
        {
            "part": "snippet",
            "q": topic,
            "type": "video",
            "maxResults": 10,
            "regionCode": os.getenv("YOUTUBE_REGION_CODE", "US"),
        },
    )
    texts = []
    for item in response.get("items", []):
        snippet = item.get("snippet", {})
        texts.append(f"{snippet.get('title', '')} {snippet.get('description', '')}")
    return [item["keyword"] for item in extract_keywords(texts, limit=10)]


def generate_script(topic: dict) -> dict:
    hints = collect_youtube_tag_hints(topic["title"])
    prompt = f"""
    Тема: {topic['title']}
    Угол: {topic.get('angle', '')}
    Why now: {topic.get('why_now', '')}
    Ключевые слова: {topic.get('keywords', [])}
    YouTube tag hints: {hints}

    Верни JSON с полями:
    - hook
    - outline (массив из 3-5 объектов с полями heading и talking_points)
    - cta
    - title
    - description
    - thumbnail_text
    - tags (массив до 15 штук)
    - title_options (массив из 2 альтернатив для A/B теста)
    - thumbnail_text_options (массив из 2 альтернатив для A/B теста)
    """
    result = llm_chat_json(
        "Ты сценарист и SEO-редактор YouTube для русскоязычного IT-канала. Верни только JSON.",
        prompt,
        temperature=0.75,
    )
    result["tags"] = list(dict.fromkeys([*result.get("tags", []), *hints]))[:15]
    return result


def render_tts_text(script_payload: dict) -> str:
    outline_lines = []
    for point in script_payload["outline"]:
        bullets = " ".join(point.get("talking_points", []))
        outline_lines.append(f"{point['heading']}. {bullets}")
    return "\n".join([script_payload["hook"], *outline_lines, script_payload["cta"]])


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a video script from topics.json")
    parser.add_argument("--topic", help="Exact topic title from data/topics.json")
    args = parser.parse_args()

    load_environment()
    topics_path = DATA_DIR / "topics.json"
    topic = pick_topic_argument(args.topic, topics_path)
    script = generate_script(topic)
    slug = slugify(topic["title"])
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topic": topic["title"],
        "topic_meta": topic,
        "slug": slug,
        **script,
    }
    payload["tts_text"] = render_tts_text(payload)
    script_path = DATA_DIR / "scripts" / f"{slug}.json"
    save_json(script_path, payload)

    topics_payload = load_json(topics_path, default={})
    for idea in topics_payload.get("ideas", []):
        if idea["title"].lower() == topic["title"].lower():
            idea["script_path"] = str(Path("data/scripts") / f"{slug}.json")
    save_json(topics_path, topics_payload)
    print(f"Saved script to {script_path}")


if __name__ == "__main__":
    main()
