#include "scene_description/SceneFactory.hpp"
#include "shared_runtime/SceneStore.hpp"

#include <catch2/catch_test_macros.hpp>

namespace halcyn::tests {
TEST_CASE("SceneStore exposes the initial bootstrap scene", "[scene-store]") {
  halcyn::shared_runtime::SceneStore sceneStore(
      halcyn::scene_description::CreateSample2DSceneDocument());
  const auto currentSceneSnapshot = sceneStore.GetCurrent();

  REQUIRE(currentSceneSnapshot);
  CHECK(currentSceneSnapshot->version == 1);
  CHECK(currentSceneSnapshot->sourceLabel == "bootstrap");
  CHECK(currentSceneSnapshot->document.kind ==
        halcyn::scene_description::SceneKind::TwoDimensional);
}

TEST_CASE("SceneStore replaces the active scene and increments the version", "[scene-store]") {
  halcyn::shared_runtime::SceneStore sceneStore(
      halcyn::scene_description::CreateSample2DSceneDocument());
  const auto updatedSnapshot =
      sceneStore.Replace(halcyn::scene_description::CreateSample3DSceneDocument(), "unit-test");

  REQUIRE(updatedSnapshot);
  CHECK(updatedSnapshot->version == 2);
  CHECK(updatedSnapshot->sourceLabel == "unit-test");
  CHECK(updatedSnapshot->document.kind == halcyn::scene_description::SceneKind::ThreeDimensional);

  const auto currentSnapshot = sceneStore.GetCurrent();
  CHECK(currentSnapshot->version == updatedSnapshot->version);
}
} // namespace halcyn::tests
