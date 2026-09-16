from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

from common import DATA_DIR, extract_keywords, llm_chat_json, load_environment, save_json, youtube_api_get


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate YouTube topic ideas from trend data.")
    parser.add_argument("--niche")
    parser.add_argument("--max-results", type=int, default=15)
    args = parser.parse_args()

    load_environment()
    niche = args.niche or os.getenv("CHANNEL_NICHE", "образовательный контент про IT")
    language = os.getenv("CHANNEL_LANGUAGE", "ru")
    frequency = os.getenv("PUBLICATION_FREQUENCY", "3 видео в неделю")
    videos = fetch_trending_videos(niche, args.max_results)
    keyword_source = [f"{video['title']} {video['description']}" for video in videos]
    keywords = extract_keywords(keyword_source, limit=15)
    ideas = generate_topic_ideas(niche, language, frequency, videos, keywords)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "channel_niche": niche,
        "language": language,
        "publication_frequency": frequency,
        "source_videos": videos,
        "keyword_analysis": keywords,
        "ideas": ideas,
    }
    save_json(DATA_DIR / "topics.json", payload)
    print(f"Saved {len(ideas)} ideas to {DATA_DIR / 'topics.json'}")


if __name__ == "__main__":
    main()
