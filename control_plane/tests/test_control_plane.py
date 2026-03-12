"""Tests for the Halcyn browser-based control plane."""

from __future__ import annotations

from pathlib import Path
import json
import threading
import time
import unittest
import urllib.request

from control_plane.runtime import ControlPlaneState
from control_plane.server import create_server


class ControlPlaneServerTests(unittest.TestCase):
    """Exercise the HTTP surface of the control plane without needing the C++ toolchain."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[2]
        cls.server = create_server("127.0.0.1", 0, cls.project_root)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_root_serves_html(self) -> None:
        """The browser entry page should be reachable."""

        with urllib.request.urlopen(f"{self.base_url}/", timeout=5) as response:
            body = response.read().decode("utf-8")

        self.assertIn("Halcyn Control Plane", body)

    def test_summary_endpoint_returns_expected_sections(self) -> None:
        """The dashboard summary should return tools, docs, jobs, and app state."""

        with urllib.request.urlopen(f"{self.base_url}/api/system/summary", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["status"], "ok")
        self.assertIn("tools", payload)
        self.assertIn("docs", payload)
        self.assertIn("app", payload)
        self.assertIn("jobs", payload)


class ControlPlaneStateTests(unittest.TestCase):
    """Exercise the testable control-plane runtime logic directly."""

    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[2]
        self.state = ControlPlaneState(self.project_root)

    def test_run_api_request_reports_connection_errors_cleanly(self) -> None:
        """API proxy failures should return a browser-friendly error payload instead of raising."""

        response = self.state.run_api_request(
            host="127.0.0.1",
            port=65534,
            method="GET",
            path="/api/v1/health",
            body="",
            content_type="application/json",
        )

        self.assertFalse(response["ok"])
        self.assertEqual(response["status"], 0)


if __name__ == "__main__":
    unittest.main()

