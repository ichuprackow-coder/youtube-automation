from __future__ import annotations

import argparse
import os
import textwrap
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFont

from common import DATA_DIR, ensure_dir, is_demo_mode, load_environment, load_json, save_json, slugify

PALETTE = ["#0F172A", "#1D4ED8", "#7C3AED", "#0F766E", "#B45309"]


def pollinations_url(prompt: str, width: int, height: int) -> str:
    encoded_prompt = quote(prompt, safe="")
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true"


def download_pollinations_image(prompt: str, output_path: Path, width: int, height: int) -> None:
    response = requests.get(pollinations_url(prompt, width, height), timeout=180)
    response.raise_for_status()
    output_path.write_bytes(response.content)


def write_placeholder(prompt: str, output_path: Path, width: int, height: int, index: int) -> None:
    image = Image.new("RGB", (width, height), PALETTE[(index - 1) % len(PALETTE)])
    draw = ImageDraw.Draw(image)
    draw.rectangle((48, 48, width - 48, height - 48), outline="white", width=4)
    font_path = os.getenv("THUMBNAIL_FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    try:
        title_font = ImageFont.truetype(font_path, 54)
        text_font = ImageFont.truetype(font_path, 30)
    except OSError:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()

    draw.text((72, 72), f"SCENE {index:02d}", fill="white", font=title_font)
    body = textwrap.fill(prompt, width=34)
    draw.multiline_text((72, 180), body, fill="#F8FAFC", font=text_font, spacing=10)
    image.save(output_path, format="JPEG", quality=92)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate scene images for a scenario-based script.")
    parser.add_argument("--topic", required=True, help="Topic title or slug")
    parser.add_argument("--demo", action="store_true", help="Use local placeholder images instead of remote generation.")
    args = parser.parse_args()

    load_environment()
    slug = slugify(args.topic)
    script_path = DATA_DIR / "scripts" / f"{slug}.json"
    script_payload = load_json(script_path)
    if not script_payload:
        raise RuntimeError(f"Script JSON not found: {script_path}")

    scenes = script_payload.get("scenes") or []
    if not scenes:
        raise RuntimeError("This script does not contain scene prompts.")

    width = int(os.getenv("SCENE_IMAGE_WIDTH", "1920"))
    height = int(os.getenv("SCENE_IMAGE_HEIGHT", "1080"))
    provider = os.getenv("SCENE_IMAGE_PROVIDER", "pollinations").lower()
    demo_mode = is_demo_mode(args.demo)
    output_dir = ensure_dir(DATA_DIR / "images" / slug)

    saved_paths: list[str] = []
    for scene in scenes:
        output_path = output_dir / f"scene-{scene['index']:02d}.jpg"
        if demo_mode or provider == "placeholder":
            write_placeholder(scene["image_prompt"], output_path, width, height, scene["index"])
        elif provider == "pollinations":
            try:
                download_pollinations_image(scene["image_prompt"], output_path, width, height)
            except requests.RequestException:
                write_placeholder(scene["image_prompt"], output_path, width, height, scene["index"])
        else:
            raise RuntimeError(f"Unsupported SCENE_IMAGE_PROVIDER={provider}")
        saved_paths.append(str(output_path))

    script_payload["scene_image_dir"] = str(output_dir)
    script_payload["scene_image_paths"] = saved_paths
    save_json(script_path, script_payload)
    print(f"Saved {len(saved_paths)} scene images to {output_dir}")


if __name__ == "__main__":
    main()
