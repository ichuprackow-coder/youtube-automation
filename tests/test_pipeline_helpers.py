from __future__ import annotations

import unittest
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scripts.bootstrap_local import upsert_line
from scripts.build_video import escape_ffmpeg_filter_path, format_srt_timestamp, write_subtitles
from scripts.check_publish_approval import main as check_publish_approval_main
from scripts.common import extract_keywords, is_demo_mode, pick_topic_argument, slugify
from scripts.generate_script import generate_script_demo
from scripts.generate_tts import demo_synthesize, elevenlabs_synthesize, main as generate_tts_main
from scripts.topic_research import build_demo_videos, generate_topic_ideas_demo
from scripts.upload_youtube import save_dry_run, upload_video


class PipelineHelpersTest(unittest.TestCase):
    def test_slugify_keeps_cyrillic(self) -> None:
        self.assertEqual(slugify("Как войти в DevOps в 2026?"), "как-войти-в-devops-в-2026")

    def test_is_demo_mode_from_environment(self) -> None:
        with patch.dict("os.environ", {"DEMO_MODE": "true"}, clear=False):
            self.assertTrue(is_demo_mode())

    def test_extract_keywords_counts_relevant_words(self) -> None:
        keywords = extract_keywords(["DevOps roadmap для junior DevOps"], limit=2)
        self.assertEqual(keywords[0]["keyword"], "devops")
        self.assertEqual(keywords[0]["mentions"], 2)

    def test_pick_topic_argument_prefers_first_without_script(self) -> None:
        temp_path = Path("tests/topics-fixture.json")
        temp_path.write_text(
            '{"ideas":[{"title":"A","script_path":"data/scripts/a.json"},{"title":"B"}]}',
            encoding="utf-8",
        )
        try:
            self.assertEqual(pick_topic_argument(None, temp_path)["title"], "B")
        finally:
            temp_path.unlink(missing_ok=True)

    def test_pick_topic_argument_matches_explicit_title(self) -> None:
        temp_path = Path("tests/topics-fixture.json")
        temp_path.write_text('{"ideas":[{"title":"A"},{"title":"B"}]}', encoding="utf-8")
        try:
            self.assertEqual(pick_topic_argument("B", temp_path)["title"], "B")
        finally:
            temp_path.unlink(missing_ok=True)

    def test_pick_topic_argument_matches_slugified_title(self) -> None:
        temp_path = Path("tests/topics-fixture.json")
        temp_path.write_text('{"ideas":[{"title":"Как войти в DevOps в 2026"}]}', encoding="utf-8")
        try:
            self.assertEqual(
                pick_topic_argument("как-войти-в-devops-в-2026", temp_path)["title"],
                "Как войти в DevOps в 2026",
            )
        finally:
            temp_path.unlink(missing_ok=True)

    def test_pick_topic_argument_creates_fallback_for_missing_title(self) -> None:
        temp_path = Path("tests/topics-fixture.json")
        temp_path.write_text('{"ideas":[{"title":"A"}]}', encoding="utf-8")
        try:
            topic = pick_topic_argument("C", temp_path)
            self.assertEqual(topic["title"], "C")
            self.assertEqual(topic["competition"], "unknown")
        finally:
            temp_path.unlink(missing_ok=True)

    def test_pick_topic_argument_raises_when_no_topics_exist(self) -> None:
        temp_path = Path("tests/topics-fixture.json")
        temp_path.write_text('{"ideas":[]}', encoding="utf-8")
        try:
            with self.assertRaises(RuntimeError):
                pick_topic_argument(None, temp_path)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_srt_timestamp_format(self) -> None:
        self.assertEqual(format_srt_timestamp(65.432), "00:01:05,432")

    def test_upsert_line_replaces_existing_value(self) -> None:
        env_path = Path("tests/demo.env")
        env_path.write_text("DEMO_MODE=false\n", encoding="utf-8")
        try:
            upsert_line(env_path, "DEMO_MODE", "true")
            self.assertEqual(env_path.read_text(encoding="utf-8"), "DEMO_MODE=true\n")
        finally:
            env_path.unlink(missing_ok=True)

    def test_ffmpeg_filter_path_escaping(self) -> None:
        escaped = escape_ffmpeg_filter_path(Path(r"/tmp/it's\test:01.srt"))
        self.assertEqual(escaped, r"/tmp/it\'s\\test\:01.srt")

    def test_write_subtitles_avoids_zero_length_segments(self) -> None:
        output_path = Path("tests/subtitles.srt")
        try:
            write_subtitles(
                {
                    "hook": "a",
                    "outline": [{"heading": "b"}, {"heading": "c"}],
                    "cta": "d",
                },
                output_path,
                0.002,
            )
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("00:00:00,001", content)
        finally:
            output_path.unlink(missing_ok=True)

    @patch("scripts.generate_tts.requests.post")
    def test_elevenlabs_synthesize_uses_expected_payload(self, post: MagicMock) -> None:
        post.return_value.raise_for_status.return_value = None
        post.return_value.content = b"audio"
        output_path = Path("tests/elevenlabs.mp3")
        try:
            with patch.dict(
                "os.environ",
                {"ELEVENLABS_API_KEY": "key", "ELEVENLABS_VOICE_ID": "voice"},
                clear=False,
            ):
                elevenlabs_synthesize("Привет", str(output_path))
            post.assert_called_once()
            _, kwargs = post.call_args
            self.assertEqual(kwargs["json"]["text"], "Привет")
            self.assertEqual(kwargs["json"]["model_id"], "eleven_multilingual_v2")
            self.assertEqual(kwargs["headers"]["xi-api-key"], "key")
        finally:
            output_path.unlink(missing_ok=True)

    def test_topic_research_demo_generates_ideas(self) -> None:
        videos = build_demo_videos("IT")
        keywords = extract_keywords([video["title"] for video in videos], limit=5)
        ideas = generate_topic_ideas_demo("IT", "ru", "3 видео в неделю", keywords)
        self.assertEqual(len(ideas), 5)
        self.assertIn("title", ideas[0])

    def test_generate_script_demo_returns_required_fields(self) -> None:
        payload = generate_script_demo({"title": "Demo topic", "keywords": ["devops"]}, ["devops", "automation"])
        self.assertIn("hook", payload)
        self.assertEqual(len(payload["outline"]), 3)
        self.assertIn("tags", payload)

    @patch("scripts.generate_tts.shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("scripts.generate_tts.subprocess.run")
    def test_demo_synthesize_uses_ffmpeg(self, run: MagicMock, _which: MagicMock) -> None:
        demo_synthesize("one two three four five six", "demo.mp3")
        run.assert_called_once()
        self.assertIn("ffmpeg", run.call_args.args[0][0])

    @patch("scripts.generate_tts.elevenlabs_synthesize")
    @patch("scripts.generate_tts.asyncio.run")
    def test_generate_tts_main_routes_to_elevenlabs_provider(self, asyncio_run: MagicMock, elevenlabs: MagicMock) -> None:
        script_path = Path("data/scripts/test-topic.json")
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text('{"tts_text":"hello"}', encoding="utf-8")
        original_argv = sys.argv
        try:
            with patch.dict("os.environ", {"TTS_PROVIDER": "elevenlabs", "DEMO_MODE": "false"}, clear=False):
                sys.argv = ["generate_tts.py", "--topic", "test topic"]
                generate_tts_main()
            elevenlabs.assert_called_once()
            asyncio_run.assert_not_called()
        finally:
            sys.argv = original_argv
            Path("data/audio/test-topic.mp3").unlink(missing_ok=True)
            script_path.unlink(missing_ok=True)

    @patch("scripts.upload_youtube.load_credentials")
    @patch("scripts.upload_youtube.build")
    def test_upload_video_logs_metadata(self, build: MagicMock, _load_credentials: MagicMock) -> None:
        slug = "topic"
        video_path = Path("data/videos/topic.mp4")
        thumb_path = Path("data/thumbnails/topic.png")
        log_path = Path("data/upload_log.json")
        latest_path = Path("data/latest_upload.json")
        video_path.parent.mkdir(parents=True, exist_ok=True)
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"video")
        thumb_path.write_bytes(b"thumb")

        insert_request = MagicMock()
        insert_request.next_chunk.side_effect = [(None, None), (None, {"id": "video-123"})]
        youtube = MagicMock()
        youtube.videos.return_value.insert.return_value = insert_request
        youtube.thumbnails.return_value.set.return_value.execute.return_value = {}
        youtube.playlistItems.return_value.insert.return_value.execute.return_value = {}
        build.return_value = youtube

        try:
            with patch.dict("os.environ", {"YOUTUBE_PLAYLIST_ID": "playlist-1"}, clear=False):
                result = upload_video(
                    {
                        "topic": "Topic",
                        "title": "Title",
                        "description": "Description",
                        "tags": ["tag1"],
                    },
                    slug,
                )
            self.assertEqual(result["video_id"], "video-123")
            self.assertTrue(log_path.exists())
            self.assertTrue(latest_path.exists())
            youtube.thumbnails.return_value.set.assert_called_once()
            youtube.playlistItems.return_value.insert.assert_called_once()
        finally:
            for path in [video_path, thumb_path, log_path, latest_path]:
                path.unlink(missing_ok=True)

    def test_save_dry_run_writes_upload_preview(self) -> None:
        video_path = Path("data/videos/topic.mp4")
        thumb_path = Path("data/thumbnails/topic.png")
        dry_run_path = Path("data/upload_dry_run.json")
        video_path.parent.mkdir(parents=True, exist_ok=True)
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"video")
        thumb_path.write_bytes(b"thumb")
        try:
            payload = save_dry_run(
                {"topic": "Topic", "title": "Title", "description": "Description", "tags": ["tag1"]},
                "topic",
            )
            self.assertEqual(payload["status"]["privacyStatus"], "unlisted")
            self.assertTrue(dry_run_path.exists())
        finally:
            for path in [video_path, thumb_path, dry_run_path]:
                path.unlink(missing_ok=True)

    @patch("scripts.check_publish_approval.get_issue")
    def test_check_publish_approval_requires_label(self, get_issue: MagicMock) -> None:
        approval_path = Path("data/publish_approval.json")
        original_argv = sys.argv
        get_issue.return_value = {"title": "Publish", "labels": [{"name": "publish-approved"}]}
        try:
            with patch.dict(
                "os.environ",
                {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "token"},
                clear=False,
            ):
                sys.argv = ["check_publish_approval.py", "--issue-number", "12"]
                check_publish_approval_main()
            payload = approval_path.read_text(encoding="utf-8")
            self.assertIn('"approved": true', payload)
        finally:
            sys.argv = original_argv
            approval_path.unlink(missing_ok=True)

    @patch("scripts.check_publish_approval.get_issue")
    def test_check_publish_approval_rejects_without_label(self, get_issue: MagicMock) -> None:
        approval_path = Path("data/publish_approval.json")
        original_argv = sys.argv
        get_issue.return_value = {"title": "Publish", "labels": [{"name": "needs-review"}]}
        try:
            with patch.dict(
                "os.environ",
                {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "token"},
                clear=False,
            ):
                sys.argv = ["check_publish_approval.py", "--issue-number", "12"]
                check_publish_approval_main()
            payload = approval_path.read_text(encoding="utf-8")
            self.assertIn('"approved": false', payload)
        finally:
            sys.argv = original_argv
            approval_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
