# Scene Studio

Scene Studio is the browser-facing scene authoring surface for Halcyn.

It lives in its own top-level folder on purpose:

- the browser UI is separated from the Control Center dashboard
- the Control Center Python code still owns the tested scene-generation logic
- the repo keeps one contract, one CI surface, and one release story

Today the browser app is a build-free static interface served by the existing Python Control Center at
`/scene-studio/`. That choice keeps the quality gates simple on machines without Node.js while still leaving
the backend contract stable if this grows into a React/Vite app later.

The current latency-sensitive architecture uses a server-side live session instead of sending one full
scene from the browser on every interactive change. The browser now sends lighter control updates to
the Control Center, and the Control Center owns the steady stream of generated scenes sent to the live
renderer. Session status now flows back to the browser over a server-sent event stream instead of
tight polling, and the browser deduplicates/debounces live control updates so it does less useless
work while you manipulate the scene.

## What it does

- exposes preset-driven 3D scene generation
- supports time, deterministic noise, pointer motion, microphone energy, and manual drive as inputs
- previews the generated JSON scene before applying it
- can submit one scene immediately on demand
- can run a persistent live session that keeps streaming scenes to the renderer on a server-side cadence
- keeps the browser-to-control-center messages smaller than the browser-to-renderer scene payloads
- receives live-session telemetry from the server without polling every few hundred milliseconds

## Main pieces

- `static/index.html`: browser entry point
- `static/app.js`: browser logic, live signal capture, preview, and session control orchestration
- `static/styles.css`: dedicated visual design for the client-facing UI
- `../browser_control_center/scene_studio_scene_builder.py`: pure scene-generation and preset logic
- `../browser_control_center/scene_studio_live_session.py`: server-side live-session engine

## Backend contract

The browser UI talks to these Control Center routes:

- `GET /api/scene-studio/catalog`
- `POST /api/scene-studio/preview`
- `POST /api/scene-studio/apply`
- `GET /api/scene-studio/session`
- `GET /api/scene-studio/session/stream`
- `POST /api/scene-studio/session/configure`
- `POST /api/scene-studio/session/start`
- `POST /api/scene-studio/session/stop`

The translator behind those routes lives in `browser_control_center/scene_studio_scene_builder.py`, and the live streaming
engine lives in `browser_control_center/scene_studio_live_session.py`.
