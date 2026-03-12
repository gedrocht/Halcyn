#pragma once

#include <cstddef>

namespace halcyn::domain
{
/**
 * Groups the safety and usability limits enforced by the app.
 *
 * These limits exist for two reasons:
 * 1. They protect the program from unexpectedly huge requests that would be confusing for beginners to debug.
 * 2. They make the API contract concrete enough that the web tooling can explain what "too large" means.
 */
struct SceneLimits
{
  /**
   * Caps the raw HTTP request body size accepted by the scene submission endpoints.
   */
  static constexpr std::size_t kMaxRequestPayloadBytes = 2U * 1024U * 1024U;

  /**
   * Caps how many vertices any one scene can contain.
   */
  static constexpr std::size_t kMaxVertexCount = 50'000U;

  /**
   * Caps how many indices a 3D scene can contain when indexed drawing is used.
   */
  static constexpr std::size_t kMaxIndexCount = 150'000U;

  /**
   * Caps how many runtime log entries are kept in memory for the web dashboard and log endpoints.
   */
  static constexpr std::size_t kMaxRuntimeLogEntries = 1'500U;
};
}  // namespace halcyn::domain

