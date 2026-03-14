#pragma once

#include "domain/SceneLimits.hpp"

#include <chrono>
#include <cstdint>
#include <deque>
#include <mutex>
#include <string>
#include <vector>

namespace halcyn::core {
/**
 * Describes the severity of one runtime log entry.
 */
enum class LogLevel { Debug, Info, Warning, Error };

/**
 * Stores one runtime log event in a format that can be displayed in the console, returned by the
 * API, and shown in the browser-based control plane.
 */
struct RuntimeLogEntry {
  std::uint64_t sequence = 0;
  LogLevel level = LogLevel::Info;
  std::string component;
  std::string message;
  std::chrono::system_clock::time_point timestampUtc = std::chrono::system_clock::now();
};

/**
 * Keeps a bounded, thread-safe log buffer for the running application.
 */
class RuntimeLog {
public:
  /**
   * Builds the log buffer with a configurable retention limit.
   */
  explicit RuntimeLog(std::size_t maxEntries = domain::SceneLimits::kMaxRuntimeLogEntries);

  /**
   * Appends one new log entry and mirrors it to the console for users who are not using the web
   * dashboard.
   */
  void Write(LogLevel level, std::string component, std::string message);

  /**
   * Returns the newest log entries, up to the requested limit.
   */
  [[nodiscard]] std::vector<RuntimeLogEntry> GetRecent(std::size_t limit) const;

private:
  /**
   * Converts a log level to the short label written into the console and API responses.
   */
  [[nodiscard]] std::string ToString(LogLevel level) const;

  /**
   * Formats a UTC timestamp into an ISO-like string for console readability.
   */
  [[nodiscard]] std::string
  FormatTimestampUtc(std::chrono::system_clock::time_point timestamp) const;

  /**
   * Protects the deque of log entries and the sequence counter.
   */
  mutable std::mutex mutex_;

  /**
   * Stores the newest runtime log entries.
   */
  std::deque<RuntimeLogEntry> entries_;

  /**
   * Stores the next unique sequence number assigned to a log entry.
   */
  std::uint64_t nextSequence_ = 1;

  /**
   * Caps how many entries remain in memory.
   */
  std::size_t maxEntries_ = domain::SceneLimits::kMaxRuntimeLogEntries;
};

/**
 * Converts a log level into the string used by API responses and documentation.
 */
std::string ToString(LogLevel level);
} // namespace halcyn::core
