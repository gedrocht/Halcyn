# Halcyn Code Reference

Welcome to the Doxygen reference for **Halcyn**, a small graphics application that renders 2D and
3D scenes described as JSON.

This documentation is intentionally written for two audiences at once:

- people who already know C++, OpenGL, and HTTP tooling and want a precise API reference
- beginners who want to understand **what each subsystem does, how data moves through it, and why
  the code is organized this way**

If you are new to the project, the fastest path is:

1. Read this page for the big picture.
2. Read [Scene JSON Guide](scene_json_guide.md) to understand the data the program accepts.
3. Read [Usage Examples](usage_examples.md) to see the main classes in context.
4. Read [External Library Guide](external_library_guide.md) when you want to understand where a
   type or function came from outside the repository.
5. Then move into the class and file reference for the part you want to change.

## What Halcyn Does

At a high level, Halcyn does four jobs:

1. It **accepts scene descriptions** from files or HTTP requests.
2. It **parses and validates** those descriptions into typed C++ data.
3. It **stores the latest accepted scene** in a thread-safe shared location.
4. It **renders that scene** in an OpenGL window while exposing runtime information through an HTTP
   API and a browser-based control surface.

That means Halcyn is not "just a renderer" and not "just a web service". It is a small,
single-process system where rendering, HTTP communication, validation, logging, and browser control
all cooperate around one shared scene model.

## End-to-End Data Flow

The core flow looks like this:

1. `main()` builds a `halcyn::desktop_app::Application`.
2. `halcyn::desktop_app::Application` creates the long-lived shared services:
   - `halcyn::scene_description::SceneJsonCodec`
   - `halcyn::shared_runtime::RuntimeLog`
   - `halcyn::shared_runtime::SceneStore`
   - `halcyn::http_api::ApiServer`
   - `halcyn::opengl_renderer::Renderer`
3. The HTTP API accepts scene JSON with `POST /api/v1/scene`.
4. `halcyn::scene_description::SceneJsonCodec` turns the raw JSON text into a typed
   `halcyn::scene_description::SceneDocument`.
5. `halcyn::scene_description::ValidateSceneDocument` checks that the scene is not only shaped
   correctly, but also *makes sense to render*.
6. `halcyn::shared_runtime::SceneStore` swaps in a new immutable scene snapshot.
7. `halcyn::opengl_renderer::Renderer` notices the snapshot version changed, converts the scene to
   GPU-friendly data with `halcyn::scene_description::BuildRenderScene`, uploads it, and draws it.

The browser-based control surfaces sit on top of that same flow. They do not talk to the renderer
directly. Instead, they call the HTTP API and let the shared scene store remain the single source
of truth.

## Why The Subsystems Are Split The Way They Are

The source tree is divided by responsibility:

- `src/desktop_app`
  - top-level process startup and command-line configuration
  - owns the lifecycle of the renderer and HTTP server
- `src/http_api`
  - translates HTTP requests into scene operations and diagnostic responses
- `src/scene_description`
  - owns the scene data model, JSON parsing, validation, and conversion to renderable buffers
- `src/shared_runtime`
  - owns shared state such as the active scene snapshot and runtime log
- `src/opengl_renderer`
  - owns the GLFW window, OpenGL resources, and frame loop

This split keeps the project teachable:

- scene validation logic can be tested without a window
- rendering logic can assume it receives validated scene data
- the HTTP layer can stay focused on transport and diagnostics
- the application bootstrap can stay small and readable

## Beginner Mental Model

If you are new to graphics or service code, it helps to think in layers:

- **Scene description layer**
  - "What should be drawn?"
- **Transport layer**
  - "How does new scene data arrive?"
- **Shared runtime layer**
  - "Where does the latest accepted scene live so multiple threads can see it?"
- **Rendering layer**
  - "How does the GPU turn the scene into pixels?"

The code is organized so each layer answers one of those questions clearly.

## Common Starting Points

### "I want to understand the JSON format."

Start with:

- `halcyn::scene_description::SceneDocument`
- `halcyn::scene_description::Scene2D`
- `halcyn::scene_description::Scene3D`
- `halcyn::scene_description::SceneJsonCodec`
- [Scene JSON Guide](scene_json_guide.md)

### "I want to understand how scenes are accepted over HTTP."

Start with:

- `halcyn::http_api::ApiServer`
- `halcyn::scene_description::SceneJsonCodec`
- `halcyn::shared_runtime::SceneStore`
- [Usage Examples](usage_examples.md)

### "I want to understand how rendering works."

Start with:

- `halcyn::opengl_renderer::Renderer`
- `halcyn::opengl_renderer::ShaderProgram`
- `halcyn::scene_description::BuildRenderScene`
- [External Library Guide](external_library_guide.md)

### "I want to add a new browser control."

Start with:

- `browser_control_center/control_center_http_server.py`
- `browser_control_center/control_center_state.py`
- `browser_scene_studio/static/app.js`
- the HTTP routes in `halcyn::http_api::ApiServer`

## Project Philosophy

Halcyn intentionally chooses clarity over cleverness in many places:

- the scene JSON format is explicit rather than ultra-compact
- validation produces beginner-friendly error messages instead of terse parser failures
- the renderer replaces entire GPU buffers when the scene changes rather than doing premature
  partial-update optimization
- shared state is represented as immutable snapshots to keep multi-threaded reasoning simple

This means some code is more verbose than the shortest possible version, but it is also easier to
teach, debug, and extend safely.

## Related Pages

- [Usage Examples](usage_examples.md)
- [Scene JSON Guide](scene_json_guide.md)
- [External Library Guide](external_library_guide.md)
