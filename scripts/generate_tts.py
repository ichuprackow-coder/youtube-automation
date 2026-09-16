from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import wave
from math import sin, pi
from struct import pack

import edge_tts
import requests

from common import DATA_DIR, ensure_dir, is_demo_mode, load_environment, load_json, require_env, slugify


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


def demo_synthesize(text: str, output_path: str) -> None:
    duration = max(3, min(len(text.split()) // 2, 30))
    if shutil.which("ffmpeg"):
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=440:duration={duration}",
                "-q:a",
                "9",
                "-acodec",
                "libmp3lame",
                output_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    sample_rate = 22_050
    amplitude = 8_000
    total_frames = sample_rate * duration
    with wave.open(output_path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for frame in range(total_frames):
            value = int(amplitude * sin(2 * pi * 440 * frame / sample_rate))
            wav_file.writeframes(pack("<h", value))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate TTS audio from a saved script.")
    parser.add_argument("--topic", required=True, help="Topic title or slug")
    parser.add_argument("--demo", action="store_true", help="Generate a local preview audio track without external TTS APIs.")
    args = parser.parse_args()

    load_environment()
    slug = slugify(args.topic)
    script_path = DATA_DIR / "scripts" / f"{slug}.json"
    script_payload = load_json(script_path)
    if not script_payload:
        raise RuntimeError(f"Script file not found: {script_path}")

    output_path = DATA_DIR / "audio" / f"{slug}.mp3"
    ensure_dir(output_path.parent)
    demo_mode = is_demo_mode(args.demo)
    provider = os.getenv("TTS_PROVIDER", "edge-tts").lower()
    text = script_payload["tts_text"]
    if demo_mode:
        demo_synthesize(text, str(output_path))
    elif provider == "edge-tts":
        asyncio.run(edge_tts_synthesize(text, str(output_path)))
    elif provider == "elevenlabs":
        elevenlabs_synthesize(text, str(output_path))
    else:
        raise RuntimeError(f"Unsupported TTS_PROVIDER={provider}")

    print(f"Saved TTS audio to {output_path}")


if __name__ == "__main__":
    main()
