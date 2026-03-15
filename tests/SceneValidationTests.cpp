#include "domain/SceneFactory.hpp"
#include "domain/SceneJsonCodec.hpp"
#include "domain/SceneLimits.hpp"
#include "domain/SceneValidation.hpp"

#include <catch2/catch_test_macros.hpp>

namespace halcyn::tests {
TEST_CASE("ValidateSceneDocument rejects degenerate 3D camera definitions",
          "[validation][camera]") {
  auto sceneDocument = domain::CreateSample3DSceneDocument();
  auto& cameraScene = std::get<domain::Scene3D>(sceneDocument.payload);

  cameraScene.camera.position = {1.0F, 1.0F, 1.0F};
  cameraScene.camera.target = {1.0F, 1.0F, 1.0F};
  cameraScene.camera.up = {0.0F, 0.0F, 0.0F};

  const auto validationErrors = domain::ValidateSceneDocument(sceneDocument);

  bool foundTargetError = false;
  bool foundUpError = false;
  for (const auto& error : validationErrors) {
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
  domain::SceneDocument sceneDocument;
  sceneDocument.kind = domain::SceneKind::TwoDimensional;

  domain::Scene2D oversizedScene;
  oversizedScene.primitiveType = domain::PrimitiveType::Points;
  oversizedScene.vertices.resize(domain::SceneLimits::kMaxVertexCount + 1U);
  sceneDocument.payload = oversizedScene;

  const auto validationErrors = domain::ValidateSceneDocument(sceneDocument);

  REQUIRE_FALSE(validationErrors.empty());
  CHECK(validationErrors.front().path == "$.vertices");
}

TEST_CASE("SceneJsonCodec rejects oversized payloads before parsing", "[json][limits]") {
  const domain::SceneJsonCodec sceneJsonCodec;
  const std::string oversizedPayload(domain::SceneLimits::kMaxRequestPayloadBytes + 1U, 'x');

  const auto sceneParseResult = sceneJsonCodec.Parse(oversizedPayload);

  REQUIRE_FALSE(sceneParseResult.succeeded);
  REQUIRE_FALSE(sceneParseResult.errors.empty());
  CHECK(sceneParseResult.errors.front().path == "$");
}
} // namespace halcyn::tests
