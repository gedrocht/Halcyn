"""Tests for the unified Halcyn Visualizer Studio package."""

from __future__ import annotations

import json
import os
import runpy
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import ttkbootstrap as ttkb

from desktop_shared_control_support.activity_journal import (
    ActivityJournal,
    get_default_activity_journal_path,
    read_recent_activity_entries,
)
from desktop_shared_control_support.audio_input_service import (
    AudioDeviceDescriptor,
    AudioSignalSnapshot,
)
from desktop_shared_control_support.render_api_client import RenderApiResponse
from desktop_visualizer_operator_console.visualizer_operator_console_controller import (
    VisualizerOperatorConsoleController,
)
from desktop_visualizer_operator_console.visualizer_operator_console_window import (
    DEFAULT_SETTINGS_FILE_NAME,
    VisualizerOperatorConsoleWindow,
)
from desktop_visualizer_operator_console.visualizer_operator_scene_builder import (
    build_catalog_payload,
    build_default_request_payload,
    build_visualizer_preview_bundle,
)


class _FakeRenderApiClient:
    """Small configurable fake renderer client for controller and window tests."""

    def __init__(
        self,
        *,
        health_status: int = 200,
        validate_status: int = 200,
        apply_status: int = 202,
        health_reason: str = "OK",
        validate_reason: str = "OK",
        apply_reason: str = "Accepted",
        health_body: str = "{}",
        validate_body: str = "{}",
        apply_body: str = "{}",
    ) -> None:
        self.requests: list[tuple[str, str, int, str]] = []
        self.health_status = health_status
        self.validate_status = validate_status
        self.apply_status = apply_status
        self.health_reason = health_reason
        self.validate_reason = validate_reason
        self.apply_reason = apply_reason
        self.health_body = health_body
        self.validate_body = validate_body
        self.apply_body = apply_body

    def health(self, host: str, port: int) -> RenderApiResponse:
        self.requests.append(("health", host, port, ""))
        return RenderApiResponse(
            ok=self.health_status < 400,
            status=self.health_status,
            reason=self.health_reason,
            body=self.health_body,
            headers={},
        )

    def validate_scene(self, host: str, port: int, scene_json: str) -> RenderApiResponse:
        self.requests.append(("validate", host, port, scene_json))
        return RenderApiResponse(
            ok=self.validate_status < 400,
            status=self.validate_status,
            reason=self.validate_reason,
            body=self.validate_body,
            headers={},
        )

    def apply_scene(self, host: str, port: int, scene_json: str) -> RenderApiResponse:
        self.requests.append(("apply", host, port, scene_json))
        return RenderApiResponse(
            ok=self.apply_status < 400,
            status=self.apply_status,
            reason=self.apply_reason,
            body=self.apply_body,
            headers={},
        )


class _FakeAudioInputService:
    """Configurable fake audio service for controller and window tests."""

    def __init__(self) -> None:
        self._snapshot = AudioSignalSnapshot(
            backend_name="fake",
            available=True,
            capturing=False,
        )
        self.closed = False
        self.refresh_error: Exception | None = None
        self.start_error: Exception | None = None
        self.last_started_arguments: tuple[str, str] | None = None
        self.devices_by_flow: dict[str, list[AudioDeviceDescriptor]] = {
            "output": [
                AudioDeviceDescriptor(
                    device_identifier="speaker-1",
                    name="Desktop speakers",
                    max_input_channels=0,
                    default_sample_rate=48_000,
                    device_flow="output",
                    max_output_channels=2,
                )
            ],
            "input": [
                AudioDeviceDescriptor(
                    device_identifier="mic-1",
                    name="USB microphone",
                    max_input_channels=2,
                    default_sample_rate=48_000,
                    device_flow="input",
                )
            ],
        }

    def devices(self, device_flow: str = "input") -> list[AudioDeviceDescriptor]:
        return self.refresh_devices(device_flow)

    def refresh_devices(self, device_flow: str = "input") -> list[AudioDeviceDescriptor]:
        if self.refresh_error is not None:
            raise self.refresh_error
        return list(self.devices_by_flow.get(device_flow, []))

    def snapshot(self) -> AudioSignalSnapshot:
        return self._snapshot

    def start_capture(
        self,
        device_identifier: str,
        device_flow: str = "input",
    ) -> AudioSignalSnapshot:
        if self.start_error is not None:
            raise self.start_error
        self.last_started_arguments = (device_identifier, device_flow)
        self._snapshot = AudioSignalSnapshot(
            backend_name="fake",
            device_identifier=device_identifier,
            device_name="Desktop speakers" if device_flow == "output" else "USB microphone",
            available=True,
            capturing=True,
            level=0.75,
            bass=0.6,
            mid=0.5,
            treble=0.4,
        )
        return self._snapshot

    def stop_capture(self) -> AudioSignalSnapshot:
        self._snapshot.capturing = False
        self._snapshot.last_error = ""
        return self._snapshot

    def close(self) -> None:
        self.closed = True


class VisualizerOperatorSceneBuilderTests(unittest.TestCase):
    """Exercise the scene-building layer behind Visualizer Studio."""

    def test_catalog_exposes_scene_and_source_modes(self) -> None:
        catalog_payload = build_catalog_payload()
        self.assertEqual(catalog_payload["status"], "ok")
        self.assertEqual(
            {entry["id"] for entry in catalog_payload["sceneModes"]},
            {"preset_scene", "bar_wall_scene"},
        )
        self.assertIn("audio_device", {entry["id"] for entry in catalog_payload["sourceModes"]})

    def test_default_request_payload_uses_one_visualizer_target(self) -> None:
        request_payload = build_default_request_payload()
        self.assertEqual(request_payload["target"]["host"], "127.0.0.1")
        self.assertEqual(request_payload["target"]["port"], 8080)
        self.assertEqual(request_payload["sceneMode"], "preset_scene")
        self.assertEqual(request_payload["source"]["audio"]["deviceFlow"], "output")

    def test_plain_text_source_builds_bar_wall_scene(self) -> None:
        preview_bundle = build_visualizer_preview_bundle(
            {
                "sceneMode": "bar_wall_scene",
                "source": {"mode": "plain_text", "plainText": "ABC"},
            }
        )

        self.assertEqual(preview_bundle.scene_mode, "bar_wall_scene")
        self.assertEqual(preview_bundle.scene["sceneType"], "3d")
        self.assertGreater(preview_bundle.analysis["barCount"], 0)

    def test_audio_source_builds_preset_scene(self) -> None:
        preview_bundle = build_visualizer_preview_bundle(
            {
                "sceneMode": "preset_scene",
                "source": {"mode": "audio_device"},
            },
            audio_signal_snapshot=AudioSignalSnapshot(
                available=True,
                capturing=True,
                level=0.8,
                bass=0.5,
                mid=0.4,
                treble=0.3,
            ),
        )

        self.assertEqual(preview_bundle.scene_mode, "preset_scene")
        self.assertIn(preview_bundle.scene["sceneType"], {"2d", "3d"})
        self.assertEqual(preview_bundle.analysis["sourceMode"], "audio_device")

    def test_pointer_source_builds_pointer_friendly_summary(self) -> None:
        preview_bundle = build_visualizer_preview_bundle(
            {
                "source": {
                    "mode": "pointer_pad",
                    "pointer": {"x": 0.25, "y": 0.75, "speed": 0.5},
                }
            }
        )

        self.assertIn("Pointer x=0.25", preview_bundle.collected_source_data.analysis["details"])
        self.assertAlmostEqual(
            preview_bundle.collected_source_data.preset_scene_signal_payload["pointer"]["speed"],
            0.5,
        )

    def test_invalid_json_raises_a_friendly_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "could not parse"):
            build_visualizer_preview_bundle(
                {
                    "source": {
                        "mode": "json_document",
                        "jsonText": "{not valid json}",
                    }
                }
            )

    def test_normalization_clamps_invalid_values_into_safe_ranges(self) -> None:
        preview_bundle = build_visualizer_preview_bundle(
            {
                "target": {"host": "   ", "port": 90000},
                "sceneMode": "mystery_mode",
                "source": {
                    "mode": "mystery_source",
                    "jsonText": "",
                    "random": {
                        "seed": -5,
                        "count": 1,
                        "minimum": 10,
                        "maximum": 5,
                    },
                    "pointer": {"x": 5, "y": -3, "speed": 100},
                    "audio": {"deviceFlow": "somewhere-else"},
                },
                "presetScene": {"presetId": "missing"},
                "barWallScene": {
                    "render": {"barGridSize": 200, "shaderStyle": "missing"},
                    "range": {
                        "mode": "manual",
                        "manualMinimum": 12,
                        "manualMaximum": 3,
                        "rollingHistoryValueCount": 2,
                        "standardDeviationMultiplier": 99,
                    },
                },
                "session": {"cadenceMs": 1},
            }
        )

        normalized_request_payload = preview_bundle.normalized_request_payload
        self.assertEqual(normalized_request_payload["target"]["host"], "127.0.0.1")
        self.assertEqual(normalized_request_payload["target"]["port"], 65535)
        self.assertEqual(normalized_request_payload["sceneMode"], "preset_scene")
        self.assertEqual(normalized_request_payload["source"]["mode"], "json_document")
        self.assertEqual(normalized_request_payload["source"]["audio"]["deviceFlow"], "output")
        self.assertEqual(normalized_request_payload["barWallScene"]["render"]["barGridSize"], 24)
        self.assertEqual(
            normalized_request_payload["barWallScene"]["range"]["manualMaximum"],
            13.0,
        )
        self.assertEqual(normalized_request_payload["session"]["cadenceMs"], 40)

    def test_constant_json_values_use_the_flat_normalized_profile_fallback(self) -> None:
        preview_bundle = build_visualizer_preview_bundle(
            {
                "sceneMode": "preset_scene",
                "source": {
                    "mode": "json_document",
                    "jsonText": '{"samples":[5,5,5,5]}',
                },
            }
        )

        signal_payload = preview_bundle.collected_source_data.preset_scene_signal_payload
        self.assertAlmostEqual(signal_payload["pointer"]["x"], 0.5)
        self.assertAlmostEqual(signal_payload["audio"]["level"], 0.5)


class ActivityJournalTests(unittest.TestCase):
    """Exercise the shared structured activity journal."""

    def test_journal_writes_and_reads_recent_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            journal_path = Path(temporary_directory) / "activity.jsonl"
            journal = ActivityJournal(source_app="tests", journal_path=journal_path)
            journal.write(component="visualizer-studio", level="info", message="hello world")
            journal.write(component="visualizer-studio", level="warning", message="second event")

            entries = read_recent_activity_entries(journal_path=journal_path, limit=10)

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[-1]["level"], "WARNING")
        self.assertEqual(entries[-1]["message"], "second event")
        self.assertEqual(journal.journal_path, journal_path)

    def test_environment_variable_controls_the_default_journal_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            configured_path = Path(temporary_directory) / "custom.jsonl"
            with mock.patch.dict(
                os.environ,
                {"HALCYN_ACTIVITY_LOG_PATH": str(configured_path)},
                clear=False,
            ):
                resolved_path = get_default_activity_journal_path()

        self.assertEqual(resolved_path, configured_path.resolve())

    def test_reader_skips_malformed_lines_and_honors_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            journal_path = Path(temporary_directory) / "activity.jsonl"
            journal_path.write_text(
                '\n{"message":"first","level":"INFO"}\nnot-json\n{"message":"second","level":"INFO"}\n',
                encoding="utf-8",
            )

            entries = read_recent_activity_entries(journal_path=journal_path, limit=1)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["message"], "second")


class VisualizerOperatorControllerTests(unittest.TestCase):
    """Exercise the controller behind Visualizer Studio."""

    def setUp(self) -> None:
        self.render_api_client = _FakeRenderApiClient()
        self.audio_input_service = _FakeAudioInputService()
        self.controller = VisualizerOperatorConsoleController(
            project_root=Path(__file__).resolve().parents[2],
            render_api_client=self.render_api_client,
            audio_input_service=self.audio_input_service,
        )

    def tearDown(self) -> None:
        self.controller.close()

    def test_start_audio_capture_updates_request_payload(self) -> None:
        audio_snapshot = self.controller.start_audio_capture("speaker-1", "output")
        request_payload = self.controller.current_request_payload()

        self.assertTrue(audio_snapshot.capturing)
        self.assertEqual(request_payload["source"]["audio"]["deviceIdentifier"], "speaker-1")
        self.assertEqual(request_payload["source"]["audio"]["deviceFlow"], "output")

    def test_stop_audio_capture_returns_idle_snapshot(self) -> None:
        self.controller.start_audio_capture("speaker-1", "output")
        audio_snapshot = self.controller.stop_audio_capture()

        self.assertFalse(audio_snapshot.capturing)

    def test_apply_current_scene_uses_renderer_client(self) -> None:
        self.controller.replace_request_payload(
            {
                "sceneMode": "bar_wall_scene",
                "source": {"mode": "plain_text", "plainText": "HELLO"},
            }
        )
        apply_result = self.controller.apply_current_scene()

        self.assertEqual(apply_result["status"], "applied")
        self.assertEqual(self.render_api_client.requests[-1][0], "apply")

    def test_live_stream_increments_applied_frames(self) -> None:
        self.controller.replace_request_payload(
            {"sceneMode": "preset_scene", "source": {"mode": "plain_text", "plainText": "HELLO"}}
        )
        self.controller.start_live_stream()
        deadline = time.time() + 0.4
        while (
            time.time() < deadline
            and self.controller.live_stream_snapshot()["frames_applied"] < 1
        ):
            time.sleep(0.02)
        live_stream_snapshot = self.controller.stop_live_stream()

        self.assertGreaterEqual(live_stream_snapshot["frames_applied"], 1)

    def test_settings_document_round_trip_preserves_scene_mode(self) -> None:
        self.controller.replace_request_payload({"sceneMode": "bar_wall_scene"})
        settings_document = self.controller.settings_document()
        normalized_request_payload = self.controller.load_settings_document(settings_document)

        self.assertEqual(normalized_request_payload["sceneMode"], "bar_wall_scene")

    def test_load_settings_document_rejects_non_object_payloads(self) -> None:
        with self.assertRaisesRegex(ValueError, "request payload object"):
            self.controller.load_settings_document({"requestPayload": "not-a-dictionary"})

    def test_refresh_audio_devices_uses_the_current_flow_when_none_is_given(self) -> None:
        self.controller.update_request_payload({"source": {"audio": {"deviceFlow": "output"}}})

        devices = self.controller.refresh_audio_devices()

        self.assertEqual(devices[0].device_flow, "output")

    def test_health_uses_renderer_client(self) -> None:
        response = self.controller.health()

        self.assertEqual(response.status, 200)
        self.assertEqual(self.render_api_client.requests[-1][0], "health")

    def test_validate_current_scene_reports_validation_failures(self) -> None:
        failing_client = _FakeRenderApiClient(
            validate_status=400,
            validate_reason="Bad Request",
            validate_body="broken",
        )
        controller = VisualizerOperatorConsoleController(
            project_root=Path(__file__).resolve().parents[2],
            render_api_client=failing_client,
            audio_input_service=_FakeAudioInputService(),
        )
        try:
            validation_result = controller.validate_current_scene()
        finally:
            controller.close()

        self.assertEqual(validation_result["status"], "validation-failed")
        self.assertEqual(validation_result["response"].status, 400)

    def test_reset_to_defaults_clears_bar_wall_history_and_live_snapshot(self) -> None:
        self.controller.replace_request_payload(
            {
                "sceneMode": "bar_wall_scene",
                "source": {"mode": "plain_text", "plainText": "HELLO"},
            }
        )
        self.controller.apply_current_scene()
        normalized_request_payload = self.controller.reset_to_defaults()

        self.assertEqual(normalized_request_payload["sceneMode"], "preset_scene")
        self.assertEqual(self.controller.live_stream_snapshot()["status"], "stopped")
        self.assertEqual(self.controller._bar_wall_rolling_history_values, [])


class VisualizerOperatorWindowTests(unittest.TestCase):
    """Exercise the Visualizer Studio window behavior."""

    def _build_window(
        self,
        controller: VisualizerOperatorConsoleController | None = None,
    ) -> tuple[ttkb.Window, VisualizerOperatorConsoleController, VisualizerOperatorConsoleWindow]:
        root_window = ttkb.Window(themename="superhero")
        root_window.withdraw()
        root_window.after = mock.Mock(return_value="after-id")  # type: ignore[method-assign]
        root_window.after_cancel = mock.Mock()  # type: ignore[method-assign]
        controller = controller or VisualizerOperatorConsoleController(
            project_root=Path(__file__).resolve().parents[2],
            render_api_client=_FakeRenderApiClient(),
            audio_input_service=_FakeAudioInputService(),
        )
        with mock.patch.object(
            VisualizerOperatorConsoleWindow,
            "_schedule_status_refresh",
            autospec=True,
            return_value=None,
        ):
            window = VisualizerOperatorConsoleWindow(root_window, controller)
        return root_window, controller, window

    def test_window_can_open_preview_json(self) -> None:
        root_window, controller, window = self._build_window()
        try:
            self.assertEqual(root_window.title(), "Halcyn Visualizer Studio")
            window._refresh_preview()
            window._open_preview_window()
            self.assertIsNotNone(window._preview_text_widget)
            assert window._preview_text_widget is not None
            preview_text = window._preview_text_widget.get("1.0", "end")
            self.assertIn("sceneType", preview_text)
        finally:
            controller.close()
            root_window.destroy()

    def test_window_loads_json_examples_and_files(self) -> None:
        root_window, controller, window = self._build_window()
        try:
            window._load_json_example('{"hello":"world"}')
            self.assertIn("hello", window._json_text_widget.get("1.0", "end"))

            with tempfile.TemporaryDirectory() as temporary_directory:
                json_file_path = Path(temporary_directory) / "example.json"
                json_file_path.write_text('{"fromFile":true}', encoding="utf-8")
                with mock.patch(
                    "desktop_visualizer_operator_console.visualizer_operator_console_window.filedialog.askopenfilename",
                    return_value=str(json_file_path),
                ):
                    window._load_json_file()

            self.assertIn("fromFile", window._json_text_widget.get("1.0", "end"))
        finally:
            controller.close()
            root_window.destroy()

    def test_window_builds_request_payload_with_selected_audio_identifier(self) -> None:
        root_window, controller, window = self._build_window()
        try:
            window._audio_device_variable.set("Output: Desktop speakers")
            request_payload = window._build_request_payload_from_user_interface()
        finally:
            controller.close()
            root_window.destroy()

        self.assertEqual(request_payload["source"]["audio"]["deviceIdentifier"], "speaker-1")

    def test_window_handles_audio_refresh_errors(self) -> None:
        audio_service = _FakeAudioInputService()
        audio_service.refresh_error = RuntimeError("refresh failed")
        controller = VisualizerOperatorConsoleController(
            project_root=Path(__file__).resolve().parents[2],
            render_api_client=_FakeRenderApiClient(),
            audio_input_service=audio_service,
        )
        root_window, controller, window = self._build_window(controller)
        try:
            with mock.patch(
                "desktop_visualizer_operator_console.visualizer_operator_console_window.messagebox.showerror"
            ) as mocked_show_error:
                window._refresh_audio_devices()
        finally:
            controller.close()
            root_window.destroy()

        mocked_show_error.assert_called_once()

    def test_window_handles_empty_audio_device_lists(self) -> None:
        audio_service = _FakeAudioInputService()
        audio_service.devices_by_flow["output"] = []
        controller = VisualizerOperatorConsoleController(
            project_root=Path(__file__).resolve().parents[2],
            render_api_client=_FakeRenderApiClient(),
            audio_input_service=audio_service,
        )
        root_window, controller, window = self._build_window(controller)
        try:
            window._refresh_audio_devices()
            self.assertEqual(window._audio_device_variable.get(), "")
        finally:
            controller.close()
            root_window.destroy()

    def test_window_start_audio_capture_requires_a_selection(self) -> None:
        root_window, controller, window = self._build_window()
        try:
            window._audio_device_variable.set("")
            with mock.patch(
                "desktop_visualizer_operator_console.visualizer_operator_console_window.messagebox.showerror"
            ) as mocked_show_error:
                window._start_audio_capture()
        finally:
            controller.close()
            root_window.destroy()

        mocked_show_error.assert_called_once()

    def test_window_start_and_stop_audio_capture_updates_status(self) -> None:
        root_window, controller, window = self._build_window()
        try:
            window._audio_device_variable.set("Output: Desktop speakers")
            window._start_audio_capture()
            window._refresh_status_labels()
            self.assertIn("Capturing Desktop speakers", window._audio_status_variable.get())
            self.assertGreater(window._volume_meter_progress_variable.get(), 0.0)

            window._stop_audio_capture()
            self.assertEqual(window._volume_meter_text_variable.get(), "0%")
        finally:
            controller.close()
            root_window.destroy()

    def test_window_start_audio_capture_surfaces_backend_errors(self) -> None:
        audio_service = _FakeAudioInputService()
        audio_service.start_error = RuntimeError("device busy")
        controller = VisualizerOperatorConsoleController(
            project_root=Path(__file__).resolve().parents[2],
            render_api_client=_FakeRenderApiClient(),
            audio_input_service=audio_service,
        )
        root_window, controller, window = self._build_window(controller)
        try:
            window._audio_device_variable.set("Output: Desktop speakers")
            with mock.patch(
                "desktop_visualizer_operator_console.visualizer_operator_console_window.messagebox.showerror"
            ) as mocked_show_error:
                window._start_audio_capture()
        finally:
            controller.close()
            root_window.destroy()

        mocked_show_error.assert_called_once()

    def test_window_pointer_motion_and_leave_update_the_controller(self) -> None:
        root_window, controller, window = self._build_window()
        try:
            with mock.patch.object(window, "_schedule_preview_refresh") as mocked_refresh:
                window._source_mode_variable.set("pointer_pad")
                window._on_pointer_motion(mock.Mock(x=300, y=120))
                request_payload = controller.current_request_payload()
                self.assertGreater(request_payload["source"]["pointer"]["speed"], 0.0)
                mocked_refresh.assert_called()

                mocked_refresh.reset_mock()
                window._on_pointer_leave(mock.Mock())
                self.assertEqual(
                    controller.current_request_payload()["source"]["pointer"]["speed"],
                    0.0,
                )
                mocked_refresh.assert_called_once()
        finally:
            controller.close()
            root_window.destroy()

    def test_window_builds_human_readable_preview_summaries(self) -> None:
        root_window, controller, window = self._build_window()
        try:
            bar_wall_summary = window._build_preview_summary_text(
                {
                    "sceneMode": "bar_wall_scene",
                    "barCount": 64,
                    "sourceValueCount": 128,
                    "activeRangeMinimum": 0.0,
                    "activeRangeMaximum": 255.0,
                    "shaderStyle": "neon",
                }
            )
            preset_summary = window._build_preview_summary_text(
                {
                    "sceneType": "3d",
                    "primitive": "triangles",
                    "vertexCount": 42,
                    "indexCount": 84,
                }
            )
        finally:
            controller.close()
            root_window.destroy()

        self.assertIn("Bar wall summary", bar_wall_summary)
        self.assertIn("shader neon", bar_wall_summary)
        self.assertIn("Preset scene summary", preset_summary)

    def test_window_transport_buttons_update_status_labels(self) -> None:
        root_window, controller, window = self._build_window()
        try:
            window._run_health_check()
            self.assertIn("Health: 200 OK", window._health_status_variable.get())

            window._validate_current_scene()
            self.assertIn("Validation: 200 OK", window._result_status_variable.get())

            window._apply_current_scene()
            self.assertIn("Apply: 202 Accepted", window._result_status_variable.get())

            window._start_live_stream()
            self.assertEqual(window._live_status_variable.get(), "Live stream running.")
            window._stop_live_stream()
            self.assertEqual(window._live_status_variable.get(), "Live stream stopped.")
        finally:
            controller.close()
            root_window.destroy()

    def test_window_transport_buttons_surface_errors(self) -> None:
        root_window, controller, window = self._build_window()
        try:
            with mock.patch.object(controller, "health", side_effect=RuntimeError("boom")):
                window._run_health_check()
                self.assertIn("Health check failed", window._health_status_variable.get())

            with mock.patch.object(
                controller,
                "validate_current_scene",
                side_effect=RuntimeError("bad validate"),
            ):
                window._validate_current_scene()
                self.assertIn("Validation failed", window._result_status_variable.get())

            with mock.patch.object(
                controller,
                "apply_current_scene",
                side_effect=RuntimeError("bad apply"),
            ):
                window._apply_current_scene()
                self.assertIn("Apply failed", window._result_status_variable.get())

            with mock.patch.object(
                controller,
                "start_live_stream",
                side_effect=RuntimeError("bad live"),
            ):
                window._start_live_stream()
                self.assertIn("Live stream failed to start", window._live_status_variable.get())
        finally:
            controller.close()
            root_window.destroy()

    def test_window_can_save_and_load_settings_files(self) -> None:
        root_window, controller, window = self._build_window()
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                settings_path = Path(temporary_directory) / DEFAULT_SETTINGS_FILE_NAME
                with mock.patch(
                    "desktop_visualizer_operator_console.visualizer_operator_console_window.filedialog.asksaveasfilename",
                    return_value=str(settings_path),
                ):
                    window._save_settings_file()

                self.assertTrue(settings_path.exists())
                saved_document = json.loads(settings_path.read_text(encoding="utf-8"))
                saved_document["requestPayload"]["sceneMode"] = "bar_wall_scene"
                settings_path.write_text(json.dumps(saved_document), encoding="utf-8")

                with mock.patch(
                    "desktop_visualizer_operator_console.visualizer_operator_console_window.filedialog.askopenfilename",
                    return_value=str(settings_path),
                ):
                    window._load_settings_file()

            self.assertEqual(window._scene_mode_variable.get(), "bar_wall_scene")
        finally:
            controller.close()
            root_window.destroy()

    def test_window_handles_load_settings_errors(self) -> None:
        root_window, controller, window = self._build_window()
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                broken_settings_path = Path(temporary_directory) / "broken.json"
                broken_settings_path.write_text("{not json}", encoding="utf-8")
                with mock.patch(
                    "desktop_visualizer_operator_console.visualizer_operator_console_window.filedialog.askopenfilename",
                    return_value=str(broken_settings_path),
                ), mock.patch(
                    "desktop_visualizer_operator_console.visualizer_operator_console_window.messagebox.showerror"
                ) as mocked_show_error:
                    window._load_settings_file()
        finally:
            controller.close()
            root_window.destroy()

        mocked_show_error.assert_called_once()

    def test_window_preview_window_can_be_reused_and_copied(self) -> None:
        root_window, controller, window = self._build_window()
        try:
            window._refresh_preview()
            window._open_preview_window()
            preview_window = window._preview_window
            window._copy_preview_json()
            self.assertIn("Copied preview JSON", window._result_status_variable.get())

            window._open_preview_window()
            self.assertIs(window._preview_window, preview_window)
            assert window._preview_text_widget is not None
            self.assertIn("sceneType", window._preview_text_widget.get("1.0", "end"))

            window._latest_preview_bundle = None
            window._copy_preview_json()
        finally:
            controller.close()
            root_window.destroy()

    def test_window_refresh_status_labels_updates_meter_and_preview_polling(self) -> None:
        root_window, controller, window = self._build_window()
        try:
            controller.start_audio_capture("speaker-1", "output")
            controller.start_live_stream()
            window._source_mode_variable.set("audio_device")
            with mock.patch.object(window, "_schedule_preview_refresh") as mocked_refresh:
                window._refresh_status_labels()
                self.assertGreater(window._volume_meter_progress_variable.get(), 0.0)
                self.assertIn("running", window._live_status_variable.get())
                mocked_refresh.assert_called_once()
        finally:
            controller.close()
            root_window.destroy()

    def test_window_reset_to_defaults_and_close_requested(self) -> None:
        root_window, controller, window = self._build_window()
        try:
            window._scene_mode_variable.set("bar_wall_scene")
            with mock.patch.object(window, "_schedule_preview_refresh") as mocked_refresh:
                window._reset_to_defaults()
                self.assertEqual(window._scene_mode_variable.get(), "preset_scene")
                self.assertGreaterEqual(mocked_refresh.call_count, 1)
                self.assertEqual(mocked_refresh.call_args_list[-1], mock.call(immediate=True))

            window._refresh_preview()
            window._open_preview_window()
            assert window._preview_window is not None

            with mock.patch.object(controller, "close", wraps=controller.close) as mocked_close:
                window._on_close_requested()
                mocked_close.assert_called_once()
        finally:
            try:
                root_window_exists = bool(root_window.winfo_exists())
            except Exception:
                root_window_exists = False
            if root_window_exists:
                root_window.destroy()


class VisualizerOperatorEntryPointTests(unittest.TestCase):
    """Exercise the module and window entry points."""

    def test_module_entry_point_calls_window_main(self) -> None:
        with mock.patch(
            "desktop_visualizer_operator_console.visualizer_operator_console_window.main"
        ) as mocked_main:
            runpy.run_module("desktop_visualizer_operator_console.__main__", run_name="__main__")

        mocked_main.assert_called_once()

    def test_window_main_constructs_the_root_window_and_runs_the_loop(self) -> None:
        with mock.patch(
            "desktop_visualizer_operator_console.visualizer_operator_console_window.ttkb.Window"
        ) as mocked_window_type, mock.patch(
            "desktop_visualizer_operator_console.visualizer_operator_console_window.VisualizerOperatorConsoleWindow"
        ) as mocked_window_class:
            root_window = mock.Mock()
            mocked_window_type.return_value = root_window

            from desktop_visualizer_operator_console.visualizer_operator_console_window import (
                main,
            )

            main()

        mocked_window_type.assert_called_once_with(themename="superhero")
        mocked_window_class.assert_called_once_with(root_window)
        root_window.mainloop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
