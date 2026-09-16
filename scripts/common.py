from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
ASSETS_DIR = REPO_ROOT / "assets"
CONFIG_DIR = REPO_ROOT / "config"

RUSSIAN_STOPWORDS = {
    "и",
    "в",
    "на",
    "с",
    "по",
    "как",
    "что",
    "это",
    "для",
    "под",
    "или",
    "из",
    "к",
    "за",
    "про",
    "не",
    "но",
    "а",
    "от",
    "до",
    "без",
    "the",
    "and",
    "with",
    "for",
    "from",
}


def load_environment() -> None:
    load_dotenv(REPO_ROOT / ".env")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", "-", value.strip().lower(), flags=re.UNICODE)
    return cleaned.strip("-") or "untitled-topic"


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return [] if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required.")
    return value


def extract_json(raw_text: str) -> Any:
    content = raw_text.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()
    return json.loads(content)


def llm_chat(system_prompt: str, user_prompt: str, *, json_mode: bool = False, temperature: float = 0.7) -> str:
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "openai":
        api_key = require_env("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        payload: dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    if provider == "gemini":
        api_key = require_env("GEMINI_API_KEY")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        generation_config: dict[str, Any] = {"temperature": temperature}
        if json_mode:
            generation_config["responseMimeType"] = "application/json"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": generation_config,
        }
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": api_key},
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]

    raise RuntimeError(f"Unsupported LLM_PROVIDER={provider}")


def llm_chat_json(system_prompt: str, user_prompt: str, *, temperature: float = 0.7) -> Any:
    return extract_json(llm_chat(system_prompt, user_prompt, json_mode=True, temperature=temperature))


def extract_keywords(texts: list[str], *, limit: int = 12) -> list[dict[str, Any]]:
    words: list[str] = []
    for text in texts:
        words.extend(re.findall(r"[A-Za-zА-Яа-яЁё0-9]{3,}", text.lower()))
    filtered = [word for word in words if word not in RUSSIAN_STOPWORDS]
    counts = Counter(filtered)
    return [{"keyword": word, "mentions": count} for word, count in counts.most_common(limit)]


def youtube_api_get(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    api_key = require_env("YOUTUBE_API_KEY")
    response = requests.get(
        f"https://www.googleapis.com/youtube/v3/{endpoint}",
        params={**params, "key": api_key},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def pick_topic_argument(raw_topic: str | None, topics_path: Path) -> dict[str, Any]:
    topics_payload = load_json(topics_path, default={})
    ideas = topics_payload.get("ideas", [])
    if raw_topic:
        raw_slug = slugify(raw_topic)
        for idea in ideas:
            if idea["title"].lower() == raw_topic.lower() or slugify(idea["title"]) == raw_slug:
                return idea
        return {"title": raw_topic, "angle": "", "keywords": [], "competition": "unknown"}
    for idea in ideas:
        if not idea.get("script_path"):
            return idea
    if ideas:
        return ideas[0]
    raise RuntimeError("No topics found. Run scripts/topic_research.py first.")
