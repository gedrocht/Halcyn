# Desktop Multi-Renderer Data Source Panel

The Desktop Multi-Renderer Data Source Panel is the shared live-input desktop
tool for Halcyn. Its job is different from the other desktop panels:

- the classic [desktop render control panel](/Y:/Halcyn/desktop_render_control_panel/README.md)
  is mainly about choosing and tuning scene presets
- the [desktop spectrograph control panel](/Y:/Halcyn/desktop_spectrograph_control_panel/README.md)
  is mainly about turning generic JSON into bar-grid scenes
- this app is mainly about capturing or generating one source of data and
  routing it into one or both renderer families

## What this app can do

- Accept a `JSON document` source and flatten arbitrary nested data into numeric values.
- Accept a `Plain text` source and convert the text into UTF-8 byte values.
- Generate deterministic `Random values` from a seed, count, minimum, and maximum.
- Capture an `Audio device` source from either output loopback or input devices.
- Use a `Pointer pad` source for fully local interactive input.
- Route the resulting source stream into:
  - the classic Halcyn renderer
  - the spectrograph renderer
  - or both at the same time
- Preview, validate, apply, and live-stream the generated scenes.
- Save and reload settings documents.
- Open a detached JSON preview window for both target scene payloads.

## Why this exists

Before this app existed, the desktop render control panel owned much of the
desktop live-data logic itself. That was useful at first, but it made the
responsibilities blur together:

- Was that app for scene editing?
- Was it for live data capture?
- Was it for routing data between tools?

This shared panel makes the split clearer:

- scene-editing tools edit scenes
- the shared data-source tool captures and routes data

## Source modes

### JSON document

Use this when you want the source panel to accept almost any structured data.
Numbers remain numbers, booleans become `1.0` or `0.0`, strings become UTF-8
bytes, arrays recurse in order, and objects recurse through their values.

Helpful references:

- Python `json`: [docs.python.org/3/library/json.html](https://docs.python.org/3/library/json.html)
- UTF-8 encoding with `str.encode`: [docs.python.org/3/library/stdtypes.html#str.encode](https://docs.python.org/3/library/stdtypes.html#str.encode)

### Plain text

Use this when the source you care about is text rather than structured JSON.
The app converts the text into UTF-8 bytes so the same spectrograph and classic
scene translators can still work with it.

### Random values

Use this when you want a repeatable test input. Because the random generator is
seeded, the same seed produces the same numeric stream.

Helpful reference:

- Python `random.Random`: [docs.python.org/3/library/random.html#random.Random](https://docs.python.org/3/library/random.html#random.Random)

### Audio device

Use this when you want real local sound to drive both renderers. The app uses
the shared desktop audio capture helpers and can switch between output loopback
and input devices.

Helpful references:

- `sounddevice`: [python-sounddevice.readthedocs.io](https://python-sounddevice.readthedocs.io/)
- `soundcard`: [soundcard.readthedocs.io](https://soundcard.readthedocs.io/)

### Pointer pad

Use this when you want a simple local control surface that does not depend on
hardware capture or files. X, Y, and pointer speed become the live numeric
stream.

## Target routing

### Classic renderer target

The classic target uses the existing desktop scene builder. The shared data
source is summarized into the smaller control signals that classic presets
already understand:

- overall level
- bass / mid / treble bands
- pointer position
- manual drive

That means the classic renderer can react to generic data without requiring a
new scene format.

### Spectrograph renderer target

The spectrograph target uses the spectrograph scene builder. The collected
source values are fed into the rolling statistical range calculation and grouped
into the chosen `N x N` bar grid.

## How to reach the supported workflow

```powershell
.\scripts\launch-visualizer-studio.ps1
```

This package remains in the repository because Visualizer Studio still reuses
its source-routing ideas and helpers internally. It is no longer a separately
launched public app.

## Testing

Run the focused test surface:

```powershell
.\scripts\test-desktop-multi-renderer-data-source-panel.ps1
```

Run lint, type checking, and coverage:

```powershell
.\scripts\lint-desktop-multi-renderer-data-source-panel.ps1
.\scripts\typecheck-desktop-multi-renderer-data-source-panel.ps1
.\scripts\measure-desktop-multi-renderer-data-source-panel-coverage.ps1
```
