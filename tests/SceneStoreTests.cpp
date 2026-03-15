#include "core/SceneStore.hpp"
#include "domain/SceneFactory.hpp"

#include <catch2/catch_test_macros.hpp>

namespace halcyn::tests {
TEST_CASE("SceneStore exposes the initial bootstrap scene", "[scene-store]") {
  halcyn::core::SceneStore sceneStore(halcyn::domain::CreateSample2DSceneDocument());
  const auto currentSceneSnapshot = sceneStore.GetCurrent();

  REQUIRE(currentSceneSnapshot);
  CHECK(currentSceneSnapshot->version == 1);
  CHECK(currentSceneSnapshot->sourceLabel == "bootstrap");
  CHECK(currentSceneSnapshot->document.kind == halcyn::domain::SceneKind::TwoDimensional);
}

TEST_CASE("SceneStore replaces the active scene and increments the version", "[scene-store]") {
  halcyn::core::SceneStore sceneStore(halcyn::domain::CreateSample2DSceneDocument());
  const auto updatedSnapshot =
      sceneStore.Replace(halcyn::domain::CreateSample3DSceneDocument(), "unit-test");

  REQUIRE(updatedSnapshot);
  CHECK(updatedSnapshot->version == 2);
  CHECK(updatedSnapshot->sourceLabel == "unit-test");
  CHECK(updatedSnapshot->document.kind == halcyn::domain::SceneKind::ThreeDimensional);

  const auto currentSnapshot = sceneStore.GetCurrent();
  CHECK(currentSnapshot->version == updatedSnapshot->version);
}
} // namespace halcyn::tests
