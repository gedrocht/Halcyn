#include "core/SceneStore.hpp"

#include <utility>

namespace halcyn::core {
SceneStore::SceneStore(domain::SceneDocument initialScene) {
  currentSnapshot_ = std::make_shared<domain::SceneSnapshot>();
  currentSnapshot_->version = nextVersion_++;
  currentSnapshot_->document = std::move(initialScene);
  currentSnapshot_->sourceLabel = "bootstrap";
  currentSnapshot_->updatedAtUtc = std::chrono::system_clock::now();
}

std::shared_ptr<const domain::SceneSnapshot> SceneStore::Replace(domain::SceneDocument document,
                                                                 std::string sourceLabel) {
  auto snapshot = std::make_shared<domain::SceneSnapshot>();
  snapshot->version = 0;
  snapshot->document = std::move(document);
  snapshot->sourceLabel = std::move(sourceLabel);
  snapshot->updatedAtUtc = std::chrono::system_clock::now();

  std::scoped_lock lock(mutex_);
  snapshot->version = nextVersion_++;
  currentSnapshot_ = snapshot;
  return currentSnapshot_;
}

std::shared_ptr<const domain::SceneSnapshot> SceneStore::GetCurrent() const {
  std::scoped_lock lock(mutex_);
  return currentSnapshot_;
}
} // namespace halcyn::core
