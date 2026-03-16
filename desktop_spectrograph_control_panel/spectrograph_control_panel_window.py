"""Tkinter window for the desktop spectrograph control panel.

The controller owns logic. This file owns presentation.

That separation lets beginners read the code in layers:

1. the builder explains how generic JSON becomes a bar grid
2. the controller explains how actions talk to the renderer
3. this window explains how people interact with those actions
"""

from __future__ import annotations

import json
import random
import tkinter as tk
from functools import partial
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from desktop_spectrograph_control_panel.spectrograph_control_panel_controller import (
    DesktopSpectrographControlPanelController,
)
from desktop_spectrograph_control_panel.spectrograph_scene_builder import (
    EXAMPLE_INPUT_DOCUMENTS,
    SpectrographBuildResult,
)

WINDOW_BACKGROUND = "#08111b"
PANEL_BACKGROUND = "#0f1d2d"
SECTION_BACKGROUND = "#13253a"
ACCENT_COLOR = "#4cc3ff"
ACCENT_SELECTED_COLOR = "#1e6b8f"
TEXT_COLOR = "#eff6ff"
SUBTLE_TEXT_COLOR = "#9ab4d1"


class DesktopSpectrographControlPanelWindow:
    """Build and coordinate the native desktop spectrograph operator window."""

    def __init__(
        self,
        root_window: tk.Tk,
        controller: DesktopSpectrographControlPanelController | None = None,
    ) -> None:
        self._root_window = root_window
        self._controller = controller or DesktopSpectrographControlPanelController()
        self._catalog_payload = self._controller.catalog_payload()
        self._scene_preview_window: tk.Toplevel | None = None
        self._scene_preview_text_widget: ScrolledText | None = None
        self._latest_preview_result: SpectrographBuildResult | None = None

        self._root_window.title("Halcyn Spectrograph Control Panel")
        self._root_window.geometry("1600x940")
        self._root_window.minsize(1320, 820)
        self._root_window.configure(background=WINDOW_BACKGROUND)
        self._root_window.protocol("WM_DELETE_WINDOW", self._on_close_requested)

        self._build_tk_variables()
        self._configure_styles()
        self._build_user_interface()
        self._sync_user_interface_from_request_payload(self._controller.current_request_payload())
        self._refresh_preview()
        self._schedule_status_poll()

    def _build_tk_variables(self) -> None:
        """Create the Tk variables that back the visible widgets."""

        self._target_host_variable = tk.StringVar()
        self._target_port_variable = tk.StringVar()
        self._bar_grid_size_variable = tk.IntVar(value=8)
        self._bar_grid_size_label_variable = tk.StringVar(value="8 x 8")
        self._anti_aliasing_variable = tk.BooleanVar(value=True)
        self._shader_style_variable = tk.StringVar(value="heatmap")
        self._range_mode_variable = tk.StringVar(value="automatic")
        self._manual_minimum_variable = tk.StringVar(value="0.0")
        self._manual_maximum_variable = tk.StringVar(value="255.0")
        self._rolling_history_value_count_variable = tk.StringVar(value="4096")
        self._standard_deviation_multiplier_variable = tk.DoubleVar(value=2.0)
        self._standard_deviation_multiplier_label_variable = tk.StringVar(value="2.00")
        self._floor_height_variable = tk.DoubleVar(value=0.08)
        self._floor_height_label_variable = tk.StringVar(value="0.08")
        self._peak_height_variable = tk.DoubleVar(value=3.4)
        self._peak_height_label_variable = tk.StringVar(value="3.40")
        self._live_cadence_variable = tk.IntVar(value=250)
        self._live_cadence_label_variable = tk.StringVar(value="250 ms")
        self._result_status_variable = tk.StringVar(value="Ready.")
        self._health_status_variable = tk.StringVar(value="Renderer health not checked yet.")
        self._statistics_summary_variable = tk.StringVar(
            value="Paste data or load an example to see range and grouping details."
        )
        self._live_stream_status_variable = tk.StringVar(value="Live stream idle.")

    def _configure_styles(self) -> None:
        """Apply a dark-mode-first ttk theme."""

        style = ttk.Style(self._root_window)
        style.theme_use("clam")
        style.configure(".", background=WINDOW_BACKGROUND, foreground=TEXT_COLOR)
        style.configure("Panel.TFrame", background=PANEL_BACKGROUND)
        style.configure("Section.TFrame", background=SECTION_BACKGROUND)
        style.configure(
            "Title.TLabel",
            background=PANEL_BACKGROUND,
            foreground=TEXT_COLOR,
            font=("Segoe UI", 18, "bold"),
        )
        style.configure(
            "Section.TLabel",
            background=SECTION_BACKGROUND,
            foreground=TEXT_COLOR,
            font=("Segoe UI", 11, "bold"),
        )
        style.configure(
            "Body.TLabel",
            background=SECTION_BACKGROUND,
            foreground=SUBTLE_TEXT_COLOR,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Value.TLabel",
            background=SECTION_BACKGROUND,
            foreground=TEXT_COLOR,
            font=("Consolas", 10),
        )
        style.configure(
            "Accent.TButton",
            background=ACCENT_SELECTED_COLOR,
            foreground=TEXT_COLOR,
            borderwidth=0,
            focusthickness=0,
        )
        style.map("Accent.TButton", background=[("active", ACCENT_COLOR)])
        style.configure("Notebook.TNotebook", background=PANEL_BACKGROUND, borderwidth=0)
        style.configure(
            "Notebook.TNotebook.Tab",
            background=SECTION_BACKGROUND,
            foreground=TEXT_COLOR,
            padding=(16, 10),
        )
        style.map(
            "Notebook.TNotebook.Tab",
            background=[("selected", ACCENT_SELECTED_COLOR)],
            foreground=[("selected", TEXT_COLOR)],
        )
        style.configure("Dark.TCheckbutton", background=SECTION_BACKGROUND, foreground=TEXT_COLOR)
        style.configure("Dark.TRadiobutton", background=SECTION_BACKGROUND, foreground=TEXT_COLOR)
        style.configure("Dark.TEntry", fieldbackground="#10243a", foreground=TEXT_COLOR)
        style.configure("Dark.TCombobox", fieldbackground="#10243a", foreground=TEXT_COLOR)
        style.configure(
            "Dark.Horizontal.TScale",
            troughcolor="#17304a",
            background=ACCENT_COLOR,
        )

    def _build_user_interface(self) -> None:
        """Create the main window layout."""

        outer_frame = ttk.Frame(self._root_window, style="Panel.TFrame", padding=16)
        outer_frame.pack(fill="both", expand=True)
        outer_frame.columnconfigure(0, weight=5)
        outer_frame.columnconfigure(1, weight=3)
        outer_frame.rowconfigure(1, weight=1)

        header_frame = ttk.Frame(outer_frame, style="Panel.TFrame")
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        header_frame.columnconfigure(0, weight=1)

        ttk.Label(
            header_frame,
            text="Desktop Spectrograph Control Panel",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header_frame,
            text=(
                "Paste generic JSON, normalize it through a rolling statistical range, "
                "and drive a 3D bar wall in the native renderer."
            ),
            style="Body.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        self._build_left_notebook(outer_frame)
        self._build_right_status_panel(outer_frame)

    def _build_left_notebook(self, parent: ttk.Frame) -> None:
        """Create the main notebook that holds data and render controls."""

        notebook = ttk.Notebook(parent, style="Notebook.TNotebook")
        notebook.grid(row=1, column=0, sticky="nsew", padx=(0, 12))

        data_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=12)
        render_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=12)
        notebook.add(data_tab, text="Data")
        notebook.add(render_tab, text="Render")

        self._build_data_tab(data_tab)
        self._build_render_tab(render_tab)

    def _build_data_tab(self, parent: ttk.Frame) -> None:
        """Create the JSON input area and data-source helper buttons."""

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        example_button_frame = ttk.Frame(parent, style="Section.TFrame", padding=12)
        example_button_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(example_button_frame, text="Example inputs", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            example_button_frame,
            text=(
                "Use these to learn what the transformer does with clean "
                "numbers, mixed nested data, or string-heavy payloads."
            ),
            style="Body.TLabel",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 10))

        for button_index, example_identifier in enumerate(EXAMPLE_INPUT_DOCUMENTS):
            ttk.Button(
                example_button_frame,
                text=example_identifier.replace("_", " ").title(),
                style="Accent.TButton",
                command=partial(self._load_example_input, example_identifier),
            ).grid(row=2, column=button_index, sticky="ew", padx=(0, 8))

        ttk.Button(
            example_button_frame,
            text="Randomize sample",
            style="Accent.TButton",
            command=self._load_random_numeric_sample,
        ).grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(
            example_button_frame,
            text="Load JSON file",
            style="Accent.TButton",
            command=self._load_json_file,
        ).grid(row=3, column=1, sticky="ew", padx=(8, 8), pady=(10, 0))
        ttk.Button(
            example_button_frame,
            text="Open current scene JSON",
            style="Accent.TButton",
            command=self._open_scene_json_window,
        ).grid(row=3, column=2, sticky="ew", pady=(10, 0))

        data_entry_frame = ttk.Frame(parent, style="Section.TFrame", padding=12)
        data_entry_frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        data_entry_frame.columnconfigure(1, weight=1)

        ttk.Label(data_entry_frame, text="Renderer host", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(
            data_entry_frame,
            textvariable=self._target_host_variable,
            style="Dark.TEntry",
            width=22,
        ).grid(row=0, column=1, sticky="w", padx=(10, 16))

        ttk.Label(data_entry_frame, text="Port", style="Section.TLabel").grid(
            row=0, column=2, sticky="w"
        )
        ttk.Entry(
            data_entry_frame,
            textvariable=self._target_port_variable,
            style="Dark.TEntry",
            width=8,
        ).grid(row=0, column=3, sticky="w", padx=(10, 0))

        text_frame = ttk.Frame(parent, style="Section.TFrame", padding=12)
        text_frame.grid(row=2, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(1, weight=1)

        ttk.Label(text_frame, text="Generic JSON input", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            text_frame,
            text=(
                "Numbers are used directly. Strings become UTF-8 byte values. Arrays and objects "
                "are flattened recursively."
            ),
            style="Body.TLabel",
        ).grid(row=0, column=1, sticky="e")

        self._input_json_text_widget = ScrolledText(
            text_frame,
            height=24,
            wrap="word",
            undo=True,
            background="#0c1d2e",
            foreground=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            relief="flat",
            font=("Consolas", 10),
        )
        self._input_json_text_widget.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="nsew",
            pady=(10, 0),
        )
        self._input_json_text_widget.bind("<<Modified>>", self._on_input_text_modified)

    def _build_render_tab(self, parent: ttk.Frame) -> None:
        """Create render, range, and session controls."""

        parent.columnconfigure(0, weight=1)

        render_frame = ttk.Frame(parent, style="Section.TFrame", padding=12)
        render_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        render_frame.columnconfigure(1, weight=1)
        ttk.Label(render_frame, text="Bar-grid rendering", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )

        ttk.Label(render_frame, text="Bar grid size", style="Body.TLabel").grid(
            row=1, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Scale(
            render_frame,
            variable=self._bar_grid_size_variable,
            orient="horizontal",
            from_=2,
            to=24,
            command=self._on_bar_grid_size_changed,
            style="Dark.Horizontal.TScale",
        ).grid(row=1, column=1, sticky="ew", padx=(12, 12), pady=(12, 0))
        ttk.Label(
            render_frame,
            textvariable=self._bar_grid_size_label_variable,
            style="Value.TLabel",
        ).grid(row=1, column=2, sticky="w", pady=(12, 0))

        ttk.Label(render_frame, text="Shader style", style="Body.TLabel").grid(
            row=2, column=0, sticky="w", pady=(12, 0)
        )
        shader_style_combobox = ttk.Combobox(
            render_frame,
            textvariable=self._shader_style_variable,
            values=self._catalog_payload["shaderStyles"],
            state="readonly",
            style="Dark.TCombobox",
            width=18,
        )
        shader_style_combobox.grid(row=2, column=1, sticky="w", padx=(12, 0), pady=(12, 0))

        ttk.Checkbutton(
            render_frame,
            text="Enable anti-aliasing",
            variable=self._anti_aliasing_variable,
            style="Dark.TCheckbutton",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 0))

        ttk.Label(render_frame, text="Bar floor height", style="Body.TLabel").grid(
            row=4, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Scale(
            render_frame,
            variable=self._floor_height_variable,
            orient="horizontal",
            from_=0.02,
            to=1.0,
            command=self._on_floor_height_changed,
            style="Dark.Horizontal.TScale",
        ).grid(row=4, column=1, sticky="ew", padx=(12, 12), pady=(12, 0))
        ttk.Label(
            render_frame,
            textvariable=self._floor_height_label_variable,
            style="Value.TLabel",
        ).grid(row=4, column=2, sticky="w", pady=(12, 0))

        ttk.Label(render_frame, text="Bar peak height", style="Body.TLabel").grid(
            row=5, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Scale(
            render_frame,
            variable=self._peak_height_variable,
            orient="horizontal",
            from_=0.5,
            to=8.0,
            command=self._on_peak_height_changed,
            style="Dark.Horizontal.TScale",
        ).grid(row=5, column=1, sticky="ew", padx=(12, 12), pady=(12, 0))
        ttk.Label(
            render_frame,
            textvariable=self._peak_height_label_variable,
            style="Value.TLabel",
        ).grid(row=5, column=2, sticky="w", pady=(12, 0))

        range_frame = ttk.Frame(parent, style="Section.TFrame", padding=12)
        range_frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        range_frame.columnconfigure(1, weight=1)
        self._manual_range_entry_widgets: list[ttk.Entry] = []
        ttk.Label(range_frame, text="Range normalization", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Radiobutton(
            range_frame,
            text="Automatic (rolling mean ± deviation)",
            value="automatic",
            variable=self._range_mode_variable,
            style="Dark.TRadiobutton",
            command=self._refresh_range_mode_widgets,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Radiobutton(
            range_frame,
            text="Manual minimum/maximum",
            value="manual",
            variable=self._range_mode_variable,
            style="Dark.TRadiobutton",
            command=self._refresh_range_mode_widgets,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

        ttk.Label(range_frame, text="Manual minimum", style="Body.TLabel").grid(
            row=3, column=0, sticky="w", pady=(12, 0)
        )
        manual_minimum_entry = ttk.Entry(
            range_frame,
            textvariable=self._manual_minimum_variable,
            style="Dark.TEntry",
            width=12,
        )
        manual_minimum_entry.grid(row=3, column=1, sticky="w", pady=(12, 0))
        ttk.Label(range_frame, text="Manual maximum", style="Body.TLabel").grid(
            row=3, column=2, sticky="w", pady=(12, 0)
        )
        manual_maximum_entry = ttk.Entry(
            range_frame,
            textvariable=self._manual_maximum_variable,
            style="Dark.TEntry",
            width=12,
        )
        manual_maximum_entry.grid(row=3, column=3, sticky="w", pady=(12, 0))
        self._manual_range_entry_widgets.extend([manual_minimum_entry, manual_maximum_entry])

        ttk.Label(range_frame, text="Rolling history values", style="Body.TLabel").grid(
            row=4, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Entry(
            range_frame,
            textvariable=self._rolling_history_value_count_variable,
            style="Dark.TEntry",
            width=12,
        ).grid(row=4, column=1, sticky="w", pady=(12, 0))

        ttk.Label(range_frame, text="Std-dev multiplier", style="Body.TLabel").grid(
            row=5, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Scale(
            range_frame,
            variable=self._standard_deviation_multiplier_variable,
            orient="horizontal",
            from_=0.1,
            to=6.0,
            command=self._on_standard_deviation_multiplier_changed,
            style="Dark.Horizontal.TScale",
        ).grid(row=5, column=1, columnspan=2, sticky="ew", padx=(12, 12), pady=(12, 0))
        ttk.Label(
            range_frame,
            textvariable=self._standard_deviation_multiplier_label_variable,
            style="Value.TLabel",
        ).grid(row=5, column=3, sticky="w", pady=(12, 0))

        session_frame = ttk.Frame(parent, style="Section.TFrame", padding=12)
        session_frame.grid(row=2, column=0, sticky="ew")
        ttk.Label(session_frame, text="Live session", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(session_frame, text="Live cadence", style="Body.TLabel").grid(
            row=1, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Scale(
            session_frame,
            variable=self._live_cadence_variable,
            orient="horizontal",
            from_=40,
            to=2000,
            command=self._on_live_cadence_changed,
            style="Dark.Horizontal.TScale",
        ).grid(row=1, column=1, sticky="ew", padx=(12, 12), pady=(12, 0))
        ttk.Label(
            session_frame,
            textvariable=self._live_cadence_label_variable,
            style="Value.TLabel",
        ).grid(row=1, column=2, sticky="w", pady=(12, 0))
        session_frame.columnconfigure(1, weight=1)

    def _build_right_status_panel(self, parent: ttk.Frame) -> None:
        """Create the status column with actions and summary readouts."""

        right_frame = ttk.Frame(parent, style="Panel.TFrame")
        right_frame.grid(row=1, column=1, sticky="nsew")
        right_frame.columnconfigure(0, weight=1)

        action_frame = ttk.Frame(right_frame, style="Section.TFrame", padding=12)
        action_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        action_frame.columnconfigure((0, 1), weight=1)
        ttk.Label(action_frame, text="Actions", style="Section.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )

        action_buttons = [
            ("Health", self._run_health_check),
            ("Validate", self._validate_current_scene),
            ("Apply", self._apply_current_scene),
            ("Start live", self._start_live_stream),
            ("Stop live", self._stop_live_stream),
            ("Revert defaults", self._revert_defaults),
            ("Load settings", self._load_settings_document),
            ("Save settings", self._save_settings_document),
        ]
        for button_index, (button_label, button_command) in enumerate(action_buttons):
            ttk.Button(
                action_frame,
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

        summary_frame = ttk.Frame(right_frame, style="Section.TFrame", padding=12)
        summary_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        summary_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)

        ttk.Label(summary_frame, text="Live summary", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            summary_frame,
            textvariable=self._health_status_variable,
            style="Body.TLabel",
            wraplength=380,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(
            summary_frame,
            textvariable=self._result_status_variable,
            style="Body.TLabel",
            wraplength=380,
            justify="left",
        ).grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(
            summary_frame,
            textvariable=self._live_stream_status_variable,
            style="Body.TLabel",
            wraplength=380,
            justify="left",
        ).grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(
            summary_frame,
            textvariable=self._statistics_summary_variable,
            style="Body.TLabel",
            wraplength=380,
            justify="left",
        ).grid(row=4, column=0, sticky="nsew", pady=(12, 0))

    def _load_example_input(self, example_identifier: str) -> None:
        """Replace the input JSON text with one built-in example."""

        example_json_text = EXAMPLE_INPUT_DOCUMENTS[example_identifier]
        self._replace_input_json_text(example_json_text)

    def _load_random_numeric_sample(self) -> None:
        """Generate one fresh numeric sample so the operator can see the bar wall move."""

        random_values = [round(random.uniform(-6.0, 18.0), 3) for _ in range(96)]
        random_payload = {"values": random_values, "label": "Randomized sample"}
        self._replace_input_json_text(json.dumps(random_payload, indent=2))

    def _load_json_file(self) -> None:
        """Load one JSON document from disk into the data editor."""

        selected_path = filedialog.askopenfilename(
            title="Open spectrograph input JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not selected_path:
            return
        json_text = Path(selected_path).read_text(encoding="utf-8")
        self._replace_input_json_text(json_text)

    def _replace_input_json_text(self, json_text: str) -> None:
        """Replace the editor contents and immediately refresh the preview."""

        self._input_json_text_widget.delete("1.0", "end")
        self._input_json_text_widget.insert("1.0", json_text)
        self._refresh_preview()

    def _on_input_text_modified(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        """Refresh the preview after user edits to the source JSON."""

        if self._input_json_text_widget.edit_modified():
            self._input_json_text_widget.edit_modified(False)
            self._refresh_preview()

    def _on_bar_grid_size_changed(self, _value: str) -> None:
        self._bar_grid_size_label_variable.set(
            f"{self._bar_grid_size_variable.get()} x {self._bar_grid_size_variable.get()}"
        )
        self._refresh_preview()

    def _on_standard_deviation_multiplier_changed(self, _value: str) -> None:
        self._standard_deviation_multiplier_label_variable.set(
            f"{self._standard_deviation_multiplier_variable.get():.2f}"
        )
        self._refresh_preview()

    def _on_floor_height_changed(self, _value: str) -> None:
        self._floor_height_label_variable.set(f"{self._floor_height_variable.get():.2f}")
        self._refresh_preview()

    def _on_peak_height_changed(self, _value: str) -> None:
        self._peak_height_label_variable.set(f"{self._peak_height_variable.get():.2f}")
        self._refresh_preview()

    def _on_live_cadence_changed(self, _value: str) -> None:
        self._live_cadence_label_variable.set(f"{self._live_cadence_variable.get()} ms")

    def _collect_request_payload_from_user_interface(self) -> dict[str, Any]:
        """Collect one full request payload from the visible widgets."""

        return {
            "target": {
                "host": self._target_host_variable.get(),
                "port": self._safe_int(self._target_port_variable.get(), 8090),
            },
            "data": {
                "jsonText": self._input_json_text_widget.get("1.0", "end").strip(),
            },
            "render": {
                "barGridSize": self._bar_grid_size_variable.get(),
                "antiAliasing": self._anti_aliasing_variable.get(),
                "shaderStyle": self._shader_style_variable.get(),
                "floorHeight": self._floor_height_variable.get(),
                "peakHeight": self._peak_height_variable.get(),
            },
            "range": {
                "mode": self._range_mode_variable.get(),
                "manualMinimum": self._safe_float(self._manual_minimum_variable.get(), 0.0),
                "manualMaximum": self._safe_float(self._manual_maximum_variable.get(), 255.0),
                "rollingHistoryValueCount": self._safe_int(
                    self._rolling_history_value_count_variable.get(),
                    4096,
                ),
                "standardDeviationMultiplier": self._standard_deviation_multiplier_variable.get(),
            },
            "session": {
                "cadenceMs": self._live_cadence_variable.get(),
            },
        }

    def _sync_user_interface_from_request_payload(self, request_payload: dict[str, Any]) -> None:
        """Populate the widgets from one normalized request payload."""

        self._target_host_variable.set(str(request_payload["target"]["host"]))
        self._target_port_variable.set(str(request_payload["target"]["port"]))
        self._replace_input_json_text(str(request_payload["data"]["jsonText"]))
        self._bar_grid_size_variable.set(int(request_payload["render"]["barGridSize"]))
        self._bar_grid_size_label_variable.set(
            f"{self._bar_grid_size_variable.get()} x {self._bar_grid_size_variable.get()}"
        )
        self._anti_aliasing_variable.set(bool(request_payload["render"]["antiAliasing"]))
        self._shader_style_variable.set(str(request_payload["render"]["shaderStyle"]))
        self._range_mode_variable.set(str(request_payload["range"]["mode"]))
        self._manual_minimum_variable.set(str(request_payload["range"]["manualMinimum"]))
        self._manual_maximum_variable.set(str(request_payload["range"]["manualMaximum"]))
        self._rolling_history_value_count_variable.set(
            str(request_payload["range"]["rollingHistoryValueCount"])
        )
        self._standard_deviation_multiplier_variable.set(
            float(request_payload["range"]["standardDeviationMultiplier"])
        )
        self._standard_deviation_multiplier_label_variable.set(
            f"{self._standard_deviation_multiplier_variable.get():.2f}"
        )
        self._floor_height_variable.set(float(request_payload["render"]["floorHeight"]))
        self._floor_height_label_variable.set(f"{self._floor_height_variable.get():.2f}")
        self._peak_height_variable.set(float(request_payload["render"]["peakHeight"]))
        self._peak_height_label_variable.set(f"{self._peak_height_variable.get():.2f}")
        self._live_cadence_variable.set(int(request_payload["session"]["cadenceMs"]))
        self._live_cadence_label_variable.set(f"{self._live_cadence_variable.get()} ms")
        self._refresh_range_mode_widgets()

    def _refresh_range_mode_widgets(self) -> None:
        """Enable or disable manual range entries based on the selected mode."""

        state = "normal" if self._range_mode_variable.get() == "manual" else "disabled"
        for manual_range_entry in self._manual_range_entry_widgets:
            manual_range_entry.configure(state=state)
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        """Push UI values into the controller and rebuild the current preview."""

        try:
            request_payload = self._collect_request_payload_from_user_interface()
            self._controller.replace_request_payload(request_payload)
            self._latest_preview_result = self._controller.preview_scene_result()
        except Exception as error:
            self._latest_preview_result = None
            self._result_status_variable.set(f"Preview error: {error}")
            self._statistics_summary_variable.set(
                "The current JSON input or range settings could not be turned into a preview."
            )
            self._update_scene_json_window()
            return

        analysis = self._latest_preview_result.analysis
        self._result_status_variable.set(
            f"Preview ready: {analysis['sourceValueCount']} source values -> "
            f"{analysis['barCount']} bars."
        )
        self._statistics_summary_variable.set(
            f"Range mode: {analysis['rangeMode']}. "
            f"Observed min/max: {analysis['observedMinimum']:.3f} .. "
            f"{analysis['observedMaximum']:.3f}. "
            f"Active min/max: {analysis['activeRangeMinimum']:.3f} .. "
            f"{analysis['activeRangeMaximum']:.3f}. "
            f"Rolling mean/std-dev: {analysis['rollingMean']:.3f} / "
            f"{analysis['rollingStandardDeviation']:.3f}. "
            f"Group size: {analysis['groupSize']}."
        )
        self._update_scene_json_window()

    def _run_health_check(self) -> None:
        """Check whether the target spectrograph renderer is reachable."""

        response = self._controller.health()
        if response.ok:
            self._health_status_variable.set(
                f"Renderer reachable: HTTP {response.status} {response.reason}."
            )
        else:
            self._health_status_variable.set(
                f"Renderer not reachable: HTTP {response.status} {response.reason}."
            )

    def _validate_current_scene(self) -> None:
        """Validate the current preview scene with the live renderer API."""

        result = self._controller.validate_current_scene()
        response = result["response"]
        if response.status == 200:
            self._result_status_variable.set("Validation succeeded. The scene is acceptable.")
        else:
            self._result_status_variable.set(
                f"Validation failed: HTTP {response.status} {response.reason}."
            )

    def _apply_current_scene(self) -> None:
        """Apply the current spectrograph scene once."""

        result = self._controller.apply_current_scene()
        response = result["response"]
        if response.status == 202:
            analysis = result["buildResult"].analysis
            self._result_status_variable.set(
                f"Applied spectrograph scene: {analysis['sourceValueCount']} source values, "
                f"{analysis['barCount']} bars."
            )
        else:
            self._result_status_variable.set(
                f"Apply failed: HTTP {response.status} {response.reason}."
            )

    def _start_live_stream(self) -> None:
        """Start repeatedly applying the spectrograph scene."""

        self._controller.replace_request_payload(self._collect_request_payload_from_user_interface())
        live_stream_snapshot = self._controller.start_live_stream()
        self._live_stream_status_variable.set(
            f"Live stream {live_stream_snapshot['status']} "
            f"at {live_stream_snapshot['cadence_ms']} ms."
        )

    def _stop_live_stream(self) -> None:
        """Stop the live-stream worker."""

        live_stream_snapshot = self._controller.stop_live_stream()
        self._live_stream_status_variable.set(f"Live stream {live_stream_snapshot['status']}.")

    def _revert_defaults(self) -> None:
        """Restore the default control payload and refresh the preview."""

        request_payload = self._controller.reset_to_defaults()
        self._sync_user_interface_from_request_payload(request_payload)
        self._refresh_preview()

    def _save_settings_document(self) -> None:
        """Save the current settings document to disk."""

        selected_path = filedialog.asksaveasfilename(
            title="Save spectrograph settings",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not selected_path:
            return

        settings_document = self._controller.settings_document()
        Path(selected_path).write_text(json.dumps(settings_document, indent=2), encoding="utf-8")
        self._result_status_variable.set(f"Saved settings to {selected_path}")

    def _load_settings_document(self) -> None:
        """Load a settings document from disk and refresh the UI."""

        selected_path = filedialog.askopenfilename(
            title="Load spectrograph settings",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not selected_path:
            return

        settings_document = json.loads(Path(selected_path).read_text(encoding="utf-8"))
        request_payload = self._controller.load_settings_document(settings_document)
        self._sync_user_interface_from_request_payload(request_payload)
        self._refresh_preview()
        self._result_status_variable.set(f"Loaded settings from {selected_path}")

    def _open_scene_json_window(self) -> None:
        """Open a detached read-only window that shows the current scene JSON."""

        if self._scene_preview_window is not None and self._scene_preview_window.winfo_exists():
            self._scene_preview_window.deiconify()
            self._scene_preview_window.lift()
            self._update_scene_json_window()
            return

        self._scene_preview_window = tk.Toplevel(self._root_window)
        self._scene_preview_window.title("Current Spectrograph Scene JSON")
        self._scene_preview_window.geometry("780x760")
        self._scene_preview_window.configure(background=WINDOW_BACKGROUND)
        self._scene_preview_window.protocol(
            "WM_DELETE_WINDOW",
            self._on_scene_preview_window_closed,
        )

        preview_frame = ttk.Frame(self._scene_preview_window, style="Panel.TFrame", padding=12)
        preview_frame.pack(fill="both", expand=True)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(1, weight=1)

        ttk.Label(
            preview_frame,
            text="Current spectrograph scene JSON",
            style="Section.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            preview_frame,
            text="Copy JSON",
            style="Accent.TButton",
            command=self._copy_scene_json_to_clipboard,
        ).grid(row=0, column=1, sticky="e")

        self._scene_preview_text_widget = ScrolledText(
            preview_frame,
            wrap="word",
            background="#0c1d2e",
            foreground=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            relief="flat",
            font=("Consolas", 10),
        )
        self._scene_preview_text_widget.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="nsew",
            pady=(10, 0),
        )
        self._scene_preview_text_widget.configure(state="disabled")
        self._update_scene_json_window()

    def _update_scene_json_window(self) -> None:
        """Refresh the detached JSON preview window if it is open."""

        if (
            self._scene_preview_window is None
            or self._scene_preview_text_widget is None
            or not self._scene_preview_window.winfo_exists()
        ):
            return

        if self._latest_preview_result is None:
            preview_text = "No valid scene preview is available right now."
        else:
            preview_text = json.dumps(self._latest_preview_result.scene, indent=2)

        self._scene_preview_text_widget.configure(state="normal")
        self._scene_preview_text_widget.delete("1.0", "end")
        self._scene_preview_text_widget.insert("1.0", preview_text)
        self._scene_preview_text_widget.configure(state="disabled")

    def _copy_scene_json_to_clipboard(self) -> None:
        """Copy the current preview scene JSON to the clipboard."""

        if self._latest_preview_result is None:
            messagebox.showinfo("Copy JSON", "There is no valid preview scene to copy yet.")
            return

        self._root_window.clipboard_clear()
        self._root_window.clipboard_append(json.dumps(self._latest_preview_result.scene, indent=2))
        self._result_status_variable.set("Copied the current scene JSON to the clipboard.")

    def _on_scene_preview_window_closed(self) -> None:
        """Forget the detached preview window after it closes."""

        if self._scene_preview_window is not None:
            self._scene_preview_window.destroy()
        self._scene_preview_window = None
        self._scene_preview_text_widget = None

    def _schedule_status_poll(self) -> None:
        """Keep the live-stream status text current while the window is open."""

        self._poll_live_stream_state()
        self._root_window.after(250, self._schedule_status_poll)

    def _poll_live_stream_state(self) -> None:
        """Refresh the live-stream summary label from the controller."""

        live_stream_snapshot = self._controller.live_stream_snapshot()
        self._live_stream_status_variable.set(
            f"Live stream {live_stream_snapshot['status']}. "
            f"Frames applied: {live_stream_snapshot['frames_applied']}. "
            f"Frames failed: {live_stream_snapshot['frames_failed']}."
        )

    def _on_close_requested(self) -> None:
        """Shut down worker threads cleanly before the process exits."""

        self._controller.close()
        self._root_window.destroy()

    @staticmethod
    def _safe_int(value: Any, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _safe_float(value: Any, fallback: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback


def main() -> None:
    """Launch the native desktop spectrograph control panel.

    This small wrapper keeps process startup easy to discover from the command
    line while leaving the interesting UI behavior inside the window class
    itself. Beginners reading the code can treat this as the "create Tk, build
    window, start event loop" step.
    """

    root_window = tk.Tk()
    DesktopSpectrographControlPanelWindow(root_window)
    root_window.mainloop()
