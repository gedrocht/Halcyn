#pragma once

#include "core/RuntimeLog.hpp"
#include "core/SceneStore.hpp"
#include "domain/SceneFactory.hpp"
#include "domain/SceneJsonCodec.hpp"
#include "domain/SceneLimits.hpp"

#include <httplib.h>

#include <atomic>
#include <memory>
#include <string>
#include <thread>

namespace halcyn::api
{
/**
 * Holds the runtime settings for the embedded HTTP API.
 */
struct ApiServerConfig
{
  /**
   * Chooses which network interface the embedded HTTP server binds to.
   */
  std::string host = "127.0.0.1";

  /**
   * Chooses which TCP port the API listens on. Use 0 to ask the operating system for any free port.
   */
  int port = 8080;

  /**
   * Caps the maximum size of one incoming HTTP request body so oversized scene submissions fail cleanly.
   */
  std::size_t maxPayloadBytes = domain::SceneLimits::kMaxRequestPayloadBytes;
};

/**
 * Runs a small HTTP server that accepts JSON scene submissions and publishes them into the shared scene store.
 */
class ApiServer
{
public:
  /**
   * Builds the server with the shared state and codec objects it needs to handle requests.
   */
  ApiServer(
    ApiServerConfig config,
    std::shared_ptr<core::SceneStore> sceneStore,
    std::shared_ptr<domain::SceneJsonCodec> codec,
    std::shared_ptr<core::RuntimeLog> runtimeLog);

  /**
   * Stops the server if it is still running. This keeps shutdown tidy even when the caller forgets to stop it.
   */
  ~ApiServer();

  /**
   * Starts listening for HTTP requests on a background thread.
   */
  void Start();

  /**
   * Requests a clean server shutdown and waits for the background thread to exit.
   */
  void Stop();

  /**
   * Returns whether the server is currently listening.
   */
  [[nodiscard]] bool IsRunning() const;

  /**
   * Returns the TCP port that the server successfully bound to. This is especially useful when callers request port 0.
   */
  [[nodiscard]] int GetBoundPort() const;

private:
  /**
   * Registers all HTTP routes before the server starts listening.
   */
  void ConfigureRoutes();

  /**
   * Builds the JSON body returned to callers when validation fails.
   */
  [[nodiscard]] std::string BuildValidationErrorResponse(const std::vector<domain::ValidationError>& errors) const;

  /**
   * Builds the JSON response returned by the log endpoint.
   */
  [[nodiscard]] std::string BuildRuntimeLogResponse(std::size_t limit) const;

  /**
   * Builds the JSON response returned by the runtime limits endpoint.
   */
  [[nodiscard]] std::string BuildRuntimeLimitsResponse() const;

  /**
   * Stores the chosen host and port values.
   */
  ApiServerConfig config_;

  /**
   * Points at the shared scene store used by the renderer and API.
   */
  std::shared_ptr<core::SceneStore> sceneStore_;

  /**
   * Points at the codec used to parse and serialize JSON scene payloads.
   */
  std::shared_ptr<domain::SceneJsonCodec> codec_;

  /**
   * Stores recent runtime log messages for API diagnostics and the browser-based control plane.
   */
  std::shared_ptr<core::RuntimeLog> runtimeLog_;

  /**
   * Owns the underlying HTTP server implementation.
   */
  httplib::Server server_;

  /**
   * Runs the blocking listen loop outside the render thread.
   */
  std::thread serverThread_;

  /**
   * Tracks whether the server is actively listening.
   */
  std::atomic<bool> isRunning_ = false;

  /**
   * Stores the actual bound port after startup succeeds.
   */
  std::atomic<int> boundPort_ = 0;
};
}  // namespace halcyn::api
