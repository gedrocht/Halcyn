#pragma once

#include "scene_description/SceneLimits.hpp"

#include <chrono>
#include <cstdint>
#include <deque>
#include <mutex>
#include <string>
#include <vector>

/**
 * @file
 * @brief Declares the shared runtime log used by the desktop app, HTTP API, and browser tools.
 */

namespace halcyn::shared_runtime {
/**
 * @brief Describes the severity of one runtime log entry.
 */
enum class LogLevel { Debug, Info, Warning, Error };

/**
 * @brief Stores one runtime log event in a structured form.
 *
 * @details
 * Each log entry contains both human-facing and machine-usable information:
 *
 * - `sequence` keeps entries ordered even when timestamps are very close together
 * - `level` lets UIs filter or colorize messages
 * - `component` identifies where the message came from
 * - `message` is the readable explanation
 * - `timestampUtc` records when the event occurred
 */
struct RuntimeLogEntry {
  /** Monotonic counter assigned when the message is written. */
  std::uint64_t sequence = 0;

  /** Severity level of the message. */
  LogLevel level = LogLevel::Info;

  /** Human-readable subsystem name such as `app`, `renderer`, or `api`. */
  std::string component;

  /** The actual message text. */
  std::string message;

  /** UTC timestamp recorded when the log entry was created. */
  std::chrono::system_clock::time_point timestampUtc = std::chrono::system_clock::now();
};

/**
 * @brief Keeps a bounded, thread-safe runtime log buffer.
 *
 * @details
 * This class deliberately serves two audiences at once:
 *
 * - local terminal users, by mirroring messages to `stdout`
 * - programmatic tools, by storing recent entries in memory for the HTTP API and browser UI
 *
 * That means Halcyn does not need one logging system for the console and a separate one for the
 * browser Control Center.
 *
 * Example:
 *
 * @code{.cpp}
 * halcyn::shared_runtime::RuntimeLog runtimeLog;
 * runtimeLog.Write(halcyn::shared_runtime::LogLevel::Info, "app", "Starting Halcyn.");
 *
 * const auto recentEntries = runtimeLog.GetRecent(25);
 * @endcode
 */
class RuntimeLog {
public:
  /**
   * @brief Builds the log buffer with a configurable retention limit.
   *
   * @param maxEntries Maximum number of recent entries kept in memory. Values smaller than 1 are
   * clamped to 1.
   */
  explicit RuntimeLog(
      std::size_t maxEntries = scene_description::SceneLimits::kMaxRuntimeLogEntries);

  /**
   * @brief Appends one new log entry and mirrors it to the console.
   *
   * @param level Severity level for the entry.
   * @param component Short subsystem label such as `app`, `renderer`, or `api`.
   * @param message Human-readable message text.
   */
  void Write(LogLevel level, std::string component, std::string message);

  /**
   * @brief Returns the newest log entries, up to the requested limit.
   *
   * @param limit Maximum number of entries to return.
   * @return A copied vector of recent entries ordered from oldest to newest within the returned
   * slice.
   */
  [[nodiscard]] std::vector<RuntimeLogEntry> GetRecent(std::size_t limit) const;

private:
  /**
   * @brief Converts a log level to the short label written into the console and API responses.
   */
  [[nodiscard]] std::string ToString(LogLevel level) const;

  /**
   * @brief Formats a UTC timestamp into an ISO-like string for console readability.
   */
  [[nodiscard]] std::string
  FormatTimestampUtc(std::chrono::system_clock::time_point timestamp) const;

  /** Protects the deque of log entries and the sequence counter. */
  mutable std::mutex mutex_;

  /** Stores the newest runtime log entries. */
  std::deque<RuntimeLogEntry> entries_;

  /** Stores the next unique sequence number assigned to a log entry. */
  std::uint64_t nextSequence_ = 1;

  /** Caps how many entries remain in memory. */
  std::size_t maxEntries_ = scene_description::SceneLimits::kMaxRuntimeLogEntries;
};

/**
 * @brief Converts a log level into the uppercase string used by API responses and documentation.
 */
std::string ToString(LogLevel level);
} // namespace halcyn::shared_runtime
