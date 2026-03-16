/**
 * @file
 * @brief Defines the dedicated executable entry point for the spectrograph-oriented renderer.
 *
 * @details
 * This executable intentionally reuses the same shared C++ application support library as the
 * standard Halcyn app. The important difference is its default personality:
 *
 * - a spectrograph-style startup sample
 * - a distinct window title
 * - a different default API port so it can coexist with the regular renderer more easily
 *
 * That means we get a second renderer app without forking the engine.
 */

#include "desktop_app/Application.hpp"

#include <exception>
#include <iostream>
#include <string>
#include <vector>

namespace {
std::vector<std::string> BuildArgumentVector(int argc, char** argv) {
  std::vector<std::string> arguments;
  arguments.reserve(static_cast<std::size_t>(argc > 0 ? argc - 1 : 0));

  for (int argumentIndex = 1; argumentIndex < argc; ++argumentIndex) {
    arguments.emplace_back(argv[argumentIndex]);
  }

  return arguments;
}
} // namespace

int main(int argc, char** argv) {
  try {
    const auto arguments = BuildArgumentVector(argc, argv);
    auto applicationConfiguration = halcyn::desktop_app::ParseCommandLineArguments(arguments);

    if (applicationConfiguration.showHelp) {
      halcyn::desktop_app::PrintHelpText();
      return 0;
    }

    // The dedicated spectrograph app only overrides values when the caller left them at the
    // ordinary Halcyn defaults. Explicit command-line choices still win.
    if (applicationConfiguration.renderer.windowTitle == "Halcyn") {
      applicationConfiguration.renderer.windowTitle = "Halcyn Spectrograph";
    }

    if (applicationConfiguration.httpApi.port == 8080) {
      applicationConfiguration.httpApi.port = 8090;
    }

    if (!applicationConfiguration.initialSceneFile.has_value() &&
        applicationConfiguration.initialSample == "default") {
      applicationConfiguration.initialSample = "spectrograph";
    }

    halcyn::desktop_app::Application application(applicationConfiguration);
    return application.Run();
  } catch (const std::exception& error) {
    std::cerr << "Halcyn Spectrograph failed to start: " << error.what() << '\n';
    return 1;
  }
}
