from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from common import ASSETS_DIR, DATA_DIR, ensure_dir, load_environment, load_json, slugify

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a"}


def ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def prepare_backgrounds(required_count: int, size: tuple[int, int]) -> list[Path]:
    background_dir = ensure_dir(ASSETS_DIR / "backgrounds")
    backgrounds = [path for path in sorted(background_dir.iterdir()) if path.suffix.lower() in IMAGE_EXTENSIONS]
    if backgrounds:
        return [backgrounds[index % len(backgrounds)] for index in range(required_count)]

    generated_dir = ensure_dir(background_dir / "generated")
    generated = []
    palette = ["#0F172A", "#1D4ED8", "#7C3AED", "#0F766E", "#B45309"]
    for index in range(required_count):
        image_path = generated_dir / f"fallback-{index + 1}.png"
        image = Image.new("RGB", size, palette[index % len(palette)])
        draw = ImageDraw.Draw(image)
        draw.rectangle((70, 70, size[0] - 70, size[1] - 70), outline="white", width=6)
        image.save(image_path)
        generated.append(image_path)
    return generated


def format_srt_timestamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def escape_ffmpeg_filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace("'", r"\'").replace(":", r"\:")


def write_subtitles(script_payload: dict, output_path: Path, total_duration: float) -> None:
    segments = [script_payload["hook"]]
    segments.extend(item["heading"] for item in script_payload["outline"])
    segments.append(script_payload["cta"])
    word_lengths = [max(len(segment.split()), 1) for segment in segments]
    total_words = sum(word_lengths)
    total_ms = max(int(round(total_duration * 1000)), len(segments))
    cursor_ms = 0
    blocks = []
    for index, (segment, words) in enumerate(zip(segments, word_lengths), start=1):
        segment_ms = max(int(round(total_ms * (words / total_words))), 1)
        start_ms = cursor_ms
        end_ms = total_ms if index == len(segments) else min(cursor_ms + segment_ms, total_ms)
        if end_ms <= start_ms:
            end_ms = min(start_ms + 1, total_ms)
        blocks.append(
            f"{index}\n{format_srt_timestamp(start_ms / 1000)} --> {format_srt_timestamp(end_ms / 1000)}\n{segment}\n"
        )
        cursor_ms = end_ms
    output_path.write_text("\n".join(blocks), encoding="utf-8")


def build_ffmpeg_command(
    backgrounds: list[Path],
    audio_path: Path,
    subtitles_path: Path,
    music_path: Path | None,
    output_path: Path,
    total_duration: float,
) -> list[str]:
    scene_count = max(len(backgrounds), 1)
    transition = 1.0 if scene_count > 1 else 0.0
    scene_duration = total_duration / scene_count
    width = 1920
    height = 1080

    command = ["ffmpeg", "-y"]
    for background in backgrounds:
        command.extend(["-loop", "1", "-t", str(scene_duration + transition), "-i", str(background)])
    command.extend(["-i", str(audio_path)])
    if music_path:
        command.extend(["-stream_loop", "-1", "-i", str(music_path)])

    filter_parts = []
    for index in range(scene_count):
        filter_parts.append(
            f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},format=yuv420p,setsar=1[v{index}]"
        )

    video_label = "[v0]"
    if scene_count > 1:
        previous = "[v0]"
        offset = scene_duration - transition
        for index in range(1, scene_count):
            next_label = f"[vxf{index}]"
            filter_parts.append(
                f"{previous}[v{index}]xfade=transition=fade:duration={transition}:offset={max(offset, 0.1):.2f}{next_label}"
            )
            previous = next_label
            offset += scene_duration - transition
        video_label = previous

    subtitle_path = escape_ffmpeg_filter_path(subtitles_path)
    filter_parts.append(
        f"{video_label}subtitles='{subtitle_path}':force_style='Alignment=2,Fontsize={int(os.getenv('SUBTITLE_FONT_SIZE', '36'))},Outline=1,Shadow=1,MarginV=40'[video]"
    )

    if music_path:
        filter_parts.append(f"[{scene_count + 1}:a]volume=0.12,atrim=0:{total_duration}[music]")
        filter_parts.append(f"[{scene_count}:a][music]amix=inputs=2:duration=first:dropout_transition=2[audio]")
        audio_map = "[audio]"
    else:
        audio_map = f"[{scene_count}:a]"

    command.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[video]",
            "-map",
            audio_map,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
    )
    return command


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a video with FFmpeg from audio and background assets.")
    parser.add_argument("--topic", required=True, help="Topic title or slug")
    args = parser.parse_args()

    load_environment()
    slug = slugify(args.topic)
    script_payload = load_json(DATA_DIR / "scripts" / f"{slug}.json")
    audio_path = DATA_DIR / "audio" / f"{slug}.mp3"
    if not script_payload or not audio_path.exists():
        raise RuntimeError("Script JSON and MP3 audio must exist before building the video.")

    total_duration = ffprobe_duration(audio_path)
    scene_count = len(script_payload["outline"]) + 2
    backgrounds = prepare_backgrounds(scene_count, (1920, 1080))
    output_path = DATA_DIR / "videos" / f"{slug}.mp4"
    ensure_dir(output_path.parent)

    music_dir = ensure_dir(ASSETS_DIR / "music")
    music_candidates = [path for path in sorted(music_dir.iterdir()) if path.suffix.lower() in AUDIO_EXTENSIONS]
    music_path = music_candidates[0] if music_candidates else None

    with tempfile.TemporaryDirectory(prefix="youtube-pipeline-") as temp_dir:
        subtitles_path = Path(temp_dir) / f"{slug}.srt"
        write_subtitles(script_payload, subtitles_path, total_duration)
        command = build_ffmpeg_command(backgrounds, audio_path, subtitles_path, music_path, output_path, total_duration)
        subprocess.run(command, check=True)

    print(f"Saved video to {output_path}")


if __name__ == "__main__":
    main()
