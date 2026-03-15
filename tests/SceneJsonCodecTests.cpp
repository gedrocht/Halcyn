#include "domain/SceneJsonCodec.hpp"
#include "domain/SceneValidation.hpp"

#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

namespace halcyn::tests {
TEST_CASE("SceneJsonCodec parses a valid 2D scene", "[json][2d]") {
  const std::string jsonText = R"({
    "sceneType": "2d",
    "primitive": "triangles",
    "pointSize": 12.0,
    "lineWidth": 4.0,
    "clearColor": { "r": 0.02, "g": 0.04, "b": 0.06, "a": 1.0 },
    "vertices": [
      { "x": -1.0, "y": -1.0, "r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0 },
      { "x": 0.0, "y": 1.0, "r": 0.0, "g": 1.0, "b": 0.0, "a": 1.0 },
      { "x": 1.0, "y": -1.0, "r": 0.0, "g": 0.0, "b": 1.0, "a": 1.0 }
    ]
  })";

  const domain::SceneJsonCodec sceneJsonCodec;
  const auto sceneParseResult = sceneJsonCodec.Parse(jsonText);

  REQUIRE(sceneParseResult.succeeded);
  REQUIRE(sceneParseResult.scene.has_value());
  REQUIRE(sceneParseResult.scene->kind == domain::SceneKind::TwoDimensional);

  const auto& parsedScene = std::get<domain::Scene2D>(sceneParseResult.scene->payload);
  CHECK(parsedScene.vertices.size() == 3);
  CHECK(parsedScene.pointSize == Catch::Approx(12.0F));
  CHECK(parsedScene.vertices[1].g == Catch::Approx(1.0F));

  const auto renderScene = domain::BuildRenderScene(*sceneParseResult.scene);
  CHECK(renderScene.vertices.size() == 3);
  CHECK(renderScene.vertices[2].z == Catch::Approx(0.0F));
  CHECK(renderScene.vertices[2].b == Catch::Approx(1.0F));
}

TEST_CASE("SceneJsonCodec parses a valid indexed 3D scene", "[json][3d]") {
  const std::string jsonText = R"({
    "sceneType": "3d",
    "primitive": "triangles",
    "camera": {
      "position": { "x": 2.0, "y": 2.0, "z": 2.0 },
      "target": { "x": 0.0, "y": 0.0, "z": 0.0 },
      "up": { "x": 0.0, "y": 1.0, "z": 0.0 },
      "fovYDegrees": 55.0,
      "nearPlane": 0.1,
      "farPlane": 50.0
    },
    "vertices": [
      { "x": -1.0, "y": 0.0, "z": 0.0, "r": 1.0, "g": 0.0, "b": 0.0 },
      { "x": 1.0, "y": 0.0, "z": 0.0, "r": 0.0, "g": 1.0, "b": 0.0 },
      { "x": 0.0, "y": 1.0, "z": 1.0, "r": 0.0, "g": 0.0, "b": 1.0 }
    ],
    "indices": [0, 1, 2]
  })";

  const domain::SceneJsonCodec sceneJsonCodec;
  const auto sceneParseResult = sceneJsonCodec.Parse(jsonText);

  REQUIRE(sceneParseResult.succeeded);
  REQUIRE(sceneParseResult.scene.has_value());
  REQUIRE(sceneParseResult.scene->kind == domain::SceneKind::ThreeDimensional);

  const auto& parsedScene = std::get<domain::Scene3D>(sceneParseResult.scene->payload);
  CHECK(parsedScene.indices.size() == 3);
  CHECK(parsedScene.vertices[0].a == Catch::Approx(1.0F));
  CHECK(parsedScene.camera.fovYDegrees == Catch::Approx(55.0F));

  const auto renderScene = domain::BuildRenderScene(*sceneParseResult.scene);
  CHECK(renderScene.vertices[2].z == Catch::Approx(1.0F));
  CHECK(renderScene.indices[1] == 1);
}

TEST_CASE("SceneJsonCodec rejects malformed scenes with readable errors", "[json][validation]") {
  const std::string jsonText = R"({
    "sceneType": "3d",
    "primitive": "triangles",
    "camera": {
      "position": { "x": 2.0, "y": 2.0, "z": 2.0 },
      "target": { "x": 0.0, "y": 0.0, "z": 0.0 },
      "up": { "x": 0.0, "y": 1.0, "z": 0.0 },
      "fovYDegrees": 200.0,
      "nearPlane": -1.0,
      "farPlane": 0.5
    },
    "vertices": [
      { "x": 0.0, "y": 0.0, "z": 0.0, "r": 1.0, "g": 1.0, "b": 1.0 }
    ]
  })";

  const domain::SceneJsonCodec sceneJsonCodec;
  const auto sceneParseResult = sceneJsonCodec.Parse(jsonText);

  REQUIRE_FALSE(sceneParseResult.succeeded);
  REQUIRE_FALSE(sceneParseResult.errors.empty());

  bool foundFovError = false;
  bool foundNearPlaneError = false;
  for (const auto& error : sceneParseResult.errors) {
    if (error.path == "$.camera.fovYDegrees") {
      foundFovError = true;
    }

    if (error.path == "$.camera.nearPlane") {
      foundNearPlaneError = true;
    }
  }

  CHECK(foundFovError);
  CHECK(foundNearPlaneError);
}
} // namespace halcyn::tests
