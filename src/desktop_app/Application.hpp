#pragma once

#include "http_api/ApiServer.hpp"
#include "opengl_renderer/Renderer.hpp"
#include "scene_description/SceneJsonCodec.hpp"
#include "shared_runtime/RuntimeLog.hpp"
#include "shared_runtime/SceneStore.hpp"

#include <memory>
#include <optional>
#include <string>
#include <vector>

/**
 * @file
 * @brief Declares the top-level application coordinator and command-line parsing helpers.
 */

namespace halcyn::desktop_app {
/**
 * @brief Holds the top-level runtime settings for the whole application.
 *
 * @details
 * This struct is deliberately plain and serializable-in-spirit. Its job is not to do work. Its job
 * is to gather every startup decision in one place so the rest of the application can be built from
 * one coherent configuration object.
 */
struct ApplicationConfig {
  /** Stores every window and frame-pacing setting used by the renderer. */
  opengl_renderer::RendererConfig renderer{};

  /** Stores every host, port, and payload-size setting used by the embedded HTTP API. */
  http_api::ApiServerConfig httpApi{};

  /**
   * @brief Optionally points at a JSON file that should be loaded before the app starts accepting
   * live API traffic.
   */
  std::optional<std::string> initialSceneFile;

  /**
   * @brief Chooses which built-in sample scene to load when no explicit file was requested.
   */
  std::string initialSample = "default";

  /**
   * @brief Tells `main()` to print usage text instead of running the full application.
   */
  bool showHelp = false;
};

/**
 * @brief Coordinates the API server, the renderer, and the shared scene state.
 *
 * @details
 * `Application` is the top-level conductor of the program. It is the class that turns configuration
 * into a running system.
 *
 * A useful beginner summary of `Run()` is:
 *
 * 1. Build the shared services.
 * 2. Load an initial scene.
 * 3. Start the HTTP API.
 * 4. Start the renderer loop.
 * 5. Shut everything down cleanly when rendering ends.
 *
 * That is why this class depends on several subsystems but does not try to implement their logic
 * itself.
 */
class Application {
public:
  /**
   * @brief Builds the application with the requested runtime settings.
   *
   * @param applicationConfiguration The complete startup configuration.
   */
  explicit Application(ApplicationConfig applicationConfiguration);

  /**
   * @brief Starts the API and render loop, then returns the process exit code.
   *
   * @return `0` on a clean run.
   */
  int Run();

private:
  /**
   * @brief Loads the initial scene chosen by the caller.
   *
   * @return A valid scene document ready to seed the shared scene store.
   */
  [[nodiscard]] scene_description::SceneDocument LoadInitialScene() const;

  /**
   * @brief Reads a scene document from a JSON file on disk.
   *
   * @param filePath Path to the JSON scene file.
   * @return The validated scene document described by that file.
   */
  [[nodiscard]] scene_description::SceneDocument
  LoadSceneFromFile(const std::string& filePath) const;

  /**
   * @brief Prints a short startup summary.
   *
   * @param listeningPort The actual port the embedded HTTP API is listening on.
   */
  void PrintStartupSummary(int listeningPort) const;

  /** Stores the chosen runtime settings. */
  ApplicationConfig applicationConfig_;
};

/**
 * @brief Parses command-line arguments into a strongly typed application configuration.
 *
 * @param arguments The command-line arguments after the executable name.
 * @return A complete application configuration.
 *
 * @throws std::runtime_error if an unknown option appears or if an option value is invalid.
 */
ApplicationConfig ParseCommandLineArguments(const std::vector<std::string>& arguments);

/**
 * @brief Prints a concise command-line help message.
 */
void PrintHelpText();
} // namespace halcyn::desktop_app
