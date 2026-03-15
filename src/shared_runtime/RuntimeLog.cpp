#include "shared_runtime/RuntimeLog.hpp"

#include <algorithm>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <utility>

namespace halcyn::shared_runtime {
RuntimeLog::RuntimeLog(std::size_t maxEntries)
    : maxEntries_(std::max<std::size_t>(1, maxEntries)) {}

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
