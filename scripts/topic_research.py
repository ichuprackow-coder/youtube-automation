from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

from common import DATA_DIR, extract_keywords, is_demo_mode, llm_chat_json, load_environment, save_json, youtube_api_get


def fetch_trending_videos(niche: str, max_results: int) -> list[dict]:
    published_after = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat().replace("+00:00", "Z")
    search_response = youtube_api_get(
        "search",
        {
            "part": "snippet",
            "q": niche,
            "type": "video",
            "order": "viewCount",
            "maxResults": max_results,
            "regionCode": os.getenv("YOUTUBE_REGION_CODE", "US"),
            "publishedAfter": published_after,
        },
    )
    items = search_response.get("items", [])
    video_ids = ",".join(item["id"]["videoId"] for item in items)
    if not video_ids:
        return []
    details = youtube_api_get(
        "videos",
        {
            "part": "snippet,statistics,contentDetails",
            "id": video_ids,
            "maxResults": max_results,
        },
    )
    indexed_stats = {item["id"]: item for item in details.get("items", [])}
    videos = []
    for item in items:
        video_id = item["id"]["videoId"]
        stats = indexed_stats.get(video_id, {})
        snippet = stats.get("snippet", item.get("snippet", {}))
        statistics = stats.get("statistics", {})
        videos.append(
            {
                "video_id": video_id,
                "title": snippet.get("title"),
                "description": snippet.get("description", ""),
                "channel_title": snippet.get("channelTitle"),
                "published_at": snippet.get("publishedAt"),
                "tags": snippet.get("tags", []),
                "views": int(statistics.get("viewCount", 0)),
                "likes": int(statistics.get("likeCount", 0)),
                "comments": int(statistics.get("commentCount", 0)),
            }
        )
    return videos


def generate_topic_ideas(niche: str, language: str, frequency: str, videos: list[dict], keywords: list[dict]) -> list[dict]:
    trend_summary = [
        {
            "title": video["title"],
            "views": video["views"],
            "channel": video["channel_title"],
        }
        for video in videos[:10]
    ]
    keyword_summary = ", ".join(item["keyword"] for item in keywords[:10])
    prompt = f"""
    Канал: {niche}
    Язык: {language}
    Частота публикаций: {frequency}
    Популярные ролики: {trend_summary}
    Частотные ключевые слова: {keyword_summary}

    Верни JSON-объект с ключом ideas. Внутри — 5 идей для видео.
    Для каждой идеи верни поля:
    - title
    - angle
    - why_now
    - keywords (массив)
    - competition (low|medium|high)
    - target_viewer
    """
    result = llm_chat_json(
        "Ты YouTube-стратег для русскоязычного IT-канала. Отвечай строго валидным JSON.",
        prompt,
        temperature=0.8,
    )
    return result["ideas"]


def build_demo_videos(niche: str) -> list[dict]:
    return [
        {
            "video_id": "demo-devops-roadmap",
            "title": f"{niche}: roadmap для новичка",
            "description": "Разбор входа в IT, DevOps, AI-инструментов и карьерного плана.",
            "channel_title": "Demo IT Channel",
            "published_at": "2026-09-01T09:00:00Z",
            "tags": ["devops", "roadmap", "it career"],
            "views": 154000,
            "likes": 8200,
            "comments": 640,
        },
        {
            "video_id": "demo-ai-automation",
            "title": "Как автоматизировать YouTube-канал с AI",
            "description": "LLM, TTS, FFmpeg и GitHub Actions в одном пайплайне.",
            "channel_title": "Demo Automation Lab",
            "published_at": "2026-09-03T12:30:00Z",
            "tags": ["youtube automation", "ai tools", "github actions"],
            "views": 98000,
            "likes": 5100,
            "comments": 410,
        },
        {
            "video_id": "demo-it-skills",
            "title": "Какие навыки в IT реально нужны в 2026",
            "description": "Практический список навыков, стеков и первых проектов.",
            "channel_title": "Demo Skills Hub",
            "published_at": "2026-09-05T15:45:00Z",
            "tags": ["it skills", "career", "2026"],
            "views": 87000,
            "likes": 4700,
            "comments": 380,
        },
    ]


def generate_topic_ideas_demo(niche: str, language: str, frequency: str, keywords: list[dict]) -> list[dict]:
    seed_keywords = [item["keyword"] for item in keywords[:5]]
    return [
        {
            "title": "Как войти в DevOps в 2026: пошаговый план",
            "angle": "Дать новичку реалистичный входной маршрут на 90 дней.",
            "why_now": f"Спрос на AI-автоматизацию и DevOps растет, а формат {frequency} требует практичных тем.",
            "keywords": seed_keywords or ["devops", "roadmap", "junior"],
            "competition": "medium",
            "target_viewer": "Новичок, который хочет перейти в IT.",
        },
        {
            "title": "5 AI-инструментов, которые экономят часы IT-специалисту",
            "angle": "Показать реальные сценарии экономии времени в работе.",
            "why_now": "AI-сервисы быстро меняют повседневные процессы команд.",
            "keywords": ["ai", "automation", "productivity", *seed_keywords[:2]],
            "competition": "medium",
            "target_viewer": "Junior/Middle IT-специалист.",
        },
        {
            "title": "GitHub Actions для новичков: автоматизируем рутину без боли",
            "angle": "Разобрать GitHub Actions на одном полезном кейсе.",
            "why_now": "Автоматизация CI/CD стала базовым навыком даже для небольших проектов.",
            "keywords": ["github actions", "ci cd", "automation"],
            "competition": "low",
            "target_viewer": "Разработчик, начинающий DevOps-практику.",
        },
        {
            "title": "Сколько реально нужно учиться, чтобы получить первую работу в IT",
            "angle": "Честный разбор сроков, ловушек и ожиданий.",
            "why_now": "Аудитория ищет приземленные карьерные ориентиры без инфоцыганства.",
            "keywords": ["it career", "roadmap", "first job"],
            "competition": "high",
            "target_viewer": "Студент или сменщик профессии.",
        },
        {
            "title": "Как собрать AI-пайплайн для контента своими руками",
            "angle": "Показать связку LLM + TTS + FFmpeg + GitHub Actions.",
            "why_now": "Создатели контента массово ищут способы ускорить продакшн.",
            "keywords": ["youtube automation", "ffmpeg", "llm", "tts"],
            "competition": "medium",
            "target_viewer": "Технарь, который хочет автоматизировать контент.",
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate YouTube topic ideas from trend data.")
    parser.add_argument("--niche")
    parser.add_argument("--max-results", type=int, default=15)
    parser.add_argument("--demo", action="store_true", help="Use built-in demo data instead of live APIs.")
    args = parser.parse_args()

    load_environment()
    niche = args.niche or os.getenv("CHANNEL_NICHE", "образовательный контент про IT")
    language = os.getenv("CHANNEL_LANGUAGE", "ru")
    frequency = os.getenv("PUBLICATION_FREQUENCY", "3 видео в неделю")
    demo_mode = is_demo_mode(args.demo)
    videos = build_demo_videos(niche) if demo_mode else fetch_trending_videos(niche, args.max_results)
    keyword_source = [f"{video['title']} {video['description']}" for video in videos]
    keywords = extract_keywords(keyword_source, limit=15)
    ideas = generate_topic_ideas_demo(niche, language, frequency, keywords) if demo_mode else generate_topic_ideas(niche, language, frequency, videos, keywords)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "channel_niche": niche,
        "language": language,
        "publication_frequency": frequency,
        "demo_mode": demo_mode,
        "source_videos": videos,
        "keyword_analysis": keywords,
        "ideas": ideas,
    }
    save_json(DATA_DIR / "topics.json", payload)
    print(f"Saved {len(ideas)} ideas to {DATA_DIR / 'topics.json'}")


if __name__ == "__main__":
    main()
