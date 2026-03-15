#include "desktop_app/Application.hpp"

#include <exception>
#include <iostream>
#include <string>
#include <vector>

/**
 * Converts raw command-line arguments into a vector of strings so the parser can work with a
 * friendlier type.
 */
std::vector<std::string> BuildArgumentVector(int argc, char** argv) {
  std::vector<std::string> arguments;
  arguments.reserve(static_cast<std::size_t>(argc > 0 ? argc - 1 : 0));

  for (int index = 1; index < argc; ++index) {
    arguments.emplace_back(argv[index]);
  }

  return arguments;
}

/**
 * Runs the full Halcyn application and prints human-readable errors if startup fails.
 */
int main(int argc, char** argv) {
  try {
    const auto arguments = BuildArgumentVector(argc, argv);
    const auto applicationConfiguration = halcyn::desktop_app::ParseCommandLineArguments(arguments);

    if (applicationConfiguration.showHelp) {
      halcyn::desktop_app::PrintHelpText();
      return 0;
    }

    halcyn::desktop_app::Application application(applicationConfiguration);
    return application.Run();
  } catch (const std::exception& error) {
    std::cerr << "Halcyn failed to start: " << error.what() << '\n';
    return 1;
  }
}
