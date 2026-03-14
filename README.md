# Halcyn

Halcyn is a C++20 application that accepts JSON scene descriptions over HTTP and renders them in a GPU-backed OpenGL window at a 60 FPS target. It supports both 2D and 3D payloads, includes unit tests, ships with example scenes and helper scripts, and now includes a browser-based control plane for build, run, test, docs, logs, and API workflows.

## What you get

- An embedded HTTP API for posting 2D or 3D JSON scenes.
- A renderer that uses OpenGL on the GPU, not software rendering on the CPU.
- A clean split between parsing/validation, shared scene state, API transport, and rendering.
- Unit tests for the scene codec, validation rules, and scene store behavior.
- PowerShell scripts for build, run, test, formatting, docs serving, code-doc generation, and sample posting.
- A browser-based control plane under `control_plane/` that can kick off builds, tests, smoke checks, docs, and API requests.
- A static dark-mode docs site under `docs/site`.
- Doxygen-ready source comments and a `Doxyfile` for generated code reference output.

## Repository layout

```text
.
|-- CMakeLists.txt
|-- CMakePresets.json
|-- Doxyfile
|-- examples/
|-- control_plane/
|-- scripts/
|-- src/
|   |-- api/
|   |-- app/
|   |-- core/
|   |-- domain/
|   `-- renderer/
|-- tests/
`-- docs/
    `-- site/
```

## Quick start

1. Run `.\scripts\bootstrap.ps1` to see which prerequisites are already installed.
2. Launch the browser control plane with `.\scripts\studio.ps1`.
3. Use the control plane dashboard to run bootstrap, build, tests, and app startup from the browser.
4. In the API Lab or another terminal, send a sample scene with `.\scripts\post-sample-2d.ps1` or `.\scripts\post-sample-3d.ps1`.
5. Open the docs site directly from the control plane or with `.\scripts\serve-docs.ps1`.
6. For a full Windows setup and troubleshooting guide, see `INSTALL.md`.

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

Helpful install routes:

- Ninja: `winget install Ninja-build.Ninja`
- LLVM and `clang-format`: `winget install LLVM.LLVM`
- Doxygen: `winget install DimitriVanHeesch.Doxygen`
- Python package: `python -m pip install jinja2`

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
- `POST /api/v1/scene/validate`
- `POST /api/v1/scene`

## Build and test scripts

- `.\scripts\bootstrap.ps1`
- `.\scripts\build.ps1`
- `.\scripts\run.ps1`
- `.\scripts\test.ps1`
- `.\scripts\check-all.ps1`
- `.\scripts\lint-control-plane.ps1`
- `.\scripts\coverage-control-plane.ps1`
- `.\scripts\verify-format.ps1`
- `.\scripts\package.ps1`
- `.\scripts\studio.ps1`
- `.\scripts\test-control-plane.ps1`
- `.\scripts\post-sample-2d.ps1`
- `.\scripts\post-sample-3d.ps1`
- `.\scripts\serve-docs.ps1`
- `.\scripts\generate-code-docs.ps1`
- `.\scripts\format.ps1`

## Documentation

- Beginner docs site: `docs/site/index.html`
- Field reference: `docs/site/field-reference.html`
- Control center guide: `docs/site/control-center.html`
- Architecture guide: `docs/site/architecture.html`
- API guide: `docs/site/api.html`
- Testing guide: `docs/site/testing.html`
- Code docs guide: `docs/site/code-docs.html`

## Browser control plane

Run `.\scripts\studio.ps1` to launch the browser-based dashboard. The control plane can:

- inspect local prerequisites
- kick off bootstrap, build, test, format, and code-doc jobs
- start and stop the managed Halcyn app process
- show control-plane logs and captured app output
- run smoke checks against the live Halcyn API
- proxy browser-issued requests into the live Halcyn API
- link directly into the docs site and generated code docs

## Code documentation generation

Run `.\scripts\generate-code-docs.ps1` after installing Doxygen. Generated HTML will be written to `docs/generated/code-reference`.

## Packaging

Run `.\scripts\package.ps1` to produce a versioned ZIP file under `artifacts/`. Each package includes the executable, examples, docs, and a `build-manifest.json` file with build metadata.

## Quality gates

- C++ warnings are treated as build failures by default.
- GitHub Actions lint the control plane, run coverage for it, build the native project, and run the native tests.
- The Pages workflow now publishes the static docs site together with generated Doxygen output.

## Notes about GPU rendering

The CPU still performs normal application work such as parsing JSON, handling HTTP requests, and submitting draw commands. The actual graphics pipeline work that turns vertices into pixels is performed by the GPU through OpenGL. This is the normal and correct architecture for modern real-time graphics applications.
