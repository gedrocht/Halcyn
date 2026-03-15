#include "scene_description/SceneFactory.hpp"
#include "scene_description/SceneJsonCodec.hpp"
#include "scene_description/SceneLimits.hpp"
#include "scene_description/SceneValidation.hpp"

#include <catch2/catch_test_macros.hpp>

namespace halcyn::tests {
TEST_CASE("ValidateSceneDocument rejects degenerate 3D camera definitions",
          "[validation][camera]") {
  auto document = scene_description::CreateSample3DSceneDocument();
  auto& scene = std::get<scene_description::Scene3D>(document.payload);

  scene.camera.position = {1.0F, 1.0F, 1.0F};
  scene.camera.target = {1.0F, 1.0F, 1.0F};
  scene.camera.up = {0.0F, 0.0F, 0.0F};

  const auto errors = scene_description::ValidateSceneDocument(document);

  bool foundTargetError = false;
  bool foundUpError = false;
  for (const auto& error : errors) {
    if (error.path == "$.camera.target") {
      foundTargetError = true;
    }

    if (error.path == "$.camera.up") {
      foundUpError = true;
    }
  }

  CHECK(foundTargetError);
  CHECK(foundUpError);
}

TEST_CASE("ValidateSceneDocument enforces scene size limits", "[validation][limits]") {
  scene_description::SceneDocument document;
  document.kind = scene_description::SceneKind::TwoDimensional;

  scene_description::Scene2D scene;
  scene.primitiveType = scene_description::PrimitiveType::Points;
  scene.vertices.resize(scene_description::SceneLimits::kMaxVertexCount + 1U);
  document.payload = scene;

  const auto errors = scene_description::ValidateSceneDocument(document);

  REQUIRE_FALSE(errors.empty());
  CHECK(errors.front().path == "$.vertices");
}

TEST_CASE("SceneJsonCodec rejects oversized payloads before parsing", "[json][limits]") {
  const scene_description::SceneJsonCodec codec;
  const std::string oversizedPayload(scene_description::SceneLimits::kMaxRequestPayloadBytes + 1U,
                                     'x');

  const auto result = codec.Parse(oversizedPayload);

  REQUIRE_FALSE(result.succeeded);
  REQUIRE_FALSE(result.errors.empty());
  CHECK(result.errors.front().path == "$");
}
} // namespace halcyn::tests
