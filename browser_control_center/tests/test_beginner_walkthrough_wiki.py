"""Regression tests for the separate beginner-friendly walkthrough wiki."""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import ClassVar

MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


class BeginnerWalkthroughWikiTests(unittest.TestCase):
    """Keep the narrative wiki complete and internally navigable."""

    project_root: ClassVar[Path]
    wiki_root: ClassVar[Path]

    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[2]
        cls.wiki_root = cls.project_root / "docs" / "wiki"

    def _read_text(self, relative_path: str) -> str:
        return (self.project_root / relative_path).read_text(encoding="utf-8")

    def test_wiki_contains_the_expected_chapter_series(self) -> None:
        """The walkthrough should keep its promised chapter set."""

        expected_files = {
            "README.md",
            "01-start-here.md",
            "02-meet-the-cast.md",
            "03-follow-one-scene.md",
            "04-scene-json-without-fear.md",
            "05-browser-tools-in-plain-language.md",
            "06-visualizer-studio-as-a-daily-driver.md",
            "07-how-bar-wall-scenes-think.md",
            "08-the-safety-net.md",
            "09-how-to-extend-halcyn.md",
        }

        discovered_files = {path.name for path in self.wiki_root.glob("*.md")}
        self.assertEqual(discovered_files, expected_files)

    def test_wiki_index_links_to_every_chapter(self) -> None:
        """The index page should expose the whole study path."""

        index_text = self._read_text("docs/wiki/README.md")
        for file_name in [
            "01-start-here.md",
            "02-meet-the-cast.md",
            "03-follow-one-scene.md",
            "04-scene-json-without-fear.md",
            "05-browser-tools-in-plain-language.md",
            "06-visualizer-studio-as-a-daily-driver.md",
            "07-how-bar-wall-scenes-think.md",
            "08-the-safety-net.md",
            "09-how-to-extend-halcyn.md",
        ]:
            self.assertIn(file_name, index_text)

    def test_each_chapter_links_back_into_the_series(self) -> None:
        """Every chapter should keep visible navigation to the larger walkthrough."""

        for chapter_path in sorted(self.wiki_root.glob("[0-9][0-9]-*.md")):
            chapter_text = chapter_path.read_text(encoding="utf-8")
            self.assertIn("Previous chapter:", chapter_text, chapter_path.name)
            self.assertIn("Next chapter:", chapter_text, chapter_path.name)
            self.assertIn("README.md", chapter_text, chapter_path.name)

    def test_all_local_markdown_links_resolve(self) -> None:
        """Relative wiki links should not silently rot."""

        markdown_paths = sorted(self.wiki_root.glob("*.md"))
        for markdown_path in markdown_paths:
            markdown_text = markdown_path.read_text(encoding="utf-8")
            for link_target in MARKDOWN_LINK_PATTERN.findall(markdown_text):
                if link_target.startswith(("http://", "https://", "mailto:", "#")):
                    continue

                resolved_target = (markdown_path.parent / link_target).resolve()
                self.assertTrue(
                    resolved_target.exists(),
                    f"{markdown_path.name} links to missing local target {link_target!r}",
                )
