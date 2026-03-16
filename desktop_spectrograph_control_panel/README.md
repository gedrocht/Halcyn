# Desktop Spectrograph Control Panel

The Desktop Spectrograph Control Panel is Halcyn's native operator console for
the dedicated spectrograph-style renderer.

It exists for the moments when a normal scene editor is not enough and you want
to answer a different question instead:

"Given almost any JSON payload, how can I turn it into a readable 3D wall of
bars that adapts to changing data ranges over time?"

This package answers that by combining three ideas:

- flatten very generic JSON into one numeric stream
- normalize that stream against a rolling statistical history
- convert the grouped values into a 3D `N x N` bar scene that the native
  renderer already knows how to draw

## Launch it

Start the dedicated spectrograph renderer:

```powershell
.\scripts\launch-halcyn-spectrograph-app.ps1
```

Then start the desktop control panel:

```powershell
.\scripts\launch-desktop-spectrograph-control-panel.ps1
```

## What it can control

- renderer host and port
- live-stream cadence, with a visible millisecond readout beside the slider
- bar-grid density through the `N x N` bar count
- shader presentation style:
  - `standard`
  - `neon`
  - `heatmap`
- multisample anti-aliasing on or off
- automatic or manual range normalization
- rolling-history length for the adaptive range model
- floor height and peak height for the bar geometry
- example payloads, file loading, and randomized numeric input
- preview, validate, apply, and continuous live streaming
- saving and loading settings as JSON
- opening the fully generated renderer scene JSON in its own window

## How the data transformation works

The spectrograph builder intentionally works in small beginner-readable stages:

1. Parse the operator-supplied JSON text.
2. Flatten nested values into one numeric stream.
3. Convert strings into UTF-8 byte values so text can still drive the bars.
4. Append the new values to a rolling history buffer.
5. Compute observed min/max, mean, and standard deviation.
6. Choose either:
   - an automatic range based on mean and standard deviation
   - or a manual minimum/maximum range from the UI
7. Group the source values into exactly `N x N` equally sized bar buckets.
8. Normalize each grouped value into a `0..1` intensity.
9. Build one colored 3D bar prism per grouped value.

That means the renderer still receives ordinary Halcyn scene JSON. The new
logic lives in the operator-side transformation layer, not in a special-case
rendering protocol.

## Main pieces

- `spectrograph_scene_builder.py`
  - Generic JSON flattening, rolling statistics, grouping, normalization, and
    final 3D bar-scene creation.
- `spectrograph_control_panel_controller.py`
  - Non-visual orchestration for preview, validate, apply, live stream, and
    settings documents.
- `spectrograph_control_panel_window.py`
  - Tkinter UI widgets and operator interaction flow.

## Helpful external references

- Tkinter overview:
  [docs.python.org/3/library/tkinter.html](https://docs.python.org/3/library/tkinter.html)
- Tk themed widgets:
  [docs.python.org/3/library/tkinter.ttk.html](https://docs.python.org/3/library/tkinter.ttk.html)
- `ScrolledText`:
  [docs.python.org/3/library/tkinter.scrolledtext.html](https://docs.python.org/3/library/tkinter.scrolledtext.html)
- File dialogs:
  [docs.python.org/3/library/dialog.html#tkinter.filedialog](https://docs.python.org/3/library/dialog.html#tkinter.filedialog)
- `json` module:
  [docs.python.org/3/library/json.html](https://docs.python.org/3/library/json.html)
- `threading`:
  [docs.python.org/3/library/threading.html](https://docs.python.org/3/library/threading.html)
- `statistics` concepts for mean and standard deviation:
  [docs.python.org/3/library/statistics.html](https://docs.python.org/3/library/statistics.html)
- UTF-8 encoding basics:
  [docs.python.org/3/library/stdtypes.html#str.encode](https://docs.python.org/3/library/stdtypes.html#str.encode)

## Testing and quality gates

The desktop spectrograph suite is held to the same Python quality bar as the
other maintained operator tools:

- `.\scripts\lint-desktop-spectrograph-control-panel.ps1`
- `.\scripts\typecheck-desktop-spectrograph-control-panel.ps1`
- `.\scripts\test-desktop-spectrograph-control-panel.ps1`
- `.\scripts\measure-desktop-spectrograph-control-panel-coverage.ps1`

The repo-level pass is still:

```powershell
.\scripts\run-all-quality-checks.ps1 -Configuration Debug
```
