"""Repository-level regression tests for script and frontend contracts."""

from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from typing import ClassVar


class _HtmlContractParser(HTMLParser):
    """Collect useful contract markers from a static HTML file."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.hrefs: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)

        element_id = attributes.get("id")
        if element_id:
            self.ids.add(element_id)

        if tag == "a":
            href = attributes.get("href")
            if href:
                self.hrefs.add(href)


class RepositoryContractTests(unittest.TestCase):
    """Protect the cross-file contracts that keep the browser tooling honest."""

    project_root: ClassVar[Path]

    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[2]

    def _read_text(self, relative_path: str) -> str:
        return (self.project_root / relative_path).read_text(encoding="utf-8")

    def _parse_html(self, relative_path: str) -> _HtmlContractParser:
        parser = _HtmlContractParser()
        parser.feed(self._read_text(relative_path))
        return parser

    def _js_element_ids(self, relative_path: str) -> set[str]:
        return set(re.findall(r'getElementById\("([^"]+)"\)', self._read_text(relative_path)))

    def test_browser_control_center_html_and_js_ids_stay_in_sync(self) -> None:
        """The Control Center dashboard should not reference missing DOM ids."""

        html_ids = self._parse_html("browser_control_center/static/index.html").ids
        js_ids = self._js_element_ids("browser_control_center/static/app.js")
        self.assertFalse(
            js_ids - html_ids,
            f"Missing Control Center HTML ids for JS bindings: {sorted(js_ids - html_ids)}",
        )

    def test_browser_scene_studio_html_and_js_ids_stay_in_sync(self) -> None:
        """The Scene Studio frontend should not reference missing DOM ids."""

        html_ids = self._parse_html("browser_scene_studio/static/index.html").ids
        js_ids = self._js_element_ids("browser_scene_studio/static/app.js")
        self.assertFalse(
            js_ids - html_ids,
            f"Missing Scene Studio HTML ids for JS bindings: {sorted(js_ids - html_ids)}",
        )

    def test_activity_monitor_html_and_js_ids_stay_in_sync(self) -> None:
        """The Activity Monitor frontend should not reference missing DOM ids."""

        html_ids = self._parse_html("browser_control_center/static/activity-monitor.html").ids
        js_ids = self._js_element_ids("browser_control_center/static/activity-monitor.js")
        self.assertFalse(
            js_ids - html_ids,
            f"Missing Activity Monitor HTML ids for JS bindings: {sorted(js_ids - html_ids)}",
        )

    def test_browser_control_center_dashboard_links_to_browser_scene_studio(self) -> None:
        """The dashboard should keep its launch path to the Scene Studio visible."""

        parser = self._parse_html("browser_control_center/static/index.html")
        self.assertIn("/scene-studio/", parser.hrefs)

    def test_runtime_and_run_script_stay_in_api_host_sync(self) -> None:
        """The runtime should keep using the current launch-halcyn-app.ps1 ApiHost name."""

        runtime_text = self._read_text("browser_control_center/control_center_state.py")
        run_script = self._read_text("scripts/launch-halcyn-app.ps1")

        self.assertIn("[string]$ApiHost = '127.0.0.1'", run_script)
        self.assertIn('"-ApiHost"', runtime_text)
        self.assertNotIn('"-Host"', runtime_text)

    def test_browser_control_center_launchers_use_shared_project_root_helper(self) -> None:
        """The browser launchers should source shared-script-helpers.ps1.

        They should also use the shared project-root helper.
        """

        for relative_path in [
            "scripts/launch-browser-control-center.ps1",
            "scripts/launch-browser-scene-studio.ps1",
        ]:
            script_text = self._read_text(relative_path)
            self.assertIn(". (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')", script_text)
            self.assertIn("$projectRoot = Get-ProjectRoot", script_text)
            self.assertIn("'--project-root'", script_text)

    def test_deprecated_wrapper_scripts_are_removed(self) -> None:
        """Deprecated wrapper scripts should stay out of the repository."""

        for relative_path in [
            "scripts/launch-desktop-multi-renderer-data-source-panel.ps1",
            "scripts/launch-desktop-render-control-panel.ps1",
            "scripts/launch-desktop-spectrograph-audio-source-panel.ps1",
            "scripts/launch-desktop-spectrograph-control-panel.ps1",
            "scripts/launch-halcyn-spectrograph-app.ps1",
            "scripts/launch-operator-console.ps1",
            "scripts/launch-spectrograph-audio-workbench.ps1",
            "scripts/lint-operator-console.ps1",
            "scripts/measure-operator-console-coverage.ps1",
            "scripts/test-operator-console.ps1",
            "scripts/typecheck-operator-console.ps1",
        ]:
            self.assertFalse(
                (self.project_root / relative_path).exists(),
                f"{relative_path} should have been removed with the deprecated wrappers.",
            )

    def test_legacy_docs_pages_are_removed(self) -> None:
        """Deprecated docs-only landing pages should stay removed."""

        for relative_path in [
            "docs/site/spectrograph-audio-source-panel.html",
            "docs/site/multi-renderer-data-source-panel.html",
        ]:
            self.assertFalse(
                (self.project_root / relative_path).exists(),
                f"{relative_path} should have been removed with the legacy docs pages.",
            )

    def test_activity_monitor_launcher_reuses_control_center_routes(self) -> None:
        """The Activity Monitor launcher should stay coupled to the Control Center server."""

        launcher_text = self._read_text("scripts/launch-activity-monitor.ps1")
        self.assertIn("Get-ControlCenterCompatibility", launcher_text)
        self.assertIn("/activity-monitor/", launcher_text)

    def test_scripts_do_not_reintroduce_provider_style_project_root_resolution(self) -> None:
        """Repository scripts should avoid the old provider-prefixed Resolve-Path pattern."""

        bad_pattern = "(Resolve-Path (Join-Path $PSScriptRoot '..')).Path"
        offenders = []

        for script_path in (self.project_root / "scripts").glob("*.ps1"):
            script_text = script_path.read_text(encoding="utf-8")
            if bad_pattern in script_text:
                offenders.append(script_path.name)

        self.assertFalse(
            offenders,
            f"Scripts still using provider-style project root resolution: {offenders}",
        )

    def test_readme_uses_current_directory_and_script_names(self) -> None:
        """The main README should teach the renamed structure instead of the retired labels."""

        readme_text = self._read_text("README.md")
        for retired_name in [
            "src/api",
            "src/app",
            "src/core",
            "src/domain",
            "src/renderer",
            r".\scripts\studio.ps1",
            r".\scripts\client-studio.ps1",
            r".\scripts\lint-control-plane.ps1",
            r".\scripts\coverage-control-plane.ps1",
            r".\scripts\typecheck-control-plane.ps1",
            r".\scripts\test-control-plane.ps1",
            r".\scripts\launch-operator-console.ps1",
            r".\scripts\launch-halcyn-spectrograph-app.ps1",
            r".\scripts\launch-spectrograph-audio-workbench.ps1",
            "client-studio.html",
            "spectrograph-audio-source-panel.html",
            "multi-renderer-data-source-panel.html",
            "desktop_render_control_panel/",
            "desktop_spectrograph_control_panel/",
            "desktop_spectrograph_audio_source_panel/",
            "desktop_multi_renderer_data_source_panel/",
        ]:
            self.assertNotIn(retired_name, readme_text)
        self.assertIn(r".\scripts\launch-visualizer-studio.ps1", readme_text)
        self.assertIn(r".\scripts\launch-activity-monitor.ps1", readme_text)
        self.assertIn(r".\scripts\launch-visualizer-workbench.ps1", readme_text)

    def test_docs_site_uses_current_directory_and_script_names(self) -> None:
        """The docs site should stay aligned with the renamed repository layout."""

        retired_terms = [
            "src/api",
            "src/app",
            "src/core",
            "src/domain",
            "src/renderer",
            "client-studio.html",
            "architecture.svg",
            "http://127.0.0.1:9001",
            "../../README.md",
            "spectrograph-audio-source-panel.html",
            "multi-renderer-data-source-panel.html",
            "launch-halcyn-spectrograph-app.ps1",
            "launch-spectrograph-audio-workbench.ps1",
        ]
        for relative_path in [
            "docs/site/index.html",
            "docs/site/tutorial.html",
            "docs/site/api.html",
            "docs/site/architecture.html",
            "docs/site/testing.html",
            "docs/site/control-center.html",
            "docs/site/scene-studio.html",
            "docs/site/desktop-control-panel.html",
            "docs/site/spectrograph-suite.html",
            "docs/site/code-docs.html",
        ]:
            page_text = self._read_text(relative_path)
            for retired_term in retired_terms:
                self.assertNotIn(
                    retired_term, page_text, f"{relative_path} still contains {retired_term!r}"
                )

    def test_spectrograph_docs_expose_the_workbench_launcher(self) -> None:
        """The bar-wall docs should keep teaching the unified workbench launch path."""

        spectrograph_suite_text = self._read_text("docs/site/spectrograph-suite.html")
        self.assertIn(r".\scripts\launch-visualizer-workbench.ps1", spectrograph_suite_text)
        self.assertIn(r".\scripts\launch-visualizer-studio.ps1", spectrograph_suite_text)
        self.assertNotIn(r".\scripts\launch-halcyn-spectrograph-app.ps1", spectrograph_suite_text)
        self.assertNotIn(
            r".\scripts\launch-spectrograph-audio-workbench.ps1",
            spectrograph_suite_text,
        )

    def test_docs_site_keeps_full_docs_map_links(self) -> None:
        """Every docs page should expose the same core navigation destinations."""

        expected_doc_links = {
            "index.html",
            "tutorial.html",
            "api.html",
            "architecture.html",
            "testing.html",
            "code-docs.html",
            "field-reference.html",
            "control-center.html",
            "scene-studio.html",
            "desktop-control-panel.html",
            "spectrograph-suite.html",
        }

        for relative_path in [
            "docs/site/index.html",
            "docs/site/tutorial.html",
            "docs/site/api.html",
            "docs/site/architecture.html",
            "docs/site/testing.html",
            "docs/site/code-docs.html",
            "docs/site/field-reference.html",
            "docs/site/control-center.html",
            "docs/site/scene-studio.html",
            "docs/site/desktop-control-panel.html",
            "docs/site/spectrograph-suite.html",
        ]:
            parser = self._parse_html(relative_path)
            missing_doc_links = sorted(expected_doc_links - parser.hrefs)
            self.assertFalse(
                missing_doc_links,
                f"{relative_path} is missing docs map links: {missing_doc_links}",
            )

    def test_docs_site_avoids_root_relative_runtime_links(self) -> None:
        """GitHub Pages docs should not pretend the live local tools exist at the site root."""

        for relative_path in [
            "docs/site/index.html",
            "docs/site/tutorial.html",
            "docs/site/api.html",
            "docs/site/architecture.html",
            "docs/site/testing.html",
            "docs/site/code-docs.html",
            "docs/site/field-reference.html",
            "docs/site/control-center.html",
            "docs/site/scene-studio.html",
            "docs/site/desktop-control-panel.html",
            "docs/site/spectrograph-suite.html",
        ]:
            parser = self._parse_html(relative_path)
            root_relative_links = sorted(href for href in parser.hrefs if href.startswith("/"))
            self.assertFalse(
                root_relative_links,
                (
                    f"{relative_path} contains root-relative links that break on "
                    f"GitHub Pages: {root_relative_links}"
                ),
            )

    def test_docs_overview_links_to_the_repository_readme_not_a_local_markdown_path(self) -> None:
        """The docs overview should point to a real README URL when hosted statically."""

        overview_page_text = self._read_text("docs/site/index.html")
        self.assertIn(
            'href="https://github.com/gedrocht/Halcyn/blob/main/README.md"',
            overview_page_text,
        )
        self.assertNotIn('href="../../README.md"', overview_page_text)

    def test_docs_site_uses_browser_rendered_architecture_text(self) -> None:
        """The architecture page should be real HTML text, not an SVG diagram reference."""

        architecture_page_text = self._read_text("docs/site/architecture.html")
        self.assertNotIn("<svg", architecture_page_text.lower())
        self.assertFalse((self.project_root / "docs/site/assets/images/architecture.svg").exists())

    def test_codeql_workflow_keeps_dependency_builds_out_of_scope(self) -> None:
        """CodeQL should stay focused on repository-owned code.

        It should not scan fetched dependency builds instead.
        """

        workflow_text = self._read_text(".github/workflows/codeql.yml")
        self.assertIn("build-mode: none", workflow_text)
        self.assertNotIn("run: ./scripts/build-halcyn-app.ps1 -Configuration Debug", workflow_text)
