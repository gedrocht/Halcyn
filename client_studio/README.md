# Client Studio

Client Studio is the browser-facing scene authoring surface for Halcyn.

It lives in its own top-level folder on purpose:

- the browser UI is separated from the control-plane dashboard
- the control-plane Python code still owns the tested scene-generation logic
- the repo keeps one contract, one CI surface, and one release story

Today the browser app is a build-free static interface served by the existing Python control plane at
`/client/`. That choice keeps the quality gates simple on machines without Node.js while still leaving
the backend contract stable if this grows into a React/Vite app later.

## What it does

- exposes preset-driven 3D scene generation
- supports time, deterministic noise, pointer motion, microphone energy, and manual drive as inputs
- previews the generated JSON scene before applying it
- validates the scene against the live Halcyn API before submitting it
- can auto-apply updates at a fixed interval for live performance workflows

## Main pieces

- `static/index.html`: browser entry point
- `static/app.js`: browser logic, live signal capture, and preview/apply orchestration
- `static/styles.css`: dedicated visual design for the client-facing UI

## Backend contract

The browser UI talks to these control-plane routes:

- `GET /api/client-studio/catalog`
- `POST /api/client-studio/preview`
- `POST /api/client-studio/apply`

The translator behind those routes lives in `control_plane/client_studio.py`.
