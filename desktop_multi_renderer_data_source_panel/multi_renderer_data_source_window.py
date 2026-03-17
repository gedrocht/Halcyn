"""Tkinter window for the shared multi-renderer data-source panel.

The window is intentionally split from the controller so a beginner can read
the code in layers:

1. the builder explains how raw data becomes renderer-ready scenes
2. the controller explains how those scenes are validated and applied
3. this window explains how the operator interacts with those actions
"""

from __future__ import annotations

import json
import tkinter as tk
from functools import partial
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from desktop_multi_renderer_data_source_panel.multi_renderer_data_source_builder import (
    MultiRendererPreviewBundle,
)
from desktop_multi_renderer_data_source_panel.multi_renderer_data_source_controller import (
    MultiRendererDataSourceController,
)
from desktop_shared_control_support.activity_log_window import DesktopActivityLogWindow

WINDOW_BACKGROUND = "#08111b"
PANEL_BACKGROUND = "#102033"
SECTION_BACKGROUND = "#14293f"
ACCENT_COLOR = "#56c8ff"
ACCENT_SELECTED_COLOR = "#245c82"
ACCENT_FOREGROUND = "#04131d"
TEXT_PRIMARY = "#eff6ff"
TEXT_SECONDARY = "#9fb7d0"
ENTRY_BACKGROUND = "#10243a"
BUTTON_BACKGROUND = "#18304a"
BUTTON_BORDER = "#2e4b69"
POINTER_PAD_BACKGROUND = "#091520"
POINTER_PAD_GRID = "#28445f"
POINTER_PAD_MARKER = "#ffd166"
METER_COLOR = "#56c8ff"
DEFAULT_SETTINGS_FILE_NAME = "halcyn-signal-router-settings.json"


class MultiRendererDataSourceWindow:
    """Build and manage the native shared data-source desktop window."""

    def __init__(
        self,
        root_window: tk.Tk,
        controller: MultiRendererDataSourceController | None = None,
    ) -> None:
        self._root_window = root_window
        self._controller = controller or MultiRendererDataSourceController()
        self._catalog_payload = self._controller.catalog_payload()
        self._classic_preset_names_by_identifier = {
            preset_entry["id"]: preset_entry["name"]
            for preset_entry in self._catalog_payload["classicPresets"]
        }
        self._classic_preset_identifiers_by_name = {
            preset_name: preset_identifier
            for preset_identifier, preset_name in self._classic_preset_names_by_identifier.items()
        }
        self._source_mode_button_widgets: dict[str, tk.Button] = {}
        self._audio_flow_button_widgets: dict[str, tk.Button] = {}
        self._source_specific_frames: dict[str, ttk.Frame] = {}
        self._json_preview_window: tk.Toplevel | None = None
        self._json_preview_text_widgets: dict[str, ScrolledText] = {}
        self._settings_file_path: Path | None = None
        self._latest_preview_bundle: MultiRendererPreviewBundle | None = None
        self._activity_log_window: DesktopActivityLogWindow | None = None
        self._last_pointer_x = 0.5
        self._last_pointer_y = 0.5
        self._pointer_marker_identifier: int | None = None

        self._root_window.title("Halcyn Signal Router")
        self._root_window.geometry("1500x920")
        self._root_window.minsize(1260, 780)
        self._root_window.configure(background=WINDOW_BACKGROUND)
        self._root_window.protocol("WM_DELETE_WINDOW", self._on_close_requested)

        self._build_tk_variables()
        self._configure_styles()
        self._build_user_interface()
        self._sync_user_interface_from_request_payload(self._controller.current_request_payload())
        self._schedule_status_refresh()

    def _build_tk_variables(self) -> None:
        """Create the Tk variables that back the visible widgets."""

        self._source_mode_variable = tk.StringVar(value="json_document")
        self._plain_text_variable = tk.StringVar(value="Halcyn")
        self._random_seed_variable = tk.StringVar(value="7")
        self._random_count_variable = tk.StringVar(value="128")
        self._random_minimum_variable = tk.StringVar(value="0.0")
        self._random_maximum_variable = tk.StringVar(value="255.0")
        self._audio_device_flow_variable = tk.StringVar(value="output")
        self._audio_device_variable = tk.StringVar(value="")
        self._classic_enabled_variable = tk.BooleanVar(value=True)
        self._classic_host_variable = tk.StringVar(value="127.0.0.1")
        self._classic_port_variable = tk.StringVar(value="8080")
        self._classic_preset_name_variable = tk.StringVar(value="")
        self._classic_use_epoch_variable = tk.BooleanVar(value=True)
        self._classic_use_noise_variable = tk.BooleanVar(value=True)
        self._spectrograph_enabled_variable = tk.BooleanVar(value=False)
        self._spectrograph_host_variable = tk.StringVar(value="127.0.0.1")
        self._spectrograph_port_variable = tk.StringVar(value="8090")
        self._spectrograph_bar_grid_size_variable = tk.IntVar(value=8)
        self._spectrograph_bar_grid_label_variable = tk.StringVar(value="8 x 8")
        self._spectrograph_shader_style_variable = tk.StringVar(value="heatmap")
        self._spectrograph_anti_aliasing_variable = tk.BooleanVar(value=True)
        self._spectrograph_range_mode_variable = tk.StringVar(value="automatic")
        self._spectrograph_manual_minimum_variable = tk.StringVar(value="0.0")
        self._spectrograph_manual_maximum_variable = tk.StringVar(value="255.0")
        self._live_cadence_variable = tk.IntVar(value=125)
        self._live_cadence_label_variable = tk.StringVar(value="125 ms")
        self._result_status_variable = tk.StringVar(value="Ready.")
        self._health_status_variable = tk.StringVar(value="Health check not run yet.")
        self._live_status_variable = tk.StringVar(value="Live stream idle.")
        self._audio_status_variable = tk.StringVar(value="Audio capture not started.")
        self._external_source_status_variable = tk.StringVar(
            value="External feed bridge not checked yet."
        )
        self._source_summary_variable = tk.StringVar(
            value="Choose a source mode to see how values will be collected."
        )
        self._volume_meter_progress_variable = tk.DoubleVar(value=0.0)
        self._volume_meter_text_variable = tk.StringVar(value="0%")

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
            background=BUTTON_BACKGROUND,
            foreground=TEXT_PRIMARY,
            borderwidth=1,
            focusthickness=0,
            focuscolor=BUTTON_BORDER,
        )
        style.map("Accent.TButton", background=[("active", ACCENT_SELECTED_COLOR)])
        style.configure("Dark.TCheckbutton", background=SECTION_BACKGROUND, foreground=TEXT_PRIMARY)
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
        style.configure("Notebook.TNotebook", background=PANEL_BACKGROUND, borderwidth=0)
        style.configure(
            "Notebook.TNotebook.Tab",
            background=SECTION_BACKGROUND,
            foreground=TEXT_PRIMARY,
            padding=(16, 8),
        )
        style.map(
            "Notebook.TNotebook.Tab",
            background=[("selected", ACCENT_SELECTED_COLOR)],
            foreground=[("selected", TEXT_PRIMARY)],
        )

    def _build_user_interface(self) -> None:
        """Create the main window layout."""

        page_shell = ttk.Frame(self._root_window, style="Shell.TFrame", padding=16)
        page_shell.pack(fill="both", expand=True)
        page_shell.columnconfigure(0, weight=4)
        page_shell.columnconfigure(1, weight=2)
        page_shell.rowconfigure(2, weight=1)

        heading = ttk.Label(
            page_shell,
            text="Signal Router",
            style="Title.TLabel",
        )
        heading.grid(row=0, column=0, columnspan=2, sticky="w")
        subtitle = ttk.Label(
            page_shell,
            text=(
                "Capture or generate one live data stream, then route it into the classic "
                "scene renderer, the bar-wall renderer, or both."
            ),
            style="Subheading.TLabel",
        )
        subtitle.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 16))

        content_frame = ttk.Frame(page_shell, style="Shell.TFrame")
        content_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        content_frame.columnconfigure(0, weight=4)
        content_frame.columnconfigure(1, weight=2)
        content_frame.rowconfigure(0, weight=1)

        self._build_left_notebook(content_frame)
        self._build_status_panel(content_frame)

    def _build_left_notebook(self, parent: ttk.Frame) -> None:
        """Create the notebook that holds source and target controls."""

        notebook = ttk.Notebook(parent, style="Notebook.TNotebook")
        notebook.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        source_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=12)
        scene_target_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=12)
        bar_wall_target_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=12)
        notebook.add(source_tab, text="Source")
        notebook.add(scene_target_tab, text="Scene Target")
        notebook.add(bar_wall_target_tab, text="Bar-Wall Target")

        self._build_source_tab(source_tab)
        self._build_classic_target_tab(scene_target_tab)
        self._build_spectrograph_target_tab(bar_wall_target_tab)

    def _build_source_tab(self, parent: ttk.Frame) -> None:
        """Create source-mode controls, audio controls, and pointer controls."""

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        source_mode_frame = ttk.Frame(parent, style="Section.TFrame", padding=12)
        source_mode_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(source_mode_frame, text="Source mode", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        source_mode_column_count = len(self._catalog_payload["sourceModes"])
        ttk.Label(
            source_mode_frame,
            text=(
                "Pick one input family. The app will translate that live data into one "
                "scene-renderer scene and/or one bar-wall scene."
            ),
            style="Body.TLabel",
        ).grid(row=1, column=0, columnspan=source_mode_column_count, sticky="w", pady=(6, 10))

        for button_index, source_mode_entry in enumerate(self._catalog_payload["sourceModes"]):
            source_mode_identifier = source_mode_entry["id"]
            button_widget = tk.Button(
                source_mode_frame,
                text=source_mode_entry["name"],
                command=partial(self._set_source_mode, source_mode_identifier),
                bg=BUTTON_BACKGROUND,
                fg=TEXT_PRIMARY,
                activebackground=ACCENT_SELECTED_COLOR,
                activeforeground=TEXT_PRIMARY,
                relief="solid",
                bd=1,
                highlightthickness=0,
                padx=12,
                pady=8,
            )
            button_widget.grid(row=2, column=button_index, sticky="ew", padx=(0, 8))
            source_mode_frame.columnconfigure(button_index, weight=1)
            self._source_mode_button_widgets[source_mode_identifier] = button_widget

        self._source_specific_container = ttk.Frame(parent, style="Panel.TFrame")
        self._source_specific_container.grid(row=1, column=0, sticky="nsew")
        self._source_specific_container.columnconfigure(0, weight=1)
        self._source_specific_container.rowconfigure(0, weight=1)

        self._source_specific_frames["json_document"] = self._build_json_source_frame(
            self._source_specific_container
        )
        self._source_specific_frames["external_json_bridge"] = (
            self._build_external_json_bridge_source_frame(self._source_specific_container)
        )
        self._source_specific_frames["plain_text"] = self._build_plain_text_source_frame(
            self._source_specific_container
        )
        self._source_specific_frames["random_values"] = self._build_random_source_frame(
            self._source_specific_container
        )
        self._source_specific_frames["audio_device"] = self._build_audio_source_frame(
            self._source_specific_container
        )
        self._source_specific_frames["pointer_pad"] = self._build_pointer_source_frame(
            self._source_specific_container
        )

    def _build_json_source_frame(self, parent: ttk.Frame) -> ttk.Frame:
        """Create the JSON-document source frame."""

        frame = ttk.Frame(parent, style="Section.TFrame", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        ttk.Label(frame, text="JSON document source", style="Section.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        button_frame = ttk.Frame(frame, style="Section.TFrame")
        button_frame.grid(row=1, column=0, sticky="ew", pady=(8, 10))
        for button_index, example_entry in enumerate(self._catalog_payload["spectrographExamples"]):
            ttk.Button(
                button_frame,
                text=example_entry["name"],
                style="Accent.TButton",
                command=partial(self._load_json_example, example_entry["jsonText"]),
            ).grid(row=0, column=button_index, sticky="ew", padx=(0, 8))
            button_frame.columnconfigure(button_index, weight=1)
        ttk.Button(
            button_frame,
            text="Load JSON file",
            style="Accent.TButton",
            command=self._load_json_file,
        ).grid(row=1, column=0, sticky="ew", pady=(8, 0))

        self._json_text_widget = ScrolledText(
            frame,
            width=80,
            height=24,
            wrap="word",
            background=ENTRY_BACKGROUND,
            foreground=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
        )
        self._json_text_widget.grid(row=2, column=0, sticky="nsew")
        return frame

    def _build_external_json_bridge_source_frame(self, parent: ttk.Frame) -> ttk.Frame:
        """Create the read-only source frame for helper-delivered external JSON."""

        frame = ttk.Frame(parent, style="Section.TFrame", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="External feed source", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            frame,
            text=(
                "This mode follows the newest JSON document sent by another local helper "
                "app, such as the Audio Sender. The Signal Router keeps listening on its "
                "own bridge even when you are editing another source mode."
            ),
            style="Body.TLabel",
            wraplength=760,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(6, 10))
        ttk.Label(
            frame,
            textvariable=self._external_source_status_variable,
            style="Body.TLabel",
            wraplength=760,
            justify="left",
        ).grid(row=2, column=0, sticky="ew", pady=(0, 12))
        ttk.Button(
            frame,
            text="Open activity monitor",
            style="Accent.TButton",
            command=self._open_activity_log_window,
        ).grid(row=3, column=0, sticky="w")
        return frame

    def _build_plain_text_source_frame(self, parent: ttk.Frame) -> ttk.Frame:
        """Create the plain-text source frame."""

        frame = ttk.Frame(parent, style="Section.TFrame", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="Plain text source", style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(
            frame,
            text="The text is converted into UTF-8 bytes before routing to each renderer.",
            style="Body.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 10))
        ttk.Label(frame, text="Text", style="Section.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Entry(
            frame,
            textvariable=self._plain_text_variable,
            style="Dark.TEntry",
            width=80,
        ).grid(row=2, column=1, sticky="ew")
        return frame

    def _build_random_source_frame(self, parent: ttk.Frame) -> ttk.Frame:
        """Create the random-value source frame."""

        frame = ttk.Frame(parent, style="Section.TFrame", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        for column_index in range(4):
            frame.columnconfigure(column_index, weight=1)
        ttk.Label(frame, text="Random value source", style="Section.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w"
        )
        ttk.Label(
            frame,
            text="The seed makes the random series repeatable, which is useful for testing.",
            style="Body.TLabel",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 10))
        self._build_labeled_entry(frame, "Seed", self._random_seed_variable, 2, 0)
        self._build_labeled_entry(frame, "Count", self._random_count_variable, 2, 1)
        self._build_labeled_entry(frame, "Minimum", self._random_minimum_variable, 2, 2)
        self._build_labeled_entry(frame, "Maximum", self._random_maximum_variable, 2, 3)
        return frame

    def _build_audio_source_frame(self, parent: ttk.Frame) -> ttk.Frame:
        """Create the audio-device source frame."""

        frame = ttk.Frame(parent, style="Section.TFrame", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="Audio device source", style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(
            frame,
            text=(
                "Choose either output loopback capture or input capture. The current audio "
                "analysis is then routed into both renderer families."
            ),
            style="Body.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 10))

        flow_button_frame = ttk.Frame(frame, style="Section.TFrame")
        flow_button_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        for button_index, (device_flow, button_label) in enumerate(
            (("output", "Output sources"), ("input", "Input sources"))
        ):
            flow_button = tk.Button(
                flow_button_frame,
                text=button_label,
                command=partial(self._set_audio_device_flow, device_flow),
                bg=BUTTON_BACKGROUND,
                fg=TEXT_PRIMARY,
                activebackground=ACCENT_SELECTED_COLOR,
                activeforeground=TEXT_PRIMARY,
                relief="solid",
                bd=1,
                highlightthickness=0,
                padx=12,
                pady=8,
            )
            flow_button.grid(row=0, column=button_index, sticky="ew", padx=(0, 8))
            flow_button_frame.columnconfigure(button_index, weight=1)
            self._audio_flow_button_widgets[device_flow] = flow_button

        ttk.Label(frame, text="Audio device", style="Section.TLabel").grid(
            row=3, column=0, sticky="w"
        )
        self._audio_device_combobox = ttk.Combobox(
            frame,
            textvariable=self._audio_device_variable,
            state="readonly",
            style="Dark.TCombobox",
            width=48,
        )
        self._audio_device_combobox.grid(row=3, column=1, sticky="ew")

        action_frame = ttk.Frame(frame, style="Section.TFrame")
        action_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 10))
        for column_index in range(3):
            action_frame.columnconfigure(column_index, weight=1)
        ttk.Button(
            action_frame,
            text="Refresh devices",
            style="Accent.TButton",
            command=self._refresh_audio_devices,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(
            action_frame,
            text="Start capture",
            style="Accent.TButton",
            command=self._start_audio_capture,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(
            action_frame,
            text="Stop capture",
            style="Accent.TButton",
            command=self._stop_audio_capture,
        ).grid(row=0, column=2, sticky="ew")

        ttk.Label(frame, text="Live volume", style="Section.TLabel").grid(
            row=5, column=0, sticky="w"
        )
        ttk.Progressbar(
            frame,
            variable=self._volume_meter_progress_variable,
            maximum=100.0,
            style="Meter.Horizontal.TProgressbar",
        ).grid(row=5, column=1, sticky="ew")
        ttk.Label(frame, textvariable=self._volume_meter_text_variable, style="Body.TLabel").grid(
            row=6, column=1, sticky="e", pady=(6, 0)
        )
        return frame

    def _build_pointer_source_frame(self, parent: ttk.Frame) -> ttk.Frame:
        """Create the pointer-pad source frame."""

        frame = ttk.Frame(parent, style="Section.TFrame", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="Pointer pad source", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            frame,
            text="Drag inside the pad to control X, Y, and movement speed.",
            style="Body.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 10))
        self._pointer_canvas = tk.Canvas(
            frame,
            width=520,
            height=360,
            background=POINTER_PAD_BACKGROUND,
            highlightbackground=POINTER_PAD_GRID,
            highlightthickness=1,
            relief="flat",
        )
        self._pointer_canvas.grid(row=2, column=0, sticky="nsew")
        self._draw_pointer_pad_grid()
        self._pointer_canvas.bind("<Button-1>", self._on_pointer_canvas_drag)
        self._pointer_canvas.bind("<B1-Motion>", self._on_pointer_canvas_drag)
        return frame

    def _build_classic_target_tab(self, parent: ttk.Frame) -> None:
        """Create the classic-renderer target configuration tab."""

        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text="Classic renderer target", style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Checkbutton(
            parent,
            text="Send to classic renderer",
            variable=self._classic_enabled_variable,
            style="Dark.TCheckbutton",
            command=self._refresh_preview,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 10))
        self._build_labeled_entry(parent, "Host", self._classic_host_variable, 2, 0)
        self._build_labeled_entry(parent, "Port", self._classic_port_variable, 2, 1)
        ttk.Label(parent, text="Preset", style="Section.TLabel").grid(row=4, column=0, sticky="w")
        self._classic_preset_combobox = ttk.Combobox(
            parent,
            textvariable=self._classic_preset_name_variable,
            values=list(self._classic_preset_identifiers_by_name.keys()),
            state="readonly",
            style="Dark.TCombobox",
        )
        self._classic_preset_combobox.grid(row=4, column=1, sticky="ew")
        self._classic_preset_combobox.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._refresh_preview(),
        )
        ttk.Checkbutton(
            parent,
            text="Include epoch motion",
            variable=self._classic_use_epoch_variable,
            style="Dark.TCheckbutton",
            command=self._refresh_preview,
        ).grid(row=5, column=0, sticky="w", pady=(10, 0))
        ttk.Checkbutton(
            parent,
            text="Include noise modulation",
            variable=self._classic_use_noise_variable,
            style="Dark.TCheckbutton",
            command=self._refresh_preview,
        ).grid(row=5, column=1, sticky="w", pady=(10, 0))

    def _build_spectrograph_target_tab(self, parent: ttk.Frame) -> None:
        """Create the spectrograph-renderer target configuration tab."""

        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text="Spectrograph renderer target", style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Checkbutton(
            parent,
            text="Send to spectrograph renderer",
            variable=self._spectrograph_enabled_variable,
            style="Dark.TCheckbutton",
            command=self._refresh_preview,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 10))
        self._build_labeled_entry(parent, "Host", self._spectrograph_host_variable, 2, 0)
        self._build_labeled_entry(parent, "Port", self._spectrograph_port_variable, 2, 1)
        ttk.Label(parent, text="Bar grid size", style="Section.TLabel").grid(
            row=4, column=0, sticky="w"
        )
        ttk.Scale(
            parent,
            variable=self._spectrograph_bar_grid_size_variable,
            from_=2,
            to=24,
            orient="horizontal",
            style="Dark.Horizontal.TScale",
            command=self._on_spectrograph_bar_grid_changed,
        ).grid(row=4, column=1, sticky="ew")
        ttk.Label(
            parent,
            textvariable=self._spectrograph_bar_grid_label_variable,
            style="Body.TLabel",
        ).grid(row=5, column=1, sticky="e")
        ttk.Label(parent, text="Shader style", style="Section.TLabel").grid(
            row=6, column=0, sticky="w"
        )
        spectrograph_shader_style_combobox = ttk.Combobox(
            parent,
            textvariable=self._spectrograph_shader_style_variable,
            values=self._catalog_payload["spectrographShaderStyles"],
            state="readonly",
            style="Dark.TCombobox",
        )
        spectrograph_shader_style_combobox.grid(row=6, column=1, sticky="ew")
        spectrograph_shader_style_combobox.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._refresh_preview(),
        )
        ttk.Checkbutton(
            parent,
            text="Enable anti-aliasing",
            variable=self._spectrograph_anti_aliasing_variable,
            style="Dark.TCheckbutton",
            command=self._refresh_preview,
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Radiobutton(
            parent,
            text="Automatic range",
            value="automatic",
            variable=self._spectrograph_range_mode_variable,
            style="Dark.TRadiobutton",
            command=self._refresh_preview,
        ).grid(row=8, column=0, sticky="w", pady=(12, 0))
        ttk.Radiobutton(
            parent,
            text="Manual range",
            value="manual",
            variable=self._spectrograph_range_mode_variable,
            style="Dark.TRadiobutton",
            command=self._refresh_preview,
        ).grid(row=8, column=1, sticky="w", pady=(12, 0))
        self._build_labeled_entry(
            parent,
            "Manual minimum",
            self._spectrograph_manual_minimum_variable,
            9,
            0,
        )
        self._build_labeled_entry(
            parent,
            "Manual maximum",
            self._spectrograph_manual_maximum_variable,
            9,
            1,
        )

    def _build_status_panel(self, parent: ttk.Frame) -> None:
        """Create the right-side actions and status panel."""

        panel = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.columnconfigure(0, weight=1)

        ttk.Label(panel, text="Actions and status", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            panel,
            text="Preview, validate, apply, save, and monitor the shared live data pipeline here.",
            style="Body.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 10))

        action_frame = ttk.Frame(panel, style="Section.TFrame", padding=12)
        action_frame.grid(row=2, column=0, sticky="ew")
        for column_index in range(2):
            action_frame.columnconfigure(column_index, weight=1)
        actions = [
            ("Check health", self._run_health_check),
            ("Preview", self._refresh_preview),
            ("Validate", self._validate_selected_targets),
            ("Apply", self._apply_selected_targets),
            ("Start live stream", self._start_live_stream),
            ("Stop live stream", self._stop_live_stream),
            ("Revert to default", self._reset_to_defaults),
            ("Load settings", self._load_settings_file),
            ("Save settings", self._save_settings_file),
            ("Open preview JSON", self._open_preview_json_window),
            ("Open activity monitor", self._open_activity_log_window),
        ]
        for button_index, (button_text, button_command) in enumerate(actions):
            ttk.Button(
                action_frame,
                text=button_text,
                style="Accent.TButton",
                command=button_command,
            ).grid(
                row=button_index // 2,
                column=button_index % 2,
                sticky="ew",
                padx=(0, 8) if button_index % 2 == 0 else (0, 0),
                pady=(0, 8),
            )

        ttk.Label(panel, text="Shared live cadence", style="Section.TLabel").grid(
            row=3, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Scale(
            panel,
            variable=self._live_cadence_variable,
            from_=40,
            to=2000,
            orient="horizontal",
            style="Dark.Horizontal.TScale",
            command=self._on_live_cadence_changed,
        ).grid(row=4, column=0, sticky="ew")
        ttk.Label(panel, textvariable=self._live_cadence_label_variable, style="Body.TLabel").grid(
            row=5, column=0, sticky="e"
        )

        summary_frame = ttk.Frame(panel, style="Section.TFrame", padding=12)
        summary_frame.grid(row=6, column=0, sticky="nsew", pady=(12, 0))
        summary_frame.columnconfigure(0, weight=1)
        ttk.Label(summary_frame, text="Source summary", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            summary_frame,
            textvariable=self._source_summary_variable,
            style="Body.TLabel",
            wraplength=360,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(6, 10))
        ttk.Label(
            summary_frame,
            text="Health",
            style="Section.TLabel",
        ).grid(row=2, column=0, sticky="w")
        ttk.Label(
            summary_frame,
            textvariable=self._health_status_variable,
            style="Body.TLabel",
            wraplength=360,
            justify="left",
        ).grid(row=3, column=0, sticky="w", pady=(6, 10))
        ttk.Label(summary_frame, text="Last result", style="Section.TLabel").grid(
            row=4, column=0, sticky="w"
        )
        ttk.Label(
            summary_frame,
            textvariable=self._result_status_variable,
            style="Body.TLabel",
            wraplength=360,
            justify="left",
        ).grid(row=5, column=0, sticky="w", pady=(6, 10))
        ttk.Label(summary_frame, text="Live stream", style="Section.TLabel").grid(
            row=6, column=0, sticky="w"
        )
        ttk.Label(
            summary_frame,
            textvariable=self._live_status_variable,
            style="Body.TLabel",
            wraplength=360,
            justify="left",
        ).grid(row=7, column=0, sticky="w", pady=(6, 10))
        ttk.Label(summary_frame, text="Audio status", style="Section.TLabel").grid(
            row=8, column=0, sticky="w"
        )
        ttk.Label(
            summary_frame,
            textvariable=self._audio_status_variable,
            style="Body.TLabel",
            wraplength=360,
            justify="left",
        ).grid(row=9, column=0, sticky="w", pady=(6, 0))
        ttk.Label(summary_frame, text="External feed", style="Section.TLabel").grid(
            row=10, column=0, sticky="w", pady=(10, 0)
        )
        ttk.Label(
            summary_frame,
            textvariable=self._external_source_status_variable,
            style="Body.TLabel",
            wraplength=360,
            justify="left",
        ).grid(row=11, column=0, sticky="w", pady=(6, 0))

    def _build_labeled_entry(
        self,
        parent: ttk.Frame,
        label_text: str,
        variable: tk.StringVar,
        row_index: int,
        column_index: int,
    ) -> None:
        """Build one small label-plus-entry pair."""

        field_frame = ttk.Frame(parent, style="Section.TFrame")
        field_frame.grid(
            row=row_index,
            column=column_index,
            sticky="ew",
            padx=(0, 12),
            pady=(0, 10),
        )
        field_frame.columnconfigure(0, weight=1)
        ttk.Label(field_frame, text=label_text, style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(field_frame, textvariable=variable, style="Dark.TEntry").grid(
            row=1, column=0, sticky="ew", pady=(4, 0)
        )

    def _load_json_example(self, json_text: str) -> None:
        """Load one example JSON document into the source editor."""

        self._json_text_widget.delete("1.0", "end")
        self._json_text_widget.insert("1.0", json_text)
        self._set_source_mode("json_document")
        self._refresh_preview()

    def _load_json_file(self) -> None:
        """Load one JSON file from disk into the source editor."""

        chosen_file_path = filedialog.askopenfilename(
            title="Open JSON file",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not chosen_file_path:
            return
        loaded_json_text = Path(chosen_file_path).read_text(encoding="utf-8")
        self._json_text_widget.delete("1.0", "end")
        self._json_text_widget.insert("1.0", loaded_json_text)
        self._set_source_mode("json_document")
        self._refresh_preview()

    def _set_source_mode(self, source_mode_identifier: str) -> None:
        """Switch the active source-mode selection."""

        self._source_mode_variable.set(source_mode_identifier)
        self._sync_source_mode_buttons()
        self._sync_source_mode_visibility()
        self._refresh_preview()

    def _set_audio_device_flow(self, device_flow: str) -> None:
        """Switch between input and output audio-device lists."""

        self._audio_device_flow_variable.set(device_flow)
        self._sync_audio_flow_buttons()
        self._refresh_audio_devices()
        self._refresh_preview()

    def _refresh_audio_devices(self) -> None:
        """Refresh the combobox list for the current audio flow."""

        device_descriptors = self._controller.refresh_audio_devices(
            self._audio_device_flow_variable.get()
        )
        self._audio_device_combobox["values"] = [
            f"{device_descriptor.device_identifier} | {device_descriptor.name}"
            for device_descriptor in device_descriptors
        ]
        if device_descriptors:
            self._audio_device_variable.set(
                f"{device_descriptors[0].device_identifier} | {device_descriptors[0].name}"
            )
        else:
            self._audio_device_variable.set("")

    def _start_audio_capture(self) -> None:
        """Start audio capture for the currently selected device."""

        selected_audio_device_text = self._audio_device_variable.get().strip()
        if not selected_audio_device_text:
            messagebox.showerror("Audio capture", "Choose an audio device first.")
            return
        selected_audio_device_identifier = selected_audio_device_text.split("|", 1)[0].strip()
        try:
            snapshot = self._controller.start_audio_capture(
                device_identifier=selected_audio_device_identifier,
                device_flow=self._audio_device_flow_variable.get(),
            )
        except Exception as error:
            messagebox.showerror("Audio capture", str(error))
            return
        self._audio_status_variable.set(
            f"Capturing from {snapshot.device_name or selected_audio_device_identifier}."
        )
        self._set_source_mode("audio_device")

    def _stop_audio_capture(self) -> None:
        """Stop audio capture."""

        snapshot = self._controller.stop_audio_capture()
        self._audio_status_variable.set(snapshot.last_error or "Audio capture stopped.")

    def _draw_pointer_pad_grid(self) -> None:
        """Draw the pointer pad background grid and initial marker."""

        canvas_width = int(self._pointer_canvas["width"])
        canvas_height = int(self._pointer_canvas["height"])
        for x_position in range(0, canvas_width + 1, 52):
            self._pointer_canvas.create_line(
                x_position,
                0,
                x_position,
                canvas_height,
                fill=POINTER_PAD_GRID,
            )
        for y_position in range(0, canvas_height + 1, 45):
            self._pointer_canvas.create_line(
                0,
                y_position,
                canvas_width,
                y_position,
                fill=POINTER_PAD_GRID,
            )
        self._pointer_marker_identifier = self._pointer_canvas.create_oval(
            248,
            168,
            272,
            192,
            fill=POINTER_PAD_MARKER,
            outline="",
        )

    def _on_pointer_canvas_drag(self, event: tk.Event[Any]) -> None:
        """Convert one pointer-pad drag into normalized pointer coordinates."""

        canvas_width = max(1, int(self._pointer_canvas.winfo_width()))
        canvas_height = max(1, int(self._pointer_canvas.winfo_height()))
        clamped_x_position = max(0, min(canvas_width, event.x))
        clamped_y_position = max(0, min(canvas_height, event.y))
        normalized_x_position = clamped_x_position / canvas_width
        normalized_y_position = 1.0 - (clamped_y_position / canvas_height)
        pointer_speed = min(
            1.0,
            (
                (normalized_x_position - self._last_pointer_x) ** 2
                + (normalized_y_position - self._last_pointer_y) ** 2
            )
            ** 0.5
            * 6.0,
        )
        self._last_pointer_x = normalized_x_position
        self._last_pointer_y = normalized_y_position
        self._controller.update_pointer_signal(
            normalized_x_position,
            normalized_y_position,
            pointer_speed,
        )
        if self._pointer_marker_identifier is not None:
            self._pointer_canvas.coords(
                self._pointer_marker_identifier,
                clamped_x_position - 12,
                clamped_y_position - 12,
                clamped_x_position + 12,
                clamped_y_position + 12,
            )
        self._set_source_mode("pointer_pad")
        self._refresh_preview()

    def _build_request_payload_from_user_interface(self) -> dict[str, Any]:
        """Collect one request payload from the current window state."""

        selected_classic_preset_identifier = self._classic_preset_identifiers_by_name.get(
            self._classic_preset_name_variable.get(),
            next(iter(self._classic_preset_names_by_identifier.keys())),
        )
        current_request_payload = self._controller.current_request_payload()
        return {
            "source": {
                "mode": self._source_mode_variable.get(),
                "jsonText": self._json_text_widget.get("1.0", "end").strip(),
                "plainText": self._plain_text_variable.get(),
                "random": {
                    "seed": self._random_seed_variable.get(),
                    "count": self._random_count_variable.get(),
                    "minimum": self._random_minimum_variable.get(),
                    "maximum": self._random_maximum_variable.get(),
                },
                "pointer": {
                    "x": self._last_pointer_x,
                    "y": self._last_pointer_y,
                    "speed": current_request_payload["source"]["pointer"]["speed"],
                },
                "audio": {
                    "deviceFlow": self._audio_device_flow_variable.get(),
                    "deviceIdentifier": self._audio_device_variable.get().split("|", 1)[0].strip(),
                },
            },
            "externalJsonBridge": {
                "host": current_request_payload["externalJsonBridge"]["host"],
                "port": current_request_payload["externalJsonBridge"]["port"],
            },
            "targets": {
                "classic": {
                    "enabled": self._classic_enabled_variable.get(),
                    "host": self._classic_host_variable.get(),
                    "port": self._classic_port_variable.get(),
                },
                "spectrograph": {
                    "enabled": self._spectrograph_enabled_variable.get(),
                    "host": self._spectrograph_host_variable.get(),
                    "port": self._spectrograph_port_variable.get(),
                },
            },
            "classicRender": {
                "presetId": selected_classic_preset_identifier,
                "useEpoch": self._classic_use_epoch_variable.get(),
                "useNoise": self._classic_use_noise_variable.get(),
            },
            "spectrographRender": {
                "barGridSize": self._spectrograph_bar_grid_size_variable.get(),
                "antiAliasing": self._spectrograph_anti_aliasing_variable.get(),
                "shaderStyle": self._spectrograph_shader_style_variable.get(),
            },
            "spectrographRange": {
                "mode": self._spectrograph_range_mode_variable.get(),
                "manualMinimum": self._spectrograph_manual_minimum_variable.get(),
                "manualMaximum": self._spectrograph_manual_maximum_variable.get(),
            },
            "session": {
                "cadenceMs": self._live_cadence_variable.get(),
            },
        }

    def _sync_user_interface_from_request_payload(self, request_payload: dict[str, Any]) -> None:
        """Populate the visible widgets from one normalized request payload."""

        self._source_mode_variable.set(str(request_payload["source"]["mode"]))
        self._json_text_widget.delete("1.0", "end")
        self._json_text_widget.insert("1.0", str(request_payload["source"]["jsonText"]))
        self._plain_text_variable.set(str(request_payload["source"]["plainText"]))
        self._random_seed_variable.set(str(request_payload["source"]["random"]["seed"]))
        self._random_count_variable.set(str(request_payload["source"]["random"]["count"]))
        self._random_minimum_variable.set(str(request_payload["source"]["random"]["minimum"]))
        self._random_maximum_variable.set(str(request_payload["source"]["random"]["maximum"]))
        self._last_pointer_x = float(request_payload["source"]["pointer"]["x"])
        self._last_pointer_y = float(request_payload["source"]["pointer"]["y"])
        self._audio_device_flow_variable.set(str(request_payload["source"]["audio"]["deviceFlow"]))
        self._classic_enabled_variable.set(bool(request_payload["targets"]["classic"]["enabled"]))
        self._classic_host_variable.set(str(request_payload["targets"]["classic"]["host"]))
        self._classic_port_variable.set(str(request_payload["targets"]["classic"]["port"]))
        self._classic_preset_name_variable.set(
            self._classic_preset_names_by_identifier[
                str(request_payload["classicRender"]["presetId"])
            ]
        )
        self._classic_use_epoch_variable.set(bool(request_payload["classicRender"]["useEpoch"]))
        self._classic_use_noise_variable.set(bool(request_payload["classicRender"]["useNoise"]))
        self._spectrograph_enabled_variable.set(
            bool(request_payload["targets"]["spectrograph"]["enabled"])
        )
        self._spectrograph_host_variable.set(
            str(request_payload["targets"]["spectrograph"]["host"])
        )
        self._spectrograph_port_variable.set(
            str(request_payload["targets"]["spectrograph"]["port"])
        )
        current_grid_size = int(request_payload["spectrographRender"]["barGridSize"])
        self._spectrograph_bar_grid_size_variable.set(current_grid_size)
        self._spectrograph_bar_grid_label_variable.set(f"{current_grid_size} x {current_grid_size}")
        self._spectrograph_shader_style_variable.set(
            str(request_payload["spectrographRender"]["shaderStyle"])
        )
        self._spectrograph_anti_aliasing_variable.set(
            bool(request_payload["spectrographRender"]["antiAliasing"])
        )
        self._spectrograph_range_mode_variable.set(
            str(request_payload["spectrographRange"]["mode"])
        )
        self._spectrograph_manual_minimum_variable.set(
            str(request_payload["spectrographRange"]["manualMinimum"])
        )
        self._spectrograph_manual_maximum_variable.set(
            str(request_payload["spectrographRange"]["manualMaximum"])
        )
        current_cadence = int(request_payload["session"]["cadenceMs"])
        self._live_cadence_variable.set(current_cadence)
        self._live_cadence_label_variable.set(f"{current_cadence} ms")
        self._sync_source_mode_buttons()
        self._sync_audio_flow_buttons()
        self._sync_source_mode_visibility()
        self._refresh_audio_devices()
        self._refresh_external_source_status()

    def _sync_source_mode_buttons(self) -> None:
        """Update the visual selected state of the source-mode buttons."""

        selected_source_mode = self._source_mode_variable.get()
        for source_mode_identifier, button_widget in self._source_mode_button_widgets.items():
            is_selected = source_mode_identifier == selected_source_mode
            button_widget.configure(
                bg=ACCENT_COLOR if is_selected else BUTTON_BACKGROUND,
                fg=ACCENT_FOREGROUND if is_selected else TEXT_PRIMARY,
            )

    def _sync_audio_flow_buttons(self) -> None:
        """Update the visual selected state of the audio-flow buttons."""

        selected_audio_device_flow = self._audio_device_flow_variable.get()
        for device_flow, button_widget in self._audio_flow_button_widgets.items():
            is_selected = device_flow == selected_audio_device_flow
            button_widget.configure(
                bg=ACCENT_COLOR if is_selected else BUTTON_BACKGROUND,
                fg=ACCENT_FOREGROUND if is_selected else TEXT_PRIMARY,
            )

    def _sync_source_mode_visibility(self) -> None:
        """Show only the frame that belongs to the chosen source mode."""

        selected_source_mode = self._source_mode_variable.get()
        for source_mode_identifier, frame in self._source_specific_frames.items():
            if source_mode_identifier == selected_source_mode:
                frame.tkraise()

    def _on_spectrograph_bar_grid_changed(self, _: str) -> None:
        """Keep the visible spectrograph grid-size label in sync with the slider."""

        current_grid_size = int(round(self._spectrograph_bar_grid_size_variable.get()))
        self._spectrograph_bar_grid_size_variable.set(current_grid_size)
        self._spectrograph_bar_grid_label_variable.set(f"{current_grid_size} x {current_grid_size}")
        self._refresh_preview()

    def _on_live_cadence_changed(self, _: str) -> None:
        """Keep the visible live-cadence label in sync with the slider."""

        current_live_cadence = int(round(self._live_cadence_variable.get()))
        self._live_cadence_variable.set(current_live_cadence)
        self._live_cadence_label_variable.set(f"{current_live_cadence} ms")

    def _refresh_preview(self) -> None:
        """Build the current preview bundle and update the summary labels."""

        try:
            request_payload = self._build_request_payload_from_user_interface()
            self._controller.replace_request_payload(request_payload)
            self._latest_preview_bundle = self._controller.preview_bundle()
        except Exception as error:
            self._result_status_variable.set(f"Preview failed: {error}")
            return

        source_analysis = self._latest_preview_bundle.collected_source_data.analysis
        self._source_summary_variable.set(
            f"{source_analysis['sourceMode']} produced {source_analysis['valueCount']} values. "
            f"Min={source_analysis['observedMinimum']:.2f}, "
            f"Max={source_analysis['observedMaximum']:.2f}, "
            f"Average={source_analysis['averageValue']:.2f}. "
            f"{source_analysis['details']}"
        )
        available_target_names = []
        if self._latest_preview_bundle.classic_scene_bundle is not None:
            available_target_names.append("scene renderer")
        if self._latest_preview_bundle.spectrograph_build_result is not None:
            available_target_names.append("bar-wall renderer")
        if available_target_names:
            self._result_status_variable.set(
                "Preview ready for " + " and ".join(available_target_names) + "."
            )
        else:
            self._result_status_variable.set("Preview built, but no targets are enabled.")
        self._refresh_external_source_status()
        self._refresh_preview_json_window_contents()

    def _run_health_check(self) -> None:
        """Run health checks for the selected targets."""

        try:
            self._controller.replace_request_payload(
                self._build_request_payload_from_user_interface()
            )
            health_result = self._controller.health_selected_targets()
        except Exception as error:
            self._health_status_variable.set(f"Health check failed before sending: {error}")
            return

        if not health_result["responses"]:
            self._health_status_variable.set("No targets are enabled.")
            return

        self._health_status_variable.set(
            "; ".join(
                f"{target_name}: {response.status} {response.reason}"
                for target_name, response in health_result["responses"].items()
            )
        )

    def _validate_selected_targets(self) -> None:
        """Validate the current preview against the selected targets."""

        try:
            self._controller.replace_request_payload(
                self._build_request_payload_from_user_interface()
            )
            validation_result = self._controller.validate_selected_targets()
            self._latest_preview_bundle = validation_result["previewBundle"]
        except Exception as error:
            self._result_status_variable.set(f"Validation failed before sending: {error}")
            return

        if not validation_result["responses"]:
            self._result_status_variable.set("No targets are enabled.")
            return

        self._result_status_variable.set(
            validation_result["status"]
            + ": "
            + "; ".join(
                f"{target_name}={response.status} {response.reason}"
                for target_name, response in validation_result["responses"].items()
            )
        )
        self._refresh_preview_json_window_contents()

    def _apply_selected_targets(self) -> None:
        """Apply the current preview to the selected targets."""

        try:
            self._controller.replace_request_payload(
                self._build_request_payload_from_user_interface()
            )
            apply_result = self._controller.apply_selected_targets()
            self._latest_preview_bundle = apply_result["previewBundle"]
        except Exception as error:
            self._result_status_variable.set(f"Apply failed before sending: {error}")
            return

        if not apply_result["responses"]:
            self._result_status_variable.set("No targets are enabled.")
            return

        self._result_status_variable.set(
            apply_result["status"]
            + ": "
            + "; ".join(
                f"{target_name}={response.status} {response.reason}"
                for target_name, response in apply_result["responses"].items()
            )
        )
        self._refresh_preview_json_window_contents()

    def _start_live_stream(self) -> None:
        """Start background live streaming for the selected targets."""

        try:
            self._controller.replace_request_payload(
                self._build_request_payload_from_user_interface()
            )
            self._controller.start_live_stream()
            self._live_status_variable.set("Live stream running.")
        except Exception as error:
            self._live_status_variable.set(f"Could not start live stream: {error}")

    def _stop_live_stream(self) -> None:
        """Stop background live streaming."""

        stopped_snapshot = self._controller.stop_live_stream()
        self._live_status_variable.set(
            f"Live stream stopped after {stopped_snapshot['cycles_attempted']} cycles."
        )

    def _reset_to_defaults(self) -> None:
        """Restore the default request payload."""

        default_request_payload = self._controller.reset_to_defaults()
        self._sync_user_interface_from_request_payload(default_request_payload)
        self._refresh_preview()

    def _save_settings_file(self) -> None:
        """Save the current settings document to disk."""

        self._controller.replace_request_payload(self._build_request_payload_from_user_interface())
        if self._settings_file_path is None:
            chosen_file_path = filedialog.asksaveasfilename(
                title="Save settings",
                defaultextension=".json",
                initialfile=DEFAULT_SETTINGS_FILE_NAME,
                filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
            )
            if not chosen_file_path:
                return
            self._settings_file_path = Path(chosen_file_path)
        settings_document = self._controller.settings_document()
        assert self._settings_file_path is not None
        self._settings_file_path.write_text(
            json.dumps(settings_document, indent=2),
            encoding="utf-8",
        )
        self._result_status_variable.set(f"Saved settings to {self._settings_file_path.name}.")

    def _load_settings_file(self) -> None:
        """Load a settings document from disk."""

        chosen_file_path = filedialog.askopenfilename(
            title="Load settings",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not chosen_file_path:
            return
        loaded_document = json.loads(Path(chosen_file_path).read_text(encoding="utf-8"))
        request_payload = self._controller.load_settings_document(loaded_document)
        self._settings_file_path = Path(chosen_file_path)
        self._sync_user_interface_from_request_payload(request_payload)
        self._result_status_variable.set(f"Loaded settings from {self._settings_file_path.name}.")
        self._refresh_preview()

    def _open_preview_json_window(self) -> None:
        """Open a detached preview window showing the target scene JSON payloads."""

        if self._latest_preview_bundle is None:
            self._refresh_preview()
        if self._json_preview_window is not None and self._json_preview_window.winfo_exists():
            self._json_preview_window.deiconify()
            self._json_preview_window.lift()
            self._refresh_preview_json_window_contents()
            return

        self._json_preview_window = tk.Toplevel(self._root_window)
        self._json_preview_window.title("Signal Router preview JSON")
        self._json_preview_window.geometry("1100x820")
        self._json_preview_window.configure(background=WINDOW_BACKGROUND)

        notebook = ttk.Notebook(self._json_preview_window, style="Notebook.TNotebook")
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        for tab_identifier, tab_title in (
            ("classic", "Scene Target"),
            ("spectrograph", "Bar-Wall Target"),
            ("analysis", "Source Analysis"),
        ):
            frame = ttk.Frame(notebook, style="Panel.TFrame", padding=12)
            notebook.add(frame, text=tab_title)
            text_widget = ScrolledText(
                frame,
                wrap="none",
                background=ENTRY_BACKGROUND,
                foreground=TEXT_PRIMARY,
                insertbackground=TEXT_PRIMARY,
                relief="flat",
            )
            text_widget.pack(fill="both", expand=True)
            self._json_preview_text_widgets[tab_identifier] = text_widget

        self._refresh_preview_json_window_contents()

    def _refresh_preview_json_window_contents(self) -> None:
        """Refresh the detached preview window if it currently exists."""

        if (
            self._json_preview_window is None
            or not self._json_preview_window.winfo_exists()
            or self._latest_preview_bundle is None
        ):
            return

        preview_text_by_tab = {
            "classic": json.dumps(
                self._latest_preview_bundle.classic_scene_bundle["scene"]
                if self._latest_preview_bundle.classic_scene_bundle is not None
                else {"status": "disabled"},
                indent=2,
            ),
            "spectrograph": json.dumps(
                self._latest_preview_bundle.spectrograph_build_result.scene
                if self._latest_preview_bundle.spectrograph_build_result is not None
                else {"status": "disabled"},
                indent=2,
            ),
            "analysis": json.dumps(
                self._latest_preview_bundle.collected_source_data.analysis,
                indent=2,
            ),
        }

        for tab_identifier, preview_text in preview_text_by_tab.items():
            text_widget = self._json_preview_text_widgets.get(tab_identifier)
            if text_widget is None:
                continue
            text_widget.configure(state="normal")
            text_widget.delete("1.0", "end")
            text_widget.insert("1.0", preview_text)
            text_widget.configure(state="disabled")

    def _open_activity_log_window(self) -> None:
        """Open the shared desktop activity monitor."""

        if self._activity_log_window is not None:
            try:
                if self._activity_log_window.window_exists():
                    self._activity_log_window.show()
                    return
            except tk.TclError:
                self._activity_log_window = None

        self._activity_log_window = DesktopActivityLogWindow(self._root_window)

    def _schedule_status_refresh(self) -> None:
        """Refresh audio and live-stream status periodically."""

        self._refresh_status_labels()
        self._root_window.after(250, self._schedule_status_refresh)

    def _refresh_status_labels(self) -> None:
        """Refresh labels that reflect continuously changing controller state."""

        audio_signal_snapshot = self._controller.audio_snapshot()
        self._volume_meter_progress_variable.set(float(audio_signal_snapshot.level) * 100.0)
        self._volume_meter_text_variable.set(f"{int(float(audio_signal_snapshot.level) * 100.0)}%")
        if audio_signal_snapshot.last_error:
            self._audio_status_variable.set(audio_signal_snapshot.last_error)
        elif audio_signal_snapshot.capturing:
            self._audio_status_variable.set(
                "Capturing "
                f"{audio_signal_snapshot.device_name or audio_signal_snapshot.device_identifier}."
            )

        live_stream_snapshot = self._controller.live_stream_snapshot()
        self._live_status_variable.set(
            f"{live_stream_snapshot['status']}; cycles={live_stream_snapshot['cycles_attempted']}; "
            f"classic={live_stream_snapshot['classic_frames_applied']}; "
            f"spectrograph={live_stream_snapshot['spectrograph_frames_applied']}"
        )
        self._refresh_external_source_status()

    def _refresh_external_source_status(self) -> None:
        """Refresh the external-feed summary shown in the window."""

        external_source_status = self._controller.external_source_status()
        bridge_status = external_source_status["bridge"]

        if bridge_status["last_error"]:
            self._external_source_status_variable.set(
                f"Bridge error on {bridge_status['host']}:{bridge_status['port']}: "
                f"{bridge_status['last_error']}"
            )
            return

        if not bridge_status["listening"]:
            self._external_source_status_variable.set(
                "The external feed bridge is not listening right now."
            )
            return

        if external_source_status["latest_received_at_utc"]:
            self._external_source_status_variable.set(
                f"Listening on {bridge_status['host']}:{bridge_status['port']}. "
                f"Latest source: {external_source_status['latest_source_label']} at "
                f"{external_source_status['latest_received_at_utc']}."
            )
            return

        self._external_source_status_variable.set(
            f"Listening on {bridge_status['host']}:{bridge_status['port']}. "
            "No helper tool has sent external JSON yet."
        )

    def _on_close_requested(self) -> None:
        """Shut down controller resources before destroying the window."""

        self._controller.close()
        if self._json_preview_window is not None and self._json_preview_window.winfo_exists():
            self._json_preview_window.destroy()
        self._root_window.destroy()


def main() -> None:
    """Launch the native desktop multi-renderer data-source panel."""

    root_window = tk.Tk()
    window = MultiRendererDataSourceWindow(root_window)
    try:
        root_window.mainloop()
    finally:
        try:
            window._controller.close()
        except Exception:
            pass
