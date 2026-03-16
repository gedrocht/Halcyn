"""Module entry point for the desktop spectrograph control panel.

Keeping the executable wrapper tiny makes it easy to launch the package with
`python -m desktop_spectrograph_control_panel` while still keeping the real
window-building logic in a separate, more testable module.
"""

from __future__ import annotations

from desktop_spectrograph_control_panel.spectrograph_control_panel_window import main

if __name__ == "__main__":
    main()
