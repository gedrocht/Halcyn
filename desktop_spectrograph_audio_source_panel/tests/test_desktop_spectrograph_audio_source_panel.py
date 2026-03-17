"""Tests for the desktop spectrograph audio-source panel."""

from __future__ import annotations

import io
import json
import runpy
import time
import tkinter as tk
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from desktop_shared_control_support.audio_input_service import (
    AudioDeviceDescriptor,
    AudioSignalSnapshot,
)
from desktop_spectrograph_audio_source_panel.spectrograph_audio_source_builder import (
    build_audio_source_preview,
    build_catalog_payload,
    build_default_request_payload,
)
from desktop_spectrograph_audio_source_panel.spectrograph_audio_source_controller import (
    DesktopSpectrographAudioSourceController,
)
from desktop_spectrograph_audio_source_panel.spectrograph_audio_source_controller import (
    _deep_merge as controller_deep_merge,
)
from desktop_spectrograph_audio_source_panel.spectrograph_audio_source_controller import (
    _safe_int as controller_safe_int,
)
from desktop_spectrograph_audio_source_panel.spectrograph_audio_source_window import (
    DesktopSpectrographAudioSourceWindow,
)
from desktop_spectrograph_audio_source_panel.spectrograph_external_bridge_client import (
    SpectrographExternalBridgeClient,
    SpectrographExternalBridgeResponse,
)


class FakeAudioInputService:
    """Small fake audio service used by the audio-source tests."""

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
                    max_output_channels=2,
                    default_sample_rate=48_000,
                    device_flow="output",
                )
            ]
        return [
            AudioDeviceDescriptor(
                device_identifier="mic-1",
                name="USB microphone",
                max_input_channels=2,
                max_output_channels=0,
                default_sample_rate=48_000,
                device_flow="input",
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
            available=True,
            capturing=True,
            device_identifier=device_identifier,
            device_name="Desktop speakers" if device_flow == "output" else "USB microphone",
            level=0.7,
            bass=0.6,
            mid=0.35,
            treble=0.2,
        )
        return self._snapshot

    def stop_capture(self) -> AudioSignalSnapshot:
        self._snapshot = AudioSignalSnapshot(
            backend_name="fake",
            available=True,
            capturing=False,
            device_identifier=self._snapshot.device_identifier,
            device_name=self._snapshot.device_name,
            level=0.0,
            bass=0.0,
            mid=0.0,
            treble=0.0,
        )
        return self._snapshot

    def close(self) -> None:
        pass


class FakeSpectrographExternalBridgeClient:
    """Small fake bridge client used by the controller and window tests."""

    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        self.next_response = SpectrographExternalBridgeResponse(
            True,
            202,
            "Accepted",
            '{"status":"accepted"}',
        )

    def deliver_json_text(
        self,
        *,
        host: str,
        port: int,
        path: str,
        source_label: str,
        json_text: str,
    ) -> SpectrographExternalBridgeResponse:
        self.requests.append(
            {
                "host": host,
                "port": port,
                "path": path,
                "sourceLabel": source_label,
                "jsonText": json_text,
            }
        )
        return self.next_response


class FakeUrlOpenResponse:
    """Tiny context-manager fake used to exercise urllib success handling."""

    def __init__(self, status: int, reason: str, body_text: str) -> None:
        self.status = status
        self.reason = reason
        self._body_text = body_text

    def __enter__(self) -> FakeUrlOpenResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        return None

    def read(self) -> bytes:
        return self._body_text.encode("utf-8")


class SpectrographAudioSourceBuilderTests(unittest.TestCase):
    """Exercise the audio-history-to-JSON transformation helpers."""

    def test_catalog_and_default_payload_expose_audio_bridge_defaults(self) -> None:
        catalog_payload = build_catalog_payload()
        default_request_payload = build_default_request_payload()

        self.assertEqual(catalog_payload["status"], "ok")
        self.assertEqual(catalog_payload["defaults"]["bridgePort"], 8091)
        self.assertEqual(default_request_payload["audio"]["deviceFlow"], "output")
        self.assertEqual(default_request_payload["audio"]["historyFrameCount"], 72)

    def test_preview_uses_recent_audio_history_and_builds_generic_json(self) -> None:
        preview = build_audio_source_preview(
            request_payload={
                "audio": {"deviceFlow": "output", "historyFrameCount": 4},
            },
            latest_audio_signal_snapshot=AudioSignalSnapshot(
                backend_name="fake",
                device_identifier="speaker-1",
                device_name="Desktop speakers",
                available=True,
                capturing=True,
                level=0.8,
                bass=0.6,
                mid=0.4,
                treble=0.2,
            ),
            recent_audio_signal_snapshots=[
                AudioSignalSnapshot(level=0.1, bass=0.2, mid=0.3, treble=0.4),
                AudioSignalSnapshot(level=0.5, bass=0.4, mid=0.3, treble=0.2),
            ],
        )

        generated_document = json.loads(preview.generated_json_text)
        self.assertEqual(generated_document["device"]["flow"], "output")
        self.assertEqual(len(generated_document["audioFrames"]), 2)
        self.assertAlmostEqual(generated_document["summary"]["currentLevel"], 0.8)
        self.assertIn("jsonText", preview.bridge_request_body)

    def test_preview_normalizes_invalid_flow_and_uses_zero_frame_when_history_is_empty(
        self,
    ) -> None:
        preview = build_audio_source_preview(
            request_payload={
                "audio": {"deviceFlow": "sideways", "historyFrameCount": "oops"},
                "session": {"cadenceMs": "oops"},
            },
            latest_audio_signal_snapshot=AudioSignalSnapshot(
                backend_name="fake",
                device_identifier="speaker-1",
                device_name="Desktop speakers",
                available=True,
                capturing=False,
            ),
            recent_audio_signal_snapshots=[],
        )

        generated_document = json.loads(preview.generated_json_text)
        self.assertEqual(preview.normalized_request_payload["audio"]["deviceFlow"], "output")
        self.assertEqual(preview.normalized_request_payload["audio"]["historyFrameCount"], 72)
        self.assertEqual(preview.normalized_request_payload["session"]["cadenceMs"], 125)
        self.assertEqual(generated_document["audioFrames"][0]["level"], 0.0)


class SpectrographExternalBridgeClientTests(unittest.TestCase):
    """Exercise success and failure paths for the tiny local bridge client."""

    def test_client_returns_success_response_for_http_202(self) -> None:
        client = SpectrographExternalBridgeClient()
        with mock.patch(
            "desktop_spectrograph_audio_source_panel.spectrograph_external_bridge_client.urllib.request.urlopen",
            return_value=FakeUrlOpenResponse(202, "Accepted", '{"status":"accepted"}'),
        ):
            response = client.deliver_json_text(
                host="127.0.0.1",
                port=8091,
                path="/external-data",
                source_label="unit-test",
                json_text='{"values":[1,2,3]}',
            )

        self.assertTrue(response.ok)
        self.assertEqual(response.status, 202)
        self.assertEqual(response.reason, "Accepted")

    def test_client_returns_http_error_details(self) -> None:
        client = SpectrographExternalBridgeClient()
        http_error = urllib.error.HTTPError(
            url="http://127.0.0.1:8091/external-data",
            code=400,
            msg="Bad Request",
            hdrs=Message(),
            fp=io.BytesIO(b'{"status":"invalid-request"}'),
        )
        with mock.patch(
            "desktop_spectrograph_audio_source_panel.spectrograph_external_bridge_client.urllib.request.urlopen",
            side_effect=http_error,
        ):
            response = client.deliver_json_text(
                host="127.0.0.1",
                port=8091,
                path="/external-data",
                source_label="unit-test",
                json_text='{"values":[1,2,3]}',
            )

        self.assertFalse(response.ok)
        self.assertEqual(response.status, 400)
        self.assertIn("invalid-request", response.body)

    def test_client_returns_generic_exception_details(self) -> None:
        client = SpectrographExternalBridgeClient()
        with mock.patch(
            "desktop_spectrograph_audio_source_panel.spectrograph_external_bridge_client.urllib.request.urlopen",
            side_effect=RuntimeError("bridge unavailable"),
        ):
            response = client.deliver_json_text(
                host="127.0.0.1",
                port=8091,
                path="/external-data",
                source_label="unit-test",
                json_text='{"values":[1,2,3]}',
            )

        self.assertFalse(response.ok)
        self.assertEqual(response.status, 0)
        self.assertEqual(response.reason, "RuntimeError")
        self.assertIn("bridge unavailable", response.body)

    def test_client_normalizes_a_bridge_path_without_a_leading_slash(self) -> None:
        client = SpectrographExternalBridgeClient()
        with mock.patch(
            "desktop_spectrograph_audio_source_panel.spectrograph_external_bridge_client.urllib.request.urlopen",
            return_value=FakeUrlOpenResponse(202, "Accepted", '{"status":"accepted"}'),
        ) as urlopen_mock:
            client.deliver_json_text(
                host="127.0.0.1",
                port=8091,
                path="external-data",
                source_label="unit-test",
                json_text='{"values":[1,2,3]}',
            )

        submitted_request = urlopen_mock.call_args[0][0]
        self.assertEqual(submitted_request.full_url, "http://127.0.0.1:8091/external-data")


class SpectrographAudioSourceControllerTests(unittest.TestCase):
    """Exercise the non-visual orchestration behind the audio-source panel."""

    def setUp(self) -> None:
        self.fake_audio_input_service = FakeAudioInputService()
        self.fake_bridge_client = FakeSpectrographExternalBridgeClient()
        self.controller = DesktopSpectrographAudioSourceController(
            audio_input_service=self.fake_audio_input_service,
            spectrograph_external_bridge_client=self.fake_bridge_client,
        )

    def tearDown(self) -> None:
        self.controller.close()

    def test_start_capture_and_deliver_once_send_audio_json_to_the_bridge(self) -> None:
        self.controller.replace_request_payload(
            {
                "audio": {"deviceFlow": "output", "deviceIdentifier": "speaker-1"},
                "bridge": {"host": "127.0.0.1", "port": 8091},
            }
        )

        self.controller.start_audio_capture("speaker-1", "output")
        delivery_result = self.controller.deliver_once()

        self.assertEqual(delivery_result["status"], "delivered")
        self.assertEqual(self.fake_bridge_client.requests[0]["port"], 8091)
        generated_document = json.loads(str(self.fake_bridge_client.requests[0]["jsonText"]))
        self.assertEqual(generated_document["device"]["identifier"], "speaker-1")

    def test_live_send_updates_status_and_keeps_delivering(self) -> None:
        self.controller.replace_request_payload(
            {
                "audio": {"deviceFlow": "input", "deviceIdentifier": "mic-1"},
                "session": {"cadenceMs": 40},
            }
        )
        self.controller.start_audio_capture("mic-1", "input")

        running_snapshot = self.controller.start_live_send()
        deadline = time.time() + 1.0
        latest_snapshot = running_snapshot
        while time.time() < deadline:
            latest_snapshot = self.controller.live_send_snapshot()
            if latest_snapshot["deliveries_succeeded"] > 0:
                break
            time.sleep(0.02)

        stopped_snapshot = self.controller.stop_live_send()

        self.assertEqual(running_snapshot["status"], "running")
        self.assertGreater(latest_snapshot["deliveries_succeeded"], 0)
        self.assertEqual(stopped_snapshot["status"], "stopped")

    def test_settings_document_round_trip_preserves_payload_choices(self) -> None:
        self.controller.update_request_payload(
            {
                "bridge": {"host": "127.0.0.9"},
                "audio": {"deviceFlow": "input", "historyFrameCount": 32},
            }
        )
        settings_document = self.controller.settings_document()
        restored_payload = self.controller.load_settings_document(settings_document)

        self.assertEqual(restored_payload["bridge"]["host"], "127.0.0.9")
        self.assertEqual(restored_payload["audio"]["historyFrameCount"], 32)
        self.assertEqual(restored_payload["audio"]["deviceFlow"], "input")

    def test_reset_defaults_invalid_settings_and_failure_delivery_paths_are_visible(self) -> None:
        self.controller.update_request_payload(
            {
                "audio": {"deviceFlow": "input", "deviceIdentifier": "mic-1"},
                "bridge": {"host": "127.0.0.9"},
            }
        )

        self.fake_bridge_client.next_response = SpectrographExternalBridgeResponse(
            False,
            503,
            "Service Unavailable",
            "bridge unavailable",
        )
        self.controller.start_audio_capture("mic-1", "input")
        delivery_result = self.controller.deliver_once()
        live_send_snapshot = self.controller.live_send_snapshot()
        reset_payload = self.controller.reset_to_defaults()

        self.assertEqual(delivery_result["status"], "delivery-failed")
        self.assertEqual(live_send_snapshot["deliveries_failed"], 1)
        self.assertEqual(reset_payload["bridge"]["host"], "127.0.0.1")

        with self.assertRaisesRegex(ValueError, "request payload object"):
            self.controller.load_settings_document({"requestPayload": "not-a-dict"})

    def test_refresh_stop_and_missing_device_paths_stay_beginner_readable(self) -> None:
        self.controller.replace_request_payload({"audio": {"deviceFlow": "input"}})

        refreshed_devices = self.controller.refresh_audio_devices()
        stopped_snapshot = self.controller.stop_audio_capture()

        self.assertEqual(refreshed_devices[0].device_flow, "input")
        self.assertFalse(stopped_snapshot.capturing)

        self.controller.replace_request_payload({"audio": {"deviceIdentifier": ""}})
        with self.assertRaisesRegex(ValueError, "Choose an audio device"):
            self.controller.start_audio_capture()

    def test_controller_helper_functions_keep_updates_simple(self) -> None:
        merged_payload = {"outer": {"left": 1, "right": 2}}
        controller_deep_merge(merged_payload, {"outer": {"right": 11}, "extra": True})

        self.assertEqual(merged_payload["outer"]["left"], 1)
        self.assertEqual(merged_payload["outer"]["right"], 11)
        self.assertTrue(merged_payload["extra"])
        self.assertEqual(controller_safe_int("15", 4), 15)
        self.assertEqual(controller_safe_int("oops", 4), 4)


class SpectrographAudioSourceWindowTests(unittest.TestCase):
    """Exercise the Tkinter audio-source window behavior."""

    def setUp(self) -> None:
        self.root_window = tk.Tk()
        self.root_window.withdraw()
        self.controller = DesktopSpectrographAudioSourceController(
            audio_input_service=FakeAudioInputService(),
            spectrograph_external_bridge_client=FakeSpectrographExternalBridgeClient(),
        )
        self.window = DesktopSpectrographAudioSourceWindow(
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

    def test_window_initializes_labels_and_updates_slider_text(self) -> None:
        self.assertIn("Choose a device", self.window._bridge_summary_variable.get())

        self.window._history_frame_count_variable.set(40)
        self.window._on_history_frame_count_changed("40")
        self.window._live_cadence_variable.set(300)
        self.window._on_live_cadence_changed("300")

        self.assertEqual(self.window._history_frame_count_label_variable.get(), "40 frames")
        self.assertEqual(self.window._live_cadence_label_variable.get(), "300 ms")

    def test_window_can_refresh_devices_start_capture_and_open_json_window(self) -> None:
        self.window._audio_device_flow_variable.set("output")
        self.window._on_device_flow_changed()
        self.window._start_audio_capture()
        self.window._open_generated_audio_json_window()
        self.root_window.update_idletasks()

        self.assertIn("Capturing", self.window._audio_status_variable.get())
        self.assertIsNotNone(self.window._generated_audio_json_text_widget)

    def test_window_can_send_live_revert_and_copy_generated_audio_json(self) -> None:
        self.window._audio_device_flow_variable.set("output")
        self.window._on_device_flow_changed()
        self.window._start_audio_capture()

        self.window._deliver_once()
        self.assertIn("Delivered audio JSON", self.window._delivery_status_variable.get())

        self.window._start_live_send()
        deadline = time.time() + 1.0
        while time.time() < deadline:
            self.window._poll_status()
            if "Successful deliveries: 1" in self.window._delivery_status_variable.get():
                break
            time.sleep(0.02)
        self.window._stop_live_send()
        self.assertIn("Live send stopped", self.window._delivery_status_variable.get())

        self.window._open_generated_audio_json_window()
        self.window._open_generated_audio_json_window()
        self.window._copy_generated_audio_json_to_clipboard()
        self.assertIn('"audioFrames"', self.root_window.clipboard_get())

        self.window._revert_defaults()
        self.assertEqual(self.window._audio_device_flow_variable.get(), "output")
        self.assertEqual(self.window._live_cadence_variable.get(), 125)

        self.window._on_generated_audio_json_window_closed()
        self.assertIsNone(self.window._generated_audio_json_window)

    def test_window_can_save_load_and_report_preview_and_copy_errors(self) -> None:
        with mock.patch(
            "desktop_spectrograph_audio_source_panel.spectrograph_audio_source_window.messagebox.showinfo"
        ) as showinfo_mock:
            self.window._latest_audio_source_preview = None
            self.window._copy_generated_audio_json_to_clipboard()
        showinfo_mock.assert_called_once()

        with TemporaryDirectory() as temporary_directory:
            settings_file_path = Path(temporary_directory) / "audio-source-settings.json"

            with mock.patch(
                "desktop_spectrograph_audio_source_panel.spectrograph_audio_source_window.filedialog.asksaveasfilename",
                return_value=str(settings_file_path),
            ):
                self.window._save_settings_document()

            saved_settings_document = json.loads(settings_file_path.read_text(encoding="utf-8"))
            saved_settings_document["requestPayload"]["bridge"]["host"] = "127.0.0.9"
            settings_file_path.write_text(
                json.dumps(saved_settings_document, indent=2),
                encoding="utf-8",
            )

            with mock.patch(
                "desktop_spectrograph_audio_source_panel.spectrograph_audio_source_window.filedialog.askopenfilename",
                return_value=str(settings_file_path),
            ):
                self.window._load_settings_document()

        self.assertEqual(self.window._bridge_host_variable.get(), "127.0.0.9")
        self.assertIn("Loaded settings", self.window._delivery_status_variable.get())

        with mock.patch.object(
            self.controller,
            "preview_payload",
            side_effect=ValueError("preview failed"),
        ):
            self.window._refresh_preview()
        self.assertIn("Preview error", self.window._delivery_status_variable.get())
        self.assertIn("could not be turned", self.window._bridge_summary_variable.get())

    def test_window_handles_missing_device_and_stop_status(self) -> None:
        self.window._audio_device_identifier_variable.set("")
        with mock.patch(
            "desktop_spectrograph_audio_source_panel.spectrograph_audio_source_window.messagebox.showinfo"
        ) as showinfo_mock:
            self.window._start_audio_capture()
        showinfo_mock.assert_called_once()

        self.window._audio_device_flow_variable.set("input")
        self.window._on_device_flow_changed()
        self.window._start_audio_capture()
        self.window._stop_audio_capture()
        self.assertIn("Audio capture stopped", self.window._audio_status_variable.get())

        self.assertEqual(DesktopSpectrographAudioSourceWindow._safe_int("oops", 9), 9)

    def test_module_entry_point_calls_window_main(self) -> None:
        with mock.patch(
            "desktop_spectrograph_audio_source_panel.spectrograph_audio_source_window.main",
            return_value=None,
        ) as main_mock:
            runpy.run_module(
                "desktop_spectrograph_audio_source_panel.__main__",
                run_name="__main__",
            )

        main_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
