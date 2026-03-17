"""Tests for the shared desktop bridge and activity-log helpers.

These helpers sit underneath multiple desktop apps, so they deserve their own
small test layer rather than only being exercised indirectly through the larger
window/controller suites.
"""

from __future__ import annotations

import json
import tkinter as tk
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from desktop_shared_control_support.activity_log import (
    DesktopActivityLogEntry,
    DesktopActivityLogger,
    read_recent_desktop_activity_entries,
)
from desktop_shared_control_support.activity_log_window import DesktopActivityLogWindow
from desktop_shared_control_support.local_json_bridge import (
    LocalJsonBridgeClient,
    LocalJsonBridgeServer,
    normalize_local_json_bridge_path,
)
from desktop_spectrograph_audio_source_panel.spectrograph_external_bridge_client import (
    SpectrographExternalBridgeClient,
)


class LocalJsonBridgeTests(unittest.TestCase):
    """Exercise the shared loopback JSON bridge helpers directly."""

    def test_local_json_bridge_client_and_server_round_trip_json_successfully(self) -> None:
        received_payloads: list[tuple[str, str]] = []
        bridge_server = LocalJsonBridgeServer(
            host="127.0.0.1",
            port=0,
            on_json_received=lambda json_text, source_label: received_payloads.append(
                (json_text, source_label)
            ),
        )
        started_status = bridge_server.start()

        bridge_client = LocalJsonBridgeClient()
        delivery_response = bridge_client.deliver_json_text(
            host=str(started_status["host"]),
            port=int(started_status["port"]),
            path="external-data",
            source_label="unit-test",
            json_text=json.dumps({"values": [1, 2, 3]}),
        )
        stopped_status = bridge_server.stop()

        self.assertTrue(delivery_response.ok)
        self.assertEqual(delivery_response.status, 202)
        self.assertEqual(received_payloads[0][1], "unit-test")
        self.assertFalse(stopped_status["listening"])

    def test_audio_sender_bridge_client_can_deliver_to_the_shared_signal_router_bridge(
        self,
    ) -> None:
        """Prove the Audio Sender client can talk to the shared bridge server.

        This is the exact cross-application path that matters when Audio Sender
        feeds Signal Router or Bars Studio, so it deserves a direct regression
        test instead of only separate unit tests on each side.
        """

        received_payloads: list[tuple[str, str]] = []
        bridge_server = LocalJsonBridgeServer(
            host="127.0.0.1",
            port=0,
            on_json_received=lambda json_text, source_label: received_payloads.append(
                (json_text, source_label)
            ),
        )
        started_status = bridge_server.start()

        audio_sender_bridge_client = SpectrographExternalBridgeClient()
        delivery_response = audio_sender_bridge_client.deliver_json_text(
            host=str(started_status["host"]),
            port=int(started_status["port"]),
            path="/external-data",
            source_label="audio-sender",
            json_text=json.dumps({"values": [0.1, 0.2, 0.3, 0.4]}),
        )

        final_bridge_status = bridge_server.stop()

        self.assertTrue(delivery_response.ok)
        self.assertEqual(delivery_response.status, 202)
        self.assertEqual(received_payloads[0][1], "audio-sender")
        self.assertEqual(
            json.loads(received_payloads[0][0]),
            {"values": [0.1, 0.2, 0.3, 0.4]},
        )
        self.assertEqual(final_bridge_status["last_source_label"], "audio-sender")

    def test_normalize_local_json_bridge_path_handles_blank_and_missing_slash(self) -> None:
        self.assertEqual(normalize_local_json_bridge_path(""), "/external-data")
        self.assertEqual(normalize_local_json_bridge_path("external-data"), "/external-data")
        self.assertEqual(
            normalize_local_json_bridge_path("/external-data/"),
            "/external-data/",
        )


class DesktopActivityLoggerTests(unittest.TestCase):
    """Exercise the shared desktop activity journal helpers."""

    def test_activity_logger_round_trips_entries_through_the_shared_reader(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            journal_file_path = Path(temporary_directory) / "desktop-activity.jsonl"
            activity_logger = DesktopActivityLogger(
                application_name="signal-router",
                journal_file_path=journal_file_path,
            )

            activity_logger.log(
                component_name="bridge",
                level="info",
                message="Started listening.",
                details={"port": 8092},
            )
            activity_logger.log(
                component_name="live-stream",
                level="warning",
                message="Skipped an unchanged frame.",
                details={"status": "unchanged"},
            )

            recent_entries = read_recent_desktop_activity_entries(
                journal_file_path=journal_file_path,
                limit=10,
            )

        self.assertEqual(len(recent_entries), 2)
        self.assertEqual(recent_entries[0].application_name, "signal-router")
        self.assertEqual(recent_entries[1].level, "WARNING")
        self.assertEqual(recent_entries[1].details["status"], "unchanged")


class DesktopActivityLogWindowTests(unittest.TestCase):
    """Exercise the shared Tk-based activity monitor window."""

    def setUp(self) -> None:
        self.root_window = tk.Tk()
        self.root_window.withdraw()

    def tearDown(self) -> None:
        try:
            self.root_window.update_idletasks()
        except tk.TclError:
            pass
        try:
            self.root_window.destroy()
        except tk.TclError:
            pass

    def test_activity_log_window_shows_entries_and_selection_details(self) -> None:
        """The monitor should show entries and render the selected JSON details."""

        sample_entries = [
            DesktopActivityLogEntry(
                recorded_at_utc="2026-03-17T18:00:00+00:00",
                application_name="signal-router",
                component_name="external-json-bridge",
                level="INFO",
                message="Bridge started.",
                details={"port": 8092},
            ),
            DesktopActivityLogEntry(
                recorded_at_utc="2026-03-17T18:00:01+00:00",
                application_name="audio-sender",
                component_name="bridge-delivery",
                level="INFO",
                message="Delivered audio JSON.",
                details={"status": 202},
            ),
        ]

        with TemporaryDirectory() as temporary_directory:
            journal_file_path = Path(temporary_directory) / "desktop-activity.jsonl"
            with mock.patch(
                "desktop_shared_control_support.activity_log_window.get_default_desktop_activity_log_path",
                return_value=journal_file_path,
            ), mock.patch(
                "desktop_shared_control_support.activity_log_window.read_recent_desktop_activity_entries",
                return_value=sample_entries,
            ):
                activity_log_window = DesktopActivityLogWindow(self.root_window)
                self.root_window.update_idletasks()

                self.assertTrue(activity_log_window.window_exists())
                self.assertIn(
                    "Showing 2 recent events",
                    activity_log_window._status_variable.get(),  # noqa: SLF001
                )
                self.assertEqual(
                    len(activity_log_window._entry_tree.get_children()),  # noqa: SLF001
                    2,
                )

                rendered_details = activity_log_window._details_text_widget.get(  # noqa: SLF001
                    "1.0",
                    "end",
                )
                self.assertIn("signal-router", rendered_details)
                self.assertIn("Bridge started.", rendered_details)

                activity_log_window.show()
                activity_log_window._close_requested()  # noqa: SLF001
                self.root_window.update_idletasks()

                self.assertFalse(activity_log_window.window_exists())

    def test_activity_monitor_module_entry_point_opens_and_waits_for_the_window(self) -> None:
        """The standalone activity monitor launcher should delegate to the shared window."""

        from desktop_shared_control_support import activity_monitor_app

        fake_root_window = mock.Mock()
        fake_activity_log_window = mock.Mock()
        fake_activity_log_window.tk_window = object()

        with mock.patch(
            "desktop_shared_control_support.activity_monitor_app.tk.Tk",
            return_value=fake_root_window,
        ), mock.patch(
            "desktop_shared_control_support.activity_monitor_app.DesktopActivityLogWindow",
            return_value=fake_activity_log_window,
        ):
            activity_monitor_app.main()

        fake_activity_log_window.show.assert_called_once()
        fake_root_window.withdraw.assert_called_once()
        fake_root_window.wait_window.assert_called_once_with(fake_activity_log_window.tk_window)
        fake_root_window.destroy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
