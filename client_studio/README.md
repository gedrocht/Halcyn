# Client Studio

Client Studio is the browser-facing scene authoring surface for Halcyn.

It lives in its own top-level folder on purpose:

- the browser UI is separated from the control-plane dashboard
- the control-plane Python code still owns the tested scene-generation logic
- the repo keeps one contract, one CI surface, and one release story

Today the browser app is a build-free static interface served by the existing Python control plane at
`/client/`. That choice keeps the quality gates simple on machines without Node.js while still leaving
the backend contract stable if this grows into a React/Vite app later.

The current latency-sensitive architecture uses a server-side live session instead of sending one full
scene from the browser on every interactive change. The browser now sends lighter control updates to
the control plane, and the control plane owns the steady stream of generated scenes sent to the live
renderer. Session status now flows back to the browser over a server-sent event stream instead of
tight polling, and the browser deduplicates/debounces live control updates so it does less useless
work while you manipulate the scene.

## What it does

- exposes preset-driven 3D scene generation
- supports time, deterministic noise, pointer motion, microphone energy, and manual drive as inputs
- previews the generated JSON scene before applying it
- can submit one scene immediately on demand
- can run a persistent live session that keeps streaming scenes to the renderer on a server-side cadence
- keeps the browser-to-control-plane messages smaller than the browser-to-renderer scene payloads
- receives live-session telemetry from the server without polling every few hundred milliseconds

## Main pieces

- `static/index.html`: browser entry point
- `static/app.js`: browser logic, live signal capture, preview, and session control orchestration
- `static/styles.css`: dedicated visual design for the client-facing UI
- `../control_plane/client_studio.py`: pure scene-generation and preset logic
- `../control_plane/client_studio_live.py`: server-side live-session engine

## Backend contract

The browser UI talks to these control-plane routes:

- `GET /api/client-studio/catalog`
- `POST /api/client-studio/preview`
- `POST /api/client-studio/apply`
- `GET /api/client-studio/session`
- `GET /api/client-studio/session/stream`
- `POST /api/client-studio/session/configure`
- `POST /api/client-studio/session/start`
- `POST /api/client-studio/session/stop`

The translator behind those routes lives in `control_plane/client_studio.py`, and the live streaming
engine lives in `control_plane/client_studio_live.py`.
