"""Desktop multi-renderer data source panel package.

This package contains a native desktop application whose main job is not
"choose every visual detail" but rather "capture, transform, and route live
data."  It can feed:

- the classic Halcyn renderer presets
- the spectrograph renderer
- or both targets at the same time

Keeping that responsibility in its own package makes the other desktop control
panels easier to understand. They can stay focused on scene editing, while this
tool focuses on data acquisition and data routing.
"""
