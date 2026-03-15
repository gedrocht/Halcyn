#include "scene_description/SceneFactory.hpp"

namespace halcyn::scene_description {
SceneDocument CreateDefaultSceneDocument() {
  // The default scene is intentionally a 2D sample because it is the smallest,
  // friendliest possible success case when the app starts for the first time.
  return CreateSample2DSceneDocument();
}

SceneDocument CreateSample2DSceneDocument() {
  // This built-in sample doubles as a visual smoke test: if the app can render
  // one colorful triangle, the basic 2D pipeline is working.
  Scene2D scene;
  scene.primitiveType = PrimitiveType::Triangles;
  scene.pointSize = 10.0F;
  scene.lineWidth = 3.0F;
  scene.clearColor = {0.05F, 0.07F, 0.11F, 1.0F};
  scene.vertices = {{-0.8F, -0.6F, 1.0F, 0.2F, 0.2F, 1.0F},
                    {0.0F, 0.7F, 0.2F, 0.9F, 0.7F, 1.0F},
                    {0.8F, -0.4F, 0.2F, 0.5F, 1.0F, 1.0F}};

  SceneDocument document;
  document.kind = SceneKind::TwoDimensional;
  document.payload = scene;
  // Keeping a matching JSON copy makes the sample easy to expose through the API
  // and easy for humans to inspect in logs or docs.
  document.originalJson = R"({
  "sceneType": "2d",
  "primitive": "triangles",
  "clearColor": { "r": 0.05, "g": 0.07, "b": 0.11, "a": 1.0 },
  "vertices": [
    { "x": -0.8, "y": -0.6, "r": 1.0, "g": 0.2, "b": 0.2, "a": 1.0 },
    { "x": 0.0, "y": 0.7, "r": 0.2, "g": 0.9, "b": 0.7, "a": 1.0 },
    { "x": 0.8, "y": -0.4, "r": 0.2, "g": 0.5, "b": 1.0, "a": 1.0 }
  ]
})";
  return document;
}

SceneDocument CreateSample3DSceneDocument() {
  // The 3D sample is a simple colored tetrahedron-like shape that exercises the
  // camera, depth testing, indexed drawing, and basic perspective rendering path.
  Scene3D scene;
  scene.primitiveType = PrimitiveType::Triangles;
  scene.clearColor = {0.04F, 0.05F, 0.08F, 1.0F};
  scene.camera.position = {2.3F, 1.8F, 2.6F};
  scene.camera.target = {0.0F, 0.0F, 0.0F};
  scene.vertices = {{-0.8F, -0.8F, 0.0F, 1.0F, 0.2F, 0.2F, 1.0F},
                    {0.8F, -0.8F, 0.0F, 0.2F, 1.0F, 0.2F, 1.0F},
                    {0.0F, 0.8F, 0.0F, 0.2F, 0.4F, 1.0F, 1.0F},
                    {0.0F, 0.0F, 1.2F, 1.0F, 0.9F, 0.2F, 1.0F}};
  scene.indices = {0, 1, 2, 0, 1, 3, 1, 2, 3, 2, 0, 3};

  SceneDocument document;
  document.kind = SceneKind::ThreeDimensional;
  document.payload = scene;
  document.originalJson = R"({
  "sceneType": "3d",
  "primitive": "triangles",
  "camera": {
    "position": { "x": 2.3, "y": 1.8, "z": 2.6 },
    "target": { "x": 0.0, "y": 0.0, "z": 0.0 },
    "up": { "x": 0.0, "y": 1.0, "z": 0.0 },
    "fovYDegrees": 60.0,
    "nearPlane": 0.1,
    "farPlane": 100.0
  },
  "vertices": [
    { "x": -0.8, "y": -0.8, "z": 0.0, "r": 1.0, "g": 0.2, "b": 0.2 },
    { "x": 0.8, "y": -0.8, "z": 0.0, "r": 0.2, "g": 1.0, "b": 0.2 },
    { "x": 0.0, "y": 0.8, "z": 0.0, "r": 0.2, "g": 0.4, "b": 1.0 },
    { "x": 0.0, "y": 0.0, "z": 1.2, "r": 1.0, "g": 0.9, "b": 0.2 }
  ],
  "indices": [0, 1, 2, 0, 1, 3, 1, 2, 3, 2, 0, 3]
})";
  return document;
}
} // namespace halcyn::scene_description
