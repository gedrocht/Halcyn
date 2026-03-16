"""Tests for the native desktop render control panel."""

from __future__ import annotations

import json
import runpy
import threading
import time
import tkinter as tk
import unittest
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import mock

from desktop_render_control_panel.audio_input_service import (
    AudioDeviceDescriptor,
    AudioSignalSnapshot,
    DesktopAudioInputService,
    SoundDeviceAudioCaptureBackend,
    UnavailableAudioCaptureBackend,
    WindowsWaveInListingBackend,
    analyze_audio_frames,
    create_default_audio_capture_backend,
)
from desktop_render_control_panel.desktop_control_panel_controller import (
    DesktopRenderControlPanelController,
    _clamp_float,
    _clamp_int,
    _deep_merge,
)
from desktop_render_control_panel.desktop_control_panel_window import (
    DesktopRenderControlPanelWindow,
)
from desktop_render_control_panel.desktop_control_scene_builder import (
    build_catalog_payload,
    build_default_request_payload,
    build_scene_bundle,
)
from desktop_render_control_panel.render_api_client import RenderApiClient, RenderApiResponse


class SceneBuilderTests(unittest.TestCase):
    """Exercise the scene generation helpers behind the desktop control panel."""

    def test_catalog_exposes_both_two_dimensional_and_three_dimensional_presets(self) -> None:
        payload = build_catalog_payload()
        scene_types = {preset["sceneType"] for preset in payload["presets"]}
        self.assertEqual(payload["status"], "ok")
        self.assertIn("2d", scene_types)
        self.assertIn("3d", scene_types)

    def test_default_payload_uses_a_full_editable_structure(self) -> None:
        payload = build_default_request_payload()
        self.assertEqual(payload["presetId"], "signal-weave-2d")
        self.assertIn("target", payload)
        self.assertIn("settings", payload)
        self.assertIn("signals", payload)
        self.assertIn("session", payload)

    def test_two_dimensional_preset_generates_a_two_dimensional_scene(self) -> None:
        bundle = build_scene_bundle(
            {
                "presetId": "pulse-grid-2d",
                "signals": {"epochSeconds": 5.0, "useAudio": False, "usePointer": False},
            }
        )

        self.assertEqual(bundle["scene"]["sceneType"], "2d")
        self.assertEqual(bundle["scene"]["primitive"], "points")
        self.assertGreater(len(bundle["scene"]["vertices"]), 0)

    def test_three_dimensional_browser_preset_is_still_available(self) -> None:
        bundle = build_scene_bundle(
            {
                "presetId": "aurora-orbit",
                "signals": {"epochSeconds": 5.0, "useAudio": False},
            }
        )

        self.assertEqual(bundle["scene"]["sceneType"], "3d")
        self.assertEqual(bundle["preset"]["sceneType"], "3d")
        self.assertGreater(len(bundle["scene"]["vertices"]), 0)


class AudioAnalysisTests(unittest.TestCase):
    """Exercise the signal-extraction helpers without needing real hardware."""

    def test_silence_produces_zero_levels(self) -> None:
        snapshot = analyze_audio_frames(
            [[0.0], [0.0], [0.0], [0.0]],
            sample_rate=48_000,
            device_identifier="mic-1",
            device_name="Test microphone",
            backend_name="fake",
            capturing=True,
        )

        self.assertEqual(snapshot.level, 0.0)
        self.assertEqual(snapshot.bass, 0.0)
        self.assertEqual(snapshot.mid, 0.0)
        self.assertEqual(snapshot.treble, 0.0)

    def test_waveform_generates_nonzero_signal_levels(self) -> None:
        waveform = [[0.8], [0.2], [-0.8], [-0.2]] * 40
        snapshot = analyze_audio_frames(
            waveform,
            sample_rate=8_000,
            device_identifier="mic-1",
            device_name="Test microphone",
            backend_name="fake",
            capturing=True,
        )

        self.assertGreater(snapshot.level, 0.0)
        self.assertGreaterEqual(snapshot.bass + snapshot.mid + snapshot.treble, 0.0)

    def test_unavailable_backend_exposes_the_reason_cleanly(self) -> None:
        backend = UnavailableAudioCaptureBackend("missing dependency")
        self.assertEqual(backend.backend_name, "unavailable")
        self.assertEqual(backend.availability_error, "missing dependency")
        self.assertEqual(backend.list_input_devices(), [])

    def test_short_or_mixed_frames_are_handled_without_crashing(self) -> None:
        snapshot = analyze_audio_frames(
            [0.5, ["bad", 0.5], object(), [0.25, -0.25]],
            sample_rate=48_000,
            device_identifier="mic-1",
            device_name="Test microphone",
            backend_name="fake",
            capturing=True,
        )

        self.assertGreaterEqual(snapshot.level, 0.0)
        self.assertEqual(snapshot.device_name, "Test microphone")


class AudioServiceTests(unittest.TestCase):
    """Exercise the optional audio backend integration and high-level service."""

    def test_audio_service_wraps_a_fake_backend(self) -> None:
        class FakeBackend:
            backend_name = "fake"
            availability_error = ""
            capture_available = True

            def __init__(self) -> None:
                self.snapshot_callback: Any | None = None

            def list_input_devices(self) -> list[AudioDeviceDescriptor]:
                return [
                    AudioDeviceDescriptor(
                        device_identifier="device-1",
                        name="Loopback device",
                        max_input_channels=2,
                        default_sample_rate=48_000,
                    )
                ]

            def open_input_stream(self, device_identifier: str, on_snapshot: Any) -> Any:
                self.snapshot_callback = on_snapshot
                return lambda: None

        backend = FakeBackend()
        service = DesktopAudioInputService(backend=backend)
        self.assertEqual(len(service.refresh_devices()), 1)
        started_snapshot = service.start_capture("device-1")
        self.assertIsNotNone(backend.snapshot_callback)
        snapshot_callback = backend.snapshot_callback
        assert snapshot_callback is not None
        snapshot_callback(
            AudioSignalSnapshot(
                backend_name="fake",
                device_identifier="device-1",
                device_name="Loopback device",
                available=True,
                capturing=True,
                level=0.7,
                bass=0.6,
                mid=0.2,
                treble=0.2,
            )
        )
        self.assertTrue(started_snapshot.capturing)
        self.assertGreater(service.snapshot().level, 0.0)
        stopped_snapshot = service.stop_capture()
        self.assertFalse(stopped_snapshot.capturing)

    def test_sounddevice_backend_uses_the_mocked_module(self) -> None:
        class FakeInputStream:
            def __init__(self, **kwargs: Any) -> None:
                self.callback = kwargs["callback"]
                self.started = False

            def start(self) -> None:
                self.started = True
                self.callback([[0.3], [0.2], [-0.3], [-0.2]], 4, None, "")

            def stop(self) -> None:
                self.started = False

            def close(self) -> None:
                self.started = False

        class FakeSoundDeviceModule:
            def query_hostapis(self) -> Any:
                return [{"name": "WASAPI"}]

            def query_devices(self, device_index: Any = None, kind: str | None = None) -> Any:
                if device_index is None:
                    return [
                        {
                            "name": "Loopback device",
                            "max_input_channels": 2,
                            "default_samplerate": 48_000,
                            "hostapi": 0,
                        }
                    ]
                return {
                    "name": "Loopback device",
                    "max_input_channels": 2,
                    "default_samplerate": 48_000,
                }

            InputStream = FakeInputStream

        with mock.patch(
            "desktop_render_control_panel.audio_input_service.importlib.import_module",
            return_value=FakeSoundDeviceModule(),
        ):
            backend = SoundDeviceAudioCaptureBackend()

        snapshots: list[AudioSignalSnapshot] = []
        devices = backend.list_input_devices()
        self.assertEqual(devices[0].name, "Loopback device (WASAPI)")
        stop_callback = backend.open_input_stream("0", snapshots.append)
        self.assertGreater(snapshots[0].level, 0.0)
        stop_callback()

    def test_audio_service_reports_backend_unavailability_and_safe_stop(self) -> None:
        service = DesktopAudioInputService(
            backend=UnavailableAudioCaptureBackend("install sounddevice")
        )

        refreshed_devices = service.refresh_devices()
        stopped_snapshot = service.stop_capture()

        self.assertEqual(refreshed_devices, [])
        self.assertFalse(stopped_snapshot.capturing)
        self.assertEqual(stopped_snapshot.last_error, "install sounddevice")

    def test_create_default_backend_prefers_windows_listing_when_sounddevice_is_missing(
        self,
    ) -> None:
        with mock.patch(
            "desktop_render_control_panel.audio_input_service.importlib.import_module",
            side_effect=ImportError("missing"),
        ), mock.patch(
            "desktop_render_control_panel.audio_input_service.WindowsWaveInListingBackend.list_input_devices",
            return_value=[
                AudioDeviceDescriptor(
                    device_identifier="winmm:0",
                    name="Microphone Array",
                    max_input_channels=2,
                    default_sample_rate=44_100,
                )
            ],
        ):
            backend = create_default_audio_capture_backend()

        self.assertIsInstance(backend, WindowsWaveInListingBackend)

    def test_create_default_backend_uses_unavailable_backend_when_no_listing_fallback_exists(
        self,
    ) -> None:
        with mock.patch(
            "desktop_render_control_panel.audio_input_service.importlib.import_module",
            side_effect=ImportError("missing"),
        ), mock.patch(
            "desktop_render_control_panel.audio_input_service.WindowsWaveInListingBackend.list_input_devices",
            return_value=[],
        ):
            backend = create_default_audio_capture_backend()

        self.assertIsInstance(backend, UnavailableAudioCaptureBackend)


class RenderApiClientTests(unittest.TestCase):
    """Exercise the HTTP client with a tiny in-process test server."""

    def setUp(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def _drain_request_body(self) -> None:
                """Consume any request body bytes before sending a response.

                Some HTTP stacks behave poorly if the handler replies to a POST
                without reading the advertised payload first. Draining the body
                keeps this tiny test server deterministic across machines.
                """

                content_length = int(self.headers.get("Content-Length", "0") or 0)
                if content_length > 0:
                    self.rfile.read(content_length)

            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/api/v1/health":
                    payload = json.dumps({"status": "ok"}).encode("utf-8")
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                self.send_error(HTTPStatus.NOT_FOUND, "missing")

            def do_POST(self) -> None:  # noqa: N802
                self._drain_request_body()
                if self.path == "/api/v1/scene/validate":
                    payload = json.dumps({"status": "valid"}).encode("utf-8")
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                if self.path == "/api/v1/scene":
                    payload = json.dumps({"status": "accepted"}).encode("utf-8")
                    self.send_response(HTTPStatus.ACCEPTED)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                self.send_error(HTTPStatus.BAD_REQUEST, "bad")

            def log_message(self, format: str, *args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]
        self.client = RenderApiClient()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_render_api_client_covers_health_validate_and_apply(self) -> None:
        health = self.client.health("127.0.0.1", self.port)
        validated = self.client.validate_scene("127.0.0.1", self.port, "{}")
        applied = self.client.apply_scene("127.0.0.1", self.port, "{}")

        self.assertEqual(health.status, 200)
        self.assertEqual(health.body_as_json(), {"status": "ok"})
        self.assertEqual(validated.status, 200)
        self.assertEqual(applied.status, 202)

    def test_render_api_client_reports_connection_errors(self) -> None:
        response = self.client.health("127.0.0.1", 1)
        self.assertEqual(response.status, 0)
        self.assertEqual(response.reason, "connection-error")

    def test_render_api_client_handles_http_errors_and_json_helpers(self) -> None:
        missing = self.client.request(
            host="127.0.0.1",
            port=self.port,
            method="GET",
            request_path="missing",
        )

        self.assertFalse(missing.ok)
        self.assertEqual(missing.status, 404)
        self.assertIsNone(RenderApiResponse(True, 200, "OK", "", {}).body_as_json())
        self.assertIsNone(RenderApiResponse(True, 200, "OK", "{bad json", {}).body_as_json())
        self.assertEqual(
            RenderApiResponse(True, 200, "OK", '"value"', {}).body_as_json(),
            {"value": "value"},
        )


@dataclass
class FakeAudioService:
    """Simple fake audio service used by the controller tests."""

    current_snapshot: AudioSignalSnapshot = AudioSignalSnapshot(
        backend_name="fake",
        available=True,
        capturing=False,
    )

    def __post_init__(self) -> None:
        self._devices = [
            AudioDeviceDescriptor(
                device_identifier="device-1",
                name="Loopback device",
                max_input_channels=2,
                default_sample_rate=48_000,
            )
        ]

    def devices(self) -> list[AudioDeviceDescriptor]:
        return list(self._devices)

    def refresh_devices(self) -> list[AudioDeviceDescriptor]:
        return list(self._devices)

    def snapshot(self) -> AudioSignalSnapshot:
        return AudioSignalSnapshot(**self.current_snapshot.to_dict())

    def start_capture(self, device_identifier: str) -> AudioSignalSnapshot:
        self.current_snapshot = AudioSignalSnapshot(
            backend_name="fake",
            device_identifier=device_identifier,
            device_name="Loopback device",
            available=True,
            capturing=True,
            level=0.65,
            bass=0.55,
            mid=0.3,
            treble=0.15,
        )
        return self.snapshot()

    def stop_capture(self) -> AudioSignalSnapshot:
        self.current_snapshot.capturing = False
        return self.snapshot()

    def close(self) -> None:
        self.current_snapshot.capturing = False


class FakeRenderApiClient:
    """Collect outgoing API calls without needing a live renderer."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str, int, str]] = []
        self.health_response = RenderApiResponse(
            ok=True,
            status=200,
            reason="OK",
            body="{}",
            headers={},
        )
        self.validate_response = RenderApiResponse(
            ok=True,
            status=200,
            reason="OK",
            body="{}",
            headers={},
        )
        self.apply_response = RenderApiResponse(
            ok=True,
            status=202,
            reason="Accepted",
            body="{}",
            headers={},
        )
        self.raise_on_apply: RuntimeError | None = None

    def health(self, host: str, port: int) -> RenderApiResponse:
        self.requests.append(("health", host, port, ""))
        return self.health_response

    def validate_scene(self, host: str, port: int, scene_json: str) -> RenderApiResponse:
        self.requests.append(("validate", host, port, scene_json))
        return self.validate_response

    def apply_scene(self, host: str, port: int, scene_json: str) -> RenderApiResponse:
        self.requests.append(("apply", host, port, scene_json))
        if self.raise_on_apply is not None:
            raise self.raise_on_apply
        return self.apply_response


class DesktopControllerTests(unittest.TestCase):
    """Exercise the non-visual controller behind the desktop window."""

    def setUp(self) -> None:
        self.fake_api_client = FakeRenderApiClient()
        self.fake_audio_service = FakeAudioService()
        self.controller = DesktopRenderControlPanelController(
            render_api_client=self.fake_api_client,
            audio_input_service=self.fake_audio_service,
        )

    def tearDown(self) -> None:
        self.controller.close()

    def test_load_preset_preserves_target_and_session(self) -> None:
        self.controller.update_request_payload(
            {
                "target": {"host": "192.168.1.80", "port": 9090},
                "session": {"cadenceMs": 80},
            }
        )
        payload = self.controller.load_preset("aurora-orbit")

        self.assertEqual(payload["target"]["host"], "192.168.1.80")
        self.assertEqual(payload["target"]["port"], 9090)
        self.assertEqual(payload["session"]["cadenceMs"], 80)
        self.assertEqual(payload["presetId"], "aurora-orbit")

    def test_reset_current_preset_to_defaults_preserves_target_and_session(self) -> None:
        self.controller.update_request_payload(
            {
                "target": {"host": "10.0.0.5", "port": 9010},
                "session": {"cadenceMs": 60},
                "settings": {"density": 200, "gain": 2.0},
            }
        )

        payload = self.controller.reset_current_preset_to_defaults()

        self.assertEqual(payload["target"]["host"], "10.0.0.5")
        self.assertEqual(payload["session"]["cadenceMs"], 60)
        self.assertEqual(payload["settings"]["density"], 96)

    def test_settings_documents_can_round_trip_through_the_controller(self) -> None:
        self.controller.update_request_payload(
            {
                "presetId": "pulse-grid-2d",
                "settings": {"gain": 1.75},
                "signals": {"useAudio": True},
            }
        )

        saved_document = self.controller.settings_document()
        restored_payload = self.controller.load_settings_document(saved_document)

        self.assertEqual(saved_document["formatVersion"], 1)
        self.assertEqual(restored_payload["presetId"], "pulse-grid-2d")
        self.assertTrue(restored_payload["signals"]["useAudio"])

    def test_validate_current_scene_calls_validation_route(self) -> None:
        validation_result = self.controller.validate_current_scene()

        self.assertEqual(validation_result["status"], "validated")
        self.assertEqual(self.fake_api_client.requests[-1][0], "validate")

    def test_apply_current_scene_calls_apply_route(self) -> None:
        apply_result = self.controller.apply_current_scene()

        self.assertEqual(apply_result["status"], "applied")
        self.assertEqual(self.fake_api_client.requests[-1][0], "apply")

    def test_pointer_and_audio_updates_flow_into_preview_bundle(self) -> None:
        self.controller.start_audio_capture("device-1")
        self.controller.update_pointer_signal(0.9, 0.1, 0.5)
        self.controller.update_request_payload({"signals": {"useAudio": True}})
        preview_bundle = self.controller.preview_scene_bundle()

        self.assertGreater(preview_bundle["signals"]["audioLevel"], 0.0)
        self.assertAlmostEqual(preview_bundle["signals"]["pointerX"], 0.9)
        self.assertAlmostEqual(preview_bundle["signals"]["pointerY"], 0.1)

    def test_live_stream_applies_multiple_frames_until_stopped(self) -> None:
        self.controller.update_request_payload({"session": {"cadenceMs": 40}})
        self.controller.start_live_stream()
        self._wait_for(lambda: self.controller.live_stream_snapshot()["frames_applied"] >= 2)
        live_snapshot = self.controller.stop_live_stream()

        self.assertGreaterEqual(live_snapshot["frames_applied"], 2)
        self.assertIn("apply", [request[0] for request in self.fake_api_client.requests])

    def test_health_check_uses_the_api_client(self) -> None:
        response = self.controller.health_check()
        self.assertEqual(response.status, 200)
        self.assertEqual(self.fake_api_client.requests[-1][0], "health")

    def test_helper_functions_clamp_and_merge_values_safely(self) -> None:
        merged_payload = {"settings": {"density": 96}}
        _deep_merge(merged_payload, {"settings": {"gain": 1.5}, "session": {"cadenceMs": 20}})

        self.assertEqual(merged_payload["settings"]["density"], 96)
        self.assertEqual(merged_payload["settings"]["gain"], 1.5)
        self.assertEqual(_clamp_float("bad", 1.5, 0.0, 2.0), 1.5)
        self.assertEqual(_clamp_float(8.0, 1.5, 0.0, 2.0), 2.0)
        self.assertEqual(_clamp_int("bad", 125, 40, 1000), 125)
        self.assertEqual(_clamp_int(5, 125, 40, 1000), 40)

    def test_controller_exposes_offline_and_validation_failures(self) -> None:
        self.fake_api_client.validate_response = RenderApiResponse(
            ok=False,
            status=400,
            reason="Bad Request",
            body="invalid",
            headers={},
        )
        self.fake_api_client.apply_response = RenderApiResponse(
            ok=False,
            status=0,
            reason="connection-error",
            body="offline",
            headers={},
        )

        validation_result = self.controller.validate_current_scene()
        apply_result = self.controller.apply_current_scene()

        self.assertEqual(validation_result["status"], "validation-failed")
        self.assertEqual(apply_result["status"], "offline")

    def test_live_stream_can_report_internal_errors(self) -> None:
        self.fake_api_client.raise_on_apply = RuntimeError("boom")

        self.controller.start_live_stream()
        self._wait_for(lambda: self.controller.live_stream_snapshot()["status"] == "error")

        live_snapshot = self.controller.live_stream_snapshot()
        self.assertEqual(live_snapshot["status"], "error")
        self.assertIn("boom", live_snapshot["last_error"])

    def test_stop_live_stream_is_safe_when_already_stopped(self) -> None:
        live_snapshot = self.controller.stop_live_stream()
        self.assertEqual(live_snapshot["status"], "stopped")

    def _wait_for(self, predicate: Any, timeout_seconds: float = 2.0) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if predicate():
                return
            time.sleep(0.02)
        self.fail("Timed out waiting for the controller to reach the expected state.")


@unittest.skipIf(not hasattr(tk, "Tk"), "Tkinter is not available in this environment.")
class DesktopWindowTests(unittest.TestCase):
    """Exercise the native window in a hidden, headless-friendly way."""

    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.fake_api_client = FakeRenderApiClient()
        self.controller = DesktopRenderControlPanelController(
            render_api_client=self.fake_api_client,
            audio_input_service=FakeAudioService(),
        )
        self.window = DesktopRenderControlPanelWindow(self.root, controller=self.controller)
        self.root.update_idletasks()

    def tearDown(self) -> None:
        try:
            if self.root.winfo_exists():
                self.window._on_close_requested()
            if self.root.winfo_exists():
                self.root.update_idletasks()
        except tk.TclError:
            pass

    def test_window_builds_and_can_switch_scene_type(self) -> None:
        self.window._scene_type_variable.set("3d")
        self.window._on_scene_type_changed()
        self.root.update_idletasks()

        preset_button_labels = [
            button.cget("text") for button in self.window._preset_button_widgets.values()
        ]
        self.assertIn("Aurora Orbit", preset_button_labels)
        self.assertEqual(
            self.window._scene_type_button_widgets["3d"].cget("foreground"),
            "#04131d",
        )
        self.assertEqual(
            self.window._scene_type_button_widgets["3d"].cget("background"),
            "#5fd1ff",
        )

    def test_window_can_refresh_preview_and_apply_actions(self) -> None:
        self.assertFalse(self.window._preview_visible_variable.get())
        self.window._refresh_preview()
        self.window._toggle_preview_visibility()
        self.root.update_idletasks()
        self.window._run_health_check()
        self.window._validate_current_scene()
        self.window._apply_current_scene()
        self.window._start_live_stream()
        time.sleep(0.08)
        self.window._stop_live_stream()
        self.root.update_idletasks()

        self.assertTrue(self.window._preview_visible_variable.get())
        preview_text = self.window._preview_text.get("1.0", "end").strip()
        self.assertIn('"sceneType"', preview_text)

    def test_window_can_drive_audio_and_pointer_inputs(self) -> None:
        self.window._refresh_audio_devices()
        self.window._audio_device_variable.set("Loopback device")
        self.window._start_audio_capture()
        pointer_event = type("PointerEvent", (), {"x": 120, "y": 80})()
        self.window._on_pointer_motion(pointer_event)
        self.window._on_pointer_leave(pointer_event)
        self.window._stop_audio_capture()
        self.root.update_idletasks()

        self.assertIn("Pointer pad", self.window._pointer_status_variable.get())

    def test_window_color_choice_and_module_entry_point_are_exercised(self) -> None:
        with mock.patch(
            "desktop_render_control_panel.desktop_control_panel_window.colorchooser.askcolor",
            return_value=((255, 0, 0), "#ff0000"),
        ):
            self.window._choose_color(self.window._primary_color_variable)

        with mock.patch(
            "desktop_render_control_panel.desktop_control_panel_window.main",
            return_value=None,
        ):
            runpy.run_module("desktop_render_control_panel.__main__", run_name="__main__")

        self.assertEqual(self.window._primary_color_variable.get(), "#ff0000")
        swatch_background = self.window._color_swatch_frames[
            str(self.window._primary_color_variable)
        ].cget("background")
        self.assertEqual(swatch_background, "#ff0000")

    def test_window_surfaces_offline_and_missing_device_states(self) -> None:
        self.fake_api_client.health_response = RenderApiResponse(
            ok=False,
            status=0,
            reason="connection-error",
            body="offline",
            headers={},
        )
        self.fake_api_client.validate_response = RenderApiResponse(
            ok=False,
            status=500,
            reason="Server Error",
            body="bad validate",
            headers={},
        )
        self.fake_api_client.apply_response = RenderApiResponse(
            ok=False,
            status=500,
            reason="Server Error",
            body="bad apply",
            headers={},
        )

        self.window._audio_device_variable.set("")
        with mock.patch(
            "desktop_render_control_panel.desktop_control_panel_window.messagebox.showinfo"
        ) as showinfo_mock:
            self.window._start_audio_capture()

        self.window._run_health_check()
        self.window._validate_current_scene()
        self.window._apply_current_scene()
        self.window._stop_audio_capture()
        self.root.update_idletasks()

        showinfo_mock.assert_called_once()
        self.assertIn("offline", self.window._health_status_variable.get())
        self.assertIn("500", self.window._result_status_variable.get())

    def test_window_handles_audio_capture_errors_and_safe_int_parsing(self) -> None:
        self.window._audio_device_variable.set("Loopback device")
        with mock.patch.object(
            self.controller,
            "start_audio_capture",
            side_effect=RuntimeError("audio failed"),
        ), mock.patch(
            "desktop_render_control_panel.desktop_control_panel_window.messagebox.showerror"
        ) as showerror_mock:
            self.window._start_audio_capture()

        self.window._port_variable.set("not-a-port")
        collected_payload = self.window._collect_request_payload_from_user_interface()

        showerror_mock.assert_called_once()
        self.assertEqual(collected_payload["target"]["port"], 8080)
        self.assertEqual(DesktopRenderControlPanelWindow._safe_int(object(), 7), 7)

    def test_window_can_save_load_and_revert_settings(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "desktop-settings.json"

            self.window._density_variable.set(180)
            self.window._gain_variable.set(1.95)
            self.window._preset_identifier_variable.set("pulse-grid-2d")
            self.window._on_preset_changed()
            self.window._density_variable.set(180)
            self.window._gain_variable.set(1.95)

            with mock.patch(
                "desktop_render_control_panel.desktop_control_panel_window.filedialog.asksaveasfilename",
                return_value=str(settings_path),
            ):
                self.window._save_settings_to_file()

            self.window._density_variable.set(32)
            self.window._gain_variable.set(0.5)

            with mock.patch(
                "desktop_render_control_panel.desktop_control_panel_window.filedialog.askopenfilename",
                return_value=str(settings_path),
            ):
                self.window._load_settings_from_file()

            self.assertEqual(self.window._density_variable.get(), 180)
            self.assertAlmostEqual(self.window._gain_variable.get(), 1.95)

            self.window._revert_current_preset_to_default_settings()

            self.assertEqual(self.window._density_variable.get(), 144)
            self.assertAlmostEqual(self.window._gain_variable.get(), 1.0)


if __name__ == "__main__":
    unittest.main()
