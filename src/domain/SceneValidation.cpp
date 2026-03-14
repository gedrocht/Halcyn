#include "domain/SceneValidation.hpp"

#include "domain/SceneLimits.hpp"

#include <cmath>
#include <sstream>

namespace halcyn::domain {
namespace {
std::size_t MinimumVertexCountFor(PrimitiveType primitiveType) {
  switch (primitiveType) {
  case PrimitiveType::Points:
    return 1;
  case PrimitiveType::Lines:
    return 2;
  case PrimitiveType::Triangles:
    return 3;
  }

  return 1;
}

bool IsPrimitiveCountAligned(PrimitiveType primitiveType, std::size_t count) {
  switch (primitiveType) {
  case PrimitiveType::Points:
    return count >= 1;
  case PrimitiveType::Lines:
    return (count >= 2) && (count % 2 == 0);
  case PrimitiveType::Triangles:
    return (count >= 3) && (count % 3 == 0);
  }

  return false;
}

bool IsApproximatelyZero(float value) {
  return std::fabs(value) < 0.0001F;
}

float SquaredLength(const Vector3Value& vector) {
  return (vector.x * vector.x) + (vector.y * vector.y) + (vector.z * vector.z);
}

Vector3Value Subtract(const Vector3Value& left, const Vector3Value& right) {
  return {left.x - right.x, left.y - right.y, left.z - right.z};
}

Vector3Value Cross(const Vector3Value& left, const Vector3Value& right) {
  return {(left.y * right.z) - (left.z * right.y), (left.z * right.x) - (left.x * right.z),
          (left.x * right.y) - (left.y * right.x)};
}
} // namespace

std::vector<ValidationError> ValidateSceneDocument(const SceneDocument& document) {
  std::vector<ValidationError> errors;

  if (document.kind == SceneKind::TwoDimensional) {
    const Scene2D& scene = std::get<Scene2D>(document.payload);

    if (scene.vertices.size() > SceneLimits::kMaxVertexCount) {
      std::ostringstream builder;
      builder << "A 2D scene may contain at most " << SceneLimits::kMaxVertexCount << " vertices.";
      errors.push_back({"$.vertices", builder.str()});
    }

    if (scene.vertices.size() < MinimumVertexCountFor(scene.primitiveType)) {
      std::ostringstream builder;
      builder << "A 2D scene using primitive '" << ToString(scene.primitiveType)
              << "' needs at least " << MinimumVertexCountFor(scene.primitiveType) << " vertices.";
      errors.push_back({"$.vertices", builder.str()});
    }

    if (!IsPrimitiveCountAligned(scene.primitiveType, scene.vertices.size())) {
      errors.push_back(
          {"$.vertices",
           "The number of 2D vertices does not line up with the selected primitive type."});
    }

    if (scene.pointSize <= 0.0F) {
      errors.push_back({"$.pointSize", "pointSize must be greater than 0."});
    }

    if (scene.lineWidth <= 0.0F) {
      errors.push_back({"$.lineWidth", "lineWidth must be greater than 0."});
    }

    return errors;
  }

  const Scene3D& scene = std::get<Scene3D>(document.payload);

  if (scene.vertices.size() > SceneLimits::kMaxVertexCount) {
    std::ostringstream builder;
    builder << "A 3D scene may contain at most " << SceneLimits::kMaxVertexCount << " vertices.";
    errors.push_back({"$.vertices", builder.str()});
  }

  if (scene.indices.size() > SceneLimits::kMaxIndexCount) {
    std::ostringstream builder;
    builder << "A 3D scene may contain at most " << SceneLimits::kMaxIndexCount << " indices.";
    errors.push_back({"$.indices", builder.str()});
  }

  if (scene.vertices.size() < MinimumVertexCountFor(scene.primitiveType)) {
    std::ostringstream builder;
    builder << "A 3D scene using primitive '" << ToString(scene.primitiveType)
            << "' needs at least " << MinimumVertexCountFor(scene.primitiveType) << " vertices.";
    errors.push_back({"$.vertices", builder.str()});
  }

  if (!scene.indices.empty()) {
    if (!IsPrimitiveCountAligned(scene.primitiveType, scene.indices.size())) {
      errors.push_back(
          {"$.indices",
           "The number of indices does not line up with the selected primitive type."});
    }

    for (std::size_t indexPosition = 0; indexPosition < scene.indices.size(); ++indexPosition) {
      if (scene.indices[indexPosition] >= scene.vertices.size()) {
        std::ostringstream builder;
        builder << "Index " << scene.indices[indexPosition] << " points past the last vertex.";
        errors.push_back({"$.indices[" + std::to_string(indexPosition) + "]", builder.str()});
      }
    }
  } else if (!IsPrimitiveCountAligned(scene.primitiveType, scene.vertices.size())) {
    errors.push_back(
        {"$.vertices",
         "The number of 3D vertices does not line up with the selected primitive type."});
  }

  if (scene.pointSize <= 0.0F) {
    errors.push_back({"$.pointSize", "pointSize must be greater than 0."});
  }

  if (scene.lineWidth <= 0.0F) {
    errors.push_back({"$.lineWidth", "lineWidth must be greater than 0."});
  }

  if (scene.camera.fovYDegrees <= 1.0F || scene.camera.fovYDegrees >= 179.0F) {
    errors.push_back({"$.camera.fovYDegrees", "fovYDegrees must be between 1 and 179."});
  }

  if (scene.camera.nearPlane <= 0.0F) {
    errors.push_back({"$.camera.nearPlane", "nearPlane must be greater than 0."});
  }

  if (scene.camera.farPlane <= scene.camera.nearPlane) {
    errors.push_back({"$.camera.farPlane", "farPlane must be greater than nearPlane."});
  }

  const Vector3Value forward = Subtract(scene.camera.target, scene.camera.position);
  if (IsApproximatelyZero(SquaredLength(forward))) {
    errors.push_back(
        {"$.camera.target", "camera.target must not be the same point as camera.position."});
  }

  if (IsApproximatelyZero(SquaredLength(scene.camera.up))) {
    errors.push_back({"$.camera.up", "camera.up must not be the zero vector."});
  }

  if (!IsApproximatelyZero(SquaredLength(forward)) &&
      !IsApproximatelyZero(SquaredLength(scene.camera.up))) {
    const Vector3Value perpendicular = Cross(forward, scene.camera.up);
    if (IsApproximatelyZero(SquaredLength(perpendicular))) {
      errors.push_back(
          {"$.camera.up",
           "camera.up must not point in the same direction as the camera view direction."});
    }
  }

  return errors;
}

RenderScene BuildRenderScene(const SceneDocument& document) {
  RenderScene renderScene;
  renderScene.kind = document.kind;

  if (document.kind == SceneKind::TwoDimensional) {
    const Scene2D& scene = std::get<Scene2D>(document.payload);
    renderScene.primitiveType = scene.primitiveType;
    renderScene.pointSize = scene.pointSize;
    renderScene.lineWidth = scene.lineWidth;
    renderScene.clearColor = scene.clearColor;

    renderScene.vertices.reserve(scene.vertices.size());
    for (const Vertex2D& vertex : scene.vertices) {
      renderScene.vertices.push_back(
          {vertex.x, vertex.y, 0.0F, vertex.r, vertex.g, vertex.b, vertex.a});
    }

    return renderScene;
  }

  const Scene3D& scene = std::get<Scene3D>(document.payload);
  renderScene.primitiveType = scene.primitiveType;
  renderScene.pointSize = scene.pointSize;
  renderScene.lineWidth = scene.lineWidth;
  renderScene.clearColor = scene.clearColor;
  renderScene.camera = scene.camera;
  renderScene.indices = scene.indices;

  renderScene.vertices.reserve(scene.vertices.size());
  for (const Vertex3D& vertex : scene.vertices) {
    renderScene.vertices.push_back(
        {vertex.x, vertex.y, vertex.z, vertex.r, vertex.g, vertex.b, vertex.a});
  }

  return renderScene;
}

std::string ToString(SceneKind kind) {
  switch (kind) {
  case SceneKind::TwoDimensional:
    return "2d";
  case SceneKind::ThreeDimensional:
    return "3d";
  }

  return "unknown";
}

std::string ToString(PrimitiveType primitiveType) {
  switch (primitiveType) {
  case PrimitiveType::Points:
    return "points";
  case PrimitiveType::Lines:
    return "lines";
  case PrimitiveType::Triangles:
    return "triangles";
  }

  return "unknown";
}

std::optional<PrimitiveType> PrimitiveTypeFromString(const std::string& value) {
  if (value == "points") {
    return PrimitiveType::Points;
  }

  if (value == "lines") {
    return PrimitiveType::Lines;
  }

  if (value == "triangles") {
    return PrimitiveType::Triangles;
  }

  return std::nullopt;
}
} // namespace halcyn::domain
