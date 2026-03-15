# Usage Examples

This page shows small, realistic examples of how the major C++ subsystems fit together.

These examples are intentionally simple. They are meant to teach the flow of the code, not to be
copy-paste production snippets.

## Parsing Scene JSON

The most common entry point for scene data is `halcyn::scene_description::SceneJsonCodec`.

@code{.cpp}
#include "scene_description/SceneJsonCodec.hpp"

#include <iostream>

int main() {
  halcyn::scene_description::SceneJsonCodec sceneJsonCodec;

  const std::string jsonText = R"({
    "sceneType": "2d",
    "primitive": "triangles",
    "vertices": [
      { "x": -0.5, "y": -0.5, "r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0 },
      { "x":  0.0, "y":  0.5, "r": 0.0, "g": 1.0, "b": 0.0, "a": 1.0 },
      { "x":  0.5, "y": -0.5, "r": 0.0, "g": 0.0, "b": 1.0, "a": 1.0 }
    ]
  })";

  const auto sceneParseResult = sceneJsonCodec.Parse(jsonText);
  if (!sceneParseResult.succeeded) {
    for (const auto& error : sceneParseResult.errors) {
      std::cerr << error.path << ": " << error.message << '\n';
    }
    return 1;
  }

  std::cout << "Scene parsed successfully.\n";
}
@endcode

Why this matters:

- the codec is where raw JSON text becomes trusted typed data
- callers get a structured list of validation errors instead of just one parser exception
- the renderer never has to deal with malformed JSON directly

## Updating The Active Scene

After parsing and validation succeed, the next step is usually to replace the current scene in the
shared scene store.

@code{.cpp}
#include "scene_description/SceneFactory.hpp"
#include "shared_runtime/SceneStore.hpp"

int main() {
  auto initialSceneDocument = halcyn::scene_description::CreateDefaultSceneDocument();
  halcyn::shared_runtime::SceneStore sceneStore(initialSceneDocument);

  auto replacementSceneDocument = halcyn::scene_description::CreateSample3DSceneDocument();
  auto currentSceneSnapshot = sceneStore.Replace(std::move(replacementSceneDocument), "example");

  // The returned snapshot includes the scene, its version, and metadata about
  // where it came from.
  return static_cast<int>(currentSceneSnapshot->version);
}
@endcode

Why the API returns a snapshot instead of `void`:

- callers often want the assigned version number immediately
- returning the immutable snapshot keeps logs, API responses, and tests consistent
- the snapshot gives one stable view of the scene even if another thread updates the store later

## Building An HTTP API Around The Shared Scene

The embedded API server shares the same `SceneStore`, `RuntimeLog`, and `SceneJsonCodec` objects as
the renderer and application bootstrap.

@code{.cpp}
#include "http_api/ApiServer.hpp"
#include "scene_description/SceneFactory.hpp"
#include "scene_description/SceneJsonCodec.hpp"
#include "shared_runtime/RuntimeLog.hpp"
#include "shared_runtime/SceneStore.hpp"

int main() {
  auto sceneStore = std::make_shared<halcyn::shared_runtime::SceneStore>(
      halcyn::scene_description::CreateDefaultSceneDocument());
  auto runtimeLog = std::make_shared<halcyn::shared_runtime::RuntimeLog>();
  auto sceneJsonCodec = std::make_shared<halcyn::scene_description::SceneJsonCodec>();

  halcyn::http_api::ApiServerConfig serverConfiguration;
  serverConfiguration.host = "127.0.0.1";
  serverConfiguration.port = 8080;

  halcyn::http_api::ApiServer httpApiServer(
      serverConfiguration,
      sceneStore,
      sceneJsonCodec,
      runtimeLog);

  httpApiServer.Start();
  httpApiServer.Stop();
}
@endcode

Why Halcyn keeps the API embedded instead of running it as a separate process:

- the renderer and API need access to the same in-memory scene snapshot
- local tooling is simpler when one process owns the whole lifecycle
- this avoids adding inter-process communication before the project actually needs it

## Running The Full Desktop Application

The application class is the "big coordinator" that wires together scene loading, the API server,
and the renderer.

@code{.cpp}
#include "desktop_app/Application.hpp"

int main() {
  halcyn::desktop_app::ApplicationConfig applicationConfiguration;
  applicationConfiguration.httpApi.host = "127.0.0.1";
  applicationConfiguration.httpApi.port = 8080;
  applicationConfiguration.renderer.windowWidth = 1280;
  applicationConfiguration.renderer.windowHeight = 720;
  applicationConfiguration.initialSample = "3d";

  halcyn::desktop_app::Application application(applicationConfiguration);
  return application.Run();
}
@endcode

This is the most useful place to start if you want to understand the overall lifecycle.

## Renderer Perspective

The renderer works with `halcyn::scene_description::RenderScene`, not raw JSON and not the
high-level `SceneDocument` variant.

That means the rendering pipeline sees:

- one normalized vertex format
- one normalized optional index buffer
- one `SceneKind` that decides whether to build a 2D or 3D matrix

This is an important design choice because it keeps the GPU upload path simple.

## Suggested Reading Order

If you want to move from beginner to confident contributor, this order works well:

1. `halcyn::desktop_app::Application`
2. `halcyn::scene_description::SceneTypes`
3. `halcyn::scene_description::SceneJsonCodec`
4. `halcyn::scene_description::ValidateSceneDocument`
5. `halcyn::shared_runtime::SceneStore`
6. `halcyn::http_api::ApiServer`
7. `halcyn::opengl_renderer::Renderer`
8. `halcyn::opengl_renderer::ShaderProgram`
