#pragma once

#include "core/RuntimeLog.hpp"
#include "api/ApiServer.hpp"
#include "core/SceneStore.hpp"
#include "domain/SceneJsonCodec.hpp"
#include "renderer/Renderer.hpp"

#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace halcyn::app
{
/**
 * Holds the top-level runtime settings for the whole application.
 */
struct ApplicationConfig
{
  /**
   * Stores every window and frame-pacing setting used by the renderer.
   */
  renderer::RendererConfig renderer {};

  /**
   * Stores every host, port, and payload-size setting used by the embedded HTTP API.
   */
  api::ApiServerConfig api {};

  /**
   * Optionally points at a JSON file that should be loaded before the app starts accepting live API traffic.
   */
  std::optional<std::string> initialSceneFile;

  /**
   * Chooses which built-in sample scene to load when no explicit file was requested.
   */
  std::string initialSample = "default";

  /**
   * Tells main() to print usage text instead of running the full application.
   */
  bool showHelp = false;
};

/**
 * Coordinates the API server, the renderer, and the scene store.
 */
class Application
{
public:
  /**
   * Builds the application with the requested runtime settings.
   */
  explicit Application(ApplicationConfig config);

  /**
   * Starts the API and render loop, then returns the process exit code.
   */
  int Run();

private:
  /**
   * Loads the initial scene chosen by the caller.
   */
  [[nodiscard]] domain::SceneDocument LoadInitialScene() const;

  /**
   * Reads a scene document from a JSON file on disk.
   */
  [[nodiscard]] domain::SceneDocument LoadSceneFromFile(const std::string& filePath) const;

  /**
   * Prints a short startup summary so beginners can immediately see the important URLs and settings.
   */
  void PrintStartupSummary(int listeningPort) const;

  /**
   * Stores the chosen runtime settings.
   */
  ApplicationConfig config_;
};

/**
 * Parses command-line arguments into a strongly typed application configuration.
 */
ApplicationConfig ParseCommandLineArguments(const std::vector<std::string>& arguments);

/**
 * Prints a concise command-line help message.
 */
void PrintHelpText();
}  // namespace halcyn::app
