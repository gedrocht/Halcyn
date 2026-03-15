#include "scene_description/SceneFactory.hpp"
#include "shared_runtime/SceneStore.hpp"

#include <catch2/catch_test_macros.hpp>

namespace halcyn::tests {
TEST_CASE("SceneStore exposes the initial bootstrap scene", "[scene-store]") {
  halcyn::shared_runtime::SceneStore store(
      halcyn::scene_description::CreateSample2DSceneDocument());
  const auto snapshot = store.GetCurrent();

  REQUIRE(snapshot);
  CHECK(snapshot->version == 1);
  CHECK(snapshot->sourceLabel == "bootstrap");
  CHECK(snapshot->document.kind == halcyn::scene_description::SceneKind::TwoDimensional);
}

TEST_CASE("SceneStore replaces the active scene and increments the version", "[scene-store]") {
  halcyn::shared_runtime::SceneStore store(
      halcyn::scene_description::CreateSample2DSceneDocument());
  const auto updatedSnapshot =
      store.Replace(halcyn::scene_description::CreateSample3DSceneDocument(), "unit-test");

  REQUIRE(updatedSnapshot);
  CHECK(updatedSnapshot->version == 2);
  CHECK(updatedSnapshot->sourceLabel == "unit-test");
  CHECK(updatedSnapshot->document.kind == halcyn::scene_description::SceneKind::ThreeDimensional);

  const auto currentSnapshot = store.GetCurrent();
  CHECK(currentSnapshot->version == updatedSnapshot->version);
}
} // namespace halcyn::tests
