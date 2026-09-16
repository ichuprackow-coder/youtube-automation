from __future__ import annotations

import argparse
import asyncio
import os

import edge_tts
import requests

from common import DATA_DIR, ensure_dir, load_environment, load_json, require_env, slugify


async def edge_tts_synthesize(text: str, output_path: str) -> None:
    voice = os.getenv("EDGE_TTS_VOICE", "ru-RU-SvetlanaNeural")
    communicator = edge_tts.Communicate(text=text, voice=voice)
    await communicator.save(output_path)


def elevenlabs_synthesize(text: str, output_path: str) -> None:
    api_key = require_env("ELEVENLABS_API_KEY")
    voice_id = require_env("ELEVENLABS_VOICE_ID")
    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={
            "xi-api-key": api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        },
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=120,
    )
    response.raise_for_status()
    with open(output_path, "wb") as audio_file:
        audio_file.write(response.content)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate TTS audio from a saved script.")
    parser.add_argument("--topic", required=True, help="Topic title or slug")
    args = parser.parse_args()

    load_environment()
    slug = slugify(args.topic)
    script_path = DATA_DIR / "scripts" / f"{slug}.json"
    script_payload = load_json(script_path)
    if not script_payload:
        raise RuntimeError(f"Script file not found: {script_path}")

    output_path = DATA_DIR / "audio" / f"{slug}.mp3"
    ensure_dir(output_path.parent)
    provider = os.getenv("TTS_PROVIDER", "edge-tts").lower()
    text = script_payload["tts_text"]
    if provider == "edge-tts":
        asyncio.run(edge_tts_synthesize(text, str(output_path)))
    elif provider == "elevenlabs":
        elevenlabs_synthesize(text, str(output_path))
    else:
        raise RuntimeError(f"Unsupported TTS_PROVIDER={provider}")

    print(f"Saved TTS audio to {output_path}")


if __name__ == "__main__":
    main()

