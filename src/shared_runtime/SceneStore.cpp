#include "shared_runtime/SceneStore.hpp"

#include <utility>

namespace halcyn::shared_runtime {
SceneStore::SceneStore(scene_description::SceneDocument initialScene) {
  currentSnapshot_ = std::make_shared<scene_description::SceneSnapshot>();
  currentSnapshot_->version = nextVersion_++;
  currentSnapshot_->document = std::move(initialScene);
  currentSnapshot_->sourceLabel = "bootstrap";
  currentSnapshot_->updatedAtUtc = std::chrono::system_clock::now();
}

std::shared_ptr<const scene_description::SceneSnapshot>
SceneStore::Replace(scene_description::SceneDocument document, std::string sourceLabel) {
  auto snapshot = std::make_shared<scene_description::SceneSnapshot>();
  snapshot->version = 0;
  snapshot->document = std::move(document);
  snapshot->sourceLabel = std::move(sourceLabel);
  snapshot->updatedAtUtc = std::chrono::system_clock::now();

  std::scoped_lock lock(mutex_);
  snapshot->version = nextVersion_++;
  currentSnapshot_ = snapshot;
  return currentSnapshot_;
}

std::shared_ptr<const scene_description::SceneSnapshot> SceneStore::GetCurrent() const {
  std::scoped_lock lock(mutex_);
  return currentSnapshot_;
}
} // namespace halcyn::shared_runtime
