# Desktop Spectrograph Audio Source Panel

The Desktop Spectrograph Audio Source Panel is the native helper app that feeds
live audio into the Desktop Spectrograph Control Panel.

This split is intentional:

- the [desktop spectrograph control panel](/Y:/Halcyn/desktop_spectrograph_control_panel/README.md)
  focuses on rendering choices such as bar count, shader style, anti-aliasing,
  and adaptive range behavior
- this panel focuses on one job: capturing audio, turning it into a rolling
  generic JSON document, and sending that document into the spectrograph
  control panel's local bridge

## What it can do

- choose audio from `Output sources` or `Input sources`
- refresh the device list and start or stop capture
- show a live volume monitor for the selected source
- keep a rolling history of recent audio frames
- package that history into beginner-readable JSON
- send the generated JSON once or repeatedly to the spectrograph control panel
- save and load settings documents
- open the generated JSON in a separate window

## Beginner mental model

If the Desktop Spectrograph Control Panel is the *render brain*, this app is
the *live audio ear*.

The audio source panel does not try to decide how many bars to draw or which
shader should color them. Instead, it answers the simpler question:

"What does the recent audio activity look like, and how can I hand that to the
spectrograph control panel in a clean generic JSON shape?"

## How to reach the supported workflow

Use the unified desktop workflow instead:

```powershell
.\scripts\launch-visualizer-studio.ps1
```

This package remains in the repository because Visualizer Studio still reuses
its audio-to-generic-data translation logic internally. It is no longer a
separately launched public helper app.

## Helpful external references

- Tkinter overview: [docs.python.org/3/library/tkinter.html](https://docs.python.org/3/library/tkinter.html)
- Tk themed widgets (`ttk`): [docs.python.org/3/library/tkinter.ttk.html](https://docs.python.org/3/library/tkinter.ttk.html)
- `ScrolledText`: [docs.python.org/3/library/tkinter.scrolledtext.html](https://docs.python.org/3/library/tkinter.scrolledtext.html)
- `urllib.request`: [docs.python.org/3/library/urllib.request.html](https://docs.python.org/3/library/urllib.request.html)
- `http.server`: [docs.python.org/3/library/http.server.html](https://docs.python.org/3/library/http.server.html)
- `sounddevice`: [python-sounddevice.readthedocs.io](https://python-sounddevice.readthedocs.io/)
- `soundcard`: [soundcard.readthedocs.io](https://soundcard.readthedocs.io/)

## Testing and quality gates

- `.\scripts\lint-desktop-spectrograph-audio-source-panel.ps1`
- `.\scripts\typecheck-desktop-spectrograph-audio-source-panel.ps1`
- `.\scripts\test-desktop-spectrograph-audio-source-panel.ps1`
- `.\scripts\measure-desktop-spectrograph-audio-source-panel-coverage.ps1`

The repo-wide pass is still:

```powershell
.\scripts\run-all-quality-checks.ps1 -Configuration Debug
```
