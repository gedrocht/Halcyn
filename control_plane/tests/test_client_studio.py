"""Tests for the Client Studio browser surface and scene translator."""

from __future__ import annotations

import json
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar, cast
from unittest import mock

from control_plane.client_studio import build_catalog_payload, build_scene_bundle
from control_plane.runtime import ControlPlaneState
from control_plane.server import ControlPlaneRequestHandler, create_server


class ClientStudioGenerationTests(unittest.TestCase):
    """Exercise the pure client-studio scene generation helpers."""

    def test_catalog_exposes_presets_sources_and_defaults(self) -> None:
        """The browser should receive preset metadata without needing the live renderer."""

        payload = build_catalog_payload()
        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(len(payload["presets"]), 3)
        self.assertEqual(payload["defaults"]["presetId"], "aurora-orbit")
        self.assertTrue(any(source["id"] == "audio" for source in payload["sources"]))

    def test_scene_bundle_generates_a_valid_default_scene(self) -> None:
        """The default preset should always produce a 3D scene with vertices."""

        bundle = build_scene_bundle({"signals": {"epochSeconds": 1234.5}})
        self.assertEqual(bundle["status"], "ok")
        self.assertEqual(bundle["scene"]["sceneType"], "3d")
        self.assertEqual(bundle["scene"]["primitive"], "points")
        self.assertGreater(len(bundle["scene"]["vertices"]), 0)
        self.assertIn("manual", bundle["analysis"]["activeSources"])

    def test_comet_ribbon_uses_lines_and_even_vertex_pairs(self) -> None:
        """The ribbon preset should emit line segments in start/end pairs."""

        bundle = build_scene_bundle(
            {
                "presetId": "comet-ribbon",
                "settings": {"density": 48},
                "signals": {"epochSeconds": 50.0, "usePointer": False, "useAudio": False},
            }
        )

        self.assertEqual(bundle["scene"]["primitive"], "lines")
        self.assertEqual(len(bundle["scene"]["vertices"]) % 2, 0)

    def test_disabled_sources_fall_back_to_safe_neutral_values(self) -> None:
        """Turning off pointer and audio sources should not leave stale browser values active."""

        bundle = build_scene_bundle(
            {
                "signals": {
                    "epochSeconds": 8.0,
                    "usePointer": False,
                    "useAudio": False,
                    "pointer": {"x": 0.9, "y": 0.1, "speed": 1.0},
                    "audio": {"level": 1.0, "bass": 1.0, "mid": 1.0, "treble": 1.0},
                }
            }
        )

        self.assertEqual(bundle["signals"]["pointerX"], 0.5)
        self.assertEqual(bundle["signals"]["pointerY"], 0.5)
        self.assertEqual(bundle["signals"]["audioLevel"], 0.0)


class ClientStudioServerTests(unittest.TestCase):
    """Exercise the HTTP-facing Client Studio routes."""

    project_root: ClassVar[Path]
    server: ClassVar[ThreadingHTTPServer]
    state: ClassVar[ControlPlaneState]
    thread: ClassVar[threading.Thread]
    base_url: ClassVar[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[2]
        cls.server = create_server("127.0.0.1", 0, cls.project_root)
        handler_class = cast(type[ControlPlaneRequestHandler], cls.server.RequestHandlerClass)
        cls.state = handler_class.state
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def _post_json(self, path: str, payload: object) -> tuple[int, dict]:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_client_route_serves_client_studio_html(self) -> None:
        """The dedicated client-studio surface should be reachable in the browser."""

        with urllib.request.urlopen(f"{self.base_url}/client/", timeout=5) as response:
            body = response.read().decode("utf-8")

        self.assertIn("Halcyn Client Studio", body)

    def test_catalog_route_returns_preset_metadata(self) -> None:
        """The browser should be able to discover presets and supported signal sources."""

        with urllib.request.urlopen(
            f"{self.base_url}/api/client-studio/catalog",
            timeout=5,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(len(payload["presets"]), 3)

    def test_preview_route_returns_generated_scene_payload(self) -> None:
        """Preview requests should return generated scenes without requiring the native app."""

        status, payload = self._post_json(
            "/api/client-studio/preview",
            {"presetId": "lattice-bloom", "signals": {"epochSeconds": 42.0}},
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["scene"]["sceneType"], "3d")

    def test_apply_route_validates_then_submits_scene(self) -> None:
        """Apply requests should validate before they submit into the live Halcyn API."""

        validation_response = {
            "ok": True,
            "status": 200,
            "reason": "OK",
            "body": "{}",
            "headers": {},
        }
        submission_response = {
            "ok": True,
            "status": 202,
            "reason": "Accepted",
            "body": "{}",
            "headers": {},
        }

        with mock.patch.object(
            self.state,
            "run_api_request",
            side_effect=[validation_response, submission_response],
        ) as patched:
            status, payload = self._post_json(
                "/api/client-studio/apply",
                {"presetId": "aurora-orbit", "signals": {"epochSeconds": 77.0}},
            )

        self.assertEqual(status, 202)
        self.assertEqual(payload["status"], "applied")
        self.assertEqual(patched.call_count, 2)
        self.assertEqual(patched.call_args_list[0].kwargs["path"], "/api/v1/scene/validate")
        self.assertEqual(patched.call_args_list[1].kwargs["path"], "/api/v1/scene")


if __name__ == "__main__":
    unittest.main()
