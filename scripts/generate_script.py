from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from common import DATA_DIR, extract_keywords, is_demo_mode, llm_chat_json, load_environment, load_json, pick_topic_argument, save_json, slugify, youtube_api_get


def collect_youtube_tag_hints(topic: str, *, demo_mode: bool = False) -> list[str]:
    if demo_mode:
        return [item["keyword"] for item in extract_keywords([topic, f"{topic} devops ai automation"], limit=8)]
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


def generate_script_demo(topic: dict, hints: list[str]) -> dict:
    title = topic["title"]
    return {
        "hook": f"Если вы хотите разобраться в теме '{title}' без воды, это видео даст вам четкий план действий уже сегодня.",
        "outline": [
            {
                "heading": "Почему эта тема важна прямо сейчас",
                "talking_points": [
                    "что меняется на рынке",
                    "какие навыки и инструменты стали обязательными",
                ],
            },
            {
                "heading": "Пошаговый план внедрения",
                "talking_points": [
                    "с чего начать за первый день",
                    "что сделать за первую неделю",
                    "как получить измеримый результат",
                ],
            },
            {
                "heading": "Типичные ошибки и как их избежать",
                "talking_points": [
                    "не пытаться автоматизировать все сразу",
                    "собирать процесс маленькими повторяемыми шагами",
                ],
            },
        ],
        "cta": "Подпишитесь на канал, чтобы получать новые практические разборы по IT и автоматизации, и заберите чеклист из описания.",
        "title": title,
        "description": (
            f"В этом видео разбираем тему: {title}.\n\n"
            "Вы получите пошаговый план, типичные ошибки и практические советы для быстрого результата.\n\n"
            "#IT #DevOps #Automation"
        ),
        "thumbnail_text": "ПРОСТОЙ ПЛАН",
        "tags": list(dict.fromkeys([*topic.get("keywords", []), *hints, "it", "automation"]))[:15],
        "title_options": [title, f"{title} — с чего начать без ошибок"],
        "thumbnail_text_options": ["ПРОСТОЙ ПЛАН", "С НУЛЯ ДО РЕЗУЛЬТАТА"],
    }


def generate_script(topic: dict, *, demo_mode: bool = False) -> dict:
    hints = collect_youtube_tag_hints(topic["title"], demo_mode=demo_mode)
    if demo_mode:
        return generate_script_demo(topic, hints)
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
    parser.add_argument("--demo", action="store_true", help="Use a deterministic demo script instead of live APIs.")
    args = parser.parse_args()

    load_environment()
    topics_path = DATA_DIR / "topics.json"
    topic = pick_topic_argument(args.topic, topics_path)
    demo_mode = is_demo_mode(args.demo)
    script = generate_script(topic, demo_mode=demo_mode)
    slug = slugify(topic["title"])
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topic": topic["title"],
        "topic_meta": topic,
        "slug": slug,
        "demo_mode": demo_mode,
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
