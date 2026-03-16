"""Module entry point for the desktop render control panel.

Keeping this tiny wrapper module means the package can be launched with
`python -m desktop_render_control_panel` while the actual window-creation logic
still lives in a more easily testable module.
"""

from __future__ import annotations

from desktop_render_control_panel.desktop_control_panel_window import main

if __name__ == "__main__":
    main()
