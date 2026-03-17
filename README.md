# Halcyn

[![CI](https://github.com/gedrocht/Halcyn/actions/workflows/ci.yml/badge.svg)](https://github.com/gedrocht/Halcyn/actions/workflows/ci.yml)
[![Pages](https://github.com/gedrocht/Halcyn/actions/workflows/pages.yml/badge.svg)](https://github.com/gedrocht/Halcyn/actions/workflows/pages.yml)
[![CodeQL](https://github.com/gedrocht/Halcyn/actions/workflows/codeql.yml/badge.svg)](https://github.com/gedrocht/Halcyn/actions/workflows/codeql.yml)

Halcyn is a C++20 application that accepts JSON scene descriptions over HTTP and renders them in a GPU-backed OpenGL window at a 60 FPS target. It supports both 2D and 3D payloads, includes unit tests, ships with example scenes and helper scripts, and now includes a growing family of operator tools around the renderer: a browser-based Control Center, a separate browser-facing Scene Studio, a native desktop render control panel for hardware-aware live control, a dedicated spectrograph-oriented renderer executable, a native desktop spectrograph control panel that turns generic JSON into a rolling 3D bar wall, a dedicated desktop spectrograph audio-source helper that captures live audio for that suite, and a shared desktop data-source panel that can feed either renderer family or both at once.

## What you get

- An embedded HTTP API for posting 2D or 3D JSON scenes.
- A renderer that uses OpenGL on the GPU, not software rendering on the CPU.
- A clean split between scene description rules, shared runtime state, HTTP transport, and rendering.
- Unit tests for the scene codec, validation rules, and scene store behavior.
- PowerShell scripts for build, run, test, formatting, docs serving, code-doc generation, and sample posting.
- A browser-based Control Center under `browser_control_center/` that can kick off builds, tests, smoke checks, docs, and API requests.
- A native desktop operator app under `desktop_render_control_panel/` that can preview, validate, apply, and live-stream scenes while selecting real local audio devices.
- A dedicated spectrograph renderer executable that starts with a 3D bar-grid scene and exposes its own default API port.
- A native desktop spectrograph operator app under `desktop_spectrograph_control_panel/` that accepts very generic JSON, normalizes it through a rolling statistical range, and turns it into a controllable 3D spectrograph scene.
- A native desktop spectrograph audio-source helper under `desktop_spectrograph_audio_source_panel/` that captures output or input audio and sends readable JSON into the spectrograph control panel's local bridge.
- A shared native desktop data-source app under `desktop_multi_renderer_data_source_panel/` that captures or generates one live data stream and routes it into the classic renderer, the spectrograph renderer, or both.
- A small shared desktop support package under `desktop_shared_control_support/` so desktop apps can share renderer HTTP helpers and audio-device integration through one clear import path.
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
5. Launch the dedicated spectrograph renderer with `.\scripts\launch-halcyn-spectrograph-app.ps1`.
6. Launch the native desktop spectrograph operator console with `.\scripts\launch-desktop-spectrograph-control-panel.ps1` if you want to turn arbitrary JSON into a rolling 3D spectrograph scene.
7. Launch the dedicated desktop spectrograph audio-source helper with `.\scripts\launch-desktop-spectrograph-audio-source-panel.ps1` if you want live output or input audio to feed the spectrograph suite.
8. Launch the shared desktop data-source panel with `.\scripts\launch-desktop-multi-renderer-data-source-panel.ps1` if you want one live input source to drive the classic renderer, the spectrograph renderer, or both.
9. Use the Control Center dashboard to run the prerequisite report, build, tests, and app startup from the browser.
10. In the Scene Studio, either desktop control panel, the spectrograph audio-source panel, the shared data-source panel, or API Lab, generate and submit sample scenes to the live renderer.
11. Open the docs site directly from the Control Center or with `.\scripts\serve-docs-site.ps1`.
12. For a full Windows setup and troubleshooting guide, see `INSTALL.md`.

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
- `.\scripts\launch-halcyn-app.ps1`
- `.\scripts\launch-halcyn-spectrograph-app.ps1`
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
- `.\scripts\launch-desktop-spectrograph-control-panel.ps1`
- `.\scripts\launch-desktop-spectrograph-audio-source-panel.ps1`
- `.\scripts\launch-desktop-multi-renderer-data-source-panel.ps1`
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

## Documentation

- Beginner docs site: `docs/site/index.html`
- Field reference: `docs/site/field-reference.html`
- Control center guide: `docs/site/control-center.html`
- Scene Studio guide: `docs/site/scene-studio.html`
- Desktop control panel guide: `docs/site/desktop-control-panel.html`
- Spectrograph suite guide: `docs/site/spectrograph-suite.html`
- Spectrograph audio-source panel guide: `docs/site/spectrograph-audio-source-panel.html`
- Shared data-source panel guide: `docs/site/multi-renderer-data-source-panel.html`
- Architecture guide: `docs/site/architecture.html`
- API guide: `docs/site/api.html`
- Testing guide: `docs/site/testing.html`
- Code docs guide: `docs/site/code-docs.html`

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

## Shared Data Source Panel

Run `.\scripts\launch-desktop-multi-renderer-data-source-panel.ps1` to open the native shared data-source console. This app can:

- accept JSON documents, plain text, random values, audio devices, or pointer-pad movement as its live source
- route the same source into the classic renderer, the spectrograph renderer, or both
- preview, validate, apply once, or live-stream the translated scenes
- save and reload a versioned settings document
- complement the other desktop panels by handling data capture and routing while they stay focused on scene editing

## Spectrograph Renderer

Run `.\scripts\launch-halcyn-spectrograph-app.ps1` to start the dedicated spectrograph-oriented renderer executable. This renderer uses the same shared engine as the regular Halcyn app, but it starts with a 3D bar-grid sample, uses a spectrograph-friendly title, and defaults to API port `8090` so it can coexist more easily with the regular renderer.

The spectrograph sample also exercises the new 3D `renderStyle` controls:

- `renderStyle.shader`
  - `standard`
  - `neon`
  - `heatmap`
- `renderStyle.antiAliasing`
  - `true` or `false`

## Desktop Spectrograph Control Panel

Run `.\scripts\launch-desktop-spectrograph-control-panel.ps1` to open the native spectrograph operator console. The spectrograph panel can:

- accept very generic JSON instead of only pre-shaped scene documents
- flatten nested arrays, objects, booleans, numbers, and strings into one numeric source stream
- convert strings into UTF-8 byte values so even non-numeric payloads still produce bars
- maintain a rolling statistical history and normalize new values against an adaptive range
- switch between automatic range calculation and manual minimum/maximum control
- choose the 3D bar-grid size `N` so the renderer shows an `N x N` wall of bars
- toggle anti-aliasing and shader presentation style for the 3D bar scene
- preview, validate, apply, and live-stream the generated spectrograph scene
- save and load operator settings as JSON
- open the fully generated Halcyn scene JSON in a separate study window
- optionally follow the latest JSON arriving from the dedicated spectrograph audio-source helper

## Desktop Spectrograph Audio Source Panel

Run `.\scripts\launch-desktop-spectrograph-audio-source-panel.ps1` to open the native spectrograph audio-source helper. This app can:

- choose from desktop `Output sources` or microphone-style `Input sources`
- refresh the device list and start or stop capture explicitly
- show a live volume meter for the currently selected source
- package a rolling history of audio snapshots into readable generic JSON
- send that JSON once or repeatedly to the spectrograph control panel's local external-data bridge
- save and reload a versioned settings document
- open the fully generated bridge JSON in a separate study window

## Code documentation generation

Run `.\scripts\generate-code-reference-docs.ps1` after installing Doxygen. Generated HTML will be written to `docs/generated/code-reference`.

## Packaging

Run `.\scripts\create-release-package.ps1` to produce a versioned ZIP file under `artifacts/`. Each package includes the executable, examples, docs, a `build-manifest.json` file with build metadata, and a companion `.sha256` file for release verification.

## Quality gates

- C++ warnings are treated as build failures by default.
- The Control Center is linted, type-checked, and required to maintain at least 90% Python coverage.
- The desktop render control panel is also linted, type-checked, and required to maintain at least 90% Python coverage.
- The desktop spectrograph control panel is also linted, type-checked, and required to maintain at least 90% Python coverage.
- The desktop spectrograph audio-source panel is also linted, type-checked, and required to maintain at least 90% Python coverage.
- GitHub Actions lint and cover all maintained Python operator surfaces, build the native project in Debug and Release, and run the native tests.
- CodeQL analyzes the native code on pushes, pull requests, and a weekly schedule.
- The Pages workflow now publishes the static docs site together with generated Doxygen output.
- Repository formatting is explicitly governed by `.clang-format` and `.editorconfig`.

## Notes about GPU rendering

The CPU still performs normal application work such as parsing JSON, handling HTTP requests, and submitting draw commands. The actual graphics pipeline work that turns vertices into pixels is performed by the GPU through OpenGL. This is the normal and correct architecture for modern real-time graphics applications.
