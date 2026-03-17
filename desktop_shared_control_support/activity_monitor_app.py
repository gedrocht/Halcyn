"""Standalone launcher for the shared desktop activity monitor.

The activity monitor is useful enough to deserve its own entry point, not just
buttons embedded inside other windows.  That way a person can watch local
bridge traffic, live-stream events, and failures even before opening another
desktop tool.
"""

from __future__ import annotations

import tkinter as tk

from desktop_shared_control_support.activity_log_window import DesktopActivityLogWindow


def main() -> None:
    """Open the shared desktop activity monitor in its own root window."""

    root_window = tk.Tk()
    root_window.withdraw()
    activity_monitor_window = DesktopActivityLogWindow(root_window)
    activity_monitor_window.show()
    root_window.wait_window(activity_monitor_window.tk_window)
    root_window.destroy()


if __name__ == "__main__":
    main()
