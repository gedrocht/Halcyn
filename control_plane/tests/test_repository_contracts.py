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

        element_identifier = attributes.get("id")
        if element_identifier:
            self.ids.add(element_identifier)

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
        """Extract the DOM ids a script expects to find at runtime."""

        return set(re.findall(r'getElementById\("([^"]+)"\)', self._read_text(relative_path)))

    def test_control_plane_html_and_js_ids_stay_in_sync(self) -> None:
        """The control-plane dashboard should not reference missing DOM ids."""

        html_element_identifiers = self._parse_html("control_plane/static/index.html").ids
        javascript_element_identifiers = self._js_element_ids("control_plane/static/app.js")
        self.assertFalse(
            javascript_element_identifiers - html_element_identifiers,
            "Missing control-plane HTML ids for JS bindings: "
            f"{sorted(javascript_element_identifiers - html_element_identifiers)}",
        )

    def test_client_studio_html_and_js_ids_stay_in_sync(self) -> None:
        """The client-studio frontend should not reference missing DOM ids."""

        html_element_identifiers = self._parse_html("client_studio/static/index.html").ids
        javascript_element_identifiers = self._js_element_ids("client_studio/static/app.js")
        self.assertFalse(
            javascript_element_identifiers - html_element_identifiers,
            "Missing client-studio HTML ids for JS bindings: "
            f"{sorted(javascript_element_identifiers - html_element_identifiers)}",
        )

    def test_control_plane_dashboard_links_to_client_studio(self) -> None:
        """The dashboard should keep its launch path to the client studio visible."""

        parser = self._parse_html("control_plane/static/index.html")
        self.assertIn("/client/", parser.hrefs)

    def test_docs_site_avoids_hardcoded_local_ports(self) -> None:
        """Docs should describe routes without assuming one specific localhost port."""

        hardcoded_localhost_references: list[str] = []
        for docs_page in (self.project_root / "docs" / "site").glob("*.html"):
            page_text = docs_page.read_text(encoding="utf-8")
            if "127.0.0.1:9001" in page_text:
                hardcoded_localhost_references.append(docs_page.name)

        self.assertFalse(
            hardcoded_localhost_references,
            "Docs pages still hardcode the default control-plane port: "
            f"{hardcoded_localhost_references}",
        )

    def test_architecture_page_uses_html_layout_instead_of_svg_text(self) -> None:
        """The architecture docs should rely on normal HTML text instead of SVG text rendering."""

        architecture_page = self._read_text("docs/site/architecture.html")
        self.assertNotIn("architecture.svg", architecture_page)
        self.assertIn("architecture-flow", architecture_page)

    def test_generated_code_docs_reflect_current_renderer_member_names(self) -> None:
        """Tracked generated code docs should stay aligned with the renamed renderer members."""

        generated_renderer_reference_path = (
            self.project_root
            / "docs"
            / "generated"
            / "code-reference"
            / "_Renderer_8hpp_source.html"
        )
        if not generated_renderer_reference_path.exists():
            self.skipTest("Generated code docs are not present in this environment.")

        generated_renderer_reference = generated_renderer_reference_path.read_text(
            encoding="utf-8"
        )
        self.assertIn("vertexArrayObjectHandle_", generated_renderer_reference)
        self.assertIn("vertexBufferObjectHandle_", generated_renderer_reference)
        self.assertIn("elementBufferObjectHandle_", generated_renderer_reference)
        self.assertNotIn(">vao_<", generated_renderer_reference)
        self.assertNotIn(">vbo_<", generated_renderer_reference)
        self.assertNotIn(">ebo_<", generated_renderer_reference)

    def test_runtime_and_run_script_stay_in_api_host_sync(self) -> None:
        """The runtime should keep using the current run.ps1 ApiHost parameter name."""

        runtime_text = self._read_text("control_plane/runtime.py")
        run_script = self._read_text("scripts/run.ps1")

        self.assertIn('[string]$ApiHost = \'127.0.0.1\'', run_script)
        self.assertIn('"-ApiHost"', runtime_text)
        self.assertNotIn('"-Host"', runtime_text)

    def test_control_plane_launchers_use_shared_project_root_helper(self) -> None:
        """The browser launchers should source common.ps1 and use the shared root helper."""

        for relative_path in ["scripts/studio.ps1", "scripts/client-studio.ps1"]:
            script_text = self._read_text(relative_path)
            self.assertIn(". (Join-Path $PSScriptRoot 'common.ps1')", script_text)
            self.assertIn("$projectRoot = Get-ProjectRoot", script_text)
            self.assertIn("'--project-root'", script_text)

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
