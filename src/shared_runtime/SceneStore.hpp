#pragma once

#include "scene_description/SceneTypes.hpp"

#include <memory>
#include <mutex>
#include <string>

/**
 * @file
 * @brief Declares the thread-safe store that holds the currently active scene snapshot.
 */

namespace halcyn::shared_runtime {
/**
 * @brief Stores the latest validated scene in a thread-safe way.
 *
 * @details
 * This class exists because Halcyn has at least two long-lived actors that care about scene data:
 *
 * - the HTTP API, which accepts updates
 * - the renderer, which reads the latest accepted scene every frame
 *
 * Rather than sharing a mutable scene object and forcing readers to worry about partially updated
 * state, `SceneStore` shares immutable @ref halcyn::scene_description::SceneSnapshot objects.
 *
 * That design keeps concurrency reasoning simple:
 *
 * - writers build a complete replacement snapshot first
 * - writers swap it in under a short lock
 * - readers receive a shared pointer to a stable immutable snapshot
 */
class SceneStore {
public:
  /**
   * @brief Builds the store with an initial scene so the renderer always has something valid to
   * draw.
   *
   * @param initialScene The first scene document the store should publish.
   */
  explicit SceneStore(scene_description::SceneDocument initialScene);

  /**
   * @brief Replaces the currently active scene with a new validated document.
   *
   * @param document The new validated scene document.
   * @param sourceLabel Human-readable note describing where the update came from.
   * @return The newly created immutable snapshot.
   *
   * @details
   * This method is the moment a new scene becomes the next authoritative state for the application.
   * The renderer will observe the new version number on a later frame and upload it to the GPU.
   */
  [[nodiscard]] std::shared_ptr<const scene_description::SceneSnapshot>
  Replace(scene_description::SceneDocument document, std::string sourceLabel);

  /**
   * @brief Returns the current immutable scene snapshot.
   *
   * @return A shared pointer to the latest active scene snapshot.
   */
  [[nodiscard]] std::shared_ptr<const scene_description::SceneSnapshot> GetCurrent() const;

private:
  /** Protects access to the current snapshot pointer and version counter. */
  mutable std::mutex mutex_;

  /** Tracks the next version number to assign to a scene update. */
  std::uint64_t nextVersion_ = 1;

  /** Holds the latest versioned scene. */
  std::shared_ptr<scene_description::SceneSnapshot> currentSnapshot_;
};
} // namespace halcyn::shared_runtime
