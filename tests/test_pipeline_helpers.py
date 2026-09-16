from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scripts.build_video import format_srt_timestamp
from scripts.common import extract_keywords, pick_topic_argument, slugify


class PipelineHelpersTest(unittest.TestCase):
    def test_slugify_keeps_cyrillic(self) -> None:
        self.assertEqual(slugify("Как войти в DevOps в 2026?"), "как-войти-в-devops-в-2026")

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


if __name__ == "__main__":
    unittest.main()
