# Halcyn

[![CI](https://github.com/gedrocht/Halcyn/actions/workflows/ci.yml/badge.svg)](https://github.com/gedrocht/Halcyn/actions/workflows/ci.yml)
[![Pages](https://github.com/gedrocht/Halcyn/actions/workflows/pages.yml/badge.svg)](https://github.com/gedrocht/Halcyn/actions/workflows/pages.yml)
[![CodeQL](https://github.com/gedrocht/Halcyn/actions/workflows/codeql.yml/badge.svg)](https://github.com/gedrocht/Halcyn/actions/workflows/codeql.yml)

Halcyn is a C++20 application that accepts JSON scene descriptions over HTTP and renders them in a GPU-backed OpenGL window at a 60 FPS target. It supports both 2D and 3D payloads, includes unit tests, ships with example scenes and helper scripts, and now includes a growing family of operator tools around the renderer: a browser-based Control Center, a separate browser-facing Scene Studio, a native desktop render control panel for hardware-aware live control, a unified Visualizer launcher for the renderer itself, a Signal Router that can drive one or both renderer modes from one live source, a focused Bars Studio for bar-wall-specific tuning, an Audio Sender helper for live audio capture, and a shared Activity Monitor for cross-tool logging.

## What you get

- An embedded HTTP API for posting 2D or 3D JSON scenes.
- A renderer that uses OpenGL on the GPU, not software rendering on the CPU.
- A clean split between scene description rules, shared runtime state, HTTP transport, and rendering.
- Unit tests for the scene codec, validation rules, and scene store behavior.
- PowerShell scripts for build, run, test, formatting, docs serving, code-doc generation, and sample posting.
- A browser-based Control Center under `browser_control_center/` that can kick off builds, tests, smoke checks, docs, and API requests.
- A native desktop operator app under `desktop_render_control_panel/` that can preview, validate, apply, and live-stream scenes while selecting real local audio devices.
- A unified Visualizer launcher that can start the renderer in its normal scene mode or in the bar-wall mode on a second API port.
- A native desktop Bars Studio under `desktop_spectrograph_control_panel/` that accepts very generic JSON, normalizes it through a rolling statistical range, and turns it into a controllable 3D bar wall.
- A native desktop Audio Sender under `desktop_spectrograph_audio_source_panel/` that captures output or input audio and sends readable JSON into a local desktop bridge.
- A shared native desktop Signal Router under `desktop_multi_renderer_data_source_panel/` that captures or generates one live data stream and routes it into the scene renderer, the bar-wall renderer, or both.
- A small shared desktop support package under `desktop_shared_control_support/` so desktop apps can share renderer HTTP helpers and audio-device integration through one clear import path.
- A shared desktop Activity Monitor backed by structured JSON-lines logs so you can inspect what happened across launchers, senders, and control panels in one place.
- A static dark-mode docs site under `docs/site`.
- Doxygen-ready source comments and a `Doxyfile` for generated code reference output.

## Repository layout

```text
.
|-- CMakeLists.txt
|-- CMakePresets.json
|-- Doxyfile
|-- browser_scene_studio/
|-- examples/
|-- browser_control_center/
|-- desktop_render_control_panel/
|-- desktop_spectrograph_control_panel/
|-- desktop_spectrograph_audio_source_panel/
|-- desktop_multi_renderer_data_source_panel/
|-- desktop_shared_control_support/
|-- scripts/
|-- src/
|   |-- http_api/
|   |-- desktop_app/
|   |-- shared_runtime/
|   |-- scene_description/
|   `-- opengl_renderer/
|-- tests/
`-- docs/
    `-- site/
```

## Quick start

1. Run `.\scripts\report-prerequisites.ps1` to see which prerequisites are already installed.
2. Launch the browser Control Center with `.\scripts\launch-browser-control-center.ps1`.
3. Open the separate client-facing scene GUI with `.\scripts\launch-browser-scene-studio.ps1` or by visiting `/scene-studio/` from the Control Center.
4. Launch the native desktop render control panel with `.\scripts\launch-desktop-render-control-panel.ps1` if you want local audio-device selection and instant 2D/3D switching in a desktop window.
5. Launch the renderer with `.\scripts\launch-visualizer.ps1`.
6. Launch the unified bar-wall workflow with `.\scripts\launch-bars-workbench.ps1` if you want the Visualizer, Signal Router, and Audio Sender opened for you together.
7. Launch the Signal Router with `.\scripts\launch-signal-router.ps1` if you want one live source to drive the scene renderer, the bar-wall renderer, or both.
8. Launch the Audio Sender with `.\scripts\launch-audio-sender.ps1` if you want live output or input audio to feed the Signal Router or Bars Studio.
9. Launch Bars Studio with `.\scripts\launch-bars-studio.ps1` if you want deeper bar-wall-specific tuning than the Signal Router provides.
10. Launch the shared Activity Monitor with `.\scripts\launch-activity-monitor.ps1` if you want one place to inspect desktop-tool logs and bridge traffic.
11. Use the Control Center dashboard to run the prerequisite report, build, tests, and app startup from the browser.
12. In the Scene Studio, desktop panels, Audio Sender, Signal Router, or API Lab, generate and submit sample scenes to the live renderer.
13. Open the docs site directly from the Control Center or with `.\scripts\serve-docs-site.ps1`.
14. For a full Windows setup and troubleshooting guide, see `INSTALL.md`.

## PowerShell first-run note

If Windows shows a security prompt before running the repository scripts, you can unblock this working tree once:

```powershell
Get-ChildItem -Path . -Recurse -File | Unblock-File
```

That removes the "downloaded from the internet" marker from files in the current repository so PowerShell stops prompting for those scripts.

## Prerequisites

The minimum setup for a local build on Windows is:

- `cmake`
- `python`
- Python package `jinja2`
- `git`
- either `Visual Studio 2022 Build Tools` with `Desktop development with C++`, or `ninja` plus a working C++ compiler

Optional extras:

- `doxygen` for generated code docs
- `clang-format` for the formatting script
- Python package `sounddevice` for microphone or line-input capture in desktop tools
- Python package `soundcard` for desktop output-loopback capture in desktop tools

Helpful install routes:

- Ninja: `winget install Ninja-build.Ninja`
- LLVM and `clang-format`: `winget install LLVM.LLVM`
- Doxygen: `winget install DimitriVanHeesch.Doxygen`
- Python package: `python -m pip install jinja2`
- Audio input package: `python -m pip install sounddevice`
- Output loopback package: `python -m pip install soundcard`

For the easiest Windows-native path, install Visual Studio 2022 Build Tools from `https://visualstudio.microsoft.com/downloads/` and select the `Desktop development with C++` workload.

## Supported JSON scene formats

### 2D scene

Each 2D vertex must include:

- `x`
- `y`
- `r`
- `g`
- `b`
- `a`

Example:

```json
{
  "sceneType": "2d",
  "primitive": "triangles",
  "vertices": [
    { "x": -1.0, "y": -1.0, "r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0 },
    { "x": 0.0, "y": 1.0, "r": 0.0, "g": 1.0, "b": 0.0, "a": 1.0 },
    { "x": 1.0, "y": -1.0, "r": 0.0, "g": 0.0, "b": 1.0, "a": 1.0 }
  ]
}
```

### 3D scene

Each 3D vertex must include:

- `x`
- `y`
- `z`
- `r`
- `g`
- `b`

`a` is optional and defaults to `1.0`. A 3D scene also needs a `camera` object and may include `indices`.
It may also include a `renderStyle` object when the caller wants to control shader presentation and multisample anti-aliasing.

Example:

```json
{
  "sceneType": "3d",
  "primitive": "triangles",
  "camera": {
    "position": { "x": 2.5, "y": 2.0, "z": 2.8 },
    "target": { "x": 0.0, "y": 0.0, "z": 0.0 },
    "up": { "x": 0.0, "y": 1.0, "z": 0.0 },
    "fovYDegrees": 60.0,
    "nearPlane": 0.1,
    "farPlane": 100.0
  },
  "renderStyle": {
    "shader": "heatmap",
    "antiAliasing": true
  },
  "vertices": [
    { "x": -0.8, "y": -0.8, "z": 0.0, "r": 1.0, "g": 0.2, "b": 0.2 },
    { "x": 0.8, "y": -0.8, "z": 0.0, "r": 0.2, "g": 1.0, "b": 0.2 },
    { "x": 0.0, "y": 0.8, "z": 0.0, "r": 0.2, "g": 0.4, "b": 1.0 }
  ],
  "indices": [0, 1, 2]
}
```

## API endpoints

- `GET /api/v1/health`
- `GET /api/v1/scene`
- `GET /api/v1/runtime/limits`
- `GET /api/v1/runtime/logs?limit=200`
- `GET /api/v1/examples/2d`
- `GET /api/v1/examples/3d`
- `GET /api/v1/examples/spectrograph`
- `POST /api/v1/scene/validate`
- `POST /api/v1/scene`

## Build and test scripts

- `.\scripts\report-prerequisites.ps1`
- `.\scripts\build-halcyn-app.ps1`
- `.\scripts\launch-visualizer.ps1`
- `.\scripts\launch-signal-router.ps1`
- `.\scripts\launch-bars-studio.ps1`
- `.\scripts\launch-audio-sender.ps1`
- `.\scripts\launch-bars-workbench.ps1`
- `.\scripts\launch-activity-monitor.ps1`
- `.\scripts\launch-halcyn-app.ps1`
- `.\scripts\run-native-tests.ps1`
- `.\scripts\run-all-quality-checks.ps1`
- `.\scripts\lint-browser-control-center.ps1`
- `.\scripts\measure-browser-control-center-coverage.ps1`
- `.\scripts\typecheck-browser-control-center.ps1`
- `.\scripts\verify-cpp-formatting.ps1`
- `.\scripts\create-release-package.ps1`
- `.\scripts\launch-browser-control-center.ps1`
- `.\scripts\launch-browser-scene-studio.ps1`
- `.\scripts\launch-desktop-render-control-panel.ps1`
- `.\scripts\test-browser-control-center.ps1`
- `.\scripts\test-desktop-render-control-panel.ps1`
- `.\scripts\test-desktop-spectrograph-control-panel.ps1`
- `.\scripts\test-desktop-spectrograph-audio-source-panel.ps1`
- `.\scripts\test-desktop-multi-renderer-data-source-panel.ps1`
- `.\scripts\lint-desktop-render-control-panel.ps1`
- `.\scripts\lint-desktop-spectrograph-control-panel.ps1`
- `.\scripts\lint-desktop-spectrograph-audio-source-panel.ps1`
- `.\scripts\lint-desktop-multi-renderer-data-source-panel.ps1`
- `.\scripts\typecheck-desktop-render-control-panel.ps1`
- `.\scripts\typecheck-desktop-spectrograph-control-panel.ps1`
- `.\scripts\typecheck-desktop-spectrograph-audio-source-panel.ps1`
- `.\scripts\typecheck-desktop-multi-renderer-data-source-panel.ps1`
- `.\scripts\measure-desktop-render-control-panel-coverage.ps1`
- `.\scripts\measure-desktop-spectrograph-control-panel-coverage.ps1`
- `.\scripts\measure-desktop-spectrograph-audio-source-panel-coverage.ps1`
- `.\scripts\measure-desktop-multi-renderer-data-source-panel-coverage.ps1`
- `.\scripts\post-example-2d-scene.ps1`
- `.\scripts\post-example-3d-scene.ps1`
- `.\scripts\serve-docs-site.ps1`
- `.\scripts\generate-code-reference-docs.ps1`
- `.\scripts\format-cpp-code.ps1`

Compatibility launchers still exist for older notes and habits:

- `.\scripts\launch-halcyn-spectrograph-app.ps1`
- `.\scripts\launch-spectrograph-audio-workbench.ps1`
- `.\scripts\launch-desktop-spectrograph-control-panel.ps1`
- `.\scripts\launch-desktop-spectrograph-audio-source-panel.ps1`
- `.\scripts\launch-desktop-multi-renderer-data-source-panel.ps1`

## Documentation

- Beginner docs site: `docs/site/index.html`
- Field reference: `docs/site/field-reference.html`
- Control center guide: `docs/site/control-center.html`
- Scene Studio guide: `docs/site/scene-studio.html`
- Desktop control panel guide: `docs/site/desktop-control-panel.html`
- Bar-wall workflow guide: `docs/site/spectrograph-suite.html`
- Audio Sender guide: `docs/site/spectrograph-audio-source-panel.html`
- Signal Router guide: `docs/site/multi-renderer-data-source-panel.html`
- Architecture guide: `docs/site/architecture.html`
- API guide: `docs/site/api.html`
- Testing guide: `docs/site/testing.html`
- Code docs guide: `docs/site/code-docs.html`

## Fastest bar-wall audio path

If you want the quickest beginner-friendly way to see the bar-wall workflow
working with live audio, use this one command:

```powershell
.\scripts\launch-bars-workbench.ps1
```

That helper opens separate windows for:

- the Visualizer in bar-wall mode
- the Signal Router
- the Audio Sender

After those windows open:

1. Enable the `Bar-Wall` target in Signal Router.
2. Choose `External feed` in Signal Router if you want it to follow incoming helper JSON.
3. Choose an audio device in Audio Sender.
4. Pick the `Signal Router` bridge target preset.
5. Click `Start capture`.
6. Use `Send once` or `Start live`.

If you still have older notes that use `.\scripts\launch-spectrograph-audio-workbench.ps1`,
that older script now acts as a compatibility wrapper around the newer
`launch-bars-workbench.ps1`.

## Browser Control Center

Run `.\scripts\launch-browser-control-center.ps1` to launch the browser-based dashboard. The Control Center can:

- inspect local prerequisites
- kick off bootstrap, build, test, format, and code-doc jobs
- start and stop the managed Halcyn app process
- show Control Center logs and captured app output
- run smoke checks against the live Halcyn API
- proxy browser-issued requests into the live Halcyn API
- link directly into the docs site and generated code docs

## Scene Studio

Run `.\scripts\launch-browser-scene-studio.ps1` or open `/scene-studio/` from the Control Center server to launch the separate browser-facing scene GUI. Scene Studio can:

- choose from multiple 3D visual presets
- drive scenes from unix time, deterministic noise, pointer motion, microphone energy, or manual sliders
- preview generated JSON scene payloads before applying them
- apply one scene immediately to the live renderer on demand
- run a server-side live session that keeps streaming scenes to the renderer on a chosen cadence
- send lighter browser control updates while the Control Center owns the continuous scene stream
- receive server-pushed live-session status instead of relying on tight browser polling

## Desktop Render Control Panel

Run `.\scripts\launch-desktop-render-control-panel.ps1` to open the native Tk-based operator console. The desktop panel can:

- switch between 2D and 3D presets immediately without changing tools
- choose real local audio input devices instead of relying only on browser microphone permissions
- preview generated JSON scenes before applying them
- validate the current scene against the live Halcyn API
- apply one scene immediately or keep a live stream running at a chosen cadence
- expose signal controls for unix time, deterministic noise, pointer input, audio energy bands, and manual drive
- serve as a desktop-side companion to the browser Control Center and Scene Studio instead of replacing them

## Signal Router

Run `.\scripts\launch-signal-router.ps1` to open the native shared data-source
console. This app is now the recommended central desktop control surface when
you want one live source to drive one or both renderer modes. It can:

- accept JSON documents, plain text, random values, audio devices, pointer-pad movement, or the latest external bridge feed
- route the same source into the scene renderer, the bar-wall renderer, or both
- preview, validate, apply once, or live-stream the translated scenes
- save and reload a versioned settings document
- expose the shared Activity Monitor so you can inspect bridge traffic and live-stream events

## Visualizer in bar-wall mode

Run `.\scripts\launch-visualizer.ps1 -Sample spectrograph -Port 8090` to start
the renderer in its bar-wall personality. If you prefer the older command
shape, `.\scripts\launch-halcyn-spectrograph-app.ps1` now acts as a
compatibility wrapper around the Visualizer launcher.

The bar-wall sample exercises the 3D `renderStyle` controls:

- `renderStyle.shader`
  - `standard`
  - `neon`
  - `heatmap`
- `renderStyle.antiAliasing`
  - `true` or `false`

## Bars Studio

Run `.\scripts\launch-bars-studio.ps1` to open the native bar-wall operator
console. Bars Studio is the specialized deep-tuning tool for the bar-wall
renderer. It can:

- accept very generic JSON instead of only pre-shaped scene documents
- flatten nested arrays, objects, booleans, numbers, and strings into one numeric source stream
- convert strings into UTF-8 byte values so even non-numeric payloads still produce bars
- maintain a rolling statistical history and normalize new values against an adaptive range
- switch between automatic range calculation and manual minimum/maximum control
- choose the 3D bar-grid size `N` so the renderer shows an `N x N` wall of bars
- toggle anti-aliasing and shader presentation style for the 3D bar scene
- preview, validate, apply, and live-stream the generated bar-wall scene
- save and load operator settings as JSON
- open the fully generated Halcyn scene JSON in a separate study window
- optionally follow the latest JSON arriving from helper apps such as Audio Sender

## Audio Sender

Run `.\scripts\launch-audio-sender.ps1` to open the native audio-source helper.
Audio Sender can:

- choose from desktop `Output sources` or microphone-style `Input sources`
- refresh the device list and start or stop capture explicitly
- show a live volume meter for the currently selected source
- package a rolling history of audio snapshots into readable generic JSON
- send that JSON once or repeatedly to the Signal Router or Bars Studio bridge
- save and reload a versioned settings document
- open the fully generated bridge JSON in a separate study window

## Activity Monitor

Run `.\scripts\launch-activity-monitor.ps1` to open the shared desktop activity
monitor. This is the easiest way to inspect structured events across the
desktop workflow in one place. It shows:

- which desktop app emitted each event
- which component inside that app reported the event
- whether the event was informational, warning-level, or an error
- JSON details such as bridge ports, delivery statuses, and live-stream counts

## Code documentation generation

Run `.\scripts\generate-code-reference-docs.ps1` after installing Doxygen. Generated HTML will be written to `docs/generated/code-reference`.

## Packaging

Run `.\scripts\create-release-package.ps1` to produce a versioned ZIP file under `artifacts/`. Each package includes the executable, examples, docs, a `build-manifest.json` file with build metadata, and a companion `.sha256` file for release verification.

## Quality gates

- C++ warnings are treated as build failures by default.
- The Control Center is linted, type-checked, and required to maintain at least 90% Python coverage.
- The desktop render control panel is also linted, type-checked, and required to maintain at least 90% Python coverage.
- Bars Studio is also linted, type-checked, and required to maintain at least 90% Python coverage.
- Audio Sender is also linted, type-checked, and required to maintain at least 90% Python coverage.
- Signal Router is also linted, type-checked, and required to maintain at least 90% Python coverage.
- GitHub Actions lint and cover all maintained Python operator surfaces, build the native project in Debug and Release, and run the native tests.
- CodeQL analyzes the native code on pushes, pull requests, and a weekly schedule.
- The Pages workflow now publishes the static docs site together with generated Doxygen output.
- Repository formatting is explicitly governed by `.clang-format` and `.editorconfig`.

## Notes about GPU rendering

The CPU still performs normal application work such as parsing JSON, handling HTTP requests, and submitting draw commands. The actual graphics pipeline work that turns vertices into pixels is performed by the GPU through OpenGL. This is the normal and correct architecture for modern real-time graphics applications.
