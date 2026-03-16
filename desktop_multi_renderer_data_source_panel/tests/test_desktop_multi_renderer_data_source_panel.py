"""Tests for the shared desktop multi-renderer data-source panel."""

from __future__ import annotations

import json
import time
import tkinter as tk
import unittest

from desktop_multi_renderer_data_source_panel.multi_renderer_data_source_builder import (
    build_catalog_payload,
    build_default_request_payload,
    build_multi_renderer_preview_bundle,
)
from desktop_multi_renderer_data_source_panel.multi_renderer_data_source_controller import (
    MultiRendererDataSourceController,
)
from desktop_multi_renderer_data_source_panel.multi_renderer_data_source_controller import (
    _deep_merge as controller_deep_merge,
)
from desktop_multi_renderer_data_source_panel.multi_renderer_data_source_controller import (
    _safe_int as controller_safe_int,
)
from desktop_multi_renderer_data_source_panel.multi_renderer_data_source_window import (
    MultiRendererDataSourceWindow,
)
from desktop_shared_control_support.audio_input_service import (
    AudioDeviceDescriptor,
    AudioSignalSnapshot,
)
from desktop_shared_control_support.render_api_client import RenderApiResponse


class FakeRenderApiClient:
    """Small fake renderer client used by the controller and window tests."""

    def __init__(self) -> None:
        self.health_response = RenderApiResponse(True, 200, "OK", '{"status":"ok"}', {})
        self.validate_response = RenderApiResponse(True, 200, "OK", '{"status":"valid"}', {})
        self.apply_response = RenderApiResponse(True, 202, "Accepted", '{"status":"accepted"}', {})
        self.health_requests: list[tuple[str, int]] = []
        self.validate_requests: list[tuple[str, int, str]] = []
        self.apply_requests: list[tuple[str, int, str]] = []

    def health(self, host: str, port: int) -> RenderApiResponse:
        self.health_requests.append((host, port))
        return self.health_response

    def validate_scene(self, host: str, port: int, scene_json: str) -> RenderApiResponse:
        self.validate_requests.append((host, port, scene_json))
        return self.validate_response

    def apply_scene(self, host: str, port: int, scene_json: str) -> RenderApiResponse:
        self.apply_requests.append((host, port, scene_json))
        return self.apply_response


class FakeAudioInputService:
    """Tiny fake audio service that behaves like the real controller dependency."""

    def __init__(self) -> None:
        self._snapshot = AudioSignalSnapshot(
            backend_name="fake",
            available=True,
            capturing=False,
            device_identifier="speaker-1",
            device_name="Desktop speakers",
        )

    def devices(self, device_flow: str = "input") -> list[AudioDeviceDescriptor]:
        return self.refresh_devices(device_flow)

    def refresh_devices(self, device_flow: str = "input") -> list[AudioDeviceDescriptor]:
        if device_flow == "output":
            return [
                AudioDeviceDescriptor(
                    device_identifier="speaker-1",
                    name="Desktop speakers",
                    max_input_channels=0,
                    default_sample_rate=48_000,
                    device_flow="output",
                    max_output_channels=2,
                )
            ]
        return [
            AudioDeviceDescriptor(
                device_identifier="mic-1",
                name="USB microphone",
                max_input_channels=2,
                default_sample_rate=48_000,
                device_flow="input",
                max_output_channels=0,
            )
        ]

    def snapshot(self) -> AudioSignalSnapshot:
        return self._snapshot

    def start_capture(
        self,
        device_identifier: str,
        device_flow: str = "input",
    ) -> AudioSignalSnapshot:
        self._snapshot = AudioSignalSnapshot(
            backend_name="fake",
            device_identifier=device_identifier,
            device_name="Desktop speakers" if device_flow == "output" else "USB microphone",
            available=True,
            capturing=True,
            level=0.7,
            bass=0.6,
            mid=0.3,
            treble=0.2,
        )
        return self._snapshot

    def stop_capture(self) -> AudioSignalSnapshot:
        self._snapshot = AudioSignalSnapshot(
            backend_name="fake",
            device_identifier=self._snapshot.device_identifier,
            device_name=self._snapshot.device_name,
            available=True,
            capturing=False,
        )
        return self._snapshot

    def close(self) -> None:
        pass


class MultiRendererDataSourceBuilderTests(unittest.TestCase):
    """Exercise the source-to-scene transformation helpers."""

    def test_catalog_and_default_payload_expose_the_shared_routing_shape(self) -> None:
        catalog_payload = build_catalog_payload()
        default_request_payload = build_default_request_payload()

        self.assertEqual(catalog_payload["status"], "ok")
        self.assertGreaterEqual(len(catalog_payload["sourceModes"]), 5)
        self.assertTrue(default_request_payload["targets"]["classic"]["enabled"])
        self.assertFalse(default_request_payload["targets"]["spectrograph"]["enabled"])

    def test_json_source_can_preview_both_targets(self) -> None:
        preview_bundle = build_multi_renderer_preview_bundle(
            {
                "source": {
                    "mode": "json_document",
                    "jsonText": json.dumps({"values": [1, 2, 3, 4, 5, 6], "label": "AB"}),
                },
                "targets": {
                    "classic": {"enabled": True},
                    "spectrograph": {"enabled": True},
                },
            }
        )

        assert preview_bundle.classic_scene_bundle is not None
        assert preview_bundle.spectrograph_build_result is not None
        self.assertIsNotNone(preview_bundle.classic_scene_bundle)
        self.assertIsNotNone(preview_bundle.spectrograph_build_result)
        self.assertEqual(preview_bundle.classic_scene_bundle["target"]["port"], 8080)
        self.assertEqual(preview_bundle.spectrograph_build_result.target["port"], 8090)

    def test_plain_text_source_turns_text_into_numeric_values(self) -> None:
        preview_bundle = build_multi_renderer_preview_bundle(
            {
                "source": {
                    "mode": "plain_text",
                    "plainText": "AB",
                }
            }
        )

        self.assertEqual(preview_bundle.collected_source_data.numeric_values, [65.0, 66.0])

    def test_audio_source_uses_audio_snapshot_values(self) -> None:
        preview_bundle = build_multi_renderer_preview_bundle(
            {
                "source": {"mode": "audio_device"},
                "targets": {"spectrograph": {"enabled": True}},
            },
            audio_signal_snapshot=AudioSignalSnapshot(
                backend_name="fake",
                device_identifier="speaker-1",
                device_name="Desktop speakers",
                available=True,
                capturing=True,
                level=0.8,
                bass=0.5,
                mid=0.3,
                treble=0.2,
            ),
        )

        self.assertEqual(preview_bundle.collected_source_data.source_mode, "audio_device")
        self.assertGreater(preview_bundle.collected_source_data.numeric_values[0], 0.0)
        self.assertIsNotNone(preview_bundle.spectrograph_build_result)


class MultiRendererDataSourceControllerTests(unittest.TestCase):
    """Exercise the non-visual orchestration behind the shared data-source panel."""

    def setUp(self) -> None:
        self.fake_render_api_client = FakeRenderApiClient()
        self.fake_audio_input_service = FakeAudioInputService()
        self.controller = MultiRendererDataSourceController(
            render_api_client=self.fake_render_api_client,
            audio_input_service=self.fake_audio_input_service,
        )

    def tearDown(self) -> None:
        self.controller.close()

    def test_apply_selected_targets_can_drive_both_renderers(self) -> None:
        self.controller.replace_request_payload(
            {
                "targets": {
                    "classic": {"enabled": True, "host": "127.0.0.9", "port": 8088},
                    "spectrograph": {"enabled": True, "host": "127.0.0.8", "port": 8098},
                },
                "source": {
                    "mode": "json_document",
                    "jsonText": json.dumps({"values": list(range(32))}),
                },
            }
        )

        apply_result = self.controller.apply_selected_targets()

        self.assertEqual(apply_result["status"], "applied")
        self.assertEqual(self.fake_render_api_client.apply_requests[0][0], "127.0.0.9")
        self.assertEqual(self.fake_render_api_client.apply_requests[1][1], 8098)

    def test_audio_capture_start_and_stop_flow_through_the_audio_service(self) -> None:
        devices = self.controller.refresh_audio_devices("output")
        self.assertEqual(devices[0].device_identifier, "speaker-1")
        started_snapshot = self.controller.start_audio_capture("speaker-1", "output")
        self.assertTrue(started_snapshot.capturing)
        stopped_snapshot = self.controller.stop_audio_capture()
        self.assertFalse(stopped_snapshot.capturing)

    def test_settings_document_round_trip_preserves_payload_choices(self) -> None:
        self.controller.update_request_payload(
            {
                "source": {"mode": "plain_text", "plainText": "hello"},
                "targets": {"spectrograph": {"enabled": True}},
            }
        )
        settings_document = self.controller.settings_document()
        restored_payload = self.controller.load_settings_document(settings_document)

        self.assertEqual(restored_payload["source"]["mode"], "plain_text")
        self.assertTrue(restored_payload["targets"]["spectrograph"]["enabled"])

    def test_live_stream_updates_status_and_applies_frames(self) -> None:
        self.controller.replace_request_payload(
            {
                "targets": {
                    "classic": {"enabled": True},
                    "spectrograph": {"enabled": True},
                },
                "source": {"mode": "random_values"},
                "session": {"cadenceMs": 40},
            }
        )

        running_snapshot = self.controller.start_live_stream()
        deadline = time.time() + 1.0
        latest_snapshot = running_snapshot
        while time.time() < deadline:
            latest_snapshot = self.controller.live_stream_snapshot()
            if latest_snapshot["classic_frames_applied"] > 0:
                break
            time.sleep(0.02)

        stopped_snapshot = self.controller.stop_live_stream()

        self.assertEqual(running_snapshot["status"], "running")
        self.assertGreater(latest_snapshot["classic_frames_applied"], 0)
        self.assertEqual(stopped_snapshot["status"], "stopped")

    def test_helper_functions_keep_controller_updates_simple(self) -> None:
        merged_payload = {"outer": {"left": 1, "right": 2}}
        controller_deep_merge(merged_payload, {"outer": {"right": 11}, "extra": True})

        self.assertEqual(merged_payload["outer"]["left"], 1)
        self.assertEqual(merged_payload["outer"]["right"], 11)
        self.assertTrue(merged_payload["extra"])
        self.assertEqual(controller_safe_int("15", 4), 15)
        self.assertEqual(controller_safe_int("oops", 4), 4)


class MultiRendererDataSourceWindowTests(unittest.TestCase):
    """Exercise the Tkinter window behavior at a high level."""

    def setUp(self) -> None:
        self.root_window = tk.Tk()
        self.root_window.withdraw()
        self.controller = MultiRendererDataSourceController(
            render_api_client=FakeRenderApiClient(),
            audio_input_service=FakeAudioInputService(),
        )
        self.window = MultiRendererDataSourceWindow(
            self.root_window,
            controller=self.controller,
        )
        self.root_window.update_idletasks()

    def tearDown(self) -> None:
        try:
            self.window._on_close_requested()
        except tk.TclError:
            pass
        try:
            self.root_window.update_idletasks()
        except tk.TclError:
            pass

    def test_window_can_preview_and_open_detached_json_tabs(self) -> None:
        self.window._spectrograph_enabled_variable.set(True)
        self.window._refresh_preview()
        self.window._open_preview_json_window()
        self.root_window.update_idletasks()

        self.assertIsNotNone(self.window._latest_preview_bundle)
        self.assertIn("classic", self.window._json_preview_text_widgets)
        self.assertIn("spectrograph", self.window._json_preview_text_widgets)

    def test_window_switches_source_modes_cleanly(self) -> None:
        self.window._set_source_mode("plain_text")
        self.window._plain_text_variable.set("hello")
        self.window._refresh_preview()

        assert self.window._latest_preview_bundle is not None
        self.assertEqual(self.window._source_mode_variable.get(), "plain_text")
        self.assertIn(
            "plain_text",
            self.window._latest_preview_bundle.collected_source_data.analysis["sourceMode"],
        )


if __name__ == "__main__":
    unittest.main()
