"""Shared activity-monitor window for desktop Halcyn tools.

The goal is not to build a full observability platform.  It is to give local
desktop tools one consistent, readable place to inspect recent structured
events such as bridge deliveries, live-stream starts, and renderer submission
failures.
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from desktop_shared_control_support.activity_log import (
    DesktopActivityLogEntry,
    get_default_desktop_activity_log_path,
    read_recent_desktop_activity_entries,
)

WINDOW_BACKGROUND = "#08111b"
PANEL_BACKGROUND = "#102033"
SECTION_BACKGROUND = "#14293f"
ENTRY_BACKGROUND = "#10243a"
TEXT_PRIMARY = "#eff6ff"
TEXT_SECONDARY = "#9fb7d0"
ACCENT_COLOR = "#56c8ff"
ACCENT_SELECTED_COLOR = "#245c82"


class DesktopActivityLogWindow:
    """Display the shared desktop activity journal in a filterable window."""

    def __init__(self, owner_window: tk.Misc, title_text: str = "Halcyn Activity Monitor") -> None:
        self._owner_window = owner_window
        self._journal_file_path = get_default_desktop_activity_log_path()
        self._window = tk.Toplevel(owner_window)
        self._window.title(title_text)
        self._window.geometry("1180x720")
        self._window.minsize(900, 520)
        self._window.configure(background=WINDOW_BACKGROUND)
        self._window.protocol("WM_DELETE_WINDOW", self._close_requested)

        self._search_text_variable = tk.StringVar(value="")
        self._auto_refresh_enabled_variable = tk.BooleanVar(value=True)
        self._status_variable = tk.StringVar(value=f"Reading {self._journal_file_path}")
        self._treeview_item_to_entry: dict[str, DesktopActivityLogEntry] = {}

        self._configure_styles()
        self._build_user_interface()
        self._refresh_entries()
        self._schedule_auto_refresh()

    def window_exists(self) -> bool:
        """Return whether the underlying Tk window still exists.

        Other desktop windows use this helper so they do not have to reach into
        this class's private ``_window`` attribute just to decide whether they
        should reuse the existing monitor or create a new one.
        """

        try:
            return bool(self._window.winfo_exists())
        except tk.TclError:
            return False

    @property
    def tk_window(self) -> tk.Toplevel:
        """Expose the underlying Tk window for the few places that need it."""

        return self._window

    def show(self) -> None:
        """Bring the existing monitor window back to the foreground."""

        if not self.window_exists():
            return
        self._window.deiconify()
        self._window.lift()
        self._window.focus_force()

    def _configure_styles(self) -> None:
        """Apply a dark ttk style so the monitor matches the desktop tools."""

        style = ttk.Style(self._window)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(".", background=WINDOW_BACKGROUND, foreground=TEXT_PRIMARY)
        style.configure("Shell.TFrame", background=WINDOW_BACKGROUND)
        style.configure("Panel.TFrame", background=PANEL_BACKGROUND)
        style.configure("Section.TFrame", background=SECTION_BACKGROUND)
        style.configure("Section.TLabel", background=SECTION_BACKGROUND, foreground=TEXT_PRIMARY)
        style.configure("Body.TLabel", background=SECTION_BACKGROUND, foreground=TEXT_SECONDARY)
        style.configure("Treeview", background=ENTRY_BACKGROUND, foreground=TEXT_PRIMARY)
        style.configure("Treeview.Heading", background=SECTION_BACKGROUND, foreground=TEXT_PRIMARY)
        style.map("Treeview", background=[("selected", ACCENT_SELECTED_COLOR)])
        style.configure("Accent.TButton", background=ACCENT_COLOR, foreground="#04131d")
        style.map("Accent.TButton", background=[("active", ACCENT_SELECTED_COLOR)])
        style.configure("Dark.TCheckbutton", background=SECTION_BACKGROUND, foreground=TEXT_PRIMARY)
        style.configure("Dark.TEntry", fieldbackground=ENTRY_BACKGROUND, foreground=TEXT_PRIMARY)

    def _build_user_interface(self) -> None:
        """Create the filter row, event table, and details viewer."""

        page_shell = ttk.Frame(self._window, style="Shell.TFrame", padding=16)
        page_shell.pack(fill="both", expand=True)
        page_shell.columnconfigure(0, weight=1)
        page_shell.rowconfigure(1, weight=1)

        control_frame = ttk.Frame(page_shell, style="Section.TFrame", padding=12)
        control_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        control_frame.columnconfigure(1, weight=1)

        ttk.Label(
            control_frame,
            text="Filter text",
            style="Body.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Entry(
            control_frame,
            textvariable=self._search_text_variable,
            style="Dark.TEntry",
        ).grid(row=0, column=1, sticky="ew", padx=(10, 12))
        ttk.Button(
            control_frame,
            text="Refresh now",
            style="Accent.TButton",
            command=self._refresh_entries,
        ).grid(row=0, column=2, sticky="ew")
        ttk.Checkbutton(
            control_frame,
            text="Auto refresh",
            variable=self._auto_refresh_enabled_variable,
            style="Dark.TCheckbutton",
        ).grid(row=0, column=3, sticky="e", padx=(12, 0))
        ttk.Label(
            control_frame,
            textvariable=self._status_variable,
            style="Body.TLabel",
            wraplength=1040,
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(10, 0))

        content_frame = ttk.Frame(page_shell, style="Panel.TFrame", padding=12)
        content_frame.grid(row=1, column=0, sticky="nsew")
        content_frame.columnconfigure(0, weight=3)
        content_frame.columnconfigure(1, weight=2)
        content_frame.rowconfigure(0, weight=1)

        table_frame = ttk.Frame(content_frame, style="Section.TFrame", padding=12)
        table_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self._entry_tree = ttk.Treeview(
            table_frame,
            columns=("time", "app", "level", "component", "message"),
            show="headings",
            height=18,
        )
        for column_name, heading_text, width in (
            ("time", "Time", 220),
            ("app", "App", 150),
            ("level", "Level", 90),
            ("component", "Component", 180),
            ("message", "Message", 460),
        ):
            self._entry_tree.heading(column_name, text=heading_text)
            self._entry_tree.column(column_name, width=width, anchor="w")
        self._entry_tree.grid(row=0, column=0, sticky="nsew")
        self._entry_tree.bind("<<TreeviewSelect>>", self._on_tree_selection_changed)

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self._entry_tree.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._entry_tree.configure(yscrollcommand=scrollbar.set)

        details_frame = ttk.Frame(content_frame, style="Section.TFrame", padding=12)
        details_frame.grid(row=0, column=1, sticky="nsew")
        details_frame.columnconfigure(0, weight=1)
        details_frame.rowconfigure(1, weight=1)
        ttk.Label(details_frame, text="Entry details", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self._details_text_widget = ScrolledText(
            details_frame,
            wrap="word",
            background=ENTRY_BACKGROUND,
            foreground=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            font=("Consolas", 10),
        )
        self._details_text_widget.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self._details_text_widget.configure(state="disabled")

    def _refresh_entries(self) -> None:
        """Reload the newest entries from the shared activity journal."""

        search_text = self._search_text_variable.get().strip().lower()
        self._treeview_item_to_entry.clear()
        for existing_item_identifier in self._entry_tree.get_children():
            self._entry_tree.delete(existing_item_identifier)

        recent_entries = read_recent_desktop_activity_entries(limit=400)
        matching_entries = [
            entry
            for entry in recent_entries
            if not search_text
            or search_text in json.dumps(entry.to_dict()).lower()
        ]

        for entry in matching_entries:
            tree_item_identifier = self._entry_tree.insert(
                "",
                "end",
                values=(
                    entry.recorded_at_utc,
                    entry.application_name,
                    entry.level,
                    entry.component_name,
                    entry.message,
                ),
            )
            self._treeview_item_to_entry[tree_item_identifier] = entry

        if matching_entries and not self._entry_tree.selection():
            first_entry_identifier = self._entry_tree.get_children()[0]
            self._entry_tree.selection_set(first_entry_identifier)
            self._entry_tree.focus(first_entry_identifier)
            self._on_tree_selection_changed()

        self._status_variable.set(
            f"Showing {len(matching_entries)} recent events from {self._journal_file_path}"
        )

    def _on_tree_selection_changed(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        """Render the selected event into the details viewer."""

        selected_identifiers = self._entry_tree.selection()
        if not selected_identifiers:
            return
        selected_entry = self._treeview_item_to_entry.get(selected_identifiers[0])
        if selected_entry is None:
            return

        self._details_text_widget.configure(state="normal")
        self._details_text_widget.delete("1.0", "end")
        self._details_text_widget.insert(
            "1.0",
            json.dumps(selected_entry.to_dict(), indent=2),
        )
        self._details_text_widget.configure(state="disabled")

    def _schedule_auto_refresh(self) -> None:
        """Keep the activity monitor fresh while it stays open."""

        if self._auto_refresh_enabled_variable.get():
            self._refresh_entries()
        if self._window.winfo_exists():
            self._window.after(750, self._schedule_auto_refresh)

    def _close_requested(self) -> None:
        """Destroy the monitor window cleanly."""

        self._window.destroy()
