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
- opening the full scene JSON in a separate window only when you want to inspect it

## How it now fits beside the shared data-source tool

This panel is intentionally no longer the "do every desktop job" app.

The responsibilities are now split more clearly:

- this panel focuses on choosing classic Halcyn scene presets and tuning how
  those presets look
- the shared
  [desktop multi-renderer data source panel](/Y:/Halcyn/desktop_multi_renderer_data_source_panel/README.md)
  focuses on capturing or generating data and routing it into one or both
  renderer families

That separation makes both apps easier to understand:

- if you want to sculpt the classic preset itself, use this panel
- if you want one source of live data to drive multiple renderer targets, use
  the shared data-source panel

## How to reach the supported workflow

```powershell
.\scripts\launch-visualizer-studio.ps1
```

This package stays in the repository because Visualizer Studio still reuses its
scene-building and audio-capture helpers internally. It is no longer a
separately launched public app.

## What it can control

- renderer host and port
- live-stream cadence
- a visible live-cadence value label, so you can see the exact millisecond number beside the slider
- 2D and 3D preset selection through persistent toggle buttons
- density, point size, line width, speed, gain, and manual drive with friendlier slider rounding
- background, primary, and secondary colors with live swatches
- unix time, deterministic noise, pointer, and audio signal sources
- a larger native pointer pad for local motion control
- real local microphone selection through the optional `sounddevice` package
- real desktop output-loopback selection through the optional `soundcard` package
- a source-type toggle that defaults to output sources and can switch to microphones
- a live volume monitor that gives one easy-to-read loudness signal
- a roomier right-hand diagnostics column that holds audio controls and pointer input

## What changed in the polished version

- the window now uses a dark-mode-first theme instead of a plain default Tk look
- the 2D/3D and preset selectors are button groups that stay visibly selected with higher-contrast text
- integer-valued sliders snap to whole numbers, and float-valued sliders snap to practical increments
- the current color choices are shown with live swatches instead of only text fields
- the full JSON preview opens in a separate window so the main panel fits typical desktop screens more comfortably
- the detached JSON preview window includes a `Copy JSON` button for quick pasting into notes, tests, or API experiments
- settings can be saved to and loaded from JSON files
- Windows machines without `sounddevice` can still list input devices through a waveIn fallback, even though real microphone capture still requires `sounddevice`
- desktop output-loopback capture now uses the optional `soundcard` package instead of relying on unsupported `sounddevice` loopback settings
- the prerequisite report now calls out both optional audio packages directly so audio setup is easier to diagnose

## Main pieces

- `desktop_control_panel_window.py`: the Tkinter window and widgets
- `desktop_control_panel_controller.py`: non-visual orchestration for payload merging, validation, apply, and live streaming
- `desktop_control_scene_builder.py`: preset catalog plus 2D/3D scene generation
- `audio_input_service.py`: the underlying audio backend detection, device enumeration, and band analysis implementation that is now also re-exported through the shared desktop support package
- `render_api_client.py`: the underlying renderer HTTP client implementation that is now also re-exported through the shared desktop support package

The controller itself now imports the shared desktop support package so that the
same audio and renderer-client plumbing can be reused by multiple desktop apps
without each app inventing its own version.

## Helpful external references

- Tkinter overview: [docs.python.org/3/library/tkinter.html](https://docs.python.org/3/library/tkinter.html)
- Tk themed widgets (`ttk`): [docs.python.org/3/library/tkinter.ttk.html](https://docs.python.org/3/library/tkinter.ttk.html)
- `tkinter.filedialog`: [docs.python.org/3/library/dialog.html#tkinter.filedialog](https://docs.python.org/3/library/dialog.html#tkinter.filedialog)
- `urllib.request`: [docs.python.org/3/library/urllib.request.html](https://docs.python.org/3/library/urllib.request.html)
- `sounddevice`: [python-sounddevice.readthedocs.io](https://python-sounddevice.readthedocs.io/)
- `soundcard`: [soundcard.readthedocs.io](https://soundcard.readthedocs.io/)
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

Local audio capture is optional. If `sounddevice` is unavailable, the desktop panel still launches and the rest of the controls still work; only microphone and line-input capture are disabled. On Windows, the panel will still try to list input devices through the built-in waveIn API so the operator can at least see what hardware is present before installing `sounddevice`.

Desktop output-loopback capture is separate. It now uses the optional `soundcard` package because the installed `sounddevice`/PortAudio build on this machine does not expose reliable WASAPI loopback capture.

Install the optional audio dependencies with:

```powershell
python -m pip install sounddevice soundcard
```
