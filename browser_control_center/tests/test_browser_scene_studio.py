"""Tests for the Scene Studio browser surface and scene translator."""

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

from browser_control_center.control_center_http_server import (
    ControlCenterRequestHandler,
    create_control_center_server,
)
from browser_control_center.control_center_state import ControlCenterState
from browser_control_center.scene_studio_live_session import SceneStudioLiveSession
from browser_control_center.scene_studio_scene_builder import (
    build_catalog_payload,
    build_scene_bundle,
)


class SceneStudioGenerationTests(unittest.TestCase):
    """Exercise the pure Scene Studio scene generation helpers."""

    def test_catalog_exposes_presets_sources_and_defaults(self) -> None:
        """The browser should receive preset metadata without needing the live renderer."""

        payload = build_catalog_payload()
        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(len(payload["presets"]), 3)
        self.assertEqual(payload["defaults"]["presetId"], "aurora-orbit")
        self.assertEqual(payload["defaults"]["autoApplyMs"], 125)
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


class SceneStudioServerTests(unittest.TestCase):
    """Exercise the HTTP-facing Scene Studio routes."""

    project_root: ClassVar[Path]
    server: ClassVar[ThreadingHTTPServer]
    state: ClassVar[ControlCenterState]
    thread: ClassVar[threading.Thread]
    base_url: ClassVar[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[2]
        cls.server = create_control_center_server("127.0.0.1", 0, cls.project_root)
        handler_class = cast(type[ControlCenterRequestHandler], cls.server.RequestHandlerClass)
        cls.state = handler_class.state
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.state.stop_scene_studio_session()
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

    def test_client_route_serves_browser_scene_studio_html(self) -> None:
        """The dedicated Scene Studio surface should be reachable in the browser."""

        with urllib.request.urlopen(f"{self.base_url}/scene-studio/", timeout=5) as response:
            body = response.read().decode("utf-8")

        self.assertIn("Halcyn Scene Studio", body)

    def test_client_static_assets_are_served(self) -> None:
        """The Scene Studio HTML should be able to load its JS and CSS assets."""

        for path, expected_snippet in [
            ("/scene-studio/static/app.js", "function bootstrap()"),
            ("/scene-studio/static/styles.css", ".page-shell"),
        ]:
            with urllib.request.urlopen(f"{self.base_url}{path}", timeout=5) as response:
                body = response.read().decode("utf-8")

            self.assertIn(expected_snippet, body)

    def test_catalog_route_returns_preset_metadata(self) -> None:
        """The browser should be able to discover presets and supported signal sources."""

        with urllib.request.urlopen(
            f"{self.base_url}/api/scene-studio/catalog",
            timeout=5,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(len(payload["presets"]), 3)

    def test_session_status_route_returns_live_session_snapshot(self) -> None:
        """The browser should be able to inspect the live-session state."""

        with urllib.request.urlopen(
            f"{self.base_url}/api/scene-studio/session",
            timeout=5,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["status"], "ok")
        self.assertIn("session", payload)
        self.assertEqual(payload["session"]["status"], "stopped")

    def test_session_stream_route_emits_initial_snapshot_event(self) -> None:
        """The browser should be able to subscribe to session updates without polling."""

        with urllib.request.urlopen(
            f"{self.base_url}/api/scene-studio/session/stream",
            timeout=5,
        ) as response:
            self.assertEqual(response.headers.get_content_type(), "text/event-stream")
            event_line = response.readline().decode("utf-8").strip()
            data_line = response.readline().decode("utf-8").strip()

        self.assertEqual(event_line, "event: session")
        payload = json.loads(data_line.removeprefix("data: "))
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["session"]["status"], "stopped")

    def test_preview_route_returns_generated_scene_payload(self) -> None:
        """Preview requests should return generated scenes without requiring the native app."""

        status, payload = self._post_json(
            "/api/scene-studio/preview",
            {"presetId": "lattice-bloom", "signals": {"epochSeconds": 42.0}},
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["scene"]["sceneType"], "3d")

    def test_apply_route_submits_scene_once(self) -> None:
        """Apply requests should submit directly to the live Halcyn API."""

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
            return_value=submission_response,
        ) as patched:
            status, payload = self._post_json(
                "/api/scene-studio/apply",
                {"presetId": "aurora-orbit", "signals": {"epochSeconds": 77.0}},
            )

        self.assertEqual(status, 202)
        self.assertEqual(payload["status"], "applied")
        self.assertGreater(payload["networkBytes"], 0)
        patched.assert_called_once()
        self.assertEqual(patched.call_args.kwargs["path"], "/api/v1/scene")

    def test_apply_route_surfaces_validation_failures_from_submission(self) -> None:
        """The fast apply path should still expose renderer-side validation failures."""

        failed_submission = {
            "ok": False,
            "status": 400,
            "reason": "Bad Request",
            "body": '{"status":"invalid-request"}',
            "headers": {},
        }

        with mock.patch.object(
            self.state,
            "run_api_request",
            return_value=failed_submission,
        ):
            status, payload = self._post_json(
                "/api/scene-studio/apply",
                {"presetId": "aurora-orbit", "signals": {"epochSeconds": 12.0}},
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "validation-failed")
        self.assertEqual(payload["submission"]["status"], 400)

    def test_live_session_routes_forward_control_requests(self) -> None:
        """The live session routes should expose configure, start, and stop controls."""

        configured = {"status": "configured", "session": {"status": "stopped", "cadence_ms": 90}}
        accepted = {"status": "accepted", "session": {"status": "running", "cadence_ms": 90}}

        with mock.patch.object(
            self.state,
            "configure_scene_studio_session",
            return_value=configured,
        ):
            status, payload = self._post_json(
                "/api/scene-studio/session/configure",
                {"session": {"cadenceMs": 90}},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "configured")

        with mock.patch.object(self.state, "start_scene_studio_session", return_value=accepted):
            status, payload = self._post_json(
                "/api/scene-studio/session/start",
                {"session": {"cadenceMs": 90}},
            )
        self.assertEqual(status, 202)
        self.assertEqual(payload["session"]["status"], "running")

        with mock.patch.object(self.state, "stop_scene_studio_session", return_value=accepted):
            status, payload = self._post_json("/api/scene-studio/session/stop", {})
        self.assertEqual(status, 202)
        self.assertEqual(payload["status"], "accepted")


class SceneStudioLiveSessionTests(unittest.TestCase):
    """Exercise the long-running server-side live session in isolation."""

    def setUp(self) -> None:
        self.submissions: list[tuple[str, int, dict]] = []
        self.logs: list[tuple[str, str, str]] = []

        def apply_callback(host: str, port: int, scene_json: str) -> dict:
            self.submissions.append((host, port, json.loads(scene_json)))
            return {
                "ok": True,
                "status": 202,
                "reason": "Accepted",
                "body": "{}",
                "headers": {},
            }

        def log_callback(level: str, component: str, message: str) -> None:
            self.logs.append((level, component, message))

        self._log_callback = log_callback
        self.session = SceneStudioLiveSession(apply_callback, self._log_callback)

    def tearDown(self) -> None:
        self.session.close()

    def _wait_for(self, predicate, timeout_seconds: float = 2.0) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if predicate():
                return
            time.sleep(0.02)
        self.fail("Timed out waiting for the live session to update.")

    def test_configure_updates_snapshot_fields(self) -> None:
        """Configuring the session should update the visible preset, target, and cadence."""

        payload = self.session.configure(
            {
                "presetId": "comet-ribbon",
                "target": {"host": "127.0.0.1", "port": 9090},
                "session": {"cadenceMs": 85},
            }
        )

        self.assertEqual(payload["preset_id"], "comet-ribbon")
        self.assertEqual(payload["target_port"], 9090)
        self.assertEqual(payload["cadence_ms"], 85)

    def test_wait_for_update_returns_the_next_revision(self) -> None:
        """Waiting for updates should unblock when the session changes."""

        initial = self.session.snapshot()
        timer = threading.Timer(
            0.05,
            lambda: self.session.configure({"session": {"cadenceMs": 90}}),
        )
        timer.start()
        try:
            snapshot, changed = self.session.wait_for_update(
                initial["revision"],
                timeout_seconds=1.0,
            )
        finally:
            timer.join(timeout=1)

        self.assertTrue(changed)
        self.assertGreater(snapshot["revision"], initial["revision"])
        self.assertEqual(snapshot["cadence_ms"], 90)

    def test_start_streams_multiple_frames_until_stopped(self) -> None:
        """Starting the session should keep applying frames until it is explicitly stopped."""

        self.session.start({"session": {"cadenceMs": 40}})
        self._wait_for(lambda: self.session.snapshot()["frames_applied"] >= 2)
        snapshot = self.session.stop()

        self.assertGreaterEqual(snapshot["frames_applied"], 2)
        self.assertEqual(snapshot["status"], "stopped")
        self.assertGreaterEqual(len(self.submissions), 2)

    def test_failed_submissions_are_recorded(self) -> None:
        """Submission failures should surface in the session snapshot instead of disappearing."""

        def failing_callback(host: str, port: int, scene_json: str) -> dict:
            self.submissions.append((host, port, json.loads(scene_json)))
            return {
                "ok": False,
                "status": 400,
                "reason": "Bad Request",
                "body": '{"status":"invalid-request"}',
                "headers": {},
            }

        self.session.close()
        self.session = SceneStudioLiveSession(failing_callback, self._log_callback)
        self.session.start({"session": {"cadenceMs": 40}})
        self._wait_for(lambda: self.session.snapshot()["frames_failed"] >= 1)
        snapshot = self.session.stop()

        self.assertGreaterEqual(snapshot["frames_failed"], 1)
        self.assertEqual(snapshot["last_submission_status"], 400)

    def test_unhandled_frame_exceptions_surface_as_session_errors(self) -> None:
        """Unexpected frame exceptions should mark the live session as errored."""

        def exploding_callback(host: str, port: int, scene_json: str) -> dict:
            raise RuntimeError("boom")

        self.session.close()
        self.session = SceneStudioLiveSession(exploding_callback, self._log_callback)
        self.session.start({"session": {"cadenceMs": 40}})
        self._wait_for(lambda: self.session.snapshot()["status"] == "error")
        snapshot = self.session.snapshot()

        self.assertEqual(snapshot["status"], "error")
        self.assertEqual(snapshot["last_submission_reason"], "exception")
        self.assertIn("boom", snapshot["last_error"])
        self.assertTrue(any("crashed" in message for _, _, message in self.logs))

    def test_stop_reports_stopping_when_the_current_frame_has_not_finished_yet(self) -> None:
        """Stopping should stay honest if the active frame is still winding down."""

        release_frame = threading.Event()
        frame_started = threading.Event()

        def slow_callback(host: str, port: int, scene_json: str) -> dict:
            frame_started.set()
            release_frame.wait(timeout=0.5)
            return {
                "ok": True,
                "status": 202,
                "reason": "Accepted",
                "body": "{}",
                "headers": {},
            }

        self.session.close()
        self.session = SceneStudioLiveSession(
            slow_callback,
            self._log_callback,
            stop_join_timeout_seconds=0.01,
        )
        self.session.start({"session": {"cadenceMs": 40}})
        self.assertTrue(frame_started.wait(timeout=1.0))

        snapshot = self.session.stop()
        self.assertEqual(snapshot["status"], "stopping")
        self.assertTrue(any("still finishing" in message for _, _, message in self.logs))

        release_frame.set()
        self._wait_for(lambda: self.session.snapshot()["status"] == "stopped")


if __name__ == "__main__":
    unittest.main()
