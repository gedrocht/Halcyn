/**
 * @file
 * @brief Implements the bounded runtime log shared by the app, API, and browser tooling.
 */

#include "shared_runtime/RuntimeLog.hpp"

#include <algorithm>
#include <cstdlib>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <thread>
#include <utility>

#include <nlohmann/json.hpp>

#if defined(_WIN32)
#include <process.h>
#else
#include <unistd.h>
#endif

namespace halcyn::shared_runtime {
namespace {
std::filesystem::path ResolveActivityJournalPathFromEnvironment() {
#if defined(_WIN32)
  char* configuredPathText = nullptr;
  std::size_t configuredPathLength = 0;
  const errno_t resolveError =
      _dupenv_s(&configuredPathText, &configuredPathLength, "HALCYN_ACTIVITY_LOG_PATH");
  if (resolveError != 0 || configuredPathText == nullptr || configuredPathLength == 0) {
    std::free(configuredPathText);
    return {};
  }

  const std::string configuredPathString(configuredPathText);
  std::free(configuredPathText);
  if (configuredPathString.empty()) {
    return {};
  }

  return std::filesystem::path(configuredPathString);
#else
  const char* configuredPathText = std::getenv("HALCYN_ACTIVITY_LOG_PATH");
  if (configuredPathText == nullptr || std::string(configuredPathText).empty()) {
    return {};
  }

  return std::filesystem::path(configuredPathText);
#endif
}
} // namespace

RuntimeLog::RuntimeLog(std::size_t maxEntries)
    : maxEntries_(std::max<std::size_t>(1, maxEntries)),
      activityJournalPath_(ResolveActivityJournalPathFromEnvironment()) {}

void RuntimeLog::Write(LogLevel level, std::string component, std::string message) {
  RuntimeLogEntry entry;

  {
    // We build the entry and push it into the bounded in-memory log while holding
    // the mutex so readers always see a consistent ordered history.
    std::scoped_lock lock(mutex_);
    entry.sequence = nextSequence_++;
    entry.level = level;
    entry.component = std::move(component);
    entry.message = std::move(message);
    entry.timestampUtc = std::chrono::system_clock::now();

    entries_.push_back(entry);
    while (entries_.size() > maxEntries_) {
      entries_.pop_front();
    }
  }

  // The runtime log doubles as a console log so local development and the control
  // plane can both observe the same events without separate logging systems.
  std::cout << '[' << FormatTimestampUtc(entry.timestampUtc) << "] [" << ToString(entry.level)
            << "] [" << entry.component << "] " << entry.message << '\n';
  AppendActivityJournalEntry(entry);
}

std::vector<RuntimeLogEntry> RuntimeLog::GetRecent(std::size_t limit) const {
  std::scoped_lock lock(mutex_);

  const std::size_t safeLimit = std::max<std::size_t>(1, limit);
  const std::size_t availableCount = entries_.size();
  const std::size_t startIndex = availableCount > safeLimit ? availableCount - safeLimit : 0;

  // We return a copy so callers can inspect the recent log without holding the mutex
  // after this function returns.
  std::vector<RuntimeLogEntry> snapshot;
  snapshot.reserve(availableCount - startIndex);

  for (std::size_t index = startIndex; index < availableCount; ++index) {
    snapshot.push_back(entries_[index]);
  }

  return snapshot;
}

std::string RuntimeLog::ToString(LogLevel level) const {
  return halcyn::shared_runtime::ToString(level);
}

std::string RuntimeLog::FormatTimestampUtc(std::chrono::system_clock::time_point timestamp) const {
  const auto time = std::chrono::system_clock::to_time_t(timestamp);
  std::tm utcTime{};
#if defined(_WIN32)
  gmtime_s(&utcTime, &time);
#else
  gmtime_r(&time, &utcTime);
#endif

  std::ostringstream builder;
  builder << std::put_time(&utcTime, "%Y-%m-%d %H:%M:%S UTC");
  return builder.str();
}

void RuntimeLog::AppendActivityJournalEntry(const RuntimeLogEntry& entry) const {
  if (activityJournalPath_.empty()) {
    return;
  }

  try {
    std::filesystem::create_directories(activityJournalPath_.parent_path());
    std::ofstream journalFile(activityJournalPath_, std::ios::app);
    if (!journalFile.is_open()) {
      return;
    }

    // The activity journal is shared with Python tools and the browser monitor, so
    // we store one explicit JSON object per line instead of a renderer-specific format.
    std::ostringstream threadIdentifierBuilder;
    threadIdentifierBuilder << std::this_thread::get_id();
    const nlohmann::json journalEntry = {
        {"timestamp_utc", FormatTimestampUtc(entry.timestampUtc)},
        {"source_app", "visualizer"},
        {"component", entry.component},
        {"level", ToString(entry.level)},
        {"message", entry.message},
        {"process_id",
#if defined(_WIN32)
         static_cast<int>(::_getpid())
#else
         static_cast<int>(::getpid())
#endif
        },
        {"extra", {{"sequence", entry.sequence}, {"thread_id", threadIdentifierBuilder.str()}}},
    };
    journalFile << journalEntry.dump() << '\n';
  } catch (...) {
    // Activity-journal writing is helpful, but it must never crash the renderer.
  }
}

std::string ToString(LogLevel level) {
  switch (level) {
  case LogLevel::Debug:
    return "DEBUG";
  case LogLevel::Info:
    return "INFO";
  case LogLevel::Warning:
    return "WARN";
  case LogLevel::Error:
    return "ERROR";
  }

  return "INFO";
}
} // namespace halcyn::shared_runtime
