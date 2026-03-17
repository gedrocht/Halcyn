/**
 * @file
 * @brief Implements the top-level application lifecycle and command-line parsing helpers.
 *
 * @details
 * This file answers the question "How does Halcyn turn configuration into a running program?"
 * It wires together the scene codec, shared scene store, runtime log, HTTP API, and renderer, then
 * defines the order in which those long-lived services start and stop.
 */

#include "desktop_app/Application.hpp"

#include "scene_description/SceneFactory.hpp"

#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace halcyn::desktop_app {
namespace {
std::string JoinValidationErrors(const std::vector<scene_description::ValidationError>& errors) {
  // Validation errors are stored as structured records so code can inspect them,
  // but when we need to show them to a person we flatten them into a readable list.
  // Keeping that formatting in one helper keeps startup error messages consistent.
  std::ostringstream formattedMessageBuilder;
  for (const scene_description::ValidationError& error : errors) {
    formattedMessageBuilder << " - " << error.path << ": " << error.message << '\n';
  }
  return formattedMessageBuilder.str();
}
} // namespace

Application::Application(ApplicationConfig applicationConfiguration)
    : applicationConfig_(std::move(applicationConfiguration)) {}

int Application::Run() {
  // The application is built from a few long-lived shared services:
  // - a codec that knows how to turn scene JSON into C++ data and back
  // - a runtime log that both the API server and renderer can write into
  // - a scene store that always holds the scene the renderer should currently draw
  //
  // We create them here first so every subsystem works with the same shared state.
  auto sceneJsonCodec = std::make_shared<scene_description::SceneJsonCodec>();
  auto runtimeLog = std::make_shared<shared_runtime::RuntimeLog>();
  auto sceneStore = std::make_shared<shared_runtime::SceneStore>(LoadInitialScene());
  http_api::ApiServer httpApiServer(applicationConfig_.httpApi, sceneStore, sceneJsonCodec,
                                    runtimeLog);
  opengl_renderer::Renderer renderer(applicationConfig_.renderer, sceneStore, runtimeLog);

  runtimeLog->Write(shared_runtime::LogLevel::Info, "app", "Starting Halcyn Visualizer.");

  try {
    // The API server is started first so external tools can immediately talk to
    // the app once the renderer window opens. After that, the renderer owns the
    // main loop until the user closes the window.
    httpApiServer.Start();
    PrintStartupSummary(httpApiServer.GetBoundPort());
    renderer.Run();
    httpApiServer.Stop();
    runtimeLog->Write(shared_runtime::LogLevel::Info, "app",
                      "Halcyn Visualizer shut down cleanly.");
    return 0;
  } catch (...) {
    httpApiServer.Stop();
    runtimeLog->Write(shared_runtime::LogLevel::Error, "app",
                      "Halcyn Visualizer stopped because an unhandled exception escaped.");
    throw;
  }
}

scene_description::SceneDocument Application::LoadInitialScene() const {
  // Startup scene selection is intentionally ordered from most explicit to least:
  // 1. a file the caller provided on the command line
  // 2. a named built-in sample
  // 3. the default safety-net scene if nothing else was requested
  if (applicationConfig_.initialSceneFile.has_value()) {
    return LoadSceneFromFile(*applicationConfig_.initialSceneFile);
  }

  if (applicationConfig_.initialSample == "3d") {
    return scene_description::CreateSample3DSceneDocument();
  }

  if (applicationConfig_.initialSample == "2d") {
    return scene_description::CreateSample2DSceneDocument();
  }

  if (applicationConfig_.initialSample == "bar-wall" ||
      applicationConfig_.initialSample == "spectrograph") {
    return scene_description::CreateSampleBarWallSceneDocument();
  }

  return scene_description::CreateDefaultSceneDocument();
}

scene_description::SceneDocument Application::LoadSceneFromFile(const std::string& filePath) const {
  std::ifstream input(filePath);
  if (!input) {
    throw std::runtime_error("The scene file could not be opened: " + filePath);
  }

  // Read the whole file into memory because the scene codec expects one complete
  // JSON document string rather than a stream that is parsed incrementally.
  std::ostringstream fileContentsBuilder;
  fileContentsBuilder << input.rdbuf();

  scene_description::SceneJsonCodec sceneJsonCodec;
  const auto sceneParseResult = sceneJsonCodec.Parse(fileContentsBuilder.str());
  if (!sceneParseResult.succeeded || !sceneParseResult.scene.has_value()) {
    throw std::runtime_error("The scene file is not a valid Halcyn scene:\n" +
                             JoinValidationErrors(sceneParseResult.errors));
  }

  return *sceneParseResult.scene;
}

void Application::PrintStartupSummary(int listeningPort) const {
  std::cout << "Halcyn Visualizer is starting.\n";
  std::cout << "Window: " << applicationConfig_.renderer.windowWidth << "x"
            << applicationConfig_.renderer.windowHeight << " ("
            << applicationConfig_.renderer.targetFramesPerSecond << " FPS target)\n";
  std::cout << "HTTP API: http://" << applicationConfig_.httpApi.host << ':' << listeningPort
            << "/api/v1/health\n";
  std::cout << "POST scenes to: http://" << applicationConfig_.httpApi.host << ':' << listeningPort
            << "/api/v1/scene\n";
  std::cout << "Open docs with: scripts/serve-docs-site.ps1\n";
}

ApplicationConfig ParseCommandLineArguments(const std::vector<std::string>& arguments) {
  ApplicationConfig applicationConfiguration;

  for (std::size_t index = 0; index < arguments.size(); ++index) {
    const std::string& argument = arguments[index];

    auto requireOptionValue = [&](const char* optionName) -> const std::string& {
      // Most options are a pair like "--port 8080". This helper centralizes the
      // "move to the next token and fail nicely if it does not exist" behavior.
      if (index + 1 >= arguments.size()) {
        throw std::runtime_error(std::string("Missing value for command-line option ") +
                                 optionName);
      }

      ++index;
      return arguments[index];
    };

    if (argument == "--help" || argument == "-h") {
      applicationConfiguration.showHelp = true;
      continue;
    }

    if (argument == "--host") {
      applicationConfiguration.httpApi.host = requireOptionValue("--host");
      continue;
    }

    if (argument == "--port") {
      applicationConfiguration.httpApi.port = std::stoi(requireOptionValue("--port"));
      continue;
    }

    if (argument == "--width") {
      applicationConfiguration.renderer.windowWidth = std::stoi(requireOptionValue("--width"));
      continue;
    }

    if (argument == "--height") {
      applicationConfiguration.renderer.windowHeight = std::stoi(requireOptionValue("--height"));
      continue;
    }

    if (argument == "--fps") {
      applicationConfiguration.renderer.targetFramesPerSecond =
          std::stoi(requireOptionValue("--fps"));
      continue;
    }

    if (argument == "--title") {
      applicationConfiguration.renderer.windowTitle = requireOptionValue("--title");
      continue;
    }

    if (argument == "--scene-file") {
      applicationConfiguration.initialSceneFile = requireOptionValue("--scene-file");
      continue;
    }

    if (argument == "--sample") {
      const std::string& sampleValue = requireOptionValue("--sample");
      if (sampleValue != "default" && sampleValue != "2d" && sampleValue != "3d" &&
          sampleValue != "bar-wall" && sampleValue != "spectrograph") {
        throw std::runtime_error(
            "--sample must be one of: default, 2d, 3d, bar-wall, spectrograph");
      }

      applicationConfiguration.initialSample = sampleValue;
      continue;
    }

    throw std::runtime_error("Unknown command-line option: " + argument);
  }

  if (applicationConfiguration.httpApi.port < 0 || applicationConfiguration.httpApi.port > 65535) {
    throw std::runtime_error("--port must be between 0 and 65535");
  }

  if (applicationConfiguration.renderer.windowWidth <= 0) {
    throw std::runtime_error("--width must be greater than 0");
  }

  if (applicationConfiguration.renderer.windowHeight <= 0) {
    throw std::runtime_error("--height must be greater than 0");
  }

  if (applicationConfiguration.renderer.targetFramesPerSecond <= 0) {
    throw std::runtime_error("--fps must be greater than 0");
  }

  return applicationConfiguration;
}

void PrintHelpText() {
  std::cout << "Halcyn command-line options:\n";
  std::cout << "  --help, -h           Show this help text.\n";
  std::cout << "  --host <host>        Set the HTTP API host. Default: 127.0.0.1\n";
  std::cout
      << "  --port <port>        Set the HTTP API port. Use 0 for any free port. Default: 8080\n";
  std::cout << "  --width <pixels>     Set the render window width. Default: 1280\n";
  std::cout << "  --height <pixels>    Set the render window height. Default: 720\n";
  std::cout << "  --fps <number>       Set the target frame rate. Default: 60\n";
  std::cout << "  --title <text>       Set the render window title. Default: Halcyn Visualizer\n";
  std::cout << "  --sample <name>      Choose the startup sample. Values: default, 2d, 3d, "
               "bar-wall, spectrograph\n";
  std::cout << "  --scene-file <path>  Load a scene JSON file before starting the API.\n";
}
} // namespace halcyn::desktop_app
