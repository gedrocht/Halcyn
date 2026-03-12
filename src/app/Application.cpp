#include "app/Application.hpp"

#include "domain/SceneFactory.hpp"

#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace halcyn::app
{
namespace
{
std::string JoinValidationErrors(const std::vector<domain::ValidationError>& errors)
{
  std::ostringstream builder;
  for (const domain::ValidationError& error : errors)
  {
    builder << " - " << error.path << ": " << error.message << '\n';
  }
  return builder.str();
}
}  // namespace

Application::Application(ApplicationConfig config) : config_(std::move(config))
{
}

int Application::Run()
{
  auto codec = std::make_shared<domain::SceneJsonCodec>();
  auto runtimeLog = std::make_shared<core::RuntimeLog>();
  auto sceneStore = std::make_shared<core::SceneStore>(LoadInitialScene());
  api::ApiServer apiServer(config_.api, sceneStore, codec, runtimeLog);
  renderer::Renderer renderer(config_.renderer, sceneStore, runtimeLog);

  runtimeLog->Write(core::LogLevel::Info, "app", "Starting Halcyn.");

  try
  {
    apiServer.Start();
    PrintStartupSummary(apiServer.GetBoundPort());
    renderer.Run();
    apiServer.Stop();
    runtimeLog->Write(core::LogLevel::Info, "app", "Halcyn shut down cleanly.");
    return 0;
  }
  catch (...)
  {
    apiServer.Stop();
    runtimeLog->Write(core::LogLevel::Error, "app", "Halcyn stopped because an unhandled exception escaped.");
    throw;
  }
}

domain::SceneDocument Application::LoadInitialScene() const
{
  if (config_.initialSceneFile.has_value())
  {
    return LoadSceneFromFile(*config_.initialSceneFile);
  }

  if (config_.initialSample == "3d")
  {
    return domain::CreateSample3DSceneDocument();
  }

  if (config_.initialSample == "2d")
  {
    return domain::CreateSample2DSceneDocument();
  }

  return domain::CreateDefaultSceneDocument();
}

domain::SceneDocument Application::LoadSceneFromFile(const std::string& filePath) const
{
  std::ifstream input(filePath);
  if (!input)
  {
    throw std::runtime_error("The scene file could not be opened: " + filePath);
  }

  std::ostringstream builder;
  builder << input.rdbuf();

  domain::SceneJsonCodec codec;
  const auto parseResult = codec.Parse(builder.str());
  if (!parseResult.succeeded || !parseResult.scene.has_value())
  {
    throw std::runtime_error(
      "The scene file is not a valid Halcyn scene:\n" + JoinValidationErrors(parseResult.errors));
  }

  return *parseResult.scene;
}

void Application::PrintStartupSummary(int listeningPort) const
{
  std::cout << "Halcyn is starting.\n";
  std::cout << "Window: " << config_.renderer.windowWidth << "x" << config_.renderer.windowHeight << " ("
            << config_.renderer.targetFramesPerSecond << " FPS target)\n";
  std::cout << "HTTP API: http://" << config_.api.host << ':' << listeningPort << "/api/v1/health\n";
  std::cout << "POST scenes to: http://" << config_.api.host << ':' << listeningPort << "/api/v1/scene\n";
  std::cout << "Open docs with: scripts/serve-docs.ps1\n";
}

ApplicationConfig ParseCommandLineArguments(const std::vector<std::string>& arguments)
{
  ApplicationConfig config;

  for (std::size_t index = 0; index < arguments.size(); ++index)
  {
    const std::string& argument = arguments[index];

    auto requireValue = [&](const char* optionName) -> const std::string&
    {
      if (index + 1 >= arguments.size())
      {
        throw std::runtime_error(std::string("Missing value for command-line option ") + optionName);
      }

      ++index;
      return arguments[index];
    };

    if (argument == "--help" || argument == "-h")
    {
      config.showHelp = true;
      continue;
    }

    if (argument == "--host")
    {
      config.api.host = requireValue("--host");
      continue;
    }

    if (argument == "--port")
    {
      config.api.port = std::stoi(requireValue("--port"));
      continue;
    }

    if (argument == "--width")
    {
      config.renderer.windowWidth = std::stoi(requireValue("--width"));
      continue;
    }

    if (argument == "--height")
    {
      config.renderer.windowHeight = std::stoi(requireValue("--height"));
      continue;
    }

    if (argument == "--fps")
    {
      config.renderer.targetFramesPerSecond = std::stoi(requireValue("--fps"));
      continue;
    }

    if (argument == "--title")
    {
      config.renderer.windowTitle = requireValue("--title");
      continue;
    }

    if (argument == "--scene-file")
    {
      config.initialSceneFile = requireValue("--scene-file");
      continue;
    }

    if (argument == "--sample")
    {
      const std::string& sampleValue = requireValue("--sample");
      if (sampleValue != "default" && sampleValue != "2d" && sampleValue != "3d")
      {
        throw std::runtime_error("--sample must be one of: default, 2d, 3d");
      }

      config.initialSample = sampleValue;
      continue;
    }

    throw std::runtime_error("Unknown command-line option: " + argument);
  }

  if (config.api.port < 0 || config.api.port > 65535)
  {
    throw std::runtime_error("--port must be between 0 and 65535");
  }

  if (config.renderer.windowWidth <= 0)
  {
    throw std::runtime_error("--width must be greater than 0");
  }

  if (config.renderer.windowHeight <= 0)
  {
    throw std::runtime_error("--height must be greater than 0");
  }

  if (config.renderer.targetFramesPerSecond <= 0)
  {
    throw std::runtime_error("--fps must be greater than 0");
  }

  return config;
}

void PrintHelpText()
{
  std::cout << "Halcyn command-line options:\n";
  std::cout << "  --help, -h           Show this help text.\n";
  std::cout << "  --host <host>        Set the HTTP API host. Default: 127.0.0.1\n";
  std::cout << "  --port <port>        Set the HTTP API port. Use 0 for any free port. Default: 8080\n";
  std::cout << "  --width <pixels>     Set the render window width. Default: 1280\n";
  std::cout << "  --height <pixels>    Set the render window height. Default: 720\n";
  std::cout << "  --fps <number>       Set the target frame rate. Default: 60\n";
  std::cout << "  --title <text>       Set the render window title. Default: Halcyn\n";
  std::cout << "  --sample <name>      Choose the startup sample. Values: default, 2d, 3d\n";
  std::cout << "  --scene-file <path>  Load a scene JSON file before starting the API.\n";
}
}  // namespace halcyn::app
