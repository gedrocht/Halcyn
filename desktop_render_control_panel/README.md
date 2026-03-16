# Desktop Render Control Panel

The Desktop Render Control Panel is Halcyn's native operator console.

It exists for the cases where the browser tools are helpful, but not quite enough:

- choosing a real local audio input device
- keeping a native control surface open beside the renderer window
- switching between 2D and 3D presets instantly
- previewing, validating, applying, and live-streaming scenes from one desktop app
- saving and loading operator setups as JSON
- reverting the current preset back to its default control values
- seeing the selected colors and pointer motion reflected immediately in the UI

## Launch it

```powershell
.\scripts\launch-desktop-render-control-panel.ps1
```

## What it can control

- renderer host and port
- live-stream cadence
- 2D and 3D preset selection through persistent toggle buttons
- density, point size, line width, speed, gain, and manual drive with friendlier slider rounding
- background, primary, and secondary colors with live swatches
- unix time, deterministic noise, pointer, and audio signal sources
- a larger native pointer pad for local motion control
- real local audio device selection through the optional `sounddevice` package

## What changed in the polished version

- the window now uses a dark-mode-first theme instead of a plain default Tk look
- the 2D/3D and preset selectors are button groups that stay visibly selected
- integer-valued sliders snap to whole numbers, and float-valued sliders snap to practical increments
- the current color choices are shown with live swatches instead of only text fields
- settings can be saved to and loaded from JSON files
- Windows machines without `sounddevice` can still list input devices through a waveIn fallback, even though real capture still requires `sounddevice`

## Main pieces

- `desktop_control_panel_window.py`: the Tkinter window and widgets
- `desktop_control_panel_controller.py`: non-visual orchestration for payload merging, validation, apply, and live streaming
- `desktop_control_scene_builder.py`: preset catalog plus 2D/3D scene generation
- `audio_input_service.py`: audio backend detection, device enumeration, and band analysis
- `render_api_client.py`: focused HTTP client for Halcyn's validation, apply, and health routes

## Helpful external references

- Tkinter overview: [docs.python.org/3/library/tkinter.html](https://docs.python.org/3/library/tkinter.html)
- Tk themed widgets (`ttk`): [docs.python.org/3/library/tkinter.ttk.html](https://docs.python.org/3/library/tkinter.ttk.html)
- `tkinter.filedialog`: [docs.python.org/3/library/dialog.html#tkinter.filedialog](https://docs.python.org/3/library/dialog.html#tkinter.filedialog)
- `urllib.request`: [docs.python.org/3/library/urllib.request.html](https://docs.python.org/3/library/urllib.request.html)
- `sounddevice`: [python-sounddevice.readthedocs.io](https://python-sounddevice.readthedocs.io/)
- `ctypes`: [docs.python.org/3/library/ctypes.html](https://docs.python.org/3/library/ctypes.html)
- `waveInGetNumDevs`: [learn.microsoft.com/windows/win32/api/mmeapi/nf-mmeapi-waveingetnumdevs](https://learn.microsoft.com/windows/win32/api/mmeapi/nf-mmeapi-waveingetnumdevs)
- `waveInGetDevCapsW`: [learn.microsoft.com/windows/win32/api/mmeapi/nf-mmeapi-waveingetdevcapsw](https://learn.microsoft.com/windows/win32/api/mmeapi/nf-mmeapi-waveingetdevcapsw)
- Threading basics: [docs.python.org/3/library/threading.html](https://docs.python.org/3/library/threading.html)

These are the main external APIs the desktop panel leans on. The inline
docstrings in the package point back to the same libraries so a beginner can
move from "what this Halcyn code is doing" to "what the underlying library API
means" without guessing where to read next.

## Testing and quality gates

The desktop panel is held to the same Python quality bar as the browser tooling:

- `.\scripts\lint-desktop-render-control-panel.ps1`
- `.\scripts\typecheck-desktop-render-control-panel.ps1`
- `.\scripts\test-desktop-render-control-panel.ps1`
- `.\scripts\measure-desktop-render-control-panel-coverage.ps1`

The full repo-level pass is still:

```powershell
.\scripts\run-all-quality-checks.ps1 -Configuration Debug
```

## Audio dependency note

Local audio capture is optional. If the `sounddevice` package is unavailable, the desktop panel still launches and the rest of the controls still work. On Windows, the panel will still try to list input devices through the built-in waveIn API so the operator can at least see what hardware is present before installing `sounddevice`.

Install the optional dependency with:

```powershell
python -m pip install sounddevice
```
