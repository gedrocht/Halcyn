#pragma once

#include "domain/SceneTypes.hpp"

#include <memory>
#include <mutex>
#include <string>

namespace halcyn::core
{
/**
 * Stores the latest validated scene in a thread-safe way so the API thread can publish updates while the
 * render thread reads snapshots without stepping on partial writes.
 */
class SceneStore
{
public:
  /**
   * Builds the store with an initial scene so the renderer always has something valid to draw.
   */
  explicit SceneStore(domain::SceneDocument initialScene);

  /**
   * Replaces the currently active scene with a new validated document and returns the newly created snapshot.
   */
  [[nodiscard]] std::shared_ptr<const domain::SceneSnapshot> Replace(
    domain::SceneDocument document,
    std::string sourceLabel);

  /**
   * Returns the current immutable scene snapshot.
   */
  [[nodiscard]] std::shared_ptr<const domain::SceneSnapshot> GetCurrent() const;

private:
  /**
   * Protects access to the current snapshot pointer and version counter.
   */
  mutable std::mutex mutex_;

  /**
   * Tracks the next version number to assign to a scene update.
   */
  std::uint64_t nextVersion_ = 1;

  /**
   * Holds the latest versioned scene.
   */
  std::shared_ptr<domain::SceneSnapshot> currentSnapshot_;
};
}  // namespace halcyn::core

