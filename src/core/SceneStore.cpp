#include "core/SceneStore.hpp"

#include <utility>

namespace halcyn::core {
SceneStore::SceneStore(domain::SceneDocument initialScene) {
  // The store always holds a full immutable snapshot object rather than raw scene
  // data alone. That lets readers see the scene, version, source, and timestamp together.
  currentSnapshot_ = std::make_shared<domain::SceneSnapshot>();
  currentSnapshot_->version = nextVersion_++;
  currentSnapshot_->document = std::move(initialScene);
  currentSnapshot_->sourceLabel = "bootstrap";
  currentSnapshot_->updatedAtUtc = std::chrono::system_clock::now();
}

std::shared_ptr<const domain::SceneSnapshot> SceneStore::Replace(domain::SceneDocument document,
                                                                 std::string sourceLabel) {
  // We build the replacement snapshot first, then swap it under the lock in one
  // short critical section so readers either see the old full snapshot or the new one.
  auto replacementSnapshot = std::make_shared<domain::SceneSnapshot>();
  replacementSnapshot->version = 0;
  replacementSnapshot->document = std::move(document);
  replacementSnapshot->sourceLabel = std::move(sourceLabel);
  replacementSnapshot->updatedAtUtc = std::chrono::system_clock::now();

  std::scoped_lock lock(mutex_);
  replacementSnapshot->version = nextVersion_++;
  currentSnapshot_ = replacementSnapshot;
  return currentSnapshot_;
}

std::shared_ptr<const domain::SceneSnapshot> SceneStore::GetCurrent() const {
  // Returning a shared_ptr to an immutable snapshot lets readers keep a stable
  // view even if another thread replaces the current scene immediately afterward.
  std::scoped_lock lock(mutex_);
  return currentSnapshot_;
}
} // namespace halcyn::core
