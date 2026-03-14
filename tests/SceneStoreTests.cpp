#include "core/SceneStore.hpp"
#include "domain/SceneFactory.hpp"

#include <catch2/catch_test_macros.hpp>

namespace halcyn::tests {
TEST_CASE("SceneStore exposes the initial bootstrap scene", "[scene-store]") {
  halcyn::core::SceneStore store(halcyn::domain::CreateSample2DSceneDocument());
  const auto snapshot = store.GetCurrent();

  REQUIRE(snapshot);
  CHECK(snapshot->version == 1);
  CHECK(snapshot->sourceLabel == "bootstrap");
  CHECK(snapshot->document.kind == halcyn::domain::SceneKind::TwoDimensional);
}

TEST_CASE("SceneStore replaces the active scene and increments the version", "[scene-store]") {
  halcyn::core::SceneStore store(halcyn::domain::CreateSample2DSceneDocument());
  const auto updatedSnapshot =
      store.Replace(halcyn::domain::CreateSample3DSceneDocument(), "unit-test");

  REQUIRE(updatedSnapshot);
  CHECK(updatedSnapshot->version == 2);
  CHECK(updatedSnapshot->sourceLabel == "unit-test");
  CHECK(updatedSnapshot->document.kind == halcyn::domain::SceneKind::ThreeDimensional);

  const auto currentSnapshot = store.GetCurrent();
  CHECK(currentSnapshot->version == updatedSnapshot->version);
}
} // namespace halcyn::tests
