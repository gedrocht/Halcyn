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
        """Extract the DOM ids a script expects to find at runtime."""

        return set(re.findall(r'getElementById\("([^"]+)"\)', self._read_text(relative_path)))

    def test_control_plane_html_and_js_ids_stay_in_sync(self) -> None:
        """The control-plane dashboard should not reference missing DOM ids."""

        html_ids = self._parse_html("control_plane/static/index.html").ids
        js_ids = self._js_element_ids("control_plane/static/app.js")
        self.assertFalse(
            js_ids - html_ids,
            f"Missing control-plane HTML ids for JS bindings: {sorted(js_ids - html_ids)}",
        )

    def test_client_studio_html_and_js_ids_stay_in_sync(self) -> None:
        """The client-studio frontend should not reference missing DOM ids."""

        html_ids = self._parse_html("client_studio/static/index.html").ids
        js_ids = self._js_element_ids("client_studio/static/app.js")
        self.assertFalse(
            js_ids - html_ids,
            f"Missing client-studio HTML ids for JS bindings: {sorted(js_ids - html_ids)}",
        )

    def test_control_plane_dashboard_links_to_client_studio(self) -> None:
        """The dashboard should keep its launch path to the client studio visible."""

        parser = self._parse_html("control_plane/static/index.html")
        self.assertIn("/client/", parser.hrefs)

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
