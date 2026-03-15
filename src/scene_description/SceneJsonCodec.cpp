/**
 * @file
 * @brief Implements JSON parsing and serialization for Halcyn scene documents.
 *
 * @details
 * This file contains the detailed JSON-to-type translation rules that back
 * `halcyn::scene_description::SceneJsonCodec`.
 *
 * Helpful external references:
 *
 * - [nlohmann/json overview](https://nlohmann.github.io/json/api/basic_json/)
 * - [`json::parse`](https://nlohmann.github.io/json/api/basic_json/parse/)
 * - [`json::dump`](https://nlohmann.github.io/json/api/basic_json/dump/)
 * - [`json::get`](https://nlohmann.github.io/json/api/basic_json/get/)
 */

#include "scene_description/SceneJsonCodec.hpp"

#include "scene_description/SceneLimits.hpp"
#include "scene_description/SceneValidation.hpp"

#include <nlohmann/json.hpp>

#include <sstream>
#include <utility>

namespace halcyn::scene_description {
namespace {
using json = nlohmann::json;

template <typename NumberType>
std::optional<NumberType> ReadNumber(const json& node, const char* key, const std::string& basePath,
                                     std::vector<ValidationError>& errors, bool required = true) {
  // These small "read one field" helpers let parsing continue after the first
  // problem so the caller gets a full list of issues instead of fixing them one by one.
  if (!node.contains(key)) {
    if (required) {
      errors.push_back({basePath + "." + key, "This numeric field is required."});
    }

    return std::nullopt;
  }

  if (!node.at(key).is_number()) {
    errors.push_back({basePath + "." + key, "Expected a number."});
    return std::nullopt;
  }

  return node.at(key).get<NumberType>();
}

std::optional<std::string> ReadString(const json& node, const char* key,
                                      const std::string& basePath,
                                      std::vector<ValidationError>& errors) {
  if (!node.contains(key)) {
    errors.push_back({basePath + "." + key, "This string field is required."});
    return std::nullopt;
  }

  if (!node.at(key).is_string()) {
    errors.push_back({basePath + "." + key, "Expected a string."});
    return std::nullopt;
  }

  return node.at(key).get<std::string>();
}

ColorRgba ReadColor(const json& node, const std::string& basePath,
                    std::vector<ValidationError>& errors) {
  ColorRgba color;
  if (!node.is_object()) {
    errors.push_back({basePath, "Expected an object with r, g, b, and optional a fields."});
    return color;
  }

  color.r = ReadNumber<float>(node, "r", basePath, errors).value_or(color.r);
  color.g = ReadNumber<float>(node, "g", basePath, errors).value_or(color.g);
  color.b = ReadNumber<float>(node, "b", basePath, errors).value_or(color.b);
  color.a = ReadNumber<float>(node, "a", basePath, errors, false).value_or(color.a);
  return color;
}

Vector3Value ReadVector3(const json& node, const std::string& basePath,
                         std::vector<ValidationError>& errors) {
  Vector3Value vector;
  if (!node.is_object()) {
    errors.push_back({basePath, "Expected an object with x, y, and z fields."});
    return vector;
  }

  vector.x = ReadNumber<float>(node, "x", basePath, errors).value_or(vector.x);
  vector.y = ReadNumber<float>(node, "y", basePath, errors).value_or(vector.y);
  vector.z = ReadNumber<float>(node, "z", basePath, errors).value_or(vector.z);
  return vector;
}

std::optional<Scene2D> Parse2DScene(const json& root, std::vector<ValidationError>& errors) {
  Scene2D scene;
  // Scene parsing here is structural: "is the JSON shaped like a 2D scene?"
  // Higher-level semantic rules, such as minimum vertex counts, are handled later
  // by ValidateSceneDocument so the responsibilities stay separated.
  if (root.contains("primitive")) {
    const auto primitiveValue = ReadString(root, "primitive", "$", errors);
    if (primitiveValue.has_value()) {
      const auto primitiveType = PrimitiveTypeFromString(*primitiveValue);
      if (!primitiveType.has_value()) {
        errors.push_back({"$.primitive", "primitive must be one of: points, lines, triangles."});
      } else {
        scene.primitiveType = *primitiveType;
      }
    }
  }

  if (root.contains("pointSize")) {
    scene.pointSize = ReadNumber<float>(root, "pointSize", "$", errors).value_or(scene.pointSize);
  }

  if (root.contains("lineWidth")) {
    scene.lineWidth = ReadNumber<float>(root, "lineWidth", "$", errors).value_or(scene.lineWidth);
  }

  if (root.contains("clearColor")) {
    scene.clearColor = ReadColor(root.at("clearColor"), "$.clearColor", errors);
  }

  if (!root.contains("vertices")) {
    errors.push_back({"$.vertices", "A 2D scene requires a vertices array."});
    return std::nullopt;
  }

  if (!root.at("vertices").is_array()) {
    errors.push_back({"$.vertices", "vertices must be an array."});
    return std::nullopt;
  }

  for (std::size_t index = 0; index < root.at("vertices").size(); ++index) {
    const json& vertexNode = root.at("vertices")[index];
    const std::string vertexPath = "$.vertices[" + std::to_string(index) + "]";
    if (!vertexNode.is_object()) {
      errors.push_back({vertexPath, "Each vertex must be an object."});
      continue;
    }

    Vertex2D vertex;
    vertex.x = ReadNumber<float>(vertexNode, "x", vertexPath, errors).value_or(vertex.x);
    vertex.y = ReadNumber<float>(vertexNode, "y", vertexPath, errors).value_or(vertex.y);
    vertex.r = ReadNumber<float>(vertexNode, "r", vertexPath, errors).value_or(vertex.r);
    vertex.g = ReadNumber<float>(vertexNode, "g", vertexPath, errors).value_or(vertex.g);
    vertex.b = ReadNumber<float>(vertexNode, "b", vertexPath, errors).value_or(vertex.b);
    vertex.a = ReadNumber<float>(vertexNode, "a", vertexPath, errors).value_or(vertex.a);
    scene.vertices.push_back(vertex);
  }

  return scene;
}

std::optional<Scene3D> Parse3DScene(const json& root, std::vector<ValidationError>& errors) {
  Scene3D scene;
  // 3D scenes reuse many of the same top-level fields as 2D scenes, but add a
  // camera and optional index buffer. This function only checks shape and type.
  if (root.contains("primitive")) {
    const auto primitiveValue = ReadString(root, "primitive", "$", errors);
    if (primitiveValue.has_value()) {
      const auto primitiveType = PrimitiveTypeFromString(*primitiveValue);
      if (!primitiveType.has_value()) {
        errors.push_back({"$.primitive", "primitive must be one of: points, lines, triangles."});
      } else {
        scene.primitiveType = *primitiveType;
      }
    }
  }

  if (root.contains("pointSize")) {
    scene.pointSize = ReadNumber<float>(root, "pointSize", "$", errors).value_or(scene.pointSize);
  }

  if (root.contains("lineWidth")) {
    scene.lineWidth = ReadNumber<float>(root, "lineWidth", "$", errors).value_or(scene.lineWidth);
  }

  if (root.contains("clearColor")) {
    scene.clearColor = ReadColor(root.at("clearColor"), "$.clearColor", errors);
  }

  if (!root.contains("camera")) {
    errors.push_back({"$.camera", "A 3D scene requires a camera object."});
  } else if (!root.at("camera").is_object()) {
    errors.push_back({"$.camera", "camera must be an object."});
  } else {
    const json& cameraNode = root.at("camera");
    if (cameraNode.contains("position")) {
      scene.camera.position = ReadVector3(cameraNode.at("position"), "$.camera.position", errors);
    } else {
      errors.push_back({"$.camera.position", "position is required."});
    }

    if (cameraNode.contains("target")) {
      scene.camera.target = ReadVector3(cameraNode.at("target"), "$.camera.target", errors);
    } else {
      errors.push_back({"$.camera.target", "target is required."});
    }

    if (cameraNode.contains("up")) {
      scene.camera.up = ReadVector3(cameraNode.at("up"), "$.camera.up", errors);
    } else {
      errors.push_back({"$.camera.up", "up is required."});
    }

    scene.camera.fovYDegrees = ReadNumber<float>(cameraNode, "fovYDegrees", "$.camera", errors)
                                   .value_or(scene.camera.fovYDegrees);
    scene.camera.nearPlane = ReadNumber<float>(cameraNode, "nearPlane", "$.camera", errors)
                                 .value_or(scene.camera.nearPlane);
    scene.camera.farPlane = ReadNumber<float>(cameraNode, "farPlane", "$.camera", errors)
                                .value_or(scene.camera.farPlane);
  }

  if (!root.contains("vertices")) {
    errors.push_back({"$.vertices", "A 3D scene requires a vertices array."});
    return std::nullopt;
  }

  if (!root.at("vertices").is_array()) {
    errors.push_back({"$.vertices", "vertices must be an array."});
    return std::nullopt;
  }

  for (std::size_t index = 0; index < root.at("vertices").size(); ++index) {
    const json& vertexNode = root.at("vertices")[index];
    const std::string vertexPath = "$.vertices[" + std::to_string(index) + "]";
    if (!vertexNode.is_object()) {
      errors.push_back({vertexPath, "Each vertex must be an object."});
      continue;
    }

    Vertex3D vertex;
    vertex.x = ReadNumber<float>(vertexNode, "x", vertexPath, errors).value_or(vertex.x);
    vertex.y = ReadNumber<float>(vertexNode, "y", vertexPath, errors).value_or(vertex.y);
    vertex.z = ReadNumber<float>(vertexNode, "z", vertexPath, errors).value_or(vertex.z);
    vertex.r = ReadNumber<float>(vertexNode, "r", vertexPath, errors).value_or(vertex.r);
    vertex.g = ReadNumber<float>(vertexNode, "g", vertexPath, errors).value_or(vertex.g);
    vertex.b = ReadNumber<float>(vertexNode, "b", vertexPath, errors).value_or(vertex.b);
    vertex.a = ReadNumber<float>(vertexNode, "a", vertexPath, errors, false).value_or(vertex.a);
    scene.vertices.push_back(vertex);
  }

  if (root.contains("indices")) {
    if (!root.at("indices").is_array()) {
      errors.push_back({"$.indices", "indices must be an array when present."});
    } else {
      for (std::size_t index = 0; index < root.at("indices").size(); ++index) {
        const json& indexNode = root.at("indices")[index];
        if (!indexNode.is_number_unsigned()) {
          errors.push_back({"$.indices[" + std::to_string(index) + "]",
                            "Each index must be an unsigned integer."});
          continue;
        }

        scene.indices.push_back(indexNode.get<std::uint32_t>());
      }
    }
  }

  return scene;
}

json SerializeColor(const ColorRgba& color) {
  return json{{"r", color.r}, {"g", color.g}, {"b", color.b}, {"a", color.a}};
}

json SerializeVector3(const Vector3Value& vector) {
  return json{{"x", vector.x}, {"y", vector.y}, {"z", vector.z}};
}
} // namespace

SceneParseResult SceneJsonCodec::Parse(const std::string& jsonText) const {
  SceneParseResult result;
  std::vector<ValidationError> errors;

  // A hard payload limit keeps accidental or malicious giant requests from asking
  // the parser and validator to do unreasonable amounts of work.
  if (jsonText.size() > SceneLimits::kMaxRequestPayloadBytes) {
    std::ostringstream messageBuilder;
    messageBuilder << "The request body is too large. The maximum supported size is "
                   << SceneLimits::kMaxRequestPayloadBytes << " bytes.";
    result.errors.push_back({"$", messageBuilder.str()});
    return result;
  }

  json rootJson;
  try {
    rootJson = json::parse(jsonText);
  } catch (const json::parse_error& error) {
    result.errors.push_back({"$", std::string("JSON parsing failed: ") + error.what()});
    return result;
  }

  if (!rootJson.is_object()) {
    result.errors.push_back({"$", "The root JSON value must be an object."});
    return result;
  }

  const auto sceneType = ReadString(rootJson, "sceneType", "$", errors);
  if (!sceneType.has_value()) {
    result.errors = std::move(errors);
    return result;
  }

  SceneDocument document;
  document.originalJson = jsonText;

  if (*sceneType == "2d") {
    document.kind = SceneKind::TwoDimensional;
    const auto scene = Parse2DScene(rootJson, errors);
    if (scene.has_value()) {
      document.payload = *scene;
    }
  } else if (*sceneType == "3d") {
    document.kind = SceneKind::ThreeDimensional;
    const auto scene = Parse3DScene(rootJson, errors);
    if (scene.has_value()) {
      document.payload = *scene;
    }
  } else {
    errors.push_back({"$.sceneType", "sceneType must be either '2d' or '3d'."});
  }

  if (!errors.empty()) {
    result.errors = std::move(errors);
    return result;
  }

  // Structural parsing answered "can this JSON be read as a scene object?"
  // Semantic validation answers "does that scene actually make sense to render?"
  const auto semanticValidationErrors = ValidateSceneDocument(document);
  if (!semanticValidationErrors.empty()) {
    result.errors = semanticValidationErrors;
    return result;
  }

  result.succeeded = true;
  result.scene = document;
  return result;
}

std::string SceneJsonCodec::Serialize(const SceneSnapshot& snapshot) const {
  json rootJson;
  // Serialization includes both the scene itself and the snapshot metadata that
  // tells clients where that scene came from and which version they are seeing.
  rootJson["version"] = snapshot.version;
  rootJson["sceneType"] = ToString(snapshot.document.kind);
  rootJson["sourceLabel"] = snapshot.sourceLabel;
  rootJson["updatedAtUtcSeconds"] =
      std::chrono::duration_cast<std::chrono::seconds>(snapshot.updatedAtUtc.time_since_epoch())
          .count();

  if (snapshot.document.kind == SceneKind::TwoDimensional) {
    const Scene2D& scene = std::get<Scene2D>(snapshot.document.payload);
    rootJson["primitive"] = ToString(scene.primitiveType);
    rootJson["pointSize"] = scene.pointSize;
    rootJson["lineWidth"] = scene.lineWidth;
    rootJson["clearColor"] = SerializeColor(scene.clearColor);
    rootJson["vertices"] = json::array();

    for (const Vertex2D& vertex : scene.vertices) {
      rootJson["vertices"].push_back(json{{"x", vertex.x},
                                          {"y", vertex.y},
                                          {"r", vertex.r},
                                          {"g", vertex.g},
                                          {"b", vertex.b},
                                          {"a", vertex.a}});
    }
  } else {
    const Scene3D& scene = std::get<Scene3D>(snapshot.document.payload);
    rootJson["primitive"] = ToString(scene.primitiveType);
    rootJson["pointSize"] = scene.pointSize;
    rootJson["lineWidth"] = scene.lineWidth;
    rootJson["clearColor"] = SerializeColor(scene.clearColor);
    rootJson["camera"] = json{{"position", SerializeVector3(scene.camera.position)},
                              {"target", SerializeVector3(scene.camera.target)},
                              {"up", SerializeVector3(scene.camera.up)},
                              {"fovYDegrees", scene.camera.fovYDegrees},
                              {"nearPlane", scene.camera.nearPlane},
                              {"farPlane", scene.camera.farPlane}};
    rootJson["vertices"] = json::array();
    for (const Vertex3D& vertex : scene.vertices) {
      rootJson["vertices"].push_back(json{{"x", vertex.x},
                                          {"y", vertex.y},
                                          {"z", vertex.z},
                                          {"r", vertex.r},
                                          {"g", vertex.g},
                                          {"b", vertex.b},
                                          {"a", vertex.a}});
    }
    rootJson["indices"] = scene.indices;
  }

  return rootJson.dump(2);
}
} // namespace halcyn::scene_description
