"""Tkinter window for the native Halcyn desktop render control panel.

Helpful library references:

- Tkinter overview: https://docs.python.org/3/library/tkinter.html
- `ttk` widgets: https://docs.python.org/3/library/tkinter.ttk.html
- `ScrolledText`: https://docs.python.org/3/library/tkinter.scrolledtext.html
- `colorchooser`: https://docs.python.org/3/library/tkinter.colorchooser.html
"""

from __future__ import annotations

import json
import math
import tkinter as tk
from tkinter import colorchooser, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from desktop_render_control_panel.desktop_control_panel_controller import (
    DesktopRenderControlPanelController,
)
from desktop_render_control_panel.desktop_control_scene_builder import DEFAULT_DESKTOP_PRESET_ID


class DesktopRenderControlPanelWindow:
    """Build and manage the native desktop control panel window.

    The window's job is to present controls and translate user gestures into
    controller calls.  It should not contain the authoritative business logic
    for scene generation, HTTP communication, or audio processing.
    """

    def __init__(
        self,
        root: tk.Tk,
        controller: DesktopRenderControlPanelController | None = None,
    ) -> None:
        # The catalog is fetched once during startup so every dropdown can build
        # from one consistent source of truth.
        self._root = root
        self._controller = controller or DesktopRenderControlPanelController()
        self._catalog = self._controller.catalog_payload()
        self._preset_entries_by_identifier = {
            preset["id"]: preset for preset in self._catalog["presets"]
        }
        self._preset_names_by_scene_type = {
            "2d": [
                preset["name"]
                for preset in self._catalog["presets"]
                if preset["sceneType"] == "2d"
            ],
            "3d": [
                preset["name"]
                for preset in self._catalog["presets"]
                if preset["sceneType"] == "3d"
            ],
        }
        self._preset_ids_by_name = {
            preset["name"]: preset["id"] for preset in self._catalog["presets"]
        }
        self._preset_names_by_identifier = {
            preset["id"]: preset["name"] for preset in self._catalog["presets"]
        }
        self._pending_sync_after_identifier: str | None = None
        self._suppress_variable_sync = False
        self._last_pointer_x = 0.5
        self._last_pointer_y = 0.5
        self._build_variables()
        self._build_user_interface()
        self._load_initial_state()
        self._root.protocol("WM_DELETE_WINDOW", self._on_close_requested)
        self._schedule_status_refresh()

    def _build_variables(self) -> None:
        """Create the Tkinter variables that keep the UI and controller in sync."""

        self._scene_type_variable = tk.StringVar(value="2d")
        self._preset_name_variable = tk.StringVar(value="")
        self._host_variable = tk.StringVar(value="127.0.0.1")
        self._port_variable = tk.StringVar(value="8080")
        self._cadence_variable = tk.IntVar(value=125)
        self._density_variable = tk.IntVar(value=96)
        self._point_size_variable = tk.DoubleVar(value=6.0)
        self._line_width_variable = tk.DoubleVar(value=2.0)
        self._speed_variable = tk.DoubleVar(value=1.0)
        self._gain_variable = tk.DoubleVar(value=1.0)
        self._manual_drive_variable = tk.DoubleVar(value=0.35)
        self._background_variable = tk.StringVar(value="#07111f")
        self._primary_color_variable = tk.StringVar(value="#6ed6ff")
        self._secondary_color_variable = tk.StringVar(value="#ffd080")
        self._use_epoch_variable = tk.BooleanVar(value=True)
        self._use_noise_variable = tk.BooleanVar(value=True)
        self._use_pointer_variable = tk.BooleanVar(value=True)
        self._use_audio_variable = tk.BooleanVar(value=False)
        self._audio_device_variable = tk.StringVar(value="")
        self._pointer_status_variable = tk.StringVar(value="Pointer pad idle")
        self._health_status_variable = tk.StringVar(value="Health check not run yet.")
        self._live_status_variable = tk.StringVar(value="Live stream stopped.")
        self._audio_status_variable = tk.StringVar(value="Audio capture not started.")
        self._result_status_variable = tk.StringVar(value="Ready.")

    def _build_user_interface(self) -> None:
        """Create the three major page columns and their child sections."""

        self._root.title("Halcyn Desktop Render Control Panel")
        self._root.geometry("1460x920")
        self._root.minsize(1200, 760)

        style = ttk.Style(self._root)
        style.configure("Heading.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Section.TLabelframe.Label", font=("Segoe UI", 11, "bold"))

        page_shell = ttk.Frame(self._root, padding=16)
        page_shell.grid(sticky="nsew")
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)

        page_shell.columnconfigure(0, weight=0)
        page_shell.columnconfigure(1, weight=0)
        page_shell.columnconfigure(2, weight=1)
        page_shell.rowconfigure(1, weight=1)

        heading = ttk.Label(
            page_shell,
            text="Desktop Render Control Panel",
            style="Heading.TLabel",
        )
        heading.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self._connection_frame = ttk.LabelFrame(
            page_shell,
            text="Renderer Connection",
            padding=12,
            style="Section.TLabelframe",
        )
        self._connection_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 12))

        self._scene_frame = ttk.LabelFrame(
            page_shell,
            text="Scene Controls",
            padding=12,
            style="Section.TLabelframe",
        )
        self._scene_frame.grid(row=1, column=1, sticky="nsew", padx=(0, 12))

        self._output_frame = ttk.LabelFrame(
            page_shell,
            text="Preview, Status, and Diagnostics",
            padding=12,
            style="Section.TLabelframe",
        )
        self._output_frame.grid(row=1, column=2, sticky="nsew")
        self._output_frame.columnconfigure(0, weight=1)
        self._output_frame.rowconfigure(3, weight=1)

        self._build_connection_section()
        self._build_scene_section()
        self._build_output_section()

    def _build_connection_section(self) -> None:
        """Create the renderer-target and transport-action controls."""

        section_frame = self._connection_frame
        for column_index in range(2):
            section_frame.columnconfigure(column_index, weight=1 if column_index == 1 else 0)

        ttk.Label(section_frame, text="Host").grid(row=0, column=0, sticky="w")
        ttk.Entry(section_frame, textvariable=self._host_variable).grid(
            row=0,
            column=1,
            sticky="ew",
            pady=(0, 8),
        )

        ttk.Label(section_frame, text="Port").grid(row=1, column=0, sticky="w")
        ttk.Entry(section_frame, textvariable=self._port_variable).grid(
            row=1,
            column=1,
            sticky="ew",
            pady=(0, 8),
        )

        ttk.Label(section_frame, text="Live cadence (ms)").grid(row=2, column=0, sticky="w")
        ttk.Scale(
            section_frame,
            from_=40,
            to=1000,
            orient="horizontal",
            variable=self._cadence_variable,
            command=lambda _: self._schedule_payload_sync(),
        ).grid(row=2, column=1, sticky="ew")
        ttk.Label(section_frame, textvariable=self._cadence_variable).grid(
            row=3,
            column=1,
            sticky="e",
            pady=(0, 8),
        )

        ttk.Button(section_frame, text="Check health", command=self._run_health_check).grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(4, 4),
        )
        ttk.Button(section_frame, text="Validate scene", command=self._validate_current_scene).grid(
            row=5,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=4,
        )
        ttk.Button(section_frame, text="Apply once", command=self._apply_current_scene).grid(
            row=6,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=4,
        )
        ttk.Button(section_frame, text="Start live stream", command=self._start_live_stream).grid(
            row=7,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=4,
        )
        ttk.Button(section_frame, text="Stop live stream", command=self._stop_live_stream).grid(
            row=8,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=4,
        )

        ttk.Separator(section_frame).grid(row=9, column=0, columnspan=2, sticky="ew", pady=10)
        ttk.Label(section_frame, text="Health").grid(row=10, column=0, sticky="nw")
        ttk.Label(section_frame, textvariable=self._health_status_variable, wraplength=280).grid(
            row=10,
            column=1,
            sticky="w",
        )

        ttk.Label(section_frame, text="Live").grid(row=11, column=0, sticky="nw", pady=(8, 0))
        ttk.Label(section_frame, textvariable=self._live_status_variable, wraplength=280).grid(
            row=11,
            column=1,
            sticky="w",
            pady=(8, 0),
        )

        ttk.Label(section_frame, text="Result").grid(row=12, column=0, sticky="nw", pady=(8, 0))
        ttk.Label(section_frame, textvariable=self._result_status_variable, wraplength=280).grid(
            row=12,
            column=1,
            sticky="w",
            pady=(8, 0),
        )

    def _build_scene_section(self) -> None:
        """Create the visual-control, signal-source, and audio-device widgets."""

        section_frame = self._scene_frame
        for column_index in range(2):
            section_frame.columnconfigure(column_index, weight=1 if column_index == 1 else 0)

        ttk.Label(section_frame, text="Scene type").grid(row=0, column=0, sticky="w")
        self._scene_type_combobox = ttk.Combobox(
            section_frame,
            textvariable=self._scene_type_variable,
            values=("2d", "3d"),
            state="readonly",
        )
        self._scene_type_combobox.grid(row=0, column=1, sticky="ew", pady=(0, 8))
        self._scene_type_combobox.bind("<<ComboboxSelected>>", self._on_scene_type_changed)

        ttk.Label(section_frame, text="Preset").grid(row=1, column=0, sticky="w")
        self._preset_combobox = ttk.Combobox(
            section_frame,
            textvariable=self._preset_name_variable,
            state="readonly",
        )
        self._preset_combobox.grid(row=1, column=1, sticky="ew", pady=(0, 8))
        self._preset_combobox.bind("<<ComboboxSelected>>", self._on_preset_changed)

        slider_row = 2
        slider_row = self._add_slider(
            section_frame,
            slider_row,
            "Density",
            self._density_variable,
            24,
            320,
        )
        slider_row = self._add_slider(
            section_frame,
            slider_row,
            "Point size",
            self._point_size_variable,
            1.0,
            24.0,
        )
        slider_row = self._add_slider(
            section_frame,
            slider_row,
            "Line width",
            self._line_width_variable,
            1.0,
            8.0,
        )
        slider_row = self._add_slider(
            section_frame,
            slider_row,
            "Speed",
            self._speed_variable,
            0.1,
            4.0,
        )
        slider_row = self._add_slider(
            section_frame,
            slider_row,
            "Gain",
            self._gain_variable,
            0.1,
            3.0,
        )
        slider_row = self._add_slider(
            section_frame,
            slider_row,
            "Manual drive",
            self._manual_drive_variable,
            0.0,
            2.0,
        )

        ttk.Label(section_frame, text="Background").grid(
            row=slider_row,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        self._build_color_row(section_frame, slider_row, self._background_variable)
        slider_row += 1
        ttk.Label(section_frame, text="Primary color").grid(
            row=slider_row,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        self._build_color_row(section_frame, slider_row, self._primary_color_variable)
        slider_row += 1
        ttk.Label(section_frame, text="Secondary color").grid(
            row=slider_row,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        self._build_color_row(section_frame, slider_row, self._secondary_color_variable)
        slider_row += 1

        signals_frame = ttk.LabelFrame(section_frame, text="Signal sources", padding=8)
        signals_frame.grid(row=slider_row, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        for signal_index, (label_text, variable) in enumerate(
            [
                ("Unix time", self._use_epoch_variable),
                ("Noise", self._use_noise_variable),
                ("Pointer pad", self._use_pointer_variable),
                ("Audio device", self._use_audio_variable),
            ]
        ):
            ttk.Checkbutton(
                signals_frame,
                text=label_text,
                variable=variable,
                command=self._schedule_payload_sync,
            ).grid(row=signal_index // 2, column=signal_index % 2, sticky="w", padx=4, pady=4)

        audio_frame = ttk.LabelFrame(section_frame, text="Audio input", padding=8)
        audio_frame.grid(row=slider_row + 1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        audio_frame.columnconfigure(1, weight=1)
        ttk.Label(audio_frame, text="Device").grid(row=0, column=0, sticky="w")
        self._audio_device_combobox = ttk.Combobox(
            audio_frame,
            textvariable=self._audio_device_variable,
            state="readonly",
        )
        self._audio_device_combobox.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ttk.Button(audio_frame, text="Refresh", command=self._refresh_audio_devices).grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(8, 0),
        )
        ttk.Button(audio_frame, text="Start capture", command=self._start_audio_capture).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(6, 0),
            pady=(8, 0),
        )
        ttk.Button(audio_frame, text="Stop capture", command=self._stop_audio_capture).grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(8, 0),
        )
        ttk.Label(audio_frame, textvariable=self._audio_status_variable, wraplength=320).grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(8, 0),
        )

        pointer_frame = ttk.LabelFrame(section_frame, text="Pointer pad", padding=8)
        pointer_frame.grid(row=slider_row + 2, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        self._pointer_canvas = tk.Canvas(
            pointer_frame,
            width=240,
            height=160,
            background="#0f1725",
            highlightthickness=1,
            highlightbackground="#3d5a80",
        )
        self._pointer_canvas.grid(row=0, column=0, sticky="nsew")
        self._pointer_canvas.bind("<Motion>", self._on_pointer_motion)
        self._pointer_canvas.bind("<Leave>", self._on_pointer_leave)
        ttk.Label(pointer_frame, textvariable=self._pointer_status_variable).grid(
            row=1,
            column=0,
            sticky="w",
            pady=(8, 0),
        )

        self._watch_control_variables()

    def _build_output_section(self) -> None:
        """Create the preview JSON pane and the small analysis summary."""

        section_frame = self._output_frame
        section_frame.rowconfigure(3, weight=1)
        section_frame.columnconfigure(0, weight=1)

        ttk.Button(section_frame, text="Refresh preview JSON", command=self._refresh_preview).grid(
            row=0,
            column=0,
            sticky="ew",
        )

        self._analysis_label = ttk.Label(
            section_frame,
            text="No preview generated yet.",
            wraplength=640,
            justify="left",
        )
        self._analysis_label.grid(row=1, column=0, sticky="w", pady=(10, 10))

        ttk.Label(section_frame, text="Current scene JSON").grid(row=2, column=0, sticky="w")
        self._preview_text = ScrolledText(
            section_frame,
            wrap="none",
            font=("Cascadia Code", 10),
        )
        self._preview_text.grid(row=3, column=0, sticky="nsew")
        self._preview_text.configure(state="disabled")

    def _add_slider(
        self,
        parent: Any,
        row: int,
        label_text: str,
        variable: tk.IntVar | tk.DoubleVar,
        minimum: float,
        maximum: float,
    ) -> int:
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky="w")
        ttk.Scale(
            parent,
            from_=minimum,
            to=maximum,
            orient="horizontal",
            variable=variable,
            command=lambda _: self._schedule_payload_sync(),
        ).grid(row=row, column=1, sticky="ew")
        ttk.Label(parent, textvariable=variable).grid(
            row=row + 1,
            column=1,
            sticky="e",
            pady=(0, 4),
        )
        return row + 2

    def _build_color_row(self, parent: Any, row: int, variable: tk.StringVar) -> None:
        color_frame = ttk.Frame(parent)
        color_frame.grid(row=row, column=1, sticky="ew", pady=(8, 0))
        color_frame.columnconfigure(0, weight=1)
        ttk.Entry(color_frame, textvariable=variable).grid(row=0, column=0, sticky="ew")

        def choose_bound_color() -> None:
            self._choose_color(variable)

        ttk.Button(
            color_frame,
            text="Choose",
            command=choose_bound_color,
        ).grid(row=0, column=1, padx=(6, 0))

    def _watch_control_variables(self) -> None:
        """Register one shared "something changed" callback for UI variables."""

        watched_variables = [
            self._host_variable,
            self._port_variable,
            self._cadence_variable,
            self._density_variable,
            self._point_size_variable,
            self._line_width_variable,
            self._speed_variable,
            self._gain_variable,
            self._manual_drive_variable,
            self._background_variable,
            self._primary_color_variable,
            self._secondary_color_variable,
            self._use_epoch_variable,
            self._use_noise_variable,
            self._use_pointer_variable,
            self._use_audio_variable,
        ]
        for variable in watched_variables:
            variable.trace_add("write", lambda *_: self._schedule_payload_sync())

    def _load_initial_state(self) -> None:
        """Populate the window from the controller's current payload."""

        default_payload = self._controller.current_request_payload()
        default_preset_identifier = str(default_payload["presetId"])
        default_scene_type = str(
            self._preset_entries_by_identifier[default_preset_identifier]["sceneType"]
        )
        self._scene_type_variable.set(default_scene_type)
        self._refresh_preset_combobox_values()
        self._preset_name_variable.set(self._preset_names_by_identifier[default_preset_identifier])
        self._set_user_interface_from_request_payload(default_payload)
        self._refresh_audio_devices()
        self._refresh_preview()

    def _refresh_preset_combobox_values(self) -> None:
        scene_type = self._scene_type_variable.get().strip().lower()
        self._preset_combobox["values"] = self._preset_names_by_scene_type.get(scene_type, [])

    def _set_user_interface_from_request_payload(self, payload: dict[str, Any]) -> None:
        """Copy a normalized request payload into the visible widgets.

        The suppression flag matters because setting Tk variables would normally
        trigger the "sync back into the controller" traces immediately.
        """

        self._suppress_variable_sync = True
        try:
            target = payload.get("target", {})
            settings = payload.get("settings", {})
            signals = payload.get("signals", {})
            audio = signals.get("audio", {})
            session = payload.get("session", {})

            self._host_variable.set(str(target.get("host", "127.0.0.1")))
            self._port_variable.set(str(target.get("port", 8080)))
            self._cadence_variable.set(int(session.get("cadenceMs", 125)))
            self._density_variable.set(int(settings.get("density", 96)))
            self._point_size_variable.set(float(settings.get("pointSize", 6.0)))
            self._line_width_variable.set(float(settings.get("lineWidth", 2.0)))
            self._speed_variable.set(float(settings.get("speed", 1.0)))
            self._gain_variable.set(float(settings.get("gain", 1.0)))
            self._manual_drive_variable.set(float(settings.get("manualDrive", 0.35)))
            self._background_variable.set(str(settings.get("background", "#07111f")))
            self._primary_color_variable.set(str(settings.get("primaryColor", "#6ed6ff")))
            self._secondary_color_variable.set(str(settings.get("secondaryColor", "#ffd080")))
            self._use_epoch_variable.set(bool(signals.get("useEpoch", True)))
            self._use_noise_variable.set(bool(signals.get("useNoise", True)))
            self._use_pointer_variable.set(bool(signals.get("usePointer", True)))
            self._use_audio_variable.set(bool(signals.get("useAudio", False)))
            if isinstance(audio, dict):
                self._audio_status_variable.set(
                    "Audio capture not started."
                    if not audio
                    else f"Audio bands ready: level {float(audio.get('level', 0.0)):.2f}"
                )
        finally:
            self._suppress_variable_sync = False

    def _collect_request_payload_from_user_interface(self) -> dict[str, Any]:
        """Build one full request payload from the current widget values."""

        selected_preset_name = self._preset_name_variable.get().strip()
        selected_preset_identifier = self._preset_ids_by_name.get(
            selected_preset_name,
            DEFAULT_DESKTOP_PRESET_ID,
        )
        current_payload = self._controller.current_request_payload()
        pointer_payload = current_payload.get("signals", {}).get("pointer", {})

        return {
            "presetId": selected_preset_identifier,
            "target": {
                "host": self._host_variable.get().strip() or "127.0.0.1",
                "port": self._safe_int(self._port_variable.get(), 8080),
            },
            "settings": {
                "density": self._safe_int(self._density_variable.get(), 96),
                "pointSize": float(self._point_size_variable.get()),
                "lineWidth": float(self._line_width_variable.get()),
                "speed": float(self._speed_variable.get()),
                "gain": float(self._gain_variable.get()),
                "manualDrive": float(self._manual_drive_variable.get()),
                "background": self._background_variable.get().strip(),
                "primaryColor": self._primary_color_variable.get().strip(),
                "secondaryColor": self._secondary_color_variable.get().strip(),
            },
            "signals": {
                "useEpoch": bool(self._use_epoch_variable.get()),
                "useNoise": bool(self._use_noise_variable.get()),
                "usePointer": bool(self._use_pointer_variable.get()),
                "useAudio": bool(self._use_audio_variable.get()),
                "pointer": {
                    "x": float(pointer_payload.get("x", 0.5)),
                    "y": float(pointer_payload.get("y", 0.5)),
                    "speed": float(pointer_payload.get("speed", 0.0)),
                },
                "manual": {"drive": float(self._manual_drive_variable.get())},
            },
            "session": {"cadenceMs": self._safe_int(self._cadence_variable.get(), 125)},
        }

    def _schedule_payload_sync(self) -> None:
        """Debounce rapid widget changes before syncing them into the controller."""

        if self._suppress_variable_sync:
            return

        if self._pending_sync_after_identifier is not None:
            self._root.after_cancel(self._pending_sync_after_identifier)

        self._pending_sync_after_identifier = self._root.after(
            100,
            self._sync_payload_to_controller,
        )

    def _sync_payload_to_controller(self) -> None:
        """Push the latest widget state into the controller and refresh preview if needed."""

        self._pending_sync_after_identifier = None
        self._controller.update_request_payload(self._collect_request_payload_from_user_interface())
        if self._controller.live_stream_snapshot()["status"] in {"running", "starting"}:
            self._refresh_preview()

    def _on_scene_type_changed(self, event: object | None = None) -> None:
        self._refresh_preset_combobox_values()
        preset_names = list(self._preset_combobox["values"])
        if not preset_names:
            return
        self._preset_name_variable.set(preset_names[0])
        self._on_preset_changed()

    def _on_preset_changed(self, event: object | None = None) -> None:
        selected_preset_name = self._preset_name_variable.get().strip()
        if not selected_preset_name:
            return
        selected_preset_identifier = self._preset_ids_by_name[selected_preset_name]
        updated_payload = self._controller.load_preset(selected_preset_identifier)
        self._set_user_interface_from_request_payload(updated_payload)
        self._refresh_preview()

    def _choose_color(self, variable: tk.StringVar) -> None:
        chosen_color = colorchooser.askcolor(color=variable.get(), parent=self._root)[1]
        if chosen_color:
            variable.set(chosen_color)
            self._schedule_payload_sync()

    def _refresh_audio_devices(self) -> None:
        """Refresh the device dropdown from the audio service."""

        devices = self._controller.refresh_audio_devices()
        device_names = [device.name for device in devices]
        self._audio_device_combobox["values"] = device_names
        if device_names and not self._audio_device_variable.get().strip():
            self._audio_device_variable.set(device_names[0])
        if not device_names:
            self._audio_status_variable.set(
                "No audio devices detected. Install the optional sounddevice "
                "package to enable capture."
            )

    def _start_audio_capture(self) -> None:
        """Start capture on the chosen device and surface readable UI errors."""

        device_name = self._audio_device_variable.get().strip()
        if not device_name:
            messagebox.showinfo("Audio capture", "Choose an input device first.")
            return
        device_identifier = next(
            (
                device.device_identifier
                for device in self._controller.audio_devices()
                if device.name == device_name
            ),
            "",
        )
        try:
            self._controller.start_audio_capture(device_identifier)
        except RuntimeError as error:
            messagebox.showerror("Audio capture", str(error))
            return
        self._audio_status_variable.set(f"Capturing from {device_name}.")

    def _stop_audio_capture(self) -> None:
        """Stop audio capture while leaving the last known analysis visible."""

        snapshot = self._controller.stop_audio_capture()
        if snapshot.last_error:
            self._audio_status_variable.set(snapshot.last_error)
        else:
            self._audio_status_variable.set("Audio capture stopped.")

    def _on_pointer_motion(self, event: tk.Event[tk.Misc]) -> None:
        """Translate pointer movement into normalized control values."""

        canvas_width = max(1, int(self._pointer_canvas.winfo_width()))
        canvas_height = max(1, int(self._pointer_canvas.winfo_height()))
        normalized_x = max(0.0, min(1.0, event.x / canvas_width))
        normalized_y = max(0.0, min(1.0, event.y / canvas_height))
        pointer_speed = math.sqrt(
            (normalized_x - self._last_pointer_x) ** 2 + (normalized_y - self._last_pointer_y) ** 2
        )
        self._last_pointer_x = normalized_x
        self._last_pointer_y = normalized_y
        normalized_pointer_speed = min(pointer_speed * 4.0, 1.0)
        self._controller.update_pointer_signal(
            normalized_x,
            normalized_y,
            normalized_pointer_speed,
        )
        self._pointer_status_variable.set(
            f"Pointer x={normalized_x:.2f} y={normalized_y:.2f} "
            f"speed={normalized_pointer_speed:.2f}"
        )
        if self._controller.live_stream_snapshot()["status"] in {"running", "starting"}:
            self._refresh_preview()

    def _on_pointer_leave(self, event: tk.Event[tk.Misc]) -> None:
        """Reset pointer speed when the operator leaves the pointer pad."""

        self._controller.update_pointer_signal(self._last_pointer_x, self._last_pointer_y, 0.0)
        self._pointer_status_variable.set("Pointer pad idle")

    def _run_health_check(self) -> None:
        """Update the status label using the renderer health endpoint."""

        response = self._controller.health_check()
        if response.status == 200:
            self._health_status_variable.set("Renderer API reachable and healthy.")
        elif response.status == 0:
            self._health_status_variable.set(f"Could not reach the renderer API: {response.body}")
        else:
            self._health_status_variable.set(
                f"Renderer API returned {response.status} {response.reason}."
            )

    def _validate_current_scene(self) -> None:
        """Validate the current preview and show both result text and JSON preview."""

        validation_result = self._controller.validate_current_scene()
        response = validation_result["response"]
        if response.status == 200:
            self._result_status_variable.set("Scene validated successfully.")
        elif response.status == 0:
            self._result_status_variable.set(f"Validation could not reach the API: {response.body}")
        else:
            self._result_status_variable.set(
                f"Validation returned {response.status} {response.reason}."
            )
        self._show_preview_bundle(validation_result["bundle"])

    def _apply_current_scene(self) -> None:
        """Apply the current preview scene and update the status text."""

        apply_result = self._controller.apply_current_scene()
        response = apply_result["response"]
        if apply_result["status"] == "applied":
            self._result_status_variable.set("Scene applied to the live renderer.")
        elif apply_result["status"] == "offline":
            self._result_status_variable.set(f"Renderer API offline: {response.body}")
        else:
            self._result_status_variable.set(
                f"Apply returned {response.status} {response.reason}."
            )
        self._show_preview_bundle(apply_result["bundle"])

    def _start_live_stream(self) -> None:
        """Start the controller-owned live stream from the current UI state."""

        self._sync_payload_to_controller()
        snapshot = self._controller.start_live_stream()
        self._live_status_variable.set(
            f"Live stream {snapshot['status']} at {snapshot['cadence_ms']} ms cadence."
        )

    def _stop_live_stream(self) -> None:
        """Stop the live stream and refresh the visible status line."""

        snapshot = self._controller.stop_live_stream()
        self._live_status_variable.set(f"Live stream {snapshot['status']}.")

    def _refresh_preview(self) -> None:
        """Rebuild and display the current preview bundle."""

        preview_bundle = self._controller.preview_scene_bundle()
        self._show_preview_bundle(preview_bundle)

    def _show_preview_bundle(self, preview_bundle: dict[str, Any]) -> None:
        """Render both the summary label and the full pretty-printed JSON scene."""

        analysis = preview_bundle["analysis"]
        self._analysis_label.configure(
            text=(
                f"Preset: {preview_bundle['preset']['name']} "
                f"({preview_bundle['scene']['sceneType']})\n"
                f"Primitive: {analysis['primitive']}\n"
                f"Vertices: {analysis['vertexCount']}  Indices: {analysis['indexCount']}\n"
                f"Active sources: {', '.join(analysis['activeSources'])}\n"
                f"Energy: {analysis['energy']}"
            )
        )
        formatted_json = json.dumps(preview_bundle["scene"], indent=2)
        self._preview_text.configure(state="normal")
        self._preview_text.delete("1.0", tk.END)
        self._preview_text.insert("1.0", formatted_json)
        self._preview_text.configure(state="disabled")

    def _schedule_status_refresh(self) -> None:
        """Keep audio/live-stream status labels gently refreshed over time."""

        self._refresh_status_labels()
        self._root.after(250, self._schedule_status_refresh)

    def _refresh_status_labels(self) -> None:
        """Refresh status labels from the controller's latest snapshots."""

        audio_snapshot = self._controller.audio_snapshot()
        if audio_snapshot.capturing:
            self._audio_status_variable.set(
                f"{audio_snapshot.device_name}: level {audio_snapshot.level:.2f}, "
                f"bass {audio_snapshot.bass:.2f}, mid {audio_snapshot.mid:.2f}, "
                f"treble {audio_snapshot.treble:.2f}"
            )
        elif audio_snapshot.last_error:
            self._audio_status_variable.set(audio_snapshot.last_error)

        live_snapshot = self._controller.live_stream_snapshot()
        self._live_status_variable.set(
            f"Live {live_snapshot['status']} | cadence {live_snapshot['cadence_ms']} ms | "
            f"attempted {live_snapshot['frames_attempted']} | "
            f"applied {live_snapshot['frames_applied']} | "
            f"failed {live_snapshot['frames_failed']}"
        )

    def _on_close_requested(self) -> None:
        """Shut down background resources before destroying the window."""

        self._controller.close()
        self._root.destroy()

    @staticmethod
    def _safe_int(value: object, default: int) -> int:
        """Parse an integer-like value without raising UI-facing exceptions."""

        if not isinstance(value, (bool, int, float, str)):
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


def main() -> None:
    """Launch the desktop render control panel."""

    root = tk.Tk()
    DesktopRenderControlPanelWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
