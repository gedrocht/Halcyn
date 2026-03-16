"""Tests for the desktop spectrograph control panel suite."""

from __future__ import annotations

import json
import runpy
import time
import tkinter as tk
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from desktop_render_control_panel.render_api_client import RenderApiResponse
from desktop_spectrograph_control_panel.spectrograph_control_panel_controller import (
    DesktopSpectrographControlPanelController,
)
from desktop_spectrograph_control_panel.spectrograph_control_panel_controller import (
    _deep_merge as controller_deep_merge,
)
from desktop_spectrograph_control_panel.spectrograph_control_panel_controller import (
    _safe_int as controller_safe_int,
)
from desktop_spectrograph_control_panel.spectrograph_control_panel_window import (
    DesktopSpectrographControlPanelWindow,
)
from desktop_spectrograph_control_panel.spectrograph_scene_builder import (
    _clamp_float,
    _clamp_int,
    build_catalog_payload,
    build_default_request_payload,
    build_spectrograph_scene_result,
    flatten_generic_json_value,
)
from desktop_spectrograph_control_panel.spectrograph_scene_builder import (
    _deep_merge as scene_builder_deep_merge,
)


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


class SpectrographSceneBuilderTests(unittest.TestCase):
    """Exercise the generic-data-to-bar-scene transformation helpers."""

    def test_catalog_and_default_payload_expose_beginner_friendly_choices(self) -> None:
        catalog_payload = build_catalog_payload()
        default_request_payload = build_default_request_payload()

        self.assertEqual(catalog_payload["status"], "ok")
        self.assertIn("heatmap", catalog_payload["shaderStyles"])
        self.assertGreaterEqual(len(catalog_payload["examples"]), 3)
        self.assertEqual(default_request_payload["render"]["shaderStyle"], "heatmap")
        self.assertEqual(default_request_payload["render"]["barGridSize"], 8)
        self.assertEqual(default_request_payload["target"]["port"], 8090)

    def test_flatten_generic_json_value_handles_numbers_booleans_strings_and_nested_objects(
        self,
    ) -> None:
        flattened_values = flatten_generic_json_value(
            {
                "numbers": [1, 2.5, True, False],
                "text": "AB",
                "nested": {"more": [3, "C"]},
            }
        )

        self.assertEqual(flattened_values, [1.0, 2.5, 1.0, 0.0, 65.0, 66.0, 3.0, 67.0])

    def test_build_spectrograph_scene_result_generates_one_bar_value_per_grid_cell(self) -> None:
        build_result = build_spectrograph_scene_result(
            {
                "data": {
                    "jsonText": json.dumps(
                        {
                            "title": "AB",
                            "values": [0, 1, 2, 3, 4, 5],
                        }
                    )
                },
                "render": {"barGridSize": 4, "shaderStyle": "heatmap", "antiAliasing": False},
            },
            rolling_history_values=[10.0, 12.0],
        )

        self.assertEqual(build_result.analysis["barGridSize"], 4)
        self.assertEqual(build_result.analysis["barCount"], 16)
        self.assertEqual(build_result.scene["sceneType"], "3d")
        self.assertEqual(build_result.scene["renderStyle"]["shader"], "heatmap")
        self.assertFalse(build_result.scene["renderStyle"]["antiAliasing"])
        self.assertEqual(len(build_result.scene["vertices"]), 16 * 8)
        self.assertEqual(len(build_result.scene["indices"]), 16 * 36)
        self.assertGreaterEqual(build_result.analysis["rollingHistoryValueCount"], 2)
        self.assertIn(65.0, build_result.flattened_source_values)

    def test_manual_range_is_preserved_and_out_of_range_values_are_counted(self) -> None:
        build_result = build_spectrograph_scene_result(
            {
                "data": {"jsonText": json.dumps({"values": [-10, 0, 50, 200]})},
                "render": {"barGridSize": 2},
                "range": {
                    "mode": "manual",
                    "manualMinimum": 0.0,
                    "manualMaximum": 100.0,
                    "rollingHistoryValueCount": 8,
                },
            }
        )

        self.assertEqual(build_result.analysis["rangeMode"], "manual")
        self.assertEqual(build_result.analysis["activeRangeMinimum"], 0.0)
        self.assertEqual(build_result.analysis["activeRangeMaximum"], 100.0)
        self.assertGreater(build_result.analysis["clippedValueCount"], 0)

    def test_invalid_json_produces_a_readable_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "could not be parsed"):
            build_spectrograph_scene_result({"data": {"jsonText": '{"bad": ]'}})

    def test_helper_functions_clamp_and_merge_values_predictably(self) -> None:
        merged_payload = {"outer": {"left": 1, "right": 2}}
        scene_builder_deep_merge(merged_payload, {"outer": {"right": 9}, "new": 7})

        self.assertEqual(merged_payload["outer"]["left"], 1)
        self.assertEqual(merged_payload["outer"]["right"], 9)
        self.assertEqual(merged_payload["new"], 7)
        self.assertEqual(_clamp_int("40", 2, 4, 32), 32)
        self.assertEqual(_clamp_int("bad", 6, 4, 32), 6)
        self.assertAlmostEqual(_clamp_float("1.25", 0.5, 0.0, 2.0), 1.25)
        self.assertAlmostEqual(_clamp_float("bad", 0.5, 0.0, 2.0), 0.5)


class SpectrographControllerTests(unittest.TestCase):
    """Exercise the non-visual orchestration behind the desktop panel."""

    def setUp(self) -> None:
        self.fake_render_api_client = FakeRenderApiClient()
        self.controller = DesktopSpectrographControlPanelController(
            render_api_client=self.fake_render_api_client
        )

    def tearDown(self) -> None:
        self.controller.close()

    def test_preview_validate_and_apply_use_the_current_renderer_target(self) -> None:
        self.controller.replace_request_payload(
            {
                "target": {"host": "127.0.0.9", "port": 8095},
                "data": {"jsonText": json.dumps({"values": [1, 2, 3, 4]})},
                "render": {"barGridSize": 3},
            }
        )

        preview_result = self.controller.preview_scene_result()
        validation_result = self.controller.validate_current_scene()
        apply_result = self.controller.apply_current_scene()

        self.assertEqual(preview_result.target["host"], "127.0.0.9")
        self.assertEqual(preview_result.target["port"], 8095)
        self.assertEqual(self.fake_render_api_client.validate_requests[0][0], "127.0.0.9")
        self.assertEqual(self.fake_render_api_client.apply_requests[0][1], 8095)
        self.assertEqual(validation_result["status"], "validated")
        self.assertEqual(apply_result["status"], "applied")
        self.assertGreater(
            self.controller.preview_scene_result().analysis["rollingHistoryValueCount"],
            0,
        )

    def test_settings_document_round_trip_preserves_the_current_payload(self) -> None:
        updated_payload = self.controller.update_request_payload(
            {
                "render": {"barGridSize": 6, "shaderStyle": "neon"},
                "range": {"mode": "manual", "manualMinimum": -10.0, "manualMaximum": 90.0},
            }
        )
        settings_document = self.controller.settings_document()
        restored_payload = self.controller.load_settings_document(settings_document)

        self.assertEqual(updated_payload["render"]["barGridSize"], 6)
        self.assertEqual(restored_payload["render"]["shaderStyle"], "neon")
        self.assertEqual(restored_payload["range"]["mode"], "manual")
        self.assertEqual(restored_payload["range"]["manualMinimum"], -10.0)

    def test_live_stream_updates_snapshot_and_stops_cleanly(self) -> None:
        self.controller.replace_request_payload(
            {
                "data": {"jsonText": json.dumps({"values": list(range(24))})},
                "session": {"cadenceMs": 40},
            }
        )

        running_snapshot = self.controller.start_live_stream()
        deadline = time.time() + 1.0
        latest_snapshot = running_snapshot
        while time.time() < deadline:
            latest_snapshot = self.controller.live_stream_snapshot()
            if latest_snapshot["frames_applied"] > 0:
                break
            time.sleep(0.02)

        stopped_snapshot = self.controller.stop_live_stream()

        self.assertEqual(running_snapshot["status"], "running")
        self.assertGreater(latest_snapshot["frames_applied"], 0)
        self.assertEqual(stopped_snapshot["status"], "stopped")

    def test_controller_helper_functions_keep_updates_simple(self) -> None:
        merged_payload = {"outer": {"left": 1, "right": 2}}
        controller_deep_merge(merged_payload, {"outer": {"right": 11}, "extra": True})

        self.assertEqual(merged_payload["outer"]["left"], 1)
        self.assertEqual(merged_payload["outer"]["right"], 11)
        self.assertTrue(merged_payload["extra"])
        self.assertEqual(controller_safe_int("15", 4), 15)
        self.assertEqual(controller_safe_int("oops", 4), 4)


class SpectrographWindowTests(unittest.TestCase):
    """Exercise the desktop spectrograph Tkinter window behavior."""

    def setUp(self) -> None:
        self.root_window = tk.Tk()
        self.root_window.withdraw()
        self.fake_render_api_client = FakeRenderApiClient()
        self.controller = DesktopSpectrographControlPanelController(
            render_api_client=self.fake_render_api_client
        )
        self.window = DesktopSpectrographControlPanelWindow(
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

    def test_window_initializes_preview_labels_and_updates_slider_text(self) -> None:
        self.assertIn("Preview ready", self.window._result_status_variable.get())
        self.assertIn("Range mode", self.window._statistics_summary_variable.get())

        self.window._bar_grid_size_variable.set(10)
        self.window._on_bar_grid_size_changed("10")
        self.window._live_cadence_variable.set(375)
        self.window._on_live_cadence_changed("375")

        self.assertEqual(self.window._bar_grid_size_label_variable.get(), "10 x 10")
        self.assertEqual(self.window._live_cadence_label_variable.get(), "375 ms")

    def test_window_can_switch_to_manual_range_and_handle_invalid_json(self) -> None:
        self.window._range_mode_variable.set("manual")
        self.window._refresh_range_mode_widgets()
        self.root_window.update_idletasks()

        manual_entry_states = [
            str(entry.cget("state")) for entry in self.window._manual_range_entry_widgets
        ]
        self.assertEqual(manual_entry_states, ["normal", "normal"])

        self.window._replace_input_json_text('{"broken": ]')
        self.root_window.update_idletasks()

        self.assertIsNone(self.window._latest_preview_result)
        self.assertIn("Preview error", self.window._result_status_variable.get())

    def test_window_can_load_examples_files_and_randomized_samples(self) -> None:
        self.window._load_example_input("string_heavy")
        self.root_window.update_idletasks()
        self.assertIn(
            "Strings become byte values",
            self.window._input_json_text_widget.get("1.0", "end"),
        )

        self.window._load_random_numeric_sample()
        self.root_window.update_idletasks()
        self.assertIn("Randomized sample", self.window._input_json_text_widget.get("1.0", "end"))

        with TemporaryDirectory() as temporary_directory:
            json_file_path = Path(temporary_directory) / "spectrograph-input.json"
            json_file_path.write_text(json.dumps({"values": [9, 8, 7]}), encoding="utf-8")

            with mock.patch(
                "desktop_spectrograph_control_panel.spectrograph_control_panel_window.filedialog.askopenfilename",
                return_value=str(json_file_path),
            ):
                self.window._load_json_file()

        self.root_window.update_idletasks()
        self.assertIn('"values": [', self.window._input_json_text_widget.get("1.0", "end"))

    def test_window_can_save_load_and_show_scene_json(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings_file_path = Path(temporary_directory) / "spectrograph-settings.json"

            with mock.patch(
                "desktop_spectrograph_control_panel.spectrograph_control_panel_window.filedialog.asksaveasfilename",
                return_value=str(settings_file_path),
            ):
                self.window._save_settings_document()

            saved_settings_document = json.loads(settings_file_path.read_text(encoding="utf-8"))
            saved_settings_document["requestPayload"]["render"]["barGridSize"] = 5
            settings_file_path.write_text(
                json.dumps(saved_settings_document, indent=2),
                encoding="utf-8",
            )

            with mock.patch(
                "desktop_spectrograph_control_panel.spectrograph_control_panel_window.filedialog.askopenfilename",
                return_value=str(settings_file_path),
            ):
                self.window._load_settings_document()

        self.window._open_scene_json_window()
        self.root_window.update_idletasks()
        self.assertIsNotNone(self.window._scene_preview_window)
        self.assertIsNotNone(self.window._scene_preview_text_widget)
        assert self.window._scene_preview_text_widget is not None
        preview_text = self.window._scene_preview_text_widget.get("1.0", "end")
        self.assertIn('"sceneType": "3d"', preview_text)

        self.window._copy_scene_json_to_clipboard()
        clipboard_text = self.root_window.clipboard_get()
        self.assertIn('"vertices"', clipboard_text)
        self.assertEqual(self.window._bar_grid_size_variable.get(), 5)

    def test_window_actions_update_renderer_status_messages(self) -> None:
        self.window._run_health_check()
        self.window._validate_current_scene()
        validation_status_text = self.window._result_status_variable.get()
        self.window._apply_current_scene()

        self.assertIn("Renderer reachable", self.window._health_status_variable.get())
        self.assertIn("Validation succeeded", validation_status_text)

        self.window._start_live_stream()
        deadline = time.time() + 1.0
        while time.time() < deadline:
            self.window._poll_live_stream_state()
            if "Frames applied" in self.window._live_stream_status_variable.get():
                break
            time.sleep(0.02)
        self.window._stop_live_stream()

        self.assertTrue(self.fake_render_api_client.apply_requests)
        self.assertIn("stopped", self.window._live_stream_status_variable.get())

    def test_window_can_revert_defaults_and_close_preview_window(self) -> None:
        self.window._bar_grid_size_variable.set(12)
        self.window._target_port_variable.set("9000")
        self.window._revert_defaults()

        self.assertEqual(self.window._bar_grid_size_variable.get(), 8)
        self.assertEqual(self.window._target_port_variable.get(), "8090")

        self.window._open_scene_json_window()
        self.root_window.update_idletasks()
        self.window._on_scene_preview_window_closed()
        self.assertIsNone(self.window._scene_preview_window)
        self.assertIsNone(self.window._scene_preview_text_widget)

    def test_window_reports_empty_copy_request_with_message_box(self) -> None:
        self.window._latest_preview_result = None
        with mock.patch(
            "desktop_spectrograph_control_panel.spectrograph_control_panel_window.messagebox.showinfo"
        ) as showinfo_mock:
            self.window._copy_scene_json_to_clipboard()

        showinfo_mock.assert_called_once()

    def test_module_entry_point_calls_window_main(self) -> None:
        with mock.patch(
            "desktop_spectrograph_control_panel.spectrograph_control_panel_window.main",
            return_value=None,
        ) as main_mock:
            runpy.run_module("desktop_spectrograph_control_panel.__main__", run_name="__main__")

        main_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
