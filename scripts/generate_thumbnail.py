from __future__ import annotations

import argparse
import base64
import io
import os
import textwrap

import requests
from PIL import Image, ImageDraw, ImageFont

from common import DATA_DIR, ensure_dir, is_demo_mode, llm_chat, load_environment, load_json, require_env, save_json, slugify


def generate_prompt(script_payload: dict, *, demo_mode: bool = False) -> str:
    if demo_mode or os.getenv("OPENAI_API_KEY", "").strip() == "<SECRET>" or os.getenv("GEMINI_API_KEY", "").strip() == "<SECRET>" or (
        not os.getenv("OPENAI_API_KEY") and not os.getenv("GEMINI_API_KEY")
    ):
        return (
            f"Контрастное YouTube-превью для темы '{script_payload['topic']}', "
            f"крупный текст '{script_payload['thumbnail_text']}', современный IT-визуал."
        )
    prompt = f"""
    Сгенерируй короткий prompt для YouTube thumbnail на русском языке.
    Тема: {script_payload['topic']}
    Заголовок: {script_payload['title']}
    Текст на превью: {script_payload['thumbnail_text']}
    """
    return llm_chat("Ты креативный арт-директор для YouTube-превью.", prompt, temperature=0.9).strip()


def generate_openai_image(prompt: str, size: str) -> Image.Image:
    api_key = require_env("OPENAI_API_KEY")
    response = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        json={"model": "gpt-image-1", "prompt": prompt, "size": size},
        timeout=180,
    )
    response.raise_for_status()
    image_b64 = response.json()["data"][0]["b64_json"]
    return Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")


def draw_template(script_payload: dict, width: int, height: int, base_image: Image.Image | None) -> Image.Image:
    image = base_image.resize((width, height)) if base_image else Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, height - 220, width, height), fill="#000000")
    font_path = os.getenv("THUMBNAIL_FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    try:
        title_font = ImageFont.truetype(font_path, 74)
        prompt_font = ImageFont.truetype(font_path, 28)
    except OSError:
        title_font = ImageFont.load_default()
        prompt_font = ImageFont.load_default()

    thumbnail_text = script_payload.get("thumbnail_text") or script_payload["topic"]
    wrapped_title = textwrap.fill(thumbnail_text.upper(), width=18)
    prompt_text = script_payload.get("thumbnail_prompt", "")
    draw.text((70, height - 200), wrapped_title, font=title_font, fill="white", spacing=10)
    draw.text((70, 50), prompt_text[:120], font=prompt_font, fill="#FACC15")
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a thumbnail image for a script.")
    parser.add_argument("--topic", required=True, help="Topic title or slug")
    parser.add_argument("--demo", action="store_true", help="Use local prompt fallback without external image or LLM APIs.")
    args = parser.parse_args()

    load_environment()
    slug = slugify(args.topic)
    script_path = DATA_DIR / "scripts" / f"{slug}.json"
    script_payload = load_json(script_path)
    if not script_payload:
        raise RuntimeError("Script JSON not found.")

    width = int(os.getenv("THUMBNAIL_WIDTH", "1280"))
    height = int(os.getenv("THUMBNAIL_HEIGHT", "720"))
    size = f"{width}x{height}"
    demo_mode = is_demo_mode(args.demo)
    thumbnail_prompt = generate_prompt(script_payload, demo_mode=demo_mode)
    script_payload["thumbnail_prompt"] = thumbnail_prompt

    provider = os.getenv("THUMBNAIL_PROVIDER", "template").lower()
    base_image = None
    if provider == "openai" and not demo_mode:
        base_image = generate_openai_image(thumbnail_prompt, size)
    elif provider != "template":
        raise RuntimeError(f"Unsupported THUMBNAIL_PROVIDER={provider}")

    thumbnail = draw_template(script_payload, width, height, base_image)
    output_path = DATA_DIR / "thumbnails" / f"{slug}.png"
    ensure_dir(output_path.parent)
    thumbnail.save(output_path)
    save_json(script_path, script_payload)
    print(f"Saved thumbnail to {output_path}")


if __name__ == "__main__":
    main()
