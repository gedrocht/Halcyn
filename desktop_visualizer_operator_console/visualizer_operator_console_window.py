"""Modern ttkbootstrap window for the unified Halcyn Visualizer Studio.

This window is intentionally beginner-friendly. The controller owns the
business logic and API behavior, while this file focuses on:

- which controls exist
- how the controls are arranged
- which controller actions each user gesture should trigger

Helpful external references:

- ttkbootstrap overview: https://ttkbootstrap.readthedocs.io/
- Tkinter overview: https://docs.python.org/3/library/tkinter.html
- Tkinter scrolled text: https://docs.python.org/3/library/tkinter.scrolledtext.html
- File dialogs: https://docs.python.org/3/library/dialog.html#tkinter.filedialog
"""

from __future__ import annotations

import json
import math
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from typing import Any

import ttkbootstrap as ttkb  # noqa: I001

from desktop_visualizer_operator_console.visualizer_operator_console_controller import (
    VisualizerOperatorConsoleController,
)
from desktop_visualizer_operator_console.visualizer_operator_scene_builder import (
    VisualizerPreviewBundle,
)

DEFAULT_SETTINGS_FILE_NAME = "halcyn-visualizer-studio-settings.json"


class VisualizerOperatorConsoleWindow:
    """Build and manage the unified desktop Visualizer Studio window."""

    def __init__(
        self,
        root_window: ttkb.Window,
        controller: VisualizerOperatorConsoleController | None = None,
    ) -> None:
        # The controller already knows how to talk to the renderer and how to
        # translate sources into scenes. The window keeps only the small amount
        # of transient UI state needed to redraw itself smoothly.
        self._root_window = root_window
        self._controller = controller or VisualizerOperatorConsoleController()
        self._catalog_payload = self._controller.catalog_payload()
        self._latest_preview_bundle: VisualizerPreviewBundle | None = None
        self._preview_window: tk.Toplevel | None = None
        self._preview_text_widget: ScrolledText | None = None
        self._settings_file_path: Path | None = None
        self._pointer_marker_identifier: int | None = None
        self._last_pointer_x = 0.5
        self._last_pointer_y = 0.5
        self._pending_preview_refresh_after_identifier: str | None = None
        self._suppress_preview_refresh_requests = False
        self._audio_device_identifiers_by_label: dict[str, str] = {}
        self._audio_device_labels_by_identifier: dict[str, str] = {}
        self._build_variables()
        self._configure_root_window()
        self._build_user_interface()
        self._sync_user_interface_from_request_payload(self._controller.current_request_payload())
        self._refresh_audio_devices()
        self._schedule_preview_refresh(immediate=True)
        self._schedule_status_refresh()

    def _build_variables(self) -> None:
        """Create Tk variables that mirror the editable request payload."""

        self._scene_mode_variable = tk.StringVar(value="preset_scene")
        self._source_mode_variable = tk.StringVar(value="json_document")
        self._target_host_variable = tk.StringVar(value="127.0.0.1")
        self._target_port_variable = tk.StringVar(value="8080")
        self._live_cadence_variable = tk.IntVar(value=125)
        self._live_cadence_label_variable = tk.StringVar(value="125 ms")
        self._plain_text_variable = tk.StringVar(value="Halcyn")
        self._random_seed_variable = tk.StringVar(value="7")
        self._random_count_variable = tk.StringVar(value="128")
        self._random_minimum_variable = tk.StringVar(value="0.0")
        self._random_maximum_variable = tk.StringVar(value="255.0")
        self._audio_device_flow_variable = tk.StringVar(value="output")
        self._audio_device_variable = tk.StringVar(value="")
        self._preset_identifier_variable = tk.StringVar(value="")
        self._preset_use_epoch_variable = tk.BooleanVar(value=True)
        self._preset_use_noise_variable = tk.BooleanVar(value=True)
        self._bar_wall_grid_size_variable = tk.IntVar(value=8)
        self._bar_wall_grid_size_label_variable = tk.StringVar(value="8 x 8")
        self._bar_wall_shader_style_variable = tk.StringVar(value="heatmap")
        self._bar_wall_anti_aliasing_variable = tk.BooleanVar(value=True)
        self._bar_wall_range_mode_variable = tk.StringVar(value="automatic")
        self._bar_wall_manual_minimum_variable = tk.StringVar(value="0.0")
        self._bar_wall_manual_maximum_variable = tk.StringVar(value="255.0")
        self._result_status_variable = tk.StringVar(value="Ready.")
        self._health_status_variable = tk.StringVar(value="Health check not run yet.")
        self._live_status_variable = tk.StringVar(value="Live stream idle.")
        self._audio_status_variable = tk.StringVar(value="Audio capture not started.")
        self._source_summary_variable = tk.StringVar(
            value="Choose a source mode to see how incoming values will be interpreted."
        )
        self._preview_summary_variable = tk.StringVar(
            value="Preview analysis will appear here after the first refresh."
        )
        self._volume_meter_progress_variable = tk.DoubleVar(value=0.0)
        self._volume_meter_text_variable = tk.StringVar(value="0%")

    def _configure_root_window(self) -> None:
        """Apply top-level window settings."""

        self._root_window.title("Halcyn Visualizer Studio")
        self._root_window.geometry("1540x940")
        self._root_window.minsize(1260, 780)
        self._root_window.protocol("WM_DELETE_WINDOW", self._on_close_requested)

    def _build_user_interface(self) -> None:
        """Create the notebook-driven window layout."""

        shell_frame = ttkb.Frame(self._root_window, padding=18)
        shell_frame.pack(fill="both", expand=True)
        shell_frame.columnconfigure(0, weight=1)
        shell_frame.rowconfigure(2, weight=1)

        ttkb.Label(
            shell_frame,
            text="Halcyn Visualizer Studio",
            font=("Segoe UI Semibold", 24),
        ).grid(row=0, column=0, sticky="w")
        ttkb.Label(
            shell_frame,
            text=(
                "One desktop place for live sources, preset scenes, bar-wall scenes, "
                "renderer transport, and diagnostics."
            ),
            bootstyle="secondary",
        ).grid(row=1, column=0, sticky="w", pady=(6, 14))

        notebook = ttkb.Notebook(shell_frame)
        notebook.grid(row=2, column=0, sticky="nsew")

        self._source_tab = ttkb.Frame(notebook, padding=16)
        self._scene_tab = ttkb.Frame(notebook, padding=16)
        self._transport_tab = ttkb.Frame(notebook, padding=16)
        notebook.add(self._source_tab, text="Source")
        notebook.add(self._scene_tab, text="Scene")
        notebook.add(self._transport_tab, text="Transport")

        self._build_source_tab()
        self._build_scene_tab()
        self._build_transport_tab()
        self._bind_live_preview_triggers()

    def _build_source_tab(self) -> None:
        """Create source-selection controls and their mode-specific widgets."""

        self._source_tab.columnconfigure(0, weight=1)
        self._source_tab.rowconfigure(2, weight=1)

        source_mode_frame = ttkb.Labelframe(self._source_tab, text="Source mode", padding=12)
        source_mode_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for source_mode_index, source_mode_entry in enumerate(self._catalog_payload["sourceModes"]):
            source_mode_frame.columnconfigure(source_mode_index, weight=1)
            ttkb.Radiobutton(
                source_mode_frame,
                text=source_mode_entry["name"],
                variable=self._source_mode_variable,
                value=source_mode_entry["id"],
                bootstyle="toolbutton",
                command=self._on_source_mode_changed,
            ).grid(row=0, column=source_mode_index, sticky="ew", padx=(0, 8))

        self._source_specific_container = ttkb.Frame(self._source_tab)
        self._source_specific_container.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        self._source_specific_container.columnconfigure(0, weight=1)
        self._source_specific_container.rowconfigure(0, weight=1)
        self._source_specific_frames: dict[str, ttkb.Frame] = {}
        self._source_specific_frames["json_document"] = self._build_json_source_frame()
        self._source_specific_frames["plain_text"] = self._build_plain_text_source_frame()
        self._source_specific_frames["random_values"] = self._build_random_source_frame()
        self._source_specific_frames["audio_device"] = self._build_audio_source_frame()
        self._source_specific_frames["pointer_pad"] = self._build_pointer_source_frame()

        summary_frame = ttkb.Labelframe(self._source_tab, text="Source summary", padding=12)
        summary_frame.grid(row=2, column=0, sticky="nsew")
        summary_frame.columnconfigure(0, weight=1)
        ttkb.Label(
            summary_frame,
            textvariable=self._source_summary_variable,
            justify="left",
            wraplength=940,
        ).grid(row=0, column=0, sticky="ew")

    def _build_json_source_frame(self) -> Any:
        """Create the editable JSON-document source frame."""

        frame = ttkb.Labelframe(self._source_specific_container, text="JSON document", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        example_button_row = ttkb.Frame(frame)
        example_button_row.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        for example_index, example_entry in enumerate(self._catalog_payload["barWallExamples"]):
            example_button_row.columnconfigure(example_index, weight=1)
            ttkb.Button(
                example_button_row,
                text=example_entry["name"],
                bootstyle="secondary",
                command=lambda json_text=example_entry["jsonText"]: self._load_json_example(
                    json_text
                ),
            ).grid(row=0, column=example_index, sticky="ew", padx=(0, 8))

        ttkb.Button(
            frame,
            text="Load JSON file",
            bootstyle="secondary",
            command=self._load_json_file,
        ).grid(row=1, column=0, sticky="w", pady=(0, 8))

        self._json_text_widget = ScrolledText(
            frame,
            height=18,
            wrap="word",
            font=("Consolas", 10),
        )
        self._json_text_widget.grid(row=2, column=0, sticky="nsew")
        self._json_text_widget.bind("<KeyRelease>", lambda _event: self._schedule_preview_refresh())
        return frame

    def _build_plain_text_source_frame(self) -> Any:
        """Create the plain-text source frame."""

        frame = ttkb.Labelframe(self._source_specific_container, text="Plain text", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)
        ttkb.Label(frame, text="Text").grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttkb.Entry(frame, textvariable=self._plain_text_variable).grid(row=0, column=1, sticky="ew")
        return frame

    def _build_random_source_frame(self) -> Any:
        """Create deterministic random-source controls."""

        frame = ttkb.Labelframe(self._source_specific_container, text="Random values", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        for column_index in range(4):
            frame.columnconfigure(column_index, weight=1)

        self._build_labeled_entry(frame, "Seed", self._random_seed_variable, 0, 0)
        self._build_labeled_entry(frame, "Count", self._random_count_variable, 0, 1)
        self._build_labeled_entry(frame, "Minimum", self._random_minimum_variable, 0, 2)
        self._build_labeled_entry(frame, "Maximum", self._random_maximum_variable, 0, 3)
        return frame

    def _build_audio_source_frame(self) -> Any:
        """Create audio-device controls and one live volume meter."""

        frame = ttkb.Labelframe(self._source_specific_container, text="Audio device", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        ttkb.Radiobutton(
            frame,
            text="Output sources",
            variable=self._audio_device_flow_variable,
            value="output",
            bootstyle="toolbutton",
            command=self._refresh_audio_devices,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttkb.Radiobutton(
            frame,
            text="Input sources",
            variable=self._audio_device_flow_variable,
            value="input",
            bootstyle="toolbutton",
            command=self._refresh_audio_devices,
        ).grid(row=0, column=1, sticky="ew")

        ttkb.Label(frame, text="Device").grid(row=1, column=0, sticky="w", pady=(12, 6))
        self._audio_device_combobox = ttkb.Combobox(
            frame,
            textvariable=self._audio_device_variable,
            state="readonly",
        )
        self._audio_device_combobox.grid(row=1, column=1, sticky="ew", pady=(12, 6))
        self._audio_device_combobox.bind(
            "<<ComboboxSelected>>", lambda _event: self._schedule_preview_refresh()
        )

        button_row = ttkb.Frame(frame)
        button_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        for column_index in range(3):
            button_row.columnconfigure(column_index, weight=1)
        ttkb.Button(
            button_row,
            text="Refresh",
            bootstyle="secondary",
            command=self._refresh_audio_devices,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttkb.Button(
            button_row,
            text="Start capture",
            bootstyle="success",
            command=self._start_audio_capture,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttkb.Button(
            button_row,
            text="Stop capture",
            bootstyle="danger",
            command=self._stop_audio_capture,
        ).grid(row=0, column=2, sticky="ew")

        ttkb.Label(frame, text="Volume").grid(row=3, column=0, sticky="w", pady=(8, 6))
        self._volume_meter = ttkb.Progressbar(
            frame,
            variable=self._volume_meter_progress_variable,
            maximum=100,
            bootstyle="info-striped",
        )
        self._volume_meter.grid(row=3, column=1, sticky="ew", pady=(8, 6))
        ttkb.Label(frame, textvariable=self._volume_meter_text_variable).grid(
            row=4, column=1, sticky="e"
        )
        return frame

    def _build_pointer_source_frame(self) -> Any:
        """Create a larger pointer pad for live x/y/speed input."""

        frame = ttkb.Labelframe(self._source_specific_container, text="Pointer pad", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        ttkb.Label(
            frame,
            text="Move inside the pad to generate x, y, and speed values.",
            bootstyle="secondary",
        ).pack(anchor="w", pady=(0, 8))

        self._pointer_canvas = tk.Canvas(frame, width=620, height=360, highlightthickness=0)
        self._pointer_canvas.pack(fill="both", expand=True)
        self._pointer_canvas.create_rectangle(0, 0, 620, 360, fill="#10243a", outline="")
        self._pointer_marker_identifier = self._pointer_canvas.create_oval(
            300,
            170,
            320,
            190,
            fill="#6ee7b7",
            outline="",
        )
        self._pointer_canvas.bind("<Motion>", self._on_pointer_motion)
        self._pointer_canvas.bind("<B1-Motion>", self._on_pointer_motion)
        self._pointer_canvas.bind("<Leave>", self._on_pointer_leave)
        return frame

    def _build_scene_tab(self) -> None:
        """Create target and scene-family settings."""

        self._scene_tab.columnconfigure(0, weight=1)
        self._scene_tab.rowconfigure(2, weight=1)

        target_frame = ttkb.Labelframe(self._scene_tab, text="Visualizer target", padding=12)
        target_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        target_frame.columnconfigure(0, weight=1)
        target_frame.columnconfigure(1, weight=1)
        self._build_labeled_entry(target_frame, "Host", self._target_host_variable, 0, 0)
        self._build_labeled_entry(target_frame, "Port", self._target_port_variable, 0, 1)

        scene_mode_frame = ttkb.Labelframe(self._scene_tab, text="Scene family", padding=12)
        scene_mode_frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        scene_mode_frame.columnconfigure(0, weight=1)
        scene_mode_frame.columnconfigure(1, weight=1)
        ttkb.Radiobutton(
            scene_mode_frame,
            text="Preset scene",
            variable=self._scene_mode_variable,
            value="preset_scene",
            bootstyle="toolbutton",
            command=self._on_scene_mode_changed,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttkb.Radiobutton(
            scene_mode_frame,
            text="Bar wall",
            variable=self._scene_mode_variable,
            value="bar_wall_scene",
            bootstyle="toolbutton",
            command=self._on_scene_mode_changed,
        ).grid(row=0, column=1, sticky="ew")

        self._scene_specific_container = ttkb.Frame(self._scene_tab)
        self._scene_specific_container.grid(row=2, column=0, sticky="nsew")
        self._scene_specific_container.columnconfigure(0, weight=1)
        self._scene_specific_container.rowconfigure(0, weight=1)
        self._scene_specific_frames: dict[str, ttkb.Frame] = {}
        self._scene_specific_frames["preset_scene"] = self._build_preset_scene_frame()
        self._scene_specific_frames["bar_wall_scene"] = self._build_bar_wall_scene_frame()

    def _build_preset_scene_frame(self) -> Any:
        """Create controls for the original preset-scene family."""

        frame = ttkb.Labelframe(
            self._scene_specific_container,
            text="Preset scene options",
            padding=12,
        )
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)
        ttkb.Label(frame, text="Preset").grid(row=0, column=0, sticky="w", padx=(0, 12))
        self._preset_combobox = ttkb.Combobox(
            frame,
            textvariable=self._preset_identifier_variable,
            values=[preset["id"] for preset in self._catalog_payload["presetScenes"]],
            state="readonly",
        )
        self._preset_combobox.grid(row=0, column=1, sticky="ew")
        self._preset_combobox.bind(
            "<<ComboboxSelected>>", lambda _event: self._schedule_preview_refresh()
        )

        ttkb.Checkbutton(
            frame,
            text="Use epoch signal",
            variable=self._preset_use_epoch_variable,
            bootstyle="success",
            command=self._schedule_preview_refresh,
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttkb.Checkbutton(
            frame,
            text="Use noise signal",
            variable=self._preset_use_noise_variable,
            bootstyle="success",
            command=self._schedule_preview_refresh,
        ).grid(row=1, column=1, sticky="w", pady=(10, 0))
        return frame

    def _build_bar_wall_scene_frame(self) -> Any:
        """Create controls for the bar-wall scene family."""

        frame = ttkb.Labelframe(self._scene_specific_container, text="Bar wall options", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        ttkb.Label(frame, text="Grid size").grid(row=0, column=0, sticky="w")
        ttkb.Scale(
            frame,
            from_=2,
            to=24,
            variable=self._bar_wall_grid_size_variable,
            command=self._on_bar_wall_grid_size_changed,
            bootstyle="info",
        ).grid(row=0, column=1, sticky="ew")
        ttkb.Label(frame, textvariable=self._bar_wall_grid_size_label_variable).grid(
            row=1, column=1, sticky="e", pady=(0, 8)
        )

        ttkb.Label(frame, text="Shader").grid(row=2, column=0, sticky="w")
        shader_style_combobox = ttkb.Combobox(
            frame,
            textvariable=self._bar_wall_shader_style_variable,
            values=self._catalog_payload["barWallShaderStyles"],
            state="readonly",
        )
        shader_style_combobox.grid(row=2, column=1, sticky="ew")
        shader_style_combobox.bind(
            "<<ComboboxSelected>>", lambda _event: self._schedule_preview_refresh()
        )

        ttkb.Checkbutton(
            frame,
            text="Anti-aliasing",
            variable=self._bar_wall_anti_aliasing_variable,
            bootstyle="success",
            command=self._schedule_preview_refresh,
        ).grid(row=3, column=1, sticky="w", pady=(10, 0))

        ttkb.Label(frame, text="Range mode").grid(row=4, column=0, sticky="w", pady=(12, 0))
        ttkb.Radiobutton(
            frame,
            text="Automatic",
            variable=self._bar_wall_range_mode_variable,
            value="automatic",
            bootstyle="toolbutton-outline",
            command=self._schedule_preview_refresh,
        ).grid(row=4, column=1, sticky="w", pady=(12, 0))
        ttkb.Radiobutton(
            frame,
            text="Manual",
            variable=self._bar_wall_range_mode_variable,
            value="manual",
            bootstyle="toolbutton-outline",
            command=self._schedule_preview_refresh,
        ).grid(row=5, column=1, sticky="w", pady=(6, 0))

        self._build_labeled_entry(
            frame,
            "Manual minimum",
            self._bar_wall_manual_minimum_variable,
            6,
            0,
        )
        self._build_labeled_entry(
            frame,
            "Manual maximum",
            self._bar_wall_manual_maximum_variable,
            6,
            1,
        )
        return frame

    def _build_transport_tab(self) -> None:
        """Create status, transport, preview, and settings controls."""

        self._transport_tab.columnconfigure(0, weight=3)
        self._transport_tab.columnconfigure(1, weight=2)
        self._transport_tab.rowconfigure(0, weight=1)

        left_column = ttkb.Frame(self._transport_tab)
        left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left_column.columnconfigure(0, weight=1)

        live_frame = ttkb.Labelframe(left_column, text="Live session", padding=12)
        live_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        live_frame.columnconfigure(1, weight=1)
        ttkb.Label(live_frame, text="Live cadence").grid(row=0, column=0, sticky="w")
        ttkb.Scale(
            live_frame,
            from_=40,
            to=2000,
            variable=self._live_cadence_variable,
            command=self._on_live_cadence_changed,
            bootstyle="info",
        ).grid(row=0, column=1, sticky="ew")
        ttkb.Label(live_frame, textvariable=self._live_cadence_label_variable).grid(
            row=1, column=1, sticky="e", pady=(0, 8)
        )

        transport_button_row = ttkb.Frame(live_frame)
        transport_button_row.grid(row=2, column=0, columnspan=2, sticky="ew")
        for column_index in range(4):
            transport_button_row.columnconfigure(column_index, weight=1)
        ttkb.Button(
            transport_button_row,
            text="Refresh preview",
            bootstyle="secondary",
            command=self._refresh_preview,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttkb.Button(
            transport_button_row,
            text="Validate",
            bootstyle="secondary",
            command=self._validate_current_scene,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttkb.Button(
            transport_button_row,
            text="Apply once",
            bootstyle="success",
            command=self._apply_current_scene,
        ).grid(row=0, column=2, sticky="ew", padx=(0, 8))
        ttkb.Button(
            transport_button_row,
            text="Check health",
            bootstyle="secondary",
            command=self._run_health_check,
        ).grid(row=0, column=3, sticky="ew")

        live_stream_button_row = ttkb.Frame(live_frame)
        live_stream_button_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        for column_index in range(3):
            live_stream_button_row.columnconfigure(column_index, weight=1)
        ttkb.Button(
            live_stream_button_row,
            text="Start live stream",
            bootstyle="primary",
            command=self._start_live_stream,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttkb.Button(
            live_stream_button_row,
            text="Stop live stream",
            bootstyle="warning",
            command=self._stop_live_stream,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttkb.Button(
            live_stream_button_row,
            text="Open JSON preview",
            bootstyle="secondary",
            command=self._open_preview_window,
        ).grid(row=0, column=2, sticky="ew")

        settings_frame = ttkb.Labelframe(left_column, text="Settings", padding=12)
        settings_frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        for column_index in range(3):
            settings_frame.columnconfigure(column_index, weight=1)
        ttkb.Button(
            settings_frame,
            text="Revert to defaults",
            bootstyle="secondary",
            command=self._reset_to_defaults,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttkb.Button(
            settings_frame,
            text="Load settings",
            bootstyle="secondary",
            command=self._load_settings_file,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttkb.Button(
            settings_frame,
            text="Save settings",
            bootstyle="secondary",
            command=self._save_settings_file,
        ).grid(row=0, column=2, sticky="ew")

        preview_frame = ttkb.Labelframe(left_column, text="Preview analysis", padding=12)
        preview_frame.grid(row=2, column=0, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        ttkb.Label(
            preview_frame,
            textvariable=self._preview_summary_variable,
            justify="left",
            wraplength=780,
        ).grid(row=0, column=0, sticky="ew")

        right_column = ttkb.Frame(self._transport_tab)
        right_column.grid(row=0, column=1, sticky="nsew")
        right_column.columnconfigure(0, weight=1)

        status_frame = ttkb.Labelframe(right_column, text="Runtime status", padding=12)
        status_frame.grid(row=0, column=0, sticky="new")
        status_frame.columnconfigure(1, weight=1)
        self._build_status_row(status_frame, 0, "Result", self._result_status_variable)
        self._build_status_row(status_frame, 1, "Health", self._health_status_variable)
        self._build_status_row(status_frame, 2, "Live stream", self._live_status_variable)
        self._build_status_row(status_frame, 3, "Audio", self._audio_status_variable)

    def _build_status_row(
        self,
        parent: Any,
        row_index: int,
        label_text: str,
        value_variable: tk.StringVar,
    ) -> None:
        """Create one labeled status row."""

        ttkb.Label(parent, text=label_text).grid(
            row=row_index,
            column=0,
            sticky="nw",
            padx=(0, 12),
            pady=(0, 8),
        )
        ttkb.Label(
            parent,
            textvariable=value_variable,
            justify="left",
            wraplength=420,
        ).grid(row=row_index, column=1, sticky="ew", pady=(0, 8))

    def _build_labeled_entry(
        self,
        parent: Any,
        label_text: str,
        variable: tk.StringVar,
        row_index: int,
        column_index: int,
    ) -> None:
        """Build one label-entry pair in a two-column layout."""

        frame = ttkb.Frame(parent)
        frame.grid(row=row_index, column=column_index, sticky="ew", padx=(0, 12), pady=(0, 8))
        frame.columnconfigure(0, weight=1)
        ttkb.Label(frame, text=label_text).grid(row=0, column=0, sticky="w")
        ttkb.Entry(frame, textvariable=variable).grid(row=1, column=0, sticky="ew")

    def _bind_live_preview_triggers(self) -> None:
        """Connect common variable changes to one debounced preview refresh."""

        preview_trigger_variables: list[tk.Variable] = [
            self._target_host_variable,
            self._target_port_variable,
            self._plain_text_variable,
            self._random_seed_variable,
            self._random_count_variable,
            self._random_minimum_variable,
            self._random_maximum_variable,
            self._audio_device_flow_variable,
            self._preset_identifier_variable,
            self._bar_wall_shader_style_variable,
            self._bar_wall_range_mode_variable,
            self._bar_wall_manual_minimum_variable,
            self._bar_wall_manual_maximum_variable,
            self._preset_use_epoch_variable,
            self._preset_use_noise_variable,
            self._bar_wall_anti_aliasing_variable,
        ]
        for variable in preview_trigger_variables:
            variable.trace_add("write", self._schedule_preview_refresh_from_trace)

    def _schedule_preview_refresh_from_trace(self, *_unused: object) -> None:
        """Bridge Tk variable traces into the debounced refresh helper."""

        if self._suppress_preview_refresh_requests:
            return
        self._schedule_preview_refresh()

    def _load_json_example(self, json_text: str) -> None:
        """Load one built-in JSON example into the editor."""

        self._json_text_widget.delete("1.0", "end")
        self._json_text_widget.insert("1.0", json_text)
        self._schedule_preview_refresh(immediate=True)

    def _load_json_file(self) -> None:
        """Load JSON text from disk into the editor."""

        file_path = filedialog.askopenfilename(
            title="Load JSON source document",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not file_path:
            return

        json_text = Path(file_path).read_text(encoding="utf-8")
        self._load_json_example(json_text)

    def _build_request_payload_from_user_interface(self) -> dict[str, Any]:
        """Collect the complete editable payload from the current widget state."""

        selected_audio_label = self._audio_device_variable.get().strip()
        selected_audio_identifier = self._audio_device_identifiers_by_label.get(
            selected_audio_label,
            selected_audio_label,
        )

        return {
            "target": {
                "host": self._target_host_variable.get().strip(),
                "port": self._target_port_variable.get().strip(),
            },
            "sceneMode": self._scene_mode_variable.get(),
            "source": {
                "mode": self._source_mode_variable.get(),
                "jsonText": self._json_text_widget.get("1.0", "end").strip(),
                "plainText": self._plain_text_variable.get(),
                "random": {
                    "seed": self._random_seed_variable.get().strip(),
                    "count": self._random_count_variable.get().strip(),
                    "minimum": self._random_minimum_variable.get().strip(),
                    "maximum": self._random_maximum_variable.get().strip(),
                },
                "pointer": {
                    "x": self._last_pointer_x,
                    "y": self._last_pointer_y,
                    "speed": 0.0,
                },
                "audio": {
                    "deviceFlow": self._audio_device_flow_variable.get(),
                    "deviceIdentifier": selected_audio_identifier,
                },
            },
            "presetScene": {
                "presetId": self._preset_identifier_variable.get(),
                "useEpoch": self._preset_use_epoch_variable.get(),
                "useNoise": self._preset_use_noise_variable.get(),
            },
            "barWallScene": {
                "render": {
                    "barGridSize": self._bar_wall_grid_size_variable.get(),
                    "shaderStyle": self._bar_wall_shader_style_variable.get(),
                    "antiAliasing": self._bar_wall_anti_aliasing_variable.get(),
                },
                "range": {
                    "mode": self._bar_wall_range_mode_variable.get(),
                    "manualMinimum": self._bar_wall_manual_minimum_variable.get().strip(),
                    "manualMaximum": self._bar_wall_manual_maximum_variable.get().strip(),
                },
            },
            "session": {
                "cadenceMs": self._live_cadence_variable.get(),
            },
        }

    def _sync_user_interface_from_request_payload(self, request_payload: dict[str, Any]) -> None:
        """Update the visible widgets to match one normalized payload."""

        target_payload = request_payload["target"]
        source_payload = request_payload["source"]
        preset_scene_payload = request_payload["presetScene"]
        bar_wall_scene_payload = request_payload["barWallScene"]
        session_payload = request_payload["session"]

        self._suppress_preview_refresh_requests = True
        try:
            self._scene_mode_variable.set(str(request_payload["sceneMode"]))
            self._source_mode_variable.set(str(source_payload["mode"]))
            self._target_host_variable.set(str(target_payload["host"]))
            self._target_port_variable.set(str(target_payload["port"]))
            self._live_cadence_variable.set(int(session_payload["cadenceMs"]))
            self._plain_text_variable.set(str(source_payload["plainText"]))
            self._random_seed_variable.set(str(source_payload["random"]["seed"]))
            self._random_count_variable.set(str(source_payload["random"]["count"]))
            self._random_minimum_variable.set(str(source_payload["random"]["minimum"]))
            self._random_maximum_variable.set(str(source_payload["random"]["maximum"]))
            self._audio_device_flow_variable.set(str(source_payload["audio"]["deviceFlow"]))
            self._preset_identifier_variable.set(str(preset_scene_payload["presetId"]))
            self._preset_use_epoch_variable.set(bool(preset_scene_payload["useEpoch"]))
            self._preset_use_noise_variable.set(bool(preset_scene_payload["useNoise"]))
            self._bar_wall_grid_size_variable.set(
                int(bar_wall_scene_payload["render"]["barGridSize"])
            )
            self._bar_wall_shader_style_variable.set(
                str(bar_wall_scene_payload["render"]["shaderStyle"])
            )
            self._bar_wall_anti_aliasing_variable.set(
                bool(bar_wall_scene_payload["render"]["antiAliasing"])
            )
            self._bar_wall_range_mode_variable.set(str(bar_wall_scene_payload["range"]["mode"]))
            self._bar_wall_manual_minimum_variable.set(
                str(bar_wall_scene_payload["range"]["manualMinimum"])
            )
            self._bar_wall_manual_maximum_variable.set(
                str(bar_wall_scene_payload["range"]["manualMaximum"])
            )

            self._json_text_widget.delete("1.0", "end")
            self._json_text_widget.insert("1.0", str(source_payload["jsonText"]))

            selected_audio_identifier = str(source_payload["audio"]["deviceIdentifier"])
            selected_audio_label = self._audio_device_labels_by_identifier.get(
                selected_audio_identifier,
                selected_audio_identifier,
            )
            self._audio_device_variable.set(selected_audio_label)
        finally:
            self._suppress_preview_refresh_requests = False

        self._on_live_cadence_changed(str(self._live_cadence_variable.get()))
        self._on_bar_wall_grid_size_changed(str(self._bar_wall_grid_size_variable.get()))
        self._sync_source_mode_visibility()
        self._sync_scene_mode_visibility()

    def _on_source_mode_changed(self) -> None:
        """Handle a source-mode selection change."""

        self._sync_source_mode_visibility()
        self._schedule_preview_refresh(immediate=True)

    def _sync_source_mode_visibility(self) -> None:
        """Show only the widgets that belong to the chosen source mode."""

        selected_source_mode = self._source_mode_variable.get()
        for source_mode, frame in self._source_specific_frames.items():
            if source_mode == selected_source_mode:
                frame.grid()
            else:
                frame.grid_remove()

    def _on_scene_mode_changed(self) -> None:
        """Handle a scene-family selection change."""

        self._sync_scene_mode_visibility()
        self._schedule_preview_refresh(immediate=True)

    def _sync_scene_mode_visibility(self) -> None:
        """Show only the widgets that belong to the chosen scene family."""

        selected_scene_mode = self._scene_mode_variable.get()
        for scene_mode, frame in self._scene_specific_frames.items():
            if scene_mode == selected_scene_mode:
                frame.grid()
            else:
                frame.grid_remove()

    def _refresh_audio_devices(self) -> None:
        """Refresh the visible audio-device list for the selected flow."""

        try:
            audio_devices = self._controller.refresh_audio_devices(
                self._audio_device_flow_variable.get()
            )
        except Exception as error:
            messagebox.showerror("Audio devices", str(error))
            return

        self._audio_device_identifiers_by_label.clear()
        self._audio_device_labels_by_identifier.clear()
        audio_device_labels: list[str] = []
        for audio_device in audio_devices:
            flow_prefix = "Output" if audio_device.device_flow == "output" else "Input"
            label = f"{flow_prefix}: {audio_device.name}"
            self._audio_device_identifiers_by_label[label] = audio_device.device_identifier
            self._audio_device_labels_by_identifier[audio_device.device_identifier] = label
            audio_device_labels.append(label)

        self._audio_device_combobox.configure(values=audio_device_labels)
        if audio_device_labels and self._audio_device_variable.get() not in audio_device_labels:
            self._audio_device_variable.set(audio_device_labels[0])
        elif not audio_device_labels:
            self._audio_device_variable.set("")

        self._schedule_preview_refresh()

    def _start_audio_capture(self) -> None:
        """Start audio capture for the selected device."""

        selected_audio_label = self._audio_device_variable.get().strip()
        selected_audio_identifier = self._audio_device_identifiers_by_label.get(
            selected_audio_label
        )
        if not selected_audio_identifier:
            messagebox.showerror(
                "Audio capture",
                "Choose an audio device before starting capture.",
            )
            return

        try:
            audio_snapshot = self._controller.start_audio_capture(
                selected_audio_identifier,
                self._audio_device_flow_variable.get(),
            )
        except Exception as error:
            messagebox.showerror("Audio capture", str(error))
            return

        self._audio_status_variable.set(
            f"Capturing {audio_snapshot.device_name or selected_audio_label}."
        )
        self._source_mode_variable.set("audio_device")
        self._sync_source_mode_visibility()
        self._schedule_preview_refresh(immediate=True)

    def _stop_audio_capture(self) -> None:
        """Stop active audio capture."""

        audio_snapshot = self._controller.stop_audio_capture()
        self._audio_status_variable.set(
            audio_snapshot.last_error or "Audio capture not started."
        )
        self._volume_meter_progress_variable.set(0.0)
        self._volume_meter_text_variable.set("0%")

    def _on_pointer_motion(self, event: tk.Event[tk.Misc]) -> None:
        """Update the pointer source sample from canvas motion."""

        canvas_width = max(1, int(self._pointer_canvas.winfo_width()))
        canvas_height = max(1, int(self._pointer_canvas.winfo_height()))
        normalized_x = min(max(event.x / canvas_width, 0.0), 1.0)
        normalized_y = min(max(event.y / canvas_height, 0.0), 1.0)
        delta_x = normalized_x - self._last_pointer_x
        delta_y = normalized_y - self._last_pointer_y
        pointer_speed = min(math.sqrt((delta_x * delta_x) + (delta_y * delta_y)) * 8.0, 1.0)
        self._last_pointer_x = normalized_x
        self._last_pointer_y = normalized_y

        if self._pointer_marker_identifier is not None:
            canvas_x = normalized_x * canvas_width
            canvas_y = normalized_y * canvas_height
            self._pointer_canvas.coords(
                self._pointer_marker_identifier,
                canvas_x - 10,
                canvas_y - 10,
                canvas_x + 10,
                canvas_y + 10,
            )

        self._controller.update_pointer_signal(normalized_x, normalized_y, pointer_speed)
        if self._source_mode_variable.get() == "pointer_pad":
            self._schedule_preview_refresh()

    def _on_pointer_leave(self, _event: tk.Event[tk.Misc]) -> None:
        """Reset the pointer speed when the cursor leaves the pointer pad."""

        self._controller.update_pointer_signal(self._last_pointer_x, self._last_pointer_y, 0.0)
        if self._source_mode_variable.get() == "pointer_pad":
            self._schedule_preview_refresh()

    def _on_bar_wall_grid_size_changed(self, _value: str) -> None:
        """Update the visible bar-grid label and refresh the preview."""

        grid_size = int(round(self._bar_wall_grid_size_variable.get()))
        self._bar_wall_grid_size_variable.set(grid_size)
        self._bar_wall_grid_size_label_variable.set(f"{grid_size} x {grid_size}")
        self._schedule_preview_refresh()

    def _on_live_cadence_changed(self, _value: str) -> None:
        """Update the visible live-cadence label and refresh the preview."""

        cadence_ms = int(round(self._live_cadence_variable.get()))
        self._live_cadence_variable.set(cadence_ms)
        self._live_cadence_label_variable.set(f"{cadence_ms} ms")
        self._schedule_preview_refresh()

    def _schedule_preview_refresh(self, *_unused: object, immediate: bool = False) -> None:
        """Debounce repeated UI edits into one preview refresh."""

        if self._pending_preview_refresh_after_identifier is not None:
            self._root_window.after_cancel(self._pending_preview_refresh_after_identifier)
            self._pending_preview_refresh_after_identifier = None

        if immediate:
            self._refresh_preview()
            return

        self._pending_preview_refresh_after_identifier = self._root_window.after(
            180,
            self._refresh_preview,
        )

    def _refresh_preview(self) -> None:
        """Build the current preview bundle and refresh the status text."""

        self._pending_preview_refresh_after_identifier = None
        try:
            normalized_request_payload = self._controller.replace_request_payload(
                self._build_request_payload_from_user_interface()
            )
            self._latest_preview_bundle = self._controller.preview_bundle()
            source_analysis = self._latest_preview_bundle.collected_source_data.analysis
            preview_analysis = self._latest_preview_bundle.analysis
            self._source_summary_variable.set(
                f"{source_analysis['sourceMode']} produced "
                f"{source_analysis['valueCount']} values. "
                f"Range: {source_analysis['observedMinimum']:.2f} .. "
                f"{source_analysis['observedMaximum']:.2f}. "
                f"{source_analysis['details']}"
            )
            self._preview_summary_variable.set(
                self._build_preview_summary_text(preview_analysis)
            )
            self._result_status_variable.set(
                f"Preview ready for {self._latest_preview_bundle.scene_mode}."
            )
            self._refresh_preview_window_contents()
            self._sync_user_interface_from_request_payload(normalized_request_payload)
        except Exception as error:
            self._result_status_variable.set(f"Preview failed: {error}")
            self._preview_summary_variable.set(str(error))

    def _build_preview_summary_text(self, preview_analysis: dict[str, Any]) -> str:
        """Turn the preview analysis dictionary into readable prose."""

        if preview_analysis.get("sceneMode") == "bar_wall_scene":
            shader_style = preview_analysis.get(
                "shaderStyle",
                self._bar_wall_shader_style_variable.get(),
            )
            return (
                "Bar wall summary: "
                f"{preview_analysis.get('barCount', 0)} bars from "
                f"{preview_analysis.get('sourceValueCount', 0)} source values, "
                f"range {float(preview_analysis.get('activeRangeMinimum', 0.0)):.2f} .. "
                f"{float(preview_analysis.get('activeRangeMaximum', 0.0)):.2f}, "
                f"shader {shader_style}."
            )

        return (
            "Preset scene summary: "
            f"scene type {preview_analysis.get('sceneType', 'unknown')}, "
            f"primitive {preview_analysis.get('primitive', 'unknown')}, "
            f"{preview_analysis.get('vertexCount', 0)} vertices, "
            f"{preview_analysis.get('indexCount', 0)} indices."
        )

    def _run_health_check(self) -> None:
        """Run one health check against the renderer API."""

        try:
            self._controller.replace_request_payload(self._build_request_payload_from_user_interface())
            response = self._controller.health()
        except Exception as error:
            self._health_status_variable.set(f"Health check failed: {error}")
            return

        self._health_status_variable.set(f"Health: {response.status} {response.reason}")

    def _validate_current_scene(self) -> None:
        """Validate the current preview scene without applying it."""

        try:
            self._controller.replace_request_payload(self._build_request_payload_from_user_interface())
            validation_result = self._controller.validate_current_scene()
        except Exception as error:
            self._result_status_variable.set(f"Validation failed: {error}")
            return

        response = validation_result["response"]
        self._result_status_variable.set(f"Validation: {response.status} {response.reason}")

    def _apply_current_scene(self) -> None:
        """Apply the current scene once."""

        try:
            self._controller.replace_request_payload(self._build_request_payload_from_user_interface())
            apply_result = self._controller.apply_current_scene()
        except Exception as error:
            self._result_status_variable.set(f"Apply failed: {error}")
            return

        response = apply_result["response"]
        self._result_status_variable.set(f"Apply: {response.status} {response.reason}")

    def _start_live_stream(self) -> None:
        """Start the controller's background live-stream worker."""

        try:
            self._controller.replace_request_payload(self._build_request_payload_from_user_interface())
            self._controller.start_live_stream()
        except Exception as error:
            self._live_status_variable.set(f"Live stream failed to start: {error}")
            return

        self._live_status_variable.set("Live stream running.")

    def _stop_live_stream(self) -> None:
        """Stop the controller's background live-stream worker."""

        self._controller.stop_live_stream()
        self._live_status_variable.set("Live stream stopped.")

    def _reset_to_defaults(self) -> None:
        """Restore the default request payload and redraw the UI."""

        normalized_request_payload = self._controller.reset_to_defaults()
        self._sync_user_interface_from_request_payload(normalized_request_payload)
        self._refresh_audio_devices()
        self._schedule_preview_refresh(immediate=True)

    def _save_settings_file(self) -> None:
        """Save the current Visualizer Studio settings to disk."""

        self._controller.replace_request_payload(self._build_request_payload_from_user_interface())
        if self._settings_file_path is None:
            selected_file_path = filedialog.asksaveasfilename(
                title="Save Visualizer Studio settings",
                initialfile=DEFAULT_SETTINGS_FILE_NAME,
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            )
            if not selected_file_path:
                return
            self._settings_file_path = Path(selected_file_path)

        settings_document = self._controller.settings_document()
        self._settings_file_path.write_text(
            json.dumps(settings_document, indent=2),
            encoding="utf-8",
        )
        self._result_status_variable.set(f"Saved settings to {self._settings_file_path.name}.")

    def _load_settings_file(self) -> None:
        """Load Visualizer Studio settings from disk."""

        selected_file_path = filedialog.askopenfilename(
            title="Load Visualizer Studio settings",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not selected_file_path:
            return

        try:
            settings_document = json.loads(Path(selected_file_path).read_text(encoding="utf-8"))
            normalized_request_payload = self._controller.load_settings_document(settings_document)
        except Exception as error:
            messagebox.showerror("Load settings", str(error))
            return

        self._settings_file_path = Path(selected_file_path)
        self._sync_user_interface_from_request_payload(normalized_request_payload)
        self._refresh_audio_devices()
        self._schedule_preview_refresh(immediate=True)

    def _open_preview_window(self) -> None:
        """Open the detached JSON preview window if it is not already visible."""

        if self._preview_window is not None and self._preview_window.winfo_exists():
            self._preview_window.deiconify()
            self._preview_window.lift()
            self._refresh_preview_window_contents()
            return

        self._preview_window = tk.Toplevel(self._root_window)
        self._preview_window.title("Current scene JSON")
        self._preview_window.geometry("900x720")
        self._preview_window.columnconfigure(0, weight=1)
        self._preview_window.rowconfigure(1, weight=1)

        button_row = ttkb.Frame(self._preview_window, padding=12)
        button_row.grid(row=0, column=0, sticky="ew")
        ttkb.Button(
            button_row,
            text="Copy JSON",
            bootstyle="secondary",
            command=self._copy_preview_json,
        ).pack(side="left")

        self._preview_text_widget = ScrolledText(
            self._preview_window,
            wrap="word",
            font=("Consolas", 10),
        )
        self._preview_text_widget.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._preview_text_widget.configure(state="disabled")
        self._refresh_preview_window_contents()

    def _copy_preview_json(self) -> None:
        """Copy the current preview JSON to the clipboard."""

        if not self._latest_preview_bundle:
            return

        preview_json_text = json.dumps(self._latest_preview_bundle.scene, indent=2)
        self._root_window.clipboard_clear()
        self._root_window.clipboard_append(preview_json_text)
        self._result_status_variable.set("Copied preview JSON to the clipboard.")

    def _refresh_preview_window_contents(self) -> None:
        """Refresh the detached preview window if it is open."""

        if (
            self._preview_window is None
            or not self._preview_window.winfo_exists()
            or self._preview_text_widget is None
        ):
            return

        preview_json_text = json.dumps(
            self._latest_preview_bundle.scene if self._latest_preview_bundle else {},
            indent=2,
        )
        self._preview_text_widget.configure(state="normal")
        self._preview_text_widget.delete("1.0", "end")
        self._preview_text_widget.insert("1.0", preview_json_text)
        self._preview_text_widget.configure(state="disabled")

    def _schedule_status_refresh(self) -> None:
        """Schedule recurring status polling from the controller."""

        self._refresh_status_labels()
        self._root_window.after(300, self._schedule_status_refresh)

    def _refresh_status_labels(self) -> None:
        """Pull audio and live-stream status from the controller."""

        audio_snapshot = self._controller.audio_snapshot()
        live_stream_snapshot = self._controller.live_stream_snapshot()
        self._audio_status_variable.set(
            audio_snapshot.last_error
            or (
                f"Capturing {audio_snapshot.device_name or 'No device selected'} "
                f"({self._audio_device_flow_variable.get()})"
                if audio_snapshot.capturing
                else "Audio capture not started."
            )
        )
        self._volume_meter_progress_variable.set(audio_snapshot.level * 100.0)
        self._volume_meter_text_variable.set(f"{audio_snapshot.level * 100.0:.0f}%")
        self._live_status_variable.set(
            f"{live_stream_snapshot['status']} | "
            f"attempted {live_stream_snapshot['frames_attempted']} | "
            f"applied {live_stream_snapshot['frames_applied']} | "
            f"failed {live_stream_snapshot['frames_failed']}"
        )

        # Audio- and pointer-driven previews change even when the user is not
        # typing. Rebuilding the preview here keeps the analysis panel current.
        if self._source_mode_variable.get() in {"audio_device", "pointer_pad"}:
            self._schedule_preview_refresh()

    def _on_close_requested(self) -> None:
        """Close child windows and release controller resources."""

        if self._pending_preview_refresh_after_identifier is not None:
            try:
                self._root_window.after_cancel(self._pending_preview_refresh_after_identifier)
            except tk.TclError:
                pass
            self._pending_preview_refresh_after_identifier = None
        if self._preview_window is not None and self._preview_window.winfo_exists():
            self._preview_window.destroy()
        self._controller.close()
        self._root_window.destroy()


def main() -> None:
    """Run the unified Visualizer Studio as a desktop application."""

    root_window = ttkb.Window(themename="superhero")
    VisualizerOperatorConsoleWindow(root_window)
    root_window.mainloop()
