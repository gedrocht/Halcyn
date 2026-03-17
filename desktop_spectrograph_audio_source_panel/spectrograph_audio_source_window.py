"""Tkinter window for the desktop spectrograph audio-source panel."""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from desktop_spectrograph_audio_source_panel.spectrograph_audio_source_builder import (
    SpectrographAudioSourcePreview,
)
from desktop_spectrograph_audio_source_panel.spectrograph_audio_source_controller import (
    DesktopSpectrographAudioSourceController,
)

WINDOW_BACKGROUND = "#08111b"
PANEL_BACKGROUND = "#102033"
SECTION_BACKGROUND = "#14293f"
ACCENT_COLOR = "#56c8ff"
ACCENT_SELECTED_COLOR = "#245c82"
TEXT_PRIMARY = "#eff6ff"
TEXT_SECONDARY = "#9fb7d0"
ENTRY_BACKGROUND = "#10243a"
METER_COLOR = "#56c8ff"


class DesktopSpectrographAudioSourceWindow:
    """Build and coordinate the native spectrograph audio-source desktop window."""

    def __init__(
        self,
        root_window: tk.Tk,
        controller: DesktopSpectrographAudioSourceController | None = None,
    ) -> None:
        self._root_window = root_window
        self._controller = controller or DesktopSpectrographAudioSourceController()
        self._catalog_payload = self._controller.catalog_payload()
        self._generated_audio_json_window: tk.Toplevel | None = None
        self._generated_audio_json_text_widget: ScrolledText | None = None
        self._latest_audio_source_preview: SpectrographAudioSourcePreview | None = None

        self._root_window.title("Halcyn Spectrograph Audio Source Panel")
        self._root_window.geometry("1380x900")
        self._root_window.minsize(1180, 760)
        self._root_window.configure(background=WINDOW_BACKGROUND)
        self._root_window.protocol("WM_DELETE_WINDOW", self._on_close_requested)

        self._build_tk_variables()
        self._configure_styles()
        self._build_user_interface()
        self._sync_user_interface_from_request_payload(self._controller.current_request_payload())
        self._refresh_device_list()
        self._refresh_preview()
        self._schedule_status_poll()

    def _build_tk_variables(self) -> None:
        """Create the Tk variables that back the visible widgets."""

        self._bridge_host_variable = tk.StringVar(value="127.0.0.1")
        self._bridge_port_variable = tk.StringVar(value="8091")
        self._bridge_path_variable = tk.StringVar(value="/external-data")
        self._source_label_variable = tk.StringVar(
            value="Desktop spectrograph audio source panel"
        )
        self._audio_device_flow_variable = tk.StringVar(value="output")
        self._audio_device_identifier_variable = tk.StringVar(value="")
        self._history_frame_count_variable = tk.IntVar(value=72)
        self._history_frame_count_label_variable = tk.StringVar(value="72 frames")
        self._live_cadence_variable = tk.IntVar(value=125)
        self._live_cadence_label_variable = tk.StringVar(value="125 ms")
        self._audio_status_variable = tk.StringVar(value="Audio capture not started.")
        self._delivery_status_variable = tk.StringVar(value="No delivery attempted yet.")
        self._bridge_summary_variable = tk.StringVar(
            value=(
                "Choose a device, start capture, then send the generated JSON "
                "to the spectrograph panel."
            )
        )
        self._volume_meter_progress_variable = tk.DoubleVar(value=0.0)
        self._volume_meter_label_variable = tk.StringVar(value="0%")

    def _configure_styles(self) -> None:
        """Apply a dark-mode-first ttk theme."""

        style = ttk.Style(self._root_window)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(".", background=WINDOW_BACKGROUND, foreground=TEXT_PRIMARY)
        style.configure("Shell.TFrame", background=WINDOW_BACKGROUND)
        style.configure("Panel.TFrame", background=PANEL_BACKGROUND)
        style.configure("Section.TFrame", background=SECTION_BACKGROUND)
        style.configure(
            "Title.TLabel",
            background=WINDOW_BACKGROUND,
            foreground=TEXT_PRIMARY,
            font=("Segoe UI Semibold", 22),
        )
        style.configure(
            "Subheading.TLabel",
            background=WINDOW_BACKGROUND,
            foreground=TEXT_SECONDARY,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Section.TLabel",
            background=SECTION_BACKGROUND,
            foreground=TEXT_PRIMARY,
            font=("Segoe UI Semibold", 11),
        )
        style.configure(
            "Body.TLabel",
            background=SECTION_BACKGROUND,
            foreground=TEXT_SECONDARY,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Value.TLabel",
            background=SECTION_BACKGROUND,
            foreground=TEXT_PRIMARY,
            font=("Consolas", 10),
        )
        style.configure(
            "Accent.TButton",
            background="#18304a",
            foreground=TEXT_PRIMARY,
            borderwidth=1,
        )
        style.map("Accent.TButton", background=[("active", ACCENT_SELECTED_COLOR)])
        style.configure("Dark.TRadiobutton", background=SECTION_BACKGROUND, foreground=TEXT_PRIMARY)
        style.configure("Dark.TEntry", fieldbackground=ENTRY_BACKGROUND, foreground=TEXT_PRIMARY)
        style.configure("Dark.TCombobox", fieldbackground=ENTRY_BACKGROUND, foreground=TEXT_PRIMARY)
        style.configure(
            "Dark.Horizontal.TScale",
            background=ACCENT_COLOR,
            troughcolor="#17304a",
        )
        style.configure(
            "Meter.Horizontal.TProgressbar",
            background=METER_COLOR,
            troughcolor="#17304a",
            bordercolor="#17304a",
        )

    def _build_user_interface(self) -> None:
        """Create the main window layout."""

        page_shell = ttk.Frame(self._root_window, style="Shell.TFrame", padding=16)
        page_shell.pack(fill="both", expand=True)
        page_shell.columnconfigure(0, weight=5)
        page_shell.columnconfigure(1, weight=3)
        page_shell.rowconfigure(2, weight=1)

        ttk.Label(
            page_shell,
            text="Desktop Spectrograph Audio Source Panel",
            style="Title.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            page_shell,
            text=(
                "Capture a local audio source, build a rolling generic JSON document from it, "
                "and send that document into the spectrograph control panel's external bridge."
            ),
            style="Subheading.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 16))

        content_frame = ttk.Frame(page_shell, style="Shell.TFrame")
        content_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        content_frame.columnconfigure(0, weight=5)
        content_frame.columnconfigure(1, weight=3)
        content_frame.rowconfigure(0, weight=1)

        self._build_left_controls(content_frame)
        self._build_right_status_panel(content_frame)

    def _build_left_controls(self, parent: ttk.Frame) -> None:
        """Create the source, bridge, and session controls."""

        left_frame = ttk.Frame(parent, style="Panel.TFrame")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left_frame.columnconfigure(0, weight=1)

        self._audio_frame = ttk.Frame(left_frame, style="Section.TFrame", padding=12)
        self._audio_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self._audio_frame.columnconfigure(1, weight=1)

        self._bridge_frame = ttk.Frame(left_frame, style="Section.TFrame", padding=12)
        self._bridge_frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self._bridge_frame.columnconfigure(1, weight=1)

        self._session_frame = ttk.Frame(left_frame, style="Section.TFrame", padding=12)
        self._session_frame.grid(row=2, column=0, sticky="ew")
        self._session_frame.columnconfigure(1, weight=1)

        self._build_audio_frame()
        self._build_bridge_frame()
        self._build_session_frame()

    def _build_right_status_panel(self, parent: ttk.Frame) -> None:
        """Create the action buttons and status summaries."""

        right_frame = ttk.Frame(parent, style="Panel.TFrame")
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)

        self._action_frame = ttk.Frame(right_frame, style="Section.TFrame", padding=12)
        self._action_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self._action_frame.columnconfigure((0, 1), weight=1)

        self._status_frame = ttk.Frame(right_frame, style="Section.TFrame", padding=12)
        self._status_frame.grid(row=1, column=0, sticky="nsew")
        self._status_frame.columnconfigure(0, weight=1)
        self._status_frame.rowconfigure(3, weight=1)

        self._build_action_frame()
        self._build_status_frame()

    def _build_audio_frame(self) -> None:
        """Create the audio-source widgets."""

        ttk.Label(self._audio_frame, text="Audio source", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            self._audio_frame,
            text=(
                "Choose whether the source should come from desktop output loopback or a "
                "microphone-style input."
            ),
            style="Body.TLabel",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 10))

        ttk.Radiobutton(
            self._audio_frame,
            text="Output sources",
            value="output",
            variable=self._audio_device_flow_variable,
            style="Dark.TRadiobutton",
            command=self._on_device_flow_changed,
        ).grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(
            self._audio_frame,
            text="Input sources",
            value="input",
            variable=self._audio_device_flow_variable,
            style="Dark.TRadiobutton",
            command=self._on_device_flow_changed,
        ).grid(row=2, column=1, sticky="w", padx=(12, 0))

        ttk.Label(self._audio_frame, text="Selected device", style="Body.TLabel").grid(
            row=3, column=0, sticky="w", pady=(12, 0)
        )
        self._audio_device_combobox = ttk.Combobox(
            self._audio_frame,
            textvariable=self._audio_device_identifier_variable,
            state="readonly",
            style="Dark.TCombobox",
        )
        self._audio_device_combobox.grid(
            row=3,
            column=1,
            columnspan=2,
            sticky="ew",
            pady=(12, 0),
        )

        ttk.Button(
            self._audio_frame,
            text="Refresh devices",
            style="Accent.TButton",
            command=self._refresh_device_list,
        ).grid(row=4, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(
            self._audio_frame,
            text="Start capture",
            style="Accent.TButton",
            command=self._start_audio_capture,
        ).grid(row=4, column=1, sticky="ew", padx=(8, 8), pady=(12, 0))
        ttk.Button(
            self._audio_frame,
            text="Stop capture",
            style="Accent.TButton",
            command=self._stop_audio_capture,
        ).grid(row=4, column=2, sticky="ew", pady=(12, 0))

        ttk.Label(self._audio_frame, text="Volume monitor", style="Body.TLabel").grid(
            row=5, column=0, sticky="w", pady=(14, 0)
        )
        ttk.Progressbar(
            self._audio_frame,
            variable=self._volume_meter_progress_variable,
            style="Meter.Horizontal.TProgressbar",
            maximum=1.0,
        ).grid(row=5, column=1, sticky="ew", padx=(12, 12), pady=(14, 0))
        ttk.Label(
            self._audio_frame,
            textvariable=self._volume_meter_label_variable,
            style="Value.TLabel",
        ).grid(row=5, column=2, sticky="w", pady=(14, 0))

    def _build_bridge_frame(self) -> None:
        """Create the target-bridge widgets."""

        ttk.Label(self._bridge_frame, text="Target bridge", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )

        ttk.Label(self._bridge_frame, text="Host", style="Body.TLabel").grid(
            row=1, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Entry(
            self._bridge_frame,
            textvariable=self._bridge_host_variable,
            style="Dark.TEntry",
            width=20,
        ).grid(row=1, column=1, sticky="w", padx=(10, 12), pady=(12, 0))

        ttk.Label(self._bridge_frame, text="Port", style="Body.TLabel").grid(
            row=1, column=2, sticky="w", pady=(12, 0)
        )
        ttk.Entry(
            self._bridge_frame,
            textvariable=self._bridge_port_variable,
            style="Dark.TEntry",
            width=8,
        ).grid(row=1, column=3, sticky="w", padx=(10, 0), pady=(12, 0))

        ttk.Label(self._bridge_frame, text="Path", style="Body.TLabel").grid(
            row=2, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Entry(
            self._bridge_frame,
            textvariable=self._bridge_path_variable,
            style="Dark.TEntry",
            width=20,
        ).grid(row=2, column=1, sticky="w", padx=(10, 12), pady=(12, 0))

        ttk.Label(self._bridge_frame, text="Source label", style="Body.TLabel").grid(
            row=3, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Entry(
            self._bridge_frame,
            textvariable=self._source_label_variable,
            style="Dark.TEntry",
            width=40,
        ).grid(row=3, column=1, columnspan=3, sticky="ew", padx=(10, 0), pady=(12, 0))

    def _build_session_frame(self) -> None:
        """Create the history and live-send widgets."""

        ttk.Label(self._session_frame, text="Session and history", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )

        ttk.Label(self._session_frame, text="History frames", style="Body.TLabel").grid(
            row=1, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Scale(
            self._session_frame,
            variable=self._history_frame_count_variable,
            orient="horizontal",
            from_=4,
            to=256,
            command=self._on_history_frame_count_changed,
            style="Dark.Horizontal.TScale",
        ).grid(row=1, column=1, sticky="ew", padx=(12, 12), pady=(12, 0))
        ttk.Label(
            self._session_frame,
            textvariable=self._history_frame_count_label_variable,
            style="Value.TLabel",
        ).grid(row=1, column=2, sticky="w", pady=(12, 0))

        ttk.Label(self._session_frame, text="Live cadence", style="Body.TLabel").grid(
            row=2, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Scale(
            self._session_frame,
            variable=self._live_cadence_variable,
            orient="horizontal",
            from_=40,
            to=2000,
            command=self._on_live_cadence_changed,
            style="Dark.Horizontal.TScale",
        ).grid(row=2, column=1, sticky="ew", padx=(12, 12), pady=(12, 0))
        ttk.Label(
            self._session_frame,
            textvariable=self._live_cadence_label_variable,
            style="Value.TLabel",
        ).grid(row=2, column=2, sticky="w", pady=(12, 0))

    def _build_action_frame(self) -> None:
        """Create the action-button group."""

        ttk.Label(self._action_frame, text="Actions", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        for button_index, (button_label, button_command) in enumerate(
            [
                ("Preview", self._refresh_preview),
                ("Send once", self._deliver_once),
                ("Start live", self._start_live_send),
                ("Stop live", self._stop_live_send),
                ("Open generated JSON", self._open_generated_audio_json_window),
                ("Revert defaults", self._revert_defaults),
                ("Load settings", self._load_settings_document),
                ("Save settings", self._save_settings_document),
            ]
        ):
            ttk.Button(
                self._action_frame,
                text=button_label,
                style="Accent.TButton",
                command=button_command,
            ).grid(
                row=1 + (button_index // 2),
                column=button_index % 2,
                sticky="ew",
                padx=(0 if button_index % 2 == 0 else 8, 0),
                pady=(10, 0),
            )

    def _build_status_frame(self) -> None:
        """Create the status-summary labels."""

        ttk.Label(self._status_frame, text="Status", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            self._status_frame,
            textvariable=self._audio_status_variable,
            style="Body.TLabel",
            wraplength=360,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(
            self._status_frame,
            textvariable=self._delivery_status_variable,
            style="Body.TLabel",
            wraplength=360,
            justify="left",
        ).grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(
            self._status_frame,
            textvariable=self._bridge_summary_variable,
            style="Body.TLabel",
            wraplength=360,
            justify="left",
        ).grid(row=3, column=0, sticky="nsew", pady=(10, 0))

    def _collect_request_payload_from_user_interface(self) -> dict[str, Any]:
        """Collect one full request payload from the visible widgets."""

        return {
            "bridge": {
                "host": self._bridge_host_variable.get(),
                "port": self._safe_int(self._bridge_port_variable.get(), 8091),
                "path": self._bridge_path_variable.get(),
                "sourceLabel": self._source_label_variable.get(),
            },
            "audio": {
                "deviceFlow": self._audio_device_flow_variable.get(),
                "deviceIdentifier": self._selected_audio_device_identifier(),
                "historyFrameCount": self._history_frame_count_variable.get(),
            },
            "session": {
                "cadenceMs": self._live_cadence_variable.get(),
            },
        }

    def _sync_user_interface_from_request_payload(self, request_payload: dict[str, Any]) -> None:
        """Populate the widgets from one normalized request payload."""

        self._bridge_host_variable.set(str(request_payload["bridge"]["host"]))
        self._bridge_port_variable.set(str(request_payload["bridge"]["port"]))
        self._bridge_path_variable.set(str(request_payload["bridge"]["path"]))
        self._source_label_variable.set(str(request_payload["bridge"]["sourceLabel"]))
        self._audio_device_flow_variable.set(str(request_payload["audio"]["deviceFlow"]))
        self._audio_device_identifier_variable.set(str(request_payload["audio"]["deviceIdentifier"]))
        self._history_frame_count_variable.set(int(request_payload["audio"]["historyFrameCount"]))
        self._history_frame_count_label_variable.set(
            f"{self._history_frame_count_variable.get()} frames"
        )
        self._live_cadence_variable.set(int(request_payload["session"]["cadenceMs"]))
        self._live_cadence_label_variable.set(f"{self._live_cadence_variable.get()} ms")

    def _refresh_device_list(self) -> None:
        """Refresh the combobox values for the chosen device flow."""

        request_payload = self._collect_request_payload_from_user_interface()
        self._controller.replace_request_payload(request_payload)
        available_audio_devices = self._controller.refresh_audio_devices(
            self._audio_device_flow_variable.get()
        )
        self._available_audio_devices_by_identifier = {
            audio_device.device_identifier: audio_device for audio_device in available_audio_devices
        }
        self._audio_device_combobox["values"] = [
            f"{audio_device.device_identifier} | {audio_device.name}"
            for audio_device in available_audio_devices
        ]
        if available_audio_devices and not self._selected_audio_device_identifier():
            first_available_audio_device = available_audio_devices[0]
            self._audio_device_identifier_variable.set(
                f"{first_available_audio_device.device_identifier} | "
                f"{first_available_audio_device.name}"
            )

    def _on_device_flow_changed(self) -> None:
        """Refresh device choices after the operator flips input/output mode."""

        self._audio_device_identifier_variable.set("")
        self._refresh_device_list()
        self._refresh_preview()

    def _on_history_frame_count_changed(self, _value: str) -> None:
        """Update the visible history-frame label and refresh the preview."""

        self._history_frame_count_label_variable.set(
            f"{self._history_frame_count_variable.get()} frames"
        )
        self._refresh_preview()

    def _on_live_cadence_changed(self, _value: str) -> None:
        """Update the visible cadence label."""

        self._live_cadence_label_variable.set(f"{self._live_cadence_variable.get()} ms")

    def _start_audio_capture(self) -> None:
        """Start capture on the currently selected audio device."""

        device_identifier = self._selected_audio_device_identifier()
        if not device_identifier:
            messagebox.showinfo("Audio capture", "Choose an audio device before starting capture.")
            return

        request_payload = self._collect_request_payload_from_user_interface()
        self._controller.replace_request_payload(request_payload)
        started_snapshot = self._controller.start_audio_capture(
            device_identifier=device_identifier,
            device_flow=self._audio_device_flow_variable.get(),
        )
        self._audio_status_variable.set(
            f"Capturing {started_snapshot.device_name or device_identifier} "
            f"from {self._audio_device_flow_variable.get()} sources."
        )
        self._refresh_preview()

    def _stop_audio_capture(self) -> None:
        """Stop audio capture and refresh the live status text."""

        stopped_snapshot = self._controller.stop_audio_capture()
        self._audio_status_variable.set(
            f"Audio capture stopped for {stopped_snapshot.device_name or 'the selected device'}."
        )

    def _refresh_preview(self) -> None:
        """Push UI values into the controller and rebuild the outgoing JSON preview."""

        try:
            request_payload = self._collect_request_payload_from_user_interface()
            self._controller.replace_request_payload(request_payload)
            self._latest_audio_source_preview = self._controller.preview_payload()
        except Exception as error:
            self._latest_audio_source_preview = None
            self._delivery_status_variable.set(f"Preview error: {error}")
            self._bridge_summary_variable.set(
                "The current settings could not be turned into a bridge-ready JSON document."
            )
            self._update_generated_audio_json_window()
            return

        analysis = self._latest_audio_source_preview.analysis
        latest_audio_signal_snapshot = self._controller.audio_snapshot()
        if latest_audio_signal_snapshot.capturing:
            self._bridge_summary_variable.set(
                f"Ready to deliver {analysis['frameCount']} audio frames to "
                f"{analysis['bridgeTarget']}. "
                f"Current level: {float(analysis['currentLevel']):.2f}. "
                f"Average level: {float(analysis['averageLevel']):.2f}. "
                f"Peak level: {float(analysis['peakLevel']):.2f}."
            )
        else:
            self._bridge_summary_variable.set(
                "Choose a device, start capture, then send the generated JSON "
                "to the spectrograph panel."
            )
        self._update_generated_audio_json_window()

    def _deliver_once(self) -> None:
        """Send the current preview once to the spectrograph control panel bridge."""

        self._controller.replace_request_payload(self._collect_request_payload_from_user_interface())
        delivery_result = self._controller.deliver_once()
        response = delivery_result["response"]
        if response.ok:
            self._delivery_status_variable.set(
                f"Delivered audio JSON: HTTP {response.status} {response.reason}."
            )
        else:
            self._delivery_status_variable.set(
                f"Delivery failed: HTTP {response.status} {response.reason}. {response.body}"
            )
        self._latest_audio_source_preview = delivery_result["preview"]
        self._update_generated_audio_json_window()

    def _start_live_send(self) -> None:
        """Start repeatedly sending the generated JSON document."""

        self._controller.replace_request_payload(self._collect_request_payload_from_user_interface())
        live_send_snapshot = self._controller.start_live_send()
        self._delivery_status_variable.set(
            f"Live send {live_send_snapshot['status']} at {live_send_snapshot['cadence_ms']} ms."
        )

    def _stop_live_send(self) -> None:
        """Stop the repeating-send worker."""

        live_send_snapshot = self._controller.stop_live_send()
        self._delivery_status_variable.set(f"Live send {live_send_snapshot['status']}.")

    def _revert_defaults(self) -> None:
        """Restore defaults, refresh devices, and rebuild the preview."""

        request_payload = self._controller.reset_to_defaults()
        self._sync_user_interface_from_request_payload(request_payload)
        self._refresh_device_list()
        self._refresh_preview()

    def _save_settings_document(self) -> None:
        """Save the current settings document to disk."""

        selected_path = filedialog.asksaveasfilename(
            title="Save spectrograph audio source settings",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not selected_path:
            return

        settings_document = self._controller.settings_document()
        Path(selected_path).write_text(json.dumps(settings_document, indent=2), encoding="utf-8")
        self._delivery_status_variable.set(f"Saved settings to {selected_path}")

    def _load_settings_document(self) -> None:
        """Load a settings document from disk and refresh the UI."""

        selected_path = filedialog.askopenfilename(
            title="Load spectrograph audio source settings",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not selected_path:
            return

        settings_document = json.loads(Path(selected_path).read_text(encoding="utf-8"))
        request_payload = self._controller.load_settings_document(settings_document)
        self._sync_user_interface_from_request_payload(request_payload)
        self._refresh_device_list()
        self._refresh_preview()
        self._delivery_status_variable.set(f"Loaded settings from {selected_path}")

    def _open_generated_audio_json_window(self) -> None:
        """Open a detached read-only window that shows the generated JSON payload."""

        if (
            self._generated_audio_json_window is not None
            and self._generated_audio_json_window.winfo_exists()
        ):
            self._generated_audio_json_window.deiconify()
            self._generated_audio_json_window.lift()
            self._update_generated_audio_json_window()
            return

        self._generated_audio_json_window = tk.Toplevel(self._root_window)
        self._generated_audio_json_window.title("Generated Spectrograph Audio JSON")
        self._generated_audio_json_window.geometry("760x720")
        self._generated_audio_json_window.configure(background=WINDOW_BACKGROUND)
        self._generated_audio_json_window.protocol(
            "WM_DELETE_WINDOW",
            self._on_generated_audio_json_window_closed,
        )

        preview_frame = ttk.Frame(
            self._generated_audio_json_window,
            style="Panel.TFrame",
            padding=12,
        )
        preview_frame.pack(fill="both", expand=True)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(1, weight=1)

        ttk.Label(
            preview_frame,
            text="Generated audio JSON sent to the spectrograph control panel",
            style="Section.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            preview_frame,
            text="Copy JSON",
            style="Accent.TButton",
            command=self._copy_generated_audio_json_to_clipboard,
        ).grid(row=0, column=1, sticky="e")

        self._generated_audio_json_text_widget = ScrolledText(
            preview_frame,
            wrap="word",
            background="#0c1d2e",
            foreground=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            font=("Consolas", 10),
        )
        self._generated_audio_json_text_widget.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="nsew",
            pady=(10, 0),
        )
        self._generated_audio_json_text_widget.configure(state="disabled")
        self._update_generated_audio_json_window()

    def _update_generated_audio_json_window(self) -> None:
        """Refresh the detached JSON preview window if it is open."""

        if (
            self._generated_audio_json_window is None
            or self._generated_audio_json_text_widget is None
            or not self._generated_audio_json_window.winfo_exists()
        ):
            return

        if self._latest_audio_source_preview is None:
            preview_text = "No valid generated audio JSON is available right now."
        else:
            preview_text = self._latest_audio_source_preview.generated_json_text

        self._generated_audio_json_text_widget.configure(state="normal")
        self._generated_audio_json_text_widget.delete("1.0", "end")
        self._generated_audio_json_text_widget.insert("1.0", preview_text)
        self._generated_audio_json_text_widget.configure(state="disabled")

    def _copy_generated_audio_json_to_clipboard(self) -> None:
        """Copy the current generated JSON document to the clipboard."""

        if self._latest_audio_source_preview is None:
            messagebox.showinfo("Copy JSON", "There is no generated JSON to copy yet.")
            return

        self._root_window.clipboard_clear()
        self._root_window.clipboard_append(
            self._latest_audio_source_preview.generated_json_text
        )
        self._delivery_status_variable.set("Copied the generated audio JSON to the clipboard.")

    def _on_generated_audio_json_window_closed(self) -> None:
        """Forget the detached JSON window after it closes."""

        if self._generated_audio_json_window is not None:
            self._generated_audio_json_window.destroy()
        self._generated_audio_json_window = None
        self._generated_audio_json_text_widget = None

    def _schedule_status_poll(self) -> None:
        """Keep audio and live-send status current while the window is open."""

        self._poll_status()
        self._root_window.after(250, self._schedule_status_poll)

    def _poll_status(self) -> None:
        """Refresh the volume meter and live-send summary from the controller."""

        latest_audio_signal_snapshot = self._controller.audio_snapshot()
        self._volume_meter_progress_variable.set(latest_audio_signal_snapshot.level)
        self._volume_meter_label_variable.set(f"{latest_audio_signal_snapshot.level * 100:.0f}%")

        live_send_snapshot = self._controller.live_send_snapshot()
        self._audio_status_variable.set(
            f"Audio backend: {latest_audio_signal_snapshot.backend_name}. "
            f"Capturing: {'yes' if latest_audio_signal_snapshot.capturing else 'no'}. "
            f"Device: {latest_audio_signal_snapshot.device_name or 'none selected'}."
        )
        self._delivery_status_variable.set(
            f"Live send {live_send_snapshot['status']}. "
            f"Successful deliveries: {live_send_snapshot['deliveries_succeeded']}. "
            f"Failed deliveries: {live_send_snapshot['deliveries_failed']}."
        )

    def _selected_audio_device_identifier(self) -> str:
        """Extract the plain device identifier from the combobox value."""

        selected_value = self._audio_device_identifier_variable.get().strip()
        if " | " in selected_value:
            return selected_value.split(" | ", 1)[0].strip()
        return selected_value

    def _on_close_requested(self) -> None:
        """Shut down worker threads cleanly before the process exits."""

        self._controller.close()
        self._root_window.destroy()

    @staticmethod
    def _safe_int(value: Any, fallback: int) -> int:
        """Convert a widget value to an int without throwing from the UI layer."""

        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback


def main() -> None:
    """Launch the native desktop spectrograph audio-source panel."""

    root_window = tk.Tk()
    DesktopSpectrographAudioSourceWindow(root_window)
    root_window.mainloop()
