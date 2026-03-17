# Halcyn

[![CI](https://github.com/gedrocht/Halcyn/actions/workflows/ci.yml/badge.svg)](https://github.com/gedrocht/Halcyn/actions/workflows/ci.yml)
[![Pages](https://github.com/gedrocht/Halcyn/actions/workflows/pages.yml/badge.svg)](https://github.com/gedrocht/Halcyn/actions/workflows/pages.yml)
[![CodeQL](https://github.com/gedrocht/Halcyn/actions/workflows/codeql.yml/badge.svg)](https://github.com/gedrocht/Halcyn/actions/workflows/codeql.yml)

Halcyn is a C++20 OpenGL application that accepts JSON scene descriptions over HTTP and renders them in a GPU-backed window. The project now centers on one native renderer, one unified desktop operator app, one browser orchestration app, and one browser-based activity monitor.

## What you get

- One native Visualizer executable that can render:
  - classic preset-driven 2D and 3D scenes
  - bar-wall scenes that behave like a colorful 3D spectrograph
- One embedded HTTP API for:
  - health checks
  - scene validation
  - scene submission
  - example scene retrieval
  - runtime log retrieval
- One browser Control Center for builds, tests, docs, API experiments, and process orchestration
- One browser Activity Monitor for sortable, filterable, shared cross-app logs
- One native Visualizer Studio app for:
  - choosing live sources
  - shaping them into scenes
  - previewing JSON
  - validating and applying scenes
  - live streaming to the renderer
- One separate browser Scene Studio for browser-first preset authoring
- Unit tests, coverage gates, static docs, and generated Doxygen reference docs

## Mental model

If you are new to the project, the simplest way to think about it is:

- `Visualizer`
  The native C++ app that actually draws pixels.
- `Visualizer Studio`
  The unified native desktop operator console that feeds data and scene settings into the Visualizer.
- `Control Center`
  The browser dashboard that launches tools, runs jobs, and exposes docs and API lab features.
- `Activity Monitor`
  The browser log viewer that reads the shared JSON-lines activity journal from all participating apps.
- `Scene Studio`
  A separate browser scene-authoring companion that focuses on preset-driven browser control.

## Repository layout

```text
.
|-- CMakeLists.txt
|-- CMakePresets.json
|-- Doxyfile
|-- browser_control_center/
|-- browser_scene_studio/
|-- desktop_shared_control_support/
|-- desktop_visualizer_operator_console/
|-- docs/
|   `-- site/
|-- examples/
|-- scripts/
|-- src/
|   |-- desktop_app/
|   |-- http_api/
|   |-- opengl_renderer/
|   |-- scene_description/
|   `-- shared_runtime/
`-- tests/
```

Some of the older split desktop packages are still present in the repository as
internal support modules, but the supported public workflow is now the unified
Visualizer Studio.

## Quick start

1. Run `.\scripts\report-prerequisites.ps1`.
2. Launch the browser Control Center with `.\scripts\launch-browser-control-center.ps1`.
3. Launch the native Visualizer with `.\scripts\launch-halcyn-app.ps1`.
4. Launch the native Visualizer Studio with `.\scripts\launch-visualizer-studio.ps1`.
5. Open the shared browser log viewer with `.\scripts\launch-activity-monitor.ps1`.
6. If you want the main native/browser workflow opened for you, run `.\scripts\launch-visualizer-workbench.ps1`.
7. If you want browser-side scene authoring, run `.\scripts\launch-browser-scene-studio.ps1`.

## One-command workbench

If you want the most beginner-friendly full setup, use:

```powershell
.\scripts\launch-visualizer-workbench.ps1
```

That helper opens:

- the native Visualizer window
- the browser Control Center
- the unified Visualizer Studio desktop app

From there, the Activity Monitor is one click away inside the Control Center, or you can open it directly with:

```powershell
.\scripts\launch-activity-monitor.ps1
```

## PowerShell first-run note

If Windows shows a security prompt before running repository scripts, you can unblock the tree once:

```powershell
Get-ChildItem -Path . -Recurse -File | Unblock-File
```

## Prerequisites

Minimum Windows-native setup:

- `cmake`
- `python`
- Python package `jinja2`
- Python package `ttkbootstrap`
- `git`
- either:
  - Visual Studio 2022 Build Tools with `Desktop development with C++`
  - or `ninja` plus a working C++ compiler

Optional extras:

- `doxygen` for generated code docs
- `clang-format` for formatting checks
- Python package `mkdocs` for the hosted beginner walkthrough wiki
- Python package `pymdown-extensions` for the hosted beginner walkthrough wiki
- Python package `sounddevice` for microphone and line-input capture
- Python package `soundcard` for desktop output-loopback capture

Helpful install routes:

- Ninja: `winget install Ninja-build.Ninja`
- LLVM and `clang-format`: `winget install LLVM.LLVM`
  - Doxygen: `winget install DimitriVanHeesch.Doxygen`
  - Python packages:
    ```powershell
  python -m pip install jinja2 ttkbootstrap mkdocs pymdown-extensions sounddevice soundcard
    ```

For the easiest Windows-native C++ path, install Visual Studio 2022 Build Tools from [visualstudio.microsoft.com/downloads](https://visualstudio.microsoft.com/downloads/) and include the `Desktop development with C++` workload.

## Supported scene families

### Preset scenes

These are the classic Halcyn 2D and 3D scene families. They are useful when you want:

- clean starter examples
- direct scene authoring
- small JSON payloads
- browser-driven experimentation in Scene Studio

### Bar-wall scenes

These are still ordinary Halcyn 3D scenes, but the content is a grid of colored bars whose heights represent grouped and normalized source data. They are useful when you want:

- generic JSON turned into visuals
- strings converted into bytes and then into bars
- rolling adaptive value ranges
- shader and anti-aliasing control
- audio-driven or other live-source-driven bar walls

## API endpoints

The unified Visualizer exposes one API surface:

- `GET /api/v1/health`
- `GET /api/v1/scene`
- `GET /api/v1/runtime/limits`
- `GET /api/v1/runtime/logs?limit=200`
- `GET /api/v1/examples/2d`
- `GET /api/v1/examples/3d`
- `GET /api/v1/examples/bar-wall`
- `GET /api/v1/examples/spectrograph`
  - compatibility alias for the same bar-wall sample
- `POST /api/v1/scene/validate`
- `POST /api/v1/scene`

## Build and test scripts

Main supported scripts:

- `.\scripts\report-prerequisites.ps1`
- `.\scripts\build-halcyn-app.ps1`
- `.\scripts\launch-halcyn-app.ps1`
- `.\scripts\launch-visualizer-studio.ps1`
- `.\scripts\launch-browser-control-center.ps1`
- `.\scripts\launch-activity-monitor.ps1`
- `.\scripts\launch-browser-scene-studio.ps1`
- `.\scripts\launch-visualizer-workbench.ps1`
- `.\scripts\run-native-tests.ps1`
- `.\scripts\run-all-quality-checks.ps1`
- `.\scripts\lint-browser-control-center.ps1`
- `.\scripts\typecheck-browser-control-center.ps1`
- `.\scripts\measure-browser-control-center-coverage.ps1`
- `.\scripts\lint-visualizer-studio.ps1`
- `.\scripts\typecheck-visualizer-studio.ps1`
- `.\scripts\test-visualizer-studio.ps1`
- `.\scripts\measure-visualizer-studio-coverage.ps1`
- `.\scripts\verify-cpp-formatting.ps1`
- `.\scripts\generate-code-reference-docs.ps1`
- `.\scripts\build-beginner-wiki.ps1`
- `.\scripts\serve-beginner-wiki.ps1`
- `.\scripts\serve-docs-site.ps1`
- `.\scripts\create-release-package.ps1`

The scripts listed above are the supported public entry points.

## Documentation

- Docs overview: `docs/site/index.html`
- Beginner walkthrough wiki source: `docs/wiki/README.md`
- Beginner walkthrough wiki hosted home: `docs/wiki/index.md`
- Tutorial: `docs/site/tutorial.html`
- API guide: `docs/site/api.html`
- Architecture guide: `docs/site/architecture.html`
- Testing guide: `docs/site/testing.html`
- Control Center guide: `docs/site/control-center.html`
- Scene Studio guide: `docs/site/scene-studio.html`
- Visualizer Studio guide: `docs/site/desktop-control-panel.html`
- Bar-wall scene guide: `docs/site/spectrograph-suite.html`
- Field reference: `docs/site/field-reference.html`
- Code docs guide: `docs/site/code-docs.html`

## Quality gates

- C++ warnings are treated as build failures by default.
- Browser Control Center Python code is linted, type-checked, tested, and required to maintain at least 90% coverage.
- Visualizer Studio Python code is linted, type-checked, tested, and required to maintain at least 90% coverage.
- GitHub Actions build native Debug and Release, run the Python quality suites, publish the docs site, and run CodeQL.
- The browser Activity Monitor reads one shared JSON-lines journal written by the Visualizer, Control Center, and Visualizer Studio.

## Code documentation generation

Run:

```powershell
.\scripts\generate-code-reference-docs.ps1
```

Generated HTML will be written to `docs/generated/code-reference`.

## Packaging

Run:

```powershell
.\scripts\create-release-package.ps1
```

This writes a versioned ZIP package under `artifacts/`.

## Beginner-friendly next step

If you only want one recommended learning path:

1. Open the docs site.
2. Read `tutorial.html`.
3. Run `.\scripts\launch-visualizer-workbench.ps1`.
4. Watch the Visualizer window.
5. Use Visualizer Studio to preview and apply scenes.
6. Use the Activity Monitor to watch the shared logs from every running app.
