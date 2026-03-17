/**
 * @file
 * @brief Implements the built-in sample scenes used by startup, tests, docs, and example endpoints.
 */

#include "scene_description/SceneFactory.hpp"

#include <algorithm>

namespace halcyn::scene_description {
namespace {
ColorRgba ShadeColor(const ColorRgba& baseColor, float intensityMultiplier) {
  auto clampChannel = [](float channel) { return std::max(0.0F, std::min(1.0F, channel)); };

  return {clampChannel(baseColor.r * intensityMultiplier),
          clampChannel(baseColor.g * intensityMultiplier),
          clampChannel(baseColor.b * intensityMultiplier), baseColor.a};
}

void AppendBar(Scene3D& scene, float centerX, float centerZ, float width, float depth, float height,
               const ColorRgba& color) {
  const std::uint32_t firstVertexIndex = static_cast<std::uint32_t>(scene.vertices.size());
  const float halfWidth = width * 0.5F;
  const float halfDepth = depth * 0.5F;

  // We intentionally duplicate the per-face vertices instead of sharing one set
  // of corner vertices. That lets the spectrograph sample assign a brighter top
  // face and darker side faces so the bars read as 3D even though Halcyn's
  // renderer still uses simple color shading instead of a full normal-based
  // lighting pipeline.
  const ColorRgba floorColor = ShadeColor(color, 0.42F);
  const ColorRgba topColor = ShadeColor(color, 1.18F);
  const ColorRgba frontColor = ShadeColor(color, 0.82F);
  const ColorRgba rightColor = ShadeColor(color, 0.96F);
  const ColorRgba backColor = ShadeColor(color, 0.68F);
  const ColorRgba leftColor = ShadeColor(color, 0.58F);

  auto appendVertex = [&scene](float x, float y, float z, const ColorRgba& faceColor) {
    scene.vertices.push_back({x, y, z, faceColor.r, faceColor.g, faceColor.b, faceColor.a});
  };

  appendVertex(centerX - halfWidth, 0.0F, centerZ - halfDepth, floorColor);
  appendVertex(centerX + halfWidth, 0.0F, centerZ - halfDepth, floorColor);
  appendVertex(centerX + halfWidth, 0.0F, centerZ + halfDepth, floorColor);
  appendVertex(centerX - halfWidth, 0.0F, centerZ + halfDepth, floorColor);

  appendVertex(centerX - halfWidth, height, centerZ - halfDepth, topColor);
  appendVertex(centerX + halfWidth, height, centerZ - halfDepth, topColor);
  appendVertex(centerX + halfWidth, height, centerZ + halfDepth, topColor);
  appendVertex(centerX - halfWidth, height, centerZ + halfDepth, topColor);

  appendVertex(centerX - halfWidth, 0.0F, centerZ - halfDepth, frontColor);
  appendVertex(centerX + halfWidth, 0.0F, centerZ - halfDepth, frontColor);
  appendVertex(centerX + halfWidth, height, centerZ - halfDepth, frontColor);
  appendVertex(centerX - halfWidth, height, centerZ - halfDepth, frontColor);

  appendVertex(centerX + halfWidth, 0.0F, centerZ - halfDepth, rightColor);
  appendVertex(centerX + halfWidth, 0.0F, centerZ + halfDepth, rightColor);
  appendVertex(centerX + halfWidth, height, centerZ + halfDepth, rightColor);
  appendVertex(centerX + halfWidth, height, centerZ - halfDepth, rightColor);

  appendVertex(centerX + halfWidth, 0.0F, centerZ + halfDepth, backColor);
  appendVertex(centerX - halfWidth, 0.0F, centerZ + halfDepth, backColor);
  appendVertex(centerX - halfWidth, height, centerZ + halfDepth, backColor);
  appendVertex(centerX + halfWidth, height, centerZ + halfDepth, backColor);

  appendVertex(centerX - halfWidth, 0.0F, centerZ + halfDepth, leftColor);
  appendVertex(centerX - halfWidth, 0.0F, centerZ - halfDepth, leftColor);
  appendVertex(centerX - halfWidth, height, centerZ - halfDepth, leftColor);
  appendVertex(centerX - halfWidth, height, centerZ + halfDepth, leftColor);

  const std::array<std::uint32_t, 36> cubeIndices = {
      0,  1,  2,  0,  2,  3,  // floor
      4,  5,  6,  4,  6,  7,  // top
      8,  9,  10, 8,  10, 11, // front
      12, 13, 14, 12, 14, 15, // right
      16, 17, 18, 16, 18, 19, // back
      20, 21, 22, 20, 22, 23  // left
  };

  for (const std::uint32_t indexOffset : cubeIndices) {
    scene.indices.push_back(firstVertexIndex + indexOffset);
  }
}
} // namespace

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

SceneDocument CreateSampleBarWallSceneDocument() {
  Scene3D scene;
  scene.primitiveType = PrimitiveType::Triangles;
  scene.clearColor = {0.03F, 0.04F, 0.08F, 1.0F};
  scene.camera.position = {6.5F, 5.5F, 6.5F};
  scene.camera.target = {0.0F, 1.4F, 0.0F};
  scene.camera.up = {0.0F, 1.0F, 0.0F};
  scene.presentationOptions.antiAliasingEnabled = true;
  scene.presentationOptions.shaderStyle = ShaderStyle::Heatmap;

  constexpr int gridSize = 6;
  constexpr float spacing = 0.82F;
  constexpr float barWidth = 0.58F;
  constexpr float barDepth = 0.58F;

  for (int rowIndex = 0; rowIndex < gridSize; ++rowIndex) {
    for (int columnIndex = 0; columnIndex < gridSize; ++columnIndex) {
      const float x =
          (static_cast<float>(columnIndex) - static_cast<float>(gridSize - 1) * 0.5F) * spacing;
      const float z =
          (static_cast<float>(rowIndex) - static_cast<float>(gridSize - 1) * 0.5F) * spacing;
      const float normalizedPhase = static_cast<float>((rowIndex * gridSize) + columnIndex) /
                                    static_cast<float>((gridSize * gridSize) - 1);
      const float height = 0.25F + (normalizedPhase * normalizedPhase * 3.2F);
      const ColorRgba color = {
          0.12F + normalizedPhase * 0.85F,
          0.18F + (1.0F - normalizedPhase) * 0.46F,
          0.88F - normalizedPhase * 0.58F,
          1.0F,
      };
      AppendBar(scene, x, z, barWidth, barDepth, height, color);
    }
  }

  SceneDocument document;
  document.kind = SceneKind::ThreeDimensional;
  document.payload = scene;
  document.originalJson = R"({
  "sceneType": "3d",
  "primitive": "triangles",
  "clearColor": { "r": 0.03, "g": 0.04, "b": 0.08, "a": 1.0 },
  "camera": {
    "position": { "x": 6.5, "y": 5.5, "z": 6.5 },
    "target": { "x": 0.0, "y": 1.4, "z": 0.0 },
    "up": { "x": 0.0, "y": 1.0, "z": 0.0 },
    "fovYDegrees": 60.0,
    "nearPlane": 0.1,
    "farPlane": 100.0
  },
  "renderStyle": {
    "shader": "heatmap",
    "antiAliasing": true
  },
  "vertices": "Generated bar-grid sample omitted for brevity.",
  "indices": "Generated bar-grid sample omitted for brevity."
})";
  return document;
}

SceneDocument CreateSampleSpectrographSceneDocument() {
  return CreateSampleBarWallSceneDocument();
}
} // namespace halcyn::scene_description
