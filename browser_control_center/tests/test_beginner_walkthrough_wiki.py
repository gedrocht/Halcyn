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
            "index.md",
            "01-start-here.md",
            "02-meet-the-cast.md",
            "03-follow-one-scene.md",
            "04-scene-json-without-fear.md",
            "05-browser-tools-in-plain-language.md",
            "06-visualizer-studio-as-a-daily-driver.md",
            "07-how-bar-wall-scenes-think.md",
            "08-the-safety-net.md",
            "09-how-to-extend-halcyn.md",
            "10-how-to-read-the-activity-monitor.md",
            "11-common-workflows.md",
            "12-troubleshooting-without-panic.md",
            "13-how-the-tests-protect-you.md",
            "14-how-the-tools-fit-together.md",
            "15-building-features-with-confidence.md",
            "appendix-glossary.md",
            "appendix-first-hour.md",
            "appendix-command-cheat-sheet.md",
            "appendix-which-tool-should-i-open.md",
        }

        discovered_files = {path.name for path in self.wiki_root.glob("*.md")}
        self.assertEqual(discovered_files, expected_files)

    def test_git_hub_readme_links_to_every_chapter(self) -> None:
        """The GitHub-readable wiki index should expose the whole study path."""

        index_text = self._read_text("docs/wiki/README.md")
        for file_name in [
            "index.md",
            "01-start-here.md",
            "02-meet-the-cast.md",
            "03-follow-one-scene.md",
            "04-scene-json-without-fear.md",
            "05-browser-tools-in-plain-language.md",
            "06-visualizer-studio-as-a-daily-driver.md",
            "07-how-bar-wall-scenes-think.md",
            "08-the-safety-net.md",
            "09-how-to-extend-halcyn.md",
            "10-how-to-read-the-activity-monitor.md",
            "11-common-workflows.md",
            "12-troubleshooting-without-panic.md",
            "13-how-the-tests-protect-you.md",
            "14-how-the-tools-fit-together.md",
            "15-building-features-with-confidence.md",
            "appendix-glossary.md",
            "appendix-first-hour.md",
            "appendix-command-cheat-sheet.md",
            "appendix-which-tool-should-i-open.md",
        ]:
            self.assertIn(file_name, index_text)

    def test_hosted_wiki_index_links_to_every_major_page(self) -> None:
        """The MkDocs landing page should expose the hosted study path."""

        hosted_index_text = self._read_text("docs/wiki/index.md")
        for file_name in [
            "01-start-here.md",
            "03-follow-one-scene.md",
            "06-visualizer-studio-as-a-daily-driver.md",
            "10-how-to-read-the-activity-monitor.md",
            "12-troubleshooting-without-panic.md",
            "15-building-features-with-confidence.md",
            "appendix-first-hour.md",
            "appendix-command-cheat-sheet.md",
        ]:
            self.assertIn(file_name, hosted_index_text)

    def test_each_chapter_links_back_into_the_series(self) -> None:
        """Every chapter should keep visible navigation to the larger walkthrough."""

        for chapter_path in sorted(self.wiki_root.glob("[0-9][0-9]-*.md")):
            chapter_text = chapter_path.read_text(encoding="utf-8")
            self.assertIn("Previous chapter:", chapter_text, chapter_path.name)
            self.assertIn("Next chapter:", chapter_text, chapter_path.name)
            self.assertIn("index.md", chapter_text, chapter_path.name)

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

    def test_hosted_wiki_does_not_keep_repo_relative_docs_links(self) -> None:
        """The hosted wiki should use public docs URLs instead of repo-only relative links."""

        for markdown_path in sorted(self.wiki_root.glob("*.md")):
            markdown_text = markdown_path.read_text(encoding="utf-8")
            self.assertNotIn("../site/", markdown_text, markdown_path.name)
            self.assertNotIn("../../README.md", markdown_text, markdown_path.name)

    def test_key_learning_aids_remain_present(self) -> None:
        """The walkthrough should keep its gentler study aids."""

        self.assertIn("Two reading tracks", self._read_text("docs/wiki/README.md"))
        self.assertIn("```mermaid", self._read_text("docs/wiki/03-follow-one-scene.md"))
        self.assertIn(
            "Try this now",
            self._read_text("docs/wiki/06-visualizer-studio-as-a-daily-driver.md"),
        )
        self.assertIn(
            "panic-proof checklist",
            self._read_text("docs/wiki/08-the-safety-net.md"),
        )
        self.assertIn(
            "Track 3",
            self._read_text("docs/wiki/index.md"),
        )
        self.assertIn(
            "Activity Monitor",
            self._read_text("docs/wiki/10-how-to-read-the-activity-monitor.md"),
        )

    def test_wiki_framework_files_exist_and_name_the_expected_pages(self) -> None:
        """The hosted wiki should keep its MkDocs config and helper scripts."""

        mkdocs_configuration_text = self._read_text("mkdocs-wiki.yml")
        self.assertIn("site_name: Halcyn Walkthrough Wiki", mkdocs_configuration_text)
        self.assertIn("docs_dir: docs/wiki", mkdocs_configuration_text)
        self.assertIn("name: readthedocs", mkdocs_configuration_text)
        for expected_nav_entry in [
            "index.md",
            "10-how-to-read-the-activity-monitor.md",
            "11-common-workflows.md",
            "12-troubleshooting-without-panic.md",
            "13-how-the-tests-protect-you.md",
            "14-how-the-tools-fit-together.md",
            "15-building-features-with-confidence.md",
            "appendix-command-cheat-sheet.md",
            "appendix-which-tool-should-i-open.md",
        ]:
            self.assertIn(expected_nav_entry, mkdocs_configuration_text)

        self.assertTrue((self.project_root / "scripts" / "build-beginner-wiki.ps1").exists())
        self.assertTrue((self.project_root / "scripts" / "serve-beginner-wiki.ps1").exists())
