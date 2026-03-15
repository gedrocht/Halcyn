#pragma once

#include "scene_description/SceneFactory.hpp"
#include "scene_description/SceneJsonCodec.hpp"
#include "scene_description/SceneLimits.hpp"
#include "shared_runtime/RuntimeLog.hpp"
#include "shared_runtime/SceneStore.hpp"

#include <httplib.h>

#include <atomic>
#include <memory>
#include <string>
#include <thread>

/**
 * @file
 * @brief Declares the embedded HTTP API used to inspect and update the active scene.
 */

namespace halcyn::http_api {
/**
 * @brief Holds the runtime settings for the embedded HTTP API.
 */
struct ApiServerConfig {
  /**
   * @brief Chooses which network interface the embedded HTTP server binds to.
   *
   * @details
   * The default value keeps the API local to the machine by binding to `127.0.0.1`.
   */
  std::string host = "127.0.0.1";

  /**
   * @brief Chooses which TCP port the API listens on.
   *
   * @details
   * Use `0` to ask the operating system to choose any free port automatically.
   */
  int port = 8080;

  /**
   * @brief Caps the maximum size of one incoming HTTP request body.
   *
   * @details
   * This protects the process from oversized scene submissions before expensive parsing and
   * validation work begins.
   */
  std::size_t maxPayloadBytes = scene_description::SceneLimits::kMaxRequestPayloadBytes;
};

/**
 * @brief Runs a small HTTP server that accepts JSON scene submissions and publishes them into the
 * shared scene store.
 *
 * @details
 * `ApiServer` exists to let external tools interact with Halcyn without needing to know anything
 * about OpenGL or internal C++ data structures.
 *
 * Its responsibilities are:
 *
 * - expose health and diagnostics endpoints
 * - parse and validate incoming scene JSON
 * - publish accepted scenes into the shared scene store
 * - expose logs and example scenes
 *
 * The class uses **cpp-httplib** as the embedded server library. Helpful official references:
 *
 * - [cpp-httplib repository and README](https://github.com/yhirose/cpp-httplib)
 * - [nlohmann/json overview](https://nlohmann.github.io/json/api/basic_json/)
 *
 * Example:
 *
 * @code{.cpp}
 * auto sceneStore = std::make_shared<halcyn::shared_runtime::SceneStore>(
 *     halcyn::scene_description::CreateDefaultSceneDocument());
 * auto runtimeLog = std::make_shared<halcyn::shared_runtime::RuntimeLog>();
 * auto sceneJsonCodec = std::make_shared<halcyn::scene_description::SceneJsonCodec>();
 *
 * halcyn::http_api::ApiServerConfig serverConfiguration;
 * serverConfiguration.host = "127.0.0.1";
 * serverConfiguration.port = 8080;
 *
 * halcyn::http_api::ApiServer httpApiServer(
 *     serverConfiguration,
 *     sceneStore,
 *     sceneJsonCodec,
 *     runtimeLog);
 *
 * httpApiServer.Start();
 * // ...
 * httpApiServer.Stop();
 * @endcode
 */
class ApiServer {
public:
  /**
   * @brief Builds the server with the shared state and codec objects it needs to handle requests.
   *
   * @param serverConfiguration Host, port, and payload limit settings.
   * @param sceneStore Shared scene store used by the API and renderer.
   * @param sceneJsonCodec Codec used to parse submitted JSON and serialize stored scenes.
   * @param runtimeLog Shared runtime log used for diagnostics.
   */
  ApiServer(ApiServerConfig serverConfiguration,
            std::shared_ptr<shared_runtime::SceneStore> sceneStore,
            std::shared_ptr<scene_description::SceneJsonCodec> sceneJsonCodec,
            std::shared_ptr<shared_runtime::RuntimeLog> runtimeLog);

  /**
   * @brief Stops the server if it is still running.
   *
   * @details
   * This keeps shutdown tidy even when the caller forgets to stop the server explicitly.
   */
  ~ApiServer();

  /**
   * @brief Starts listening for HTTP requests on a background thread.
   *
   * @throws std::runtime_error if the server cannot bind or cannot enter the listening state.
   *
   * @details
   * The underlying `listen_after_bind` call is blocking, so Halcyn runs it on a dedicated thread.
   * That lets the main thread keep running the renderer.
   */
  void Start();

  /**
   * @brief Requests a clean server shutdown and waits for the background thread to exit.
   */
  void Stop();

  /**
   * @brief Returns whether the server is currently listening.
   */
  [[nodiscard]] bool IsRunning() const;

  /**
   * @brief Returns the TCP port that the server successfully bound to.
   *
   * @details
   * This is especially useful when callers request port `0` and let the operating system choose a
   * free port.
   */
  [[nodiscard]] int GetBoundPort() const;

private:
  /**
   * @brief Registers all HTTP routes before the server starts listening.
   *
   * @details
   * The route set intentionally includes both "real work" endpoints and "teaching / diagnostics"
   * endpoints so the app is easier to explore:
   *
   * - `/api/v1/health`
   * - `/api/v1/scene`
   * - `/api/v1/scene/validate`
   * - `/api/v1/runtime/logs`
   * - `/api/v1/runtime/limits`
   * - `/api/v1/examples/2d`
   * - `/api/v1/examples/3d`
   */
  void ConfigureRoutes();

  /**
   * @brief Builds the JSON body returned to callers when validation fails.
   */
  [[nodiscard]] std::string
  BuildValidationErrorResponse(const std::vector<scene_description::ValidationError>& errors) const;

  /**
   * @brief Builds the JSON response returned by the log endpoint.
   */
  [[nodiscard]] std::string BuildRuntimeLogResponse(std::size_t limit) const;

  /**
   * @brief Builds the JSON response returned by the runtime limits endpoint.
   */
  [[nodiscard]] std::string BuildRuntimeLimitsResponse() const;

  /** Stores the chosen host and port values. */
  ApiServerConfig serverConfiguration_;

  /** Points at the shared scene store used by the renderer and API. */
  std::shared_ptr<shared_runtime::SceneStore> sceneStore_;

  /** Points at the codec used to parse and serialize JSON scene payloads. */
  std::shared_ptr<scene_description::SceneJsonCodec> sceneJsonCodec_;

  /** Stores recent runtime log messages for API diagnostics and browser-based tools. */
  std::shared_ptr<shared_runtime::RuntimeLog> runtimeLog_;

  /** Owns the underlying HTTP server implementation from cpp-httplib. */
  httplib::Server httpServer_;

  /** Runs the blocking listen loop outside the render thread. */
  std::thread serverThread_;

  /** Tracks whether the server is actively listening. */
  std::atomic<bool> serverIsRunning_ = false;

  /** Stores the actual bound port after startup succeeds. */
  std::atomic<int> listeningPort_ = 0;
};
} // namespace halcyn::http_api
