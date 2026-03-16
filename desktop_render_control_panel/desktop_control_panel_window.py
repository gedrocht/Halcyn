"""Tkinter window for the native Halcyn desktop render control panel.

Helpful library references:

- Tkinter overview: https://docs.python.org/3/library/tkinter.html
- `ttk` widgets: https://docs.python.org/3/library/tkinter.ttk.html
- `ScrolledText`: https://docs.python.org/3/library/tkinter.scrolledtext.html
- `colorchooser`: https://docs.python.org/3/library/tkinter.colorchooser.html
- `filedialog`: https://docs.python.org/3/library/dialog.html#tkinter.filedialog
"""

from __future__ import annotations

import json
import math
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from desktop_render_control_panel.desktop_control_panel_controller import (
    DesktopRenderControlPanelController,
)
from desktop_render_control_panel.desktop_control_scene_builder import DEFAULT_DESKTOP_PRESET_ID

WINDOW_BACKGROUND = "#071018"
SURFACE_BACKGROUND = "#101b2a"
SURFACE_BORDER = "#21364d"
TEXT_PRIMARY = "#edf4ff"
TEXT_SECONDARY = "#9eb3c9"
ACCENT_COLOR = "#5fd1ff"
ACCENT_COLOR_ACTIVE = "#89e0ff"
ACCENT_FOREGROUND = "#04131d"
ENTRY_BACKGROUND = "#162537"
POINTER_PAD_BACKGROUND = "#09121c"
POINTER_PAD_GRID = "#284058"
POINTER_PAD_MARKER = "#ffd166"
COLOR_SWATCH_BORDER = "#6b7f94"
VOLUME_METER_COLOR = ACCENT_COLOR
SELECTION_BUTTON_BACKGROUND = "#172537"
SELECTION_BUTTON_FOREGROUND = TEXT_PRIMARY
SELECTION_BUTTON_BORDER = "#2d435c"
SELECTION_BUTTON_SELECTED_BACKGROUND = ACCENT_COLOR
SELECTION_BUTTON_SELECTED_FOREGROUND = ACCENT_FOREGROUND
DEFAULT_SETTINGS_FILE_NAME = "halcyn-desktop-control-panel-settings.json"


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
        self._preset_identifiers_by_scene_type = {
            "2d": [
                preset["id"]
                for preset in self._catalog["presets"]
                if preset["sceneType"] == "2d"
            ],
            "3d": [
                preset["id"]
                for preset in self._catalog["presets"]
                if preset["sceneType"] == "3d"
            ],
        }
        self._preset_names_by_identifier = {
            preset["id"]: preset["name"] for preset in self._catalog["presets"]
        }
        self._pending_sync_after_identifier: str | None = None
        self._suppress_variable_sync = False
        self._last_pointer_x = 0.5
        self._last_pointer_y = 0.5
        self._pointer_crosshair_item_identifier: int | None = None
        self._pointer_marker_item_identifier: int | None = None
        self._settings_file_path: Path | None = None
        self._preview_window: tk.Toplevel | None = None
        self._preview_text_widget: ScrolledText | None = None
        self._live_cadence_value_label: ttk.Label | None = None
        self._latest_preview_json_text = ""
        self._audio_device_flow_button_widgets: dict[str, tk.Button] = {}
        self._volume_meter_progress_variable = tk.DoubleVar(value=0.0)
        self._volume_meter_text_variable = tk.StringVar(value="0%")
        self._scene_type_button_widgets: dict[str, tk.Button] = {}
        self._build_variables()
        self._slider_display_variables = self._build_slider_display_variables()
        self._color_swatch_frames: dict[str, tk.Frame] = {}
        self._preset_button_widgets: dict[str, tk.Button] = {}
        self._build_user_interface()
        self._load_initial_state()
        self._root.protocol("WM_DELETE_WINDOW", self._on_close_requested)
        self._schedule_status_refresh()

    def _build_variables(self) -> None:
        """Create the Tkinter variables that keep the UI and controller in sync."""

        self._scene_type_variable = tk.StringVar(value="2d")
        self._preset_identifier_variable = tk.StringVar(value="")
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
        self._audio_device_flow_variable = tk.StringVar(value="output")
        self._audio_device_variable = tk.StringVar(value="")
        self._pointer_status_variable = tk.StringVar(value="Pointer pad idle")
        self._health_status_variable = tk.StringVar(value="Health check not run yet.")
        self._live_status_variable = tk.StringVar(value="Live stream stopped.")
        self._audio_status_variable = tk.StringVar(value="Audio capture not started.")
        self._result_status_variable = tk.StringVar(value="Ready.")

    def _build_slider_display_variables(self) -> dict[str, tk.StringVar]:
        """Create formatted label variables for the numeric slider values."""

        return {
            "cadence": tk.StringVar(value="125 ms"),
            "density": tk.StringVar(value="96"),
            "pointSize": tk.StringVar(value="6.0"),
            "lineWidth": tk.StringVar(value="2.0"),
            "speed": tk.StringVar(value="1.00"),
            "gain": tk.StringVar(value="1.00"),
            "manualDrive": tk.StringVar(value="0.35"),
        }

    def _build_user_interface(self) -> None:
        """Create the three major page columns and their child sections."""

        self._root.title("Halcyn Desktop Render Control Panel")
        self._root.geometry("1440x840")
        self._root.minsize(1180, 700)
        self._configure_dark_theme()

        page_shell = ttk.Frame(self._root, padding=16, style="Surface.TFrame")
        page_shell.grid(sticky="nsew")
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)

        page_shell.columnconfigure(0, weight=1)
        page_shell.columnconfigure(1, weight=2)
        page_shell.columnconfigure(2, weight=2)
        page_shell.rowconfigure(2, weight=1)

        heading = ttk.Label(
            page_shell,
            text="Desktop Render Control Panel",
            style="Heading.TLabel",
        )
        heading.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        subtitle = ttk.Label(
            page_shell,
            text=(
                "Native live scene control with presets, local audio routing, "
                "instant 2D/3D switching, and renderer-aware diagnostics."
            ),
            style="Subheading.TLabel",
        )
        subtitle.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 16))

        self._connection_frame = ttk.LabelFrame(
            page_shell,
            text="Renderer Connection",
            padding=12,
            style="Panel.TLabelframe",
        )
        self._connection_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 12))

        self._scene_frame = ttk.LabelFrame(
            page_shell,
            text="Scene Controls",
            padding=12,
            style="Panel.TLabelframe",
        )
        self._scene_frame.grid(row=2, column=1, sticky="nsew", padx=(0, 12))

        self._output_frame = ttk.LabelFrame(
            page_shell,
            text="Preview, Status, and Diagnostics",
            padding=12,
            style="Panel.TLabelframe",
        )
        self._output_frame.grid(row=2, column=2, sticky="nsew")
        self._output_frame.columnconfigure(0, weight=1)
        self._output_frame.rowconfigure(3, weight=1)

        self._build_connection_section()
        self._build_scene_section()
        self._build_output_section()

    def _configure_dark_theme(self) -> None:
        """Apply a consistent dark theme so the desktop app matches the rest of the project."""

        style = ttk.Style(self._root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self._root.configure(background=WINDOW_BACKGROUND)
        style.configure(".", background=WINDOW_BACKGROUND, foreground=TEXT_PRIMARY)
        style.configure("TFrame", background=WINDOW_BACKGROUND)
        style.configure("Surface.TFrame", background=WINDOW_BACKGROUND)
        style.configure("TLabel", background=WINDOW_BACKGROUND, foreground=TEXT_PRIMARY)
        style.configure(
            "Heading.TLabel",
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
            "Panel.TLabelframe",
            background=SURFACE_BACKGROUND,
            foreground=TEXT_PRIMARY,
            bordercolor=SURFACE_BORDER,
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "Panel.TLabelframe.Label",
            background=SURFACE_BACKGROUND,
            foreground=TEXT_PRIMARY,
            font=("Segoe UI Semibold", 11),
        )
        style.configure(
            "PanelInner.TFrame",
            background=SURFACE_BACKGROUND,
        )
        style.configure(
            "TButton",
            background=ENTRY_BACKGROUND,
            foreground=TEXT_PRIMARY,
            bordercolor=SURFACE_BORDER,
            focusthickness=1,
            focuscolor=ACCENT_COLOR,
            padding=(10, 8),
        )
        style.map(
            "TButton",
            background=[("active", SURFACE_BORDER)],
            foreground=[("disabled", TEXT_SECONDARY)],
        )
        style.configure(
            "Accent.TButton",
            background=ACCENT_COLOR,
            foreground=ACCENT_FOREGROUND,
            bordercolor=ACCENT_COLOR,
            padding=(10, 8),
        )
        style.map(
            "Accent.TButton",
            background=[("active", ACCENT_COLOR_ACTIVE)],
        )
        style.configure(
            "TEntry",
            fieldbackground=ENTRY_BACKGROUND,
            foreground=TEXT_PRIMARY,
            insertcolor=TEXT_PRIMARY,
            bordercolor=SURFACE_BORDER,
        )
        style.configure(
            "TCombobox",
            fieldbackground=ENTRY_BACKGROUND,
            foreground=TEXT_PRIMARY,
            arrowcolor=TEXT_PRIMARY,
            bordercolor=SURFACE_BORDER,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", ENTRY_BACKGROUND)],
            foreground=[("readonly", TEXT_PRIMARY)],
        )
        style.configure(
            "TLabelframe",
            background=SURFACE_BACKGROUND,
            foreground=TEXT_PRIMARY,
            bordercolor=SURFACE_BORDER,
        )
        style.configure("TLabelframe.Label", background=SURFACE_BACKGROUND, foreground=TEXT_PRIMARY)
        style.configure("TCheckbutton", background=SURFACE_BACKGROUND, foreground=TEXT_PRIMARY)
        self._configure_audio_meter_styles(style)

    def _configure_audio_meter_styles(self, style: ttk.Style) -> None:
        """Style the single visible volume meter so it stays readable on the dark theme."""

        style.configure(
            "AudioVolume.Horizontal.TProgressbar",
            troughcolor=ENTRY_BACKGROUND,
            background=VOLUME_METER_COLOR,
            lightcolor=VOLUME_METER_COLOR,
            darkcolor=VOLUME_METER_COLOR,
            bordercolor=SURFACE_BORDER,
            thickness=10,
        )

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
        self._build_slider(
            section_frame,
            row=2,
            variable=self._cadence_variable,
            display_variable=self._slider_display_variables["cadence"],
            minimum=40,
            maximum=1000,
            resolution=1.0,
            digits_after_decimal=0,
            suffix=" ms",
        )
        self._live_cadence_value_label = ttk.Label(
            section_frame,
            textvariable=self._slider_display_variables["cadence"],
        )
        self._live_cadence_value_label.grid(row=3, column=1, sticky="e", pady=(0, 4))

        ttk.Button(
            section_frame,
            text="Check health",
            command=self._run_health_check,
            style="Accent.TButton",
        ).grid(
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
        """Create the scene-shaping widgets that operators adjust most often."""

        section_frame = self._scene_frame
        for column_index in range(2):
            section_frame.columnconfigure(column_index, weight=1 if column_index == 1 else 0)

        ttk.Label(
            section_frame,
            text="Scene type",
            style="Subheading.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        self._scene_type_button_frame = tk.Frame(
            section_frame,
            background=SURFACE_BACKGROUND,
            highlightthickness=0,
        )
        self._scene_type_button_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 10))
        self._scene_type_button_frame.columnconfigure((0, 1), weight=1)
        self._scene_type_button_widgets["2d"] = self._build_segmented_button(
            parent=self._scene_type_button_frame,
            text="2D",
            value="2d",
            column=0,
            command=self._on_scene_type_button_pressed,
        )
        self._scene_type_button_widgets["3d"] = self._build_segmented_button(
            parent=self._scene_type_button_frame,
            text="3D",
            value="3d",
            column=1,
            command=self._on_scene_type_button_pressed,
        )

        ttk.Label(
            section_frame,
            text="Preset",
            style="Subheading.TLabel",
        ).grid(row=2, column=0, columnspan=2, sticky="w")
        self._preset_button_frame = tk.Frame(
            section_frame,
            background=SURFACE_BACKGROUND,
            highlightthickness=0,
        )
        self._preset_button_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 12))
        self._preset_button_frame.columnconfigure((0, 1), weight=1)

        scene_actions_frame = ttk.Frame(section_frame, style="PanelInner.TFrame")
        scene_actions_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        scene_actions_frame.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(
            scene_actions_frame,
            text="Revert to default",
            command=self._revert_current_preset_to_default_settings,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(
            scene_actions_frame,
            text="Load settings",
            command=self._load_settings_from_file,
        ).grid(row=0, column=1, sticky="ew", padx=3)
        ttk.Button(
            scene_actions_frame,
            text="Save settings",
            command=self._save_settings_to_file,
        ).grid(row=0, column=2, sticky="ew", padx=(6, 0))

        slider_row = 5
        slider_row = self._add_slider(
            section_frame,
            slider_row,
            "Density",
            self._density_variable,
            self._slider_display_variables["density"],
            24,
            320,
            1.0,
            0,
        )
        slider_row = self._add_slider(
            section_frame,
            slider_row,
            "Point size",
            self._point_size_variable,
            self._slider_display_variables["pointSize"],
            1.0,
            24.0,
            0.5,
            1,
        )
        slider_row = self._add_slider(
            section_frame,
            slider_row,
            "Line width",
            self._line_width_variable,
            self._slider_display_variables["lineWidth"],
            1.0,
            8.0,
            0.25,
            2,
        )
        slider_row = self._add_slider(
            section_frame,
            slider_row,
            "Speed",
            self._speed_variable,
            self._slider_display_variables["speed"],
            0.1,
            4.0,
            0.05,
            2,
        )
        slider_row = self._add_slider(
            section_frame,
            slider_row,
            "Gain",
            self._gain_variable,
            self._slider_display_variables["gain"],
            0.1,
            3.0,
            0.05,
            2,
        )
        slider_row = self._add_slider(
            section_frame,
            slider_row,
            "Manual drive",
            self._manual_drive_variable,
            self._slider_display_variables["manualDrive"],
            0.0,
            2.0,
            0.05,
            2,
        )

        ttk.Label(section_frame, text="Background", style="Subheading.TLabel").grid(
            row=slider_row,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        self._build_color_row(section_frame, slider_row, self._background_variable)
        slider_row += 1
        ttk.Label(section_frame, text="Primary color", style="Subheading.TLabel").grid(
            row=slider_row,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        self._build_color_row(section_frame, slider_row, self._primary_color_variable)
        slider_row += 1
        ttk.Label(section_frame, text="Secondary color", style="Subheading.TLabel").grid(
            row=slider_row,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        self._build_color_row(section_frame, slider_row, self._secondary_color_variable)
        slider_row += 1

        signals_frame = ttk.LabelFrame(
            section_frame,
            text="Signal sources",
            padding=10,
            style="Panel.TLabelframe",
        )
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

        self._watch_control_variables()
        self._rebuild_preset_button_group()
        self._refresh_scene_type_button_styles()

    def _build_output_section(self) -> None:
        """Create preview actions plus the heavier diagnostic widgets.

        The right-most column has more vertical breathing room, so it is a
        better home for the audio controls and pointer pad than the already
        crowded scene-control column.
        """

        section_frame = self._output_frame
        section_frame.rowconfigure(3, weight=1)
        section_frame.columnconfigure(0, weight=1)

        action_frame = ttk.Frame(section_frame, style="PanelInner.TFrame")
        action_frame.grid(
            row=0,
            column=0,
            sticky="ew",
        )
        action_frame.columnconfigure(0, weight=1)
        action_frame.columnconfigure(1, weight=1)
        ttk.Button(
            action_frame,
            text="Refresh preview",
            command=self._refresh_preview,
            style="Accent.TButton",
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 6),
        )
        self._preview_toggle_button = ttk.Button(
            action_frame,
            text="Open current scene JSON",
            command=self._open_preview_window,
        )
        self._preview_toggle_button.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(6, 0),
        )

        self._analysis_label = ttk.Label(
            section_frame,
            text="No preview generated yet.",
            wraplength=520,
            justify="left",
        )
        self._analysis_label.grid(row=1, column=0, sticky="w", pady=(10, 10))

        self._build_audio_input_section(section_frame, row=2)
        self._build_pointer_pad_section(section_frame, row=3)

    def _build_audio_input_section(self, parent: ttk.LabelFrame, *, row: int) -> None:
        """Create the audio-capture controls in the roomier diagnostics column."""

        audio_frame = ttk.LabelFrame(
            parent,
            text="Audio sources",
            padding=10,
            style="Panel.TLabelframe",
        )
        audio_frame.grid(row=row, column=0, sticky="ew", pady=(12, 0))
        audio_frame.columnconfigure(1, weight=1)
        ttk.Label(audio_frame, text="Source type", style="Subheading.TLabel").grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
        )
        audio_source_type_frame = tk.Frame(
            audio_frame,
            background=SURFACE_BACKGROUND,
            highlightthickness=0,
        )
        audio_source_type_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 10))
        audio_source_type_frame.columnconfigure((0, 1), weight=1)
        self._audio_device_flow_button_widgets["output"] = self._build_segmented_button(
            parent=audio_source_type_frame,
            text="Output sources",
            value="output",
            column=0,
            command=self._on_audio_device_flow_button_pressed,
        )
        self._audio_device_flow_button_widgets["input"] = self._build_segmented_button(
            parent=audio_source_type_frame,
            text="Input sources",
            value="input",
            column=1,
            command=self._on_audio_device_flow_button_pressed,
        )

        ttk.Label(audio_frame, text="Device").grid(row=2, column=0, sticky="w")
        self._audio_device_combobox = ttk.Combobox(
            audio_frame,
            textvariable=self._audio_device_variable,
            state="readonly",
        )
        self._audio_device_combobox.grid(row=2, column=1, sticky="ew", padx=(6, 0))
        ttk.Button(audio_frame, text="Refresh", command=self._refresh_audio_devices).grid(
            row=3,
            column=0,
            sticky="ew",
            pady=(8, 0),
        )
        ttk.Button(audio_frame, text="Start capture", command=self._start_audio_capture).grid(
            row=3,
            column=1,
            sticky="ew",
            padx=(6, 0),
            pady=(8, 0),
        )
        ttk.Button(audio_frame, text="Stop capture", command=self._stop_audio_capture).grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(8, 0),
        )
        ttk.Label(audio_frame, textvariable=self._audio_status_variable, wraplength=520).grid(
            row=5,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Label(audio_frame, text="Audio monitor", style="Subheading.TLabel").grid(
            row=6,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(10, 0),
        )
        audio_frame.columnconfigure(1, weight=1)
        audio_frame.columnconfigure(2, weight=0)
        self._build_volume_meter_row(audio_frame, row=7)

    def _build_pointer_pad_section(self, parent: ttk.LabelFrame, *, row: int) -> None:
        """Create the pointer pad in the column that can spare the vertical room."""

        pointer_frame = ttk.LabelFrame(
            parent,
            text="Pointer pad",
            padding=10,
            style="Panel.TLabelframe",
        )
        pointer_frame.grid(row=row, column=0, sticky="nsew", pady=(12, 0))
        pointer_frame.columnconfigure(0, weight=1)
        pointer_frame.rowconfigure(0, weight=1)
        self._pointer_canvas = tk.Canvas(
            pointer_frame,
            width=420,
            height=230,
            background=POINTER_PAD_BACKGROUND,
            highlightthickness=1,
            highlightbackground=POINTER_PAD_GRID,
            relief="flat",
            borderwidth=0,
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
        self._draw_pointer_pad_background()

    def _build_volume_meter_row(
        self,
        parent: ttk.LabelFrame,
        *,
        row: int,
    ) -> None:
        """Create the single visible volume meter used for capture confidence."""

        ttk.Label(parent, text="Volume").grid(row=row, column=0, sticky="w", pady=(6, 0))
        ttk.Progressbar(
            parent,
            variable=self._volume_meter_progress_variable,
            maximum=100.0,
            style="AudioVolume.Horizontal.TProgressbar",
        ).grid(row=row, column=1, sticky="ew", padx=(8, 8), pady=(6, 0))
        ttk.Label(parent, textvariable=self._volume_meter_text_variable).grid(
            row=row,
            column=2,
            sticky="e",
            pady=(6, 0),
        )

    def _add_slider(
        self,
        parent: Any,
        row: int,
        label_text: str,
        variable: tk.IntVar | tk.DoubleVar,
        display_variable: tk.StringVar,
        minimum: float,
        maximum: float,
        resolution: float,
        digits_after_decimal: int,
    ) -> int:
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky="w")
        self._build_slider(
            parent,
            row=row,
            variable=variable,
            display_variable=display_variable,
            minimum=minimum,
            maximum=maximum,
            resolution=resolution,
            digits_after_decimal=digits_after_decimal,
        )
        ttk.Label(parent, textvariable=display_variable).grid(
            row=row + 1,
            column=1,
            sticky="e",
            pady=(0, 4),
        )
        return row + 2

    def _build_slider(
        self,
        parent: Any,
        *,
        row: int,
        variable: tk.IntVar | tk.DoubleVar,
        display_variable: tk.StringVar,
        minimum: float,
        maximum: float,
        resolution: float,
        digits_after_decimal: int,
        suffix: str = "",
    ) -> None:
        """Create one quantized dark-themed slider plus its display value."""

        scale = tk.Scale(
            parent,
            from_=minimum,
            to=maximum,
            orient="horizontal",
            resolution=resolution,
            showvalue=False,
            variable=variable,
            background=SURFACE_BACKGROUND,
            foreground=TEXT_SECONDARY,
            troughcolor=ENTRY_BACKGROUND,
            activebackground=ACCENT_COLOR_ACTIVE,
            highlightthickness=0,
            bd=0,
            relief="flat",
            command=lambda _: self._on_slider_value_changed(
                variable,
                display_variable,
                resolution,
                digits_after_decimal,
                suffix,
            ),
        )
        scale.grid(row=row, column=1, sticky="ew")
        self._on_slider_value_changed(
            variable,
            display_variable,
            resolution,
            digits_after_decimal,
            suffix,
        )

    def _build_color_row(self, parent: Any, row: int, variable: tk.StringVar) -> None:
        color_frame = ttk.Frame(parent)
        color_frame.grid(row=row, column=1, sticky="ew", pady=(8, 0))
        color_frame.columnconfigure(0, weight=1)
        ttk.Entry(color_frame, textvariable=variable).grid(row=0, column=0, sticky="ew")
        swatch_frame = tk.Frame(
            color_frame,
            width=26,
            height=26,
            background=variable.get(),
            highlightthickness=1,
            highlightbackground=COLOR_SWATCH_BORDER,
            highlightcolor=COLOR_SWATCH_BORDER,
        )
        swatch_frame.grid(row=0, column=1, padx=(8, 0))
        swatch_frame.grid_propagate(False)
        self._color_swatch_frames[str(variable)] = swatch_frame

        def choose_bound_color() -> None:
            self._choose_color(variable)

        ttk.Button(
            color_frame,
            text="Choose",
            command=choose_bound_color,
        ).grid(row=0, column=2, padx=(8, 0))

    def _build_segmented_button(
        self,
        *,
        parent: tk.Misc,
        text: str,
        value: str,
        column: int,
        command: Any,
    ) -> tk.Button:
        """Create one button-like radio control for scene type or preset selection."""

        def choose_bound_value() -> None:
            command(value)

        button = tk.Button(
            parent,
            text=text,
            command=choose_bound_value,
            background=SELECTION_BUTTON_BACKGROUND,
            foreground=SELECTION_BUTTON_FOREGROUND,
            activebackground=ACCENT_COLOR_ACTIVE,
            activeforeground=ACCENT_FOREGROUND,
            disabledforeground=TEXT_SECONDARY,
            highlightthickness=1,
            highlightbackground=SELECTION_BUTTON_BORDER,
            highlightcolor=SELECTION_BUTTON_BORDER,
            bd=0,
            relief="flat",
            padx=12,
            pady=9,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
        )
        button.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0))
        return button

    def _rebuild_preset_button_group(self) -> None:
        """Recreate the preset toggle buttons for the current 2D or 3D mode."""

        for button in self._preset_button_widgets.values():
            button.destroy()
        self._preset_button_widgets = {}

        preset_identifiers = self._preset_identifiers_by_scene_type.get(
            self._scene_type_variable.get().strip().lower(),
            [],
        )
        for preset_button_index, preset_identifier in enumerate(preset_identifiers):
            row_index = preset_button_index // 2
            column_index = preset_button_index % 2
            self._preset_button_frame.rowconfigure(row_index, weight=0)

            def choose_bound_preset(
                selected_preset_identifier: str = preset_identifier,
            ) -> None:
                self._on_preset_button_pressed(selected_preset_identifier)

            button = tk.Button(
                self._preset_button_frame,
                text=self._preset_names_by_identifier[preset_identifier],
                command=choose_bound_preset,
                background=SELECTION_BUTTON_BACKGROUND,
                foreground=SELECTION_BUTTON_FOREGROUND,
                activebackground=ACCENT_COLOR_ACTIVE,
                activeforeground=ACCENT_FOREGROUND,
                disabledforeground=TEXT_SECONDARY,
                highlightthickness=1,
                highlightbackground=SELECTION_BUTTON_BORDER,
                highlightcolor=SELECTION_BUTTON_BORDER,
                bd=0,
                relief="flat",
                anchor="w",
                justify="left",
                wraplength=170,
                padx=12,
                pady=9,
                font=("Segoe UI", 10),
                cursor="hand2",
            )
            button.grid(
                row=row_index,
                column=column_index,
                sticky="ew",
                padx=(0, 6) if column_index == 0 else (6, 0),
                pady=(0, 6),
            )
            self._preset_button_widgets[preset_identifier] = button
        self._refresh_preset_button_styles()

    def _draw_pointer_pad_background(self) -> None:
        """Render a simple guidance grid so the larger pointer pad feels intentional."""

        self._pointer_canvas.delete("all")
        canvas_width = int(self._pointer_canvas["width"])
        canvas_height = int(self._pointer_canvas["height"])
        for column_index in range(1, 4):
            x_position = canvas_width * column_index / 4
            self._pointer_canvas.create_line(
                x_position,
                0,
                x_position,
                canvas_height,
                fill=POINTER_PAD_GRID,
                dash=(2, 6),
            )
        for row_index in range(1, 4):
            y_position = canvas_height * row_index / 4
            self._pointer_canvas.create_line(
                0,
                y_position,
                canvas_width,
                y_position,
                fill=POINTER_PAD_GRID,
                dash=(2, 6),
            )
        self._pointer_crosshair_item_identifier = self._pointer_canvas.create_line(
            canvas_width * 0.5,
            0,
            canvas_width * 0.5,
            canvas_height,
            fill=ACCENT_COLOR,
            width=1,
        )
        self._pointer_marker_item_identifier = self._pointer_canvas.create_oval(
            canvas_width * 0.5 - 8,
            canvas_height * 0.5 - 8,
            canvas_width * 0.5 + 8,
            canvas_height * 0.5 + 8,
            fill=POINTER_PAD_MARKER,
            outline="",
        )

    def _on_slider_value_changed(
        self,
        variable: tk.IntVar | tk.DoubleVar,
        display_variable: tk.StringVar,
        resolution: float,
        digits_after_decimal: int,
        suffix: str = "",
    ) -> None:
        """Quantize slider values and keep the visible label human-friendly."""

        quantized_value = self._round_to_increment(float(variable.get()), resolution)
        if isinstance(variable, tk.IntVar):
            variable.set(int(round(quantized_value)))
            display_variable.set(f"{int(round(quantized_value))}{suffix}")
        else:
            variable.set(quantized_value)
            display_variable.set(f"{quantized_value:.{digits_after_decimal}f}{suffix}")
        self._schedule_payload_sync()

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

        for color_variable in [
            self._background_variable,
            self._primary_color_variable,
            self._secondary_color_variable,
        ]:
            color_variable.trace_add(
                "write",
                lambda *_,
                watched_color_variable=color_variable: self._refresh_color_swatch(
                    watched_color_variable
                ),
            )

    def _load_initial_state(self) -> None:
        """Populate the window from the controller's current payload."""

        default_payload = self._controller.current_request_payload()
        default_preset_identifier = str(default_payload["presetId"])
        default_scene_type = str(
            self._preset_entries_by_identifier[default_preset_identifier]["sceneType"]
        )
        self._scene_type_variable.set(default_scene_type)
        self._rebuild_preset_button_group()
        self._preset_identifier_variable.set(default_preset_identifier)
        self._refresh_audio_device_flow_button_styles()
        self._refresh_scene_type_button_styles()
        self._refresh_preset_button_styles()
        self._set_user_interface_from_request_payload(default_payload)
        self._refresh_audio_devices()
        self._refresh_preview()

    def _set_user_interface_from_request_payload(self, payload: dict[str, Any]) -> None:
        """Copy a normalized request payload into the visible widgets.

        The suppression flag matters because setting Tk variables would normally
        trigger the "sync back into the controller" traces immediately.
        """

        self._suppress_variable_sync = True
        try:
            preset_identifier = str(payload.get("presetId", DEFAULT_DESKTOP_PRESET_ID))
            preset_entry = self._preset_entries_by_identifier.get(
                preset_identifier,
                self._preset_entries_by_identifier[DEFAULT_DESKTOP_PRESET_ID],
            )
            target = payload.get("target", {})
            settings = payload.get("settings", {})
            signals = payload.get("signals", {})
            audio = signals.get("audio", {})
            session = payload.get("session", {})

            self._scene_type_variable.set(str(preset_entry.get("sceneType", "2d")))
            self._rebuild_preset_button_group()
            self._preset_identifier_variable.set(preset_identifier)
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
                self._update_volume_meter_display(level=float(audio.get("level", 0.0)))
                self._audio_status_variable.set(
                    "Audio capture not started."
                    if not audio
                    else f"Audio source ready: volume {float(audio.get('level', 0.0)):.2f}"
                )
        finally:
            self._suppress_variable_sync = False
        self._refresh_scene_type_button_styles()
        self._refresh_preset_button_styles()
        self._refresh_all_slider_display_labels()
        self._refresh_all_color_swatches()

    def _collect_request_payload_from_user_interface(self) -> dict[str, Any]:
        """Build one full request payload from the current widget values."""

        selected_preset_identifier = self._preset_identifier_variable.get().strip()
        if selected_preset_identifier not in self._preset_entries_by_identifier:
            selected_preset_identifier = DEFAULT_DESKTOP_PRESET_ID
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
                "pointSize": self._round_to_increment(float(self._point_size_variable.get()), 0.5),
                "lineWidth": self._round_to_increment(float(self._line_width_variable.get()), 0.25),
                "speed": self._round_to_increment(float(self._speed_variable.get()), 0.05),
                "gain": self._round_to_increment(float(self._gain_variable.get()), 0.05),
                "manualDrive": self._round_to_increment(
                    float(self._manual_drive_variable.get()),
                    0.05,
                ),
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
        self._rebuild_preset_button_group()
        preset_identifiers = self._preset_identifiers_by_scene_type.get(
            self._scene_type_variable.get().strip().lower(),
            [],
        )
        if not preset_identifiers:
            return
        self._preset_identifier_variable.set(preset_identifiers[0])
        self._refresh_scene_type_button_styles()
        self._refresh_preset_button_styles()
        self._on_preset_changed()

    def _on_preset_changed(self, event: object | None = None) -> None:
        selected_preset_identifier = self._preset_identifier_variable.get().strip()
        if not selected_preset_identifier:
            return
        self._refresh_preset_button_styles()
        updated_payload = self._controller.load_preset(selected_preset_identifier)
        self._set_user_interface_from_request_payload(updated_payload)
        self._refresh_preview()

    def _on_scene_type_button_pressed(self, selected_scene_type: str) -> None:
        """Handle a direct press on one of the 2D/3D mode buttons."""

        self._scene_type_variable.set(selected_scene_type)
        self._on_scene_type_changed()

    def _on_preset_button_pressed(self, selected_preset_identifier: str) -> None:
        """Handle a direct press on one of the preset buttons."""

        self._preset_identifier_variable.set(selected_preset_identifier)
        self._on_preset_changed()

    def _on_audio_device_flow_button_pressed(self, selected_device_flow: str) -> None:
        """Switch between output-source and input-source device lists."""

        self._audio_device_flow_variable.set(selected_device_flow)
        self._refresh_audio_device_flow_button_styles()
        if self._controller.audio_snapshot().capturing:
            self._controller.stop_audio_capture()
        self._audio_device_variable.set("")
        self._refresh_audio_devices()

    def _choose_color(self, variable: tk.StringVar) -> None:
        chosen_color = colorchooser.askcolor(color=variable.get(), parent=self._root)[1]
        if chosen_color:
            variable.set(chosen_color)
            self._schedule_payload_sync()

    def _refresh_audio_devices(self) -> None:
        """Refresh the device dropdown from the audio service."""

        selected_device_flow = self._selected_audio_device_flow()
        devices = self._controller.refresh_audio_devices(selected_device_flow)
        device_names = [device.name for device in devices]
        self._audio_device_combobox["values"] = device_names
        if device_names and self._audio_device_variable.get().strip() not in device_names:
            self._audio_device_variable.set(device_names[0])
        elif not device_names:
            self._audio_device_variable.set("")
        audio_snapshot = self._controller.audio_snapshot()
        readable_source_label = (
            "output source" if selected_device_flow == "output" else "input source"
        )
        if device_names and audio_snapshot.last_error:
            self._audio_status_variable.set(
                f"Found {len(device_names)} {readable_source_label}(s). {audio_snapshot.last_error}"
            )
        elif device_names:
            self._audio_status_variable.set(
                f"Found {len(device_names)} {readable_source_label}(s). "
                "Choose one and start capture."
            )
        else:
            no_devices_message = (
                "No output audio sources detected. Install the optional soundcard package "
                "to capture desktop output audio, or switch to input sources to use microphones."
                if selected_device_flow == "output"
                else "No input audio sources detected. Connect or enable a microphone, or switch "
                "back to output sources."
            )
            if audio_snapshot.last_error:
                self._audio_status_variable.set(f"{no_devices_message} {audio_snapshot.last_error}")
            else:
                self._audio_status_variable.set(no_devices_message)

    def _start_audio_capture(self) -> None:
        """Start capture on the chosen device and surface readable UI errors."""

        device_name = self._audio_device_variable.get().strip()
        selected_device_flow = self._selected_audio_device_flow()
        readable_source_label = (
            "output source" if selected_device_flow == "output" else "input source"
        )
        if not device_name:
            messagebox.showinfo("Audio capture", f"Choose an {readable_source_label} first.")
            return
        device_identifier = next(
            (
                device.device_identifier
                for device in self._controller.audio_devices(selected_device_flow)
                if device.name == device_name
            ),
            "",
        )
        if not device_identifier:
            messagebox.showerror(
                "Audio capture",
                (
                    "The selected audio source is no longer available. "
                    "Refresh the device list and try again."
                ),
            )
            return
        try:
            self._controller.start_audio_capture(device_identifier, selected_device_flow)
        except Exception as error:
            messagebox.showerror("Audio capture", str(error))
            return
        # Starting capture is the strongest signal that the operator wants the
        # live scene to react to audio immediately, so the UI enables the audio
        # source flag for them and refreshes the preview right away.
        self._use_audio_variable.set(True)
        self._sync_payload_to_controller()
        self._audio_status_variable.set(f"Capturing from {device_name}.")
        self._refresh_status_labels()
        self._refresh_preview()

    def _stop_audio_capture(self) -> None:
        """Stop audio capture while leaving the last known analysis visible."""

        snapshot = self._controller.stop_audio_capture()
        if snapshot.last_error:
            self._audio_status_variable.set(snapshot.last_error)
        else:
            self._audio_status_variable.set("Audio capture stopped.")
        self._refresh_status_labels()
        self._refresh_preview()

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
        self._move_pointer_visual_marker(normalized_x, normalized_y)
        self._pointer_status_variable.set(
            f"Pointer x={normalized_x:.2f} y={normalized_y:.2f} "
            f"speed={normalized_pointer_speed:.2f}"
        )
        if self._controller.live_stream_snapshot()["status"] in {"running", "starting"}:
            self._refresh_preview()

    def _on_pointer_leave(self, event: tk.Event[tk.Misc]) -> None:
        """Reset pointer speed when the operator leaves the pointer pad."""

        self._controller.update_pointer_signal(self._last_pointer_x, self._last_pointer_y, 0.0)
        self._move_pointer_visual_marker(self._last_pointer_x, self._last_pointer_y)
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
        """Render both the summary label and the latest pretty-printed JSON scene."""

        analysis = preview_bundle["analysis"]
        readable_scene_type = str(preview_bundle["scene"]["sceneType"]).upper()
        self._analysis_label.configure(
            text=(
                f"Preset: {preview_bundle['preset']['name']} "
                f"({readable_scene_type})\n"
                f"Primitive: {analysis['primitive']}\n"
                f"Vertices: {analysis['vertexCount']}  Indices: {analysis['indexCount']}\n"
                f"Active sources: {', '.join(analysis['activeSources'])}\n"
                f"Energy: {analysis['energy']}"
            )
        )
        self._latest_preview_json_text = json.dumps(preview_bundle["scene"], indent=2)
        self._render_preview_json_in_window()

    def _open_preview_window(self) -> None:
        """Open a separate JSON window so the main panel can stay compact."""

        if self._preview_window is not None and self._preview_window.winfo_exists():
            self._preview_window.deiconify()
            self._preview_window.lift()
            self._preview_window.focus_force()
            self._render_preview_json_in_window()
            return

        preview_window = tk.Toplevel(self._root)
        preview_window.title("Current scene JSON")
        preview_window.geometry("760x720")
        preview_window.minsize(560, 420)
        preview_window.configure(background=WINDOW_BACKGROUND)
        preview_window.columnconfigure(0, weight=1)
        preview_window.rowconfigure(0, weight=1)

        preview_shell = ttk.Frame(preview_window, padding=16, style="Surface.TFrame")
        preview_shell.grid(sticky="nsew")
        preview_shell.columnconfigure(0, weight=1)
        preview_shell.columnconfigure(1, weight=0)
        preview_shell.rowconfigure(1, weight=1)

        ttk.Label(
            preview_shell,
            text="Current scene JSON",
            style="Heading.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        preview_text_widget = ScrolledText(
            preview_shell,
            wrap="none",
            font=("Cascadia Code", 10),
            background=ENTRY_BACKGROUND,
            foreground=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            selectbackground=ACCENT_COLOR,
            selectforeground=ACCENT_FOREGROUND,
            relief="flat",
            borderwidth=0,
        )
        preview_text_widget.grid(row=1, column=0, sticky="nsew")
        preview_text_widget.configure(state="disabled")

        preview_window.protocol("WM_DELETE_WINDOW", self._close_preview_window)
        self._preview_window = preview_window
        self._preview_text_widget = preview_text_widget
        ttk.Button(
            preview_shell,
            text="Copy JSON",
            command=self._copy_preview_json_to_clipboard,
        ).grid(row=0, column=1, sticky="e", padx=(12, 0), pady=(0, 12))

        if not self._latest_preview_json_text:
            self._refresh_preview()
            return

        self._render_preview_json_in_window()

    def _render_preview_json_in_window(self) -> None:
        """Refresh the detached JSON window when it is open."""

        if self._preview_text_widget is None or not self._preview_text_widget.winfo_exists():
            return

        self._preview_text_widget.configure(state="normal")
        self._preview_text_widget.delete("1.0", tk.END)
        self._preview_text_widget.insert("1.0", self._latest_preview_json_text)
        self._preview_text_widget.configure(state="disabled")

    def _close_preview_window(self) -> None:
        """Forget the detached preview window after the operator closes it."""

        if self._preview_window is not None and self._preview_window.winfo_exists():
            self._preview_window.destroy()
        self._preview_window = None
        self._preview_text_widget = None

    def _copy_preview_json_to_clipboard(self) -> None:
        """Copy the current preview JSON so operators can paste it elsewhere quickly."""

        if not self._latest_preview_json_text:
            self._refresh_preview()
        self._root.clipboard_clear()
        self._root.clipboard_append(self._latest_preview_json_text)
        self._result_status_variable.set("Copied the current scene JSON to the clipboard.")

    def _schedule_status_refresh(self) -> None:
        """Keep audio/live-stream status labels gently refreshed over time."""

        self._refresh_status_labels()
        self._root.after(250, self._schedule_status_refresh)

    def _refresh_status_labels(self) -> None:
        """Refresh status labels from the controller's latest snapshots."""

        audio_snapshot = self._controller.audio_snapshot()
        self._update_volume_meter_display(
            level=audio_snapshot.level if audio_snapshot.capturing else 0.0,
        )
        if audio_snapshot.capturing:
            self._audio_status_variable.set(
                f"{audio_snapshot.device_name}: volume {audio_snapshot.level:.2f}"
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

    def _move_pointer_visual_marker(self, normalized_x: float, normalized_y: float) -> None:
        """Move the canvas marker and crosshair so the larger pad feels alive."""

        if (
            self._pointer_marker_item_identifier is None
            or self._pointer_crosshair_item_identifier is None
        ):
            return
        canvas_width = max(1, int(self._pointer_canvas.winfo_width()))
        canvas_height = max(1, int(self._pointer_canvas.winfo_height()))
        x_position = normalized_x * canvas_width
        y_position = normalized_y * canvas_height
        self._pointer_canvas.coords(
            self._pointer_marker_item_identifier,
            x_position - 8,
            y_position - 8,
            x_position + 8,
            y_position + 8,
        )
        self._pointer_canvas.coords(
            self._pointer_crosshair_item_identifier,
            x_position,
            0,
            x_position,
            canvas_height,
        )

    def _refresh_scene_type_button_styles(self) -> None:
        """Keep the 2D/3D buttons visibly selected with strong contrast."""

        selected_scene_type = self._scene_type_variable.get().strip().lower()
        for scene_type_value, button in self._scene_type_button_widgets.items():
            self._apply_selection_button_style(
                button,
                selected=(scene_type_value == selected_scene_type),
            )

    def _refresh_audio_device_flow_button_styles(self) -> None:
        """Keep the audio source-type buttons aligned with the selected source flow."""

        selected_device_flow = self._selected_audio_device_flow()
        for device_flow, button in self._audio_device_flow_button_widgets.items():
            self._apply_selection_button_style(
                button,
                selected=(device_flow == selected_device_flow),
            )

    def _refresh_preset_button_styles(self) -> None:
        """Keep the preset buttons visually aligned with the active preset."""

        selected_preset_identifier = self._preset_identifier_variable.get().strip()
        for preset_identifier, button in self._preset_button_widgets.items():
            self._apply_selection_button_style(
                button,
                selected=(preset_identifier == selected_preset_identifier),
            )

    def _apply_selection_button_style(self, button: tk.Button, *, selected: bool) -> None:
        """Apply the selected or unselected palette to one custom selection button."""

        if selected:
            button.configure(
                background=SELECTION_BUTTON_SELECTED_BACKGROUND,
                foreground=SELECTION_BUTTON_SELECTED_FOREGROUND,
                activebackground=ACCENT_COLOR_ACTIVE,
                activeforeground=ACCENT_FOREGROUND,
                highlightbackground=SELECTION_BUTTON_SELECTED_BACKGROUND,
                highlightcolor=SELECTION_BUTTON_SELECTED_BACKGROUND,
                relief="sunken",
            )
            return

        button.configure(
            background=SELECTION_BUTTON_BACKGROUND,
            foreground=SELECTION_BUTTON_FOREGROUND,
            activebackground=SURFACE_BORDER,
            activeforeground=TEXT_PRIMARY,
            highlightbackground=SELECTION_BUTTON_BORDER,
            highlightcolor=SELECTION_BUTTON_BORDER,
            relief="flat",
        )

    def _refresh_color_swatch(self, variable: tk.StringVar) -> None:
        """Keep the visual color swatches in sync with the typed hex values."""

        swatch_frame = self._color_swatch_frames.get(str(variable))
        if swatch_frame is not None:
            try:
                swatch_frame.configure(background=variable.get())
            except tk.TclError:
                swatch_frame.configure(background="#000000")

    def _refresh_all_color_swatches(self) -> None:
        for color_variable in [
            self._background_variable,
            self._primary_color_variable,
            self._secondary_color_variable,
        ]:
            self._refresh_color_swatch(color_variable)

    def _update_volume_meter_display(self, *, level: float) -> None:
        """Keep the single visible volume meter synchronized with the latest snapshot."""

        clamped_percentage = max(0.0, min(100.0, float(level) * 100.0))
        self._volume_meter_progress_variable.set(clamped_percentage)
        self._volume_meter_text_variable.set(f"{int(round(clamped_percentage))}%")

    def _refresh_all_slider_display_labels(self) -> None:
        """Recompute the formatted slider labels after loading or reverting settings."""

        self._on_slider_value_changed(
            self._cadence_variable,
            self._slider_display_variables["cadence"],
            1.0,
            0,
            " ms",
        )
        self._on_slider_value_changed(
            self._density_variable,
            self._slider_display_variables["density"],
            1.0,
            0,
        )
        self._on_slider_value_changed(
            self._point_size_variable,
            self._slider_display_variables["pointSize"],
            0.5,
            1,
        )
        self._on_slider_value_changed(
            self._line_width_variable,
            self._slider_display_variables["lineWidth"],
            0.25,
            2,
        )
        self._on_slider_value_changed(
            self._speed_variable,
            self._slider_display_variables["speed"],
            0.05,
            2,
        )
        self._on_slider_value_changed(
            self._gain_variable,
            self._slider_display_variables["gain"],
            0.05,
            2,
        )
        self._on_slider_value_changed(
            self._manual_drive_variable,
            self._slider_display_variables["manualDrive"],
            0.05,
            2,
        )

    def _revert_current_preset_to_default_settings(self) -> None:
        """Restore the current preset's default settings while keeping the current target."""

        updated_payload = self._controller.reset_current_preset_to_defaults()
        self._set_user_interface_from_request_payload(updated_payload)
        self._result_status_variable.set("Reverted the current preset to its default settings.")
        self._refresh_preview()

    def _save_settings_to_file(self) -> None:
        """Save the current control payload to a reusable JSON file."""

        self._sync_payload_to_controller()
        selected_path = filedialog.asksaveasfilename(
            parent=self._root,
            title="Save desktop control panel settings",
            initialfile=DEFAULT_SETTINGS_FILE_NAME,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not selected_path:
            return
        settings_document = self._controller.settings_document()
        Path(selected_path).write_text(json.dumps(settings_document, indent=2), encoding="utf-8")
        self._settings_file_path = Path(selected_path)
        self._result_status_variable.set(f"Saved settings to {self._settings_file_path.name}.")

    def _load_settings_from_file(self) -> None:
        """Load a saved settings JSON file and refresh the whole window state."""

        selected_path = filedialog.askopenfilename(
            parent=self._root,
            title="Load desktop control panel settings",
            initialfile=DEFAULT_SETTINGS_FILE_NAME,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not selected_path:
            return
        try:
            settings_document = json.loads(Path(selected_path).read_text(encoding="utf-8"))
            if not isinstance(settings_document, dict):
                raise ValueError("Settings files must contain a JSON object at the top level.")
            updated_payload = self._controller.load_settings_document(settings_document)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            messagebox.showerror("Load settings", str(error))
            return
        self._settings_file_path = Path(selected_path)
        self._set_user_interface_from_request_payload(updated_payload)
        self._result_status_variable.set(f"Loaded settings from {self._settings_file_path.name}.")
        self._refresh_preview()

    def _on_close_requested(self) -> None:
        """Shut down background resources before destroying the window."""

        self._close_preview_window()
        self._controller.close()
        self._root.destroy()

    @staticmethod
    def _round_to_increment(value: float, increment: float) -> float:
        """Round a floating-point value to a friendly control increment."""

        if increment <= 0:
            return value
        rounded_value = round(value / increment) * increment
        decimal_places = max(0, len(str(increment).split(".")[-1].rstrip("0")))
        return round(rounded_value, decimal_places)

    @staticmethod
    def _safe_int(value: object, default: int) -> int:
        """Parse an integer-like value without raising UI-facing exceptions."""

        if not isinstance(value, (bool, int, float, str)):
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _selected_audio_device_flow(self) -> str:
        """Normalize the UI selection down to the supported input/output source types."""

        return (
            "output"
            if self._audio_device_flow_variable.get().strip().lower() == "output"
            else "input"
        )


def main() -> None:
    """Launch the desktop render control panel."""

    root = tk.Tk()
    DesktopRenderControlPanelWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
