#pragma once

#include <array>
#include <chrono>
#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <variant>
#include <vector>

namespace halcyn::domain {
/**
 * Describes whether an incoming scene should be interpreted as a 2D scene or a 3D scene.
 */
enum class SceneKind { TwoDimensional, ThreeDimensional };

/**
 * Describes how the renderer should connect vertices into visible geometry.
 */
enum class PrimitiveType { Points, Lines, Triangles };

/**
 * Stores one vertex for a 2D scene. The position is two-dimensional and the color includes alpha.
 */
struct Vertex2D {
  /** Horizontal position of the vertex in 2D scene space. */
  float x = 0.0F;

  /** Vertical position of the vertex in 2D scene space. */
  float y = 0.0F;

  /** Red color channel for this vertex. */
  float r = 1.0F;

  /** Green color channel for this vertex. */
  float g = 1.0F;

  /** Blue color channel for this vertex. */
  float b = 1.0F;

  /** Alpha color channel for this vertex. */
  float a = 1.0F;
};

/**
 * Stores one vertex for a 3D scene. The position is three-dimensional and the color is RGB with
 * optional alpha.
 */
struct Vertex3D {
  /** Horizontal position of the vertex in 3D scene space. */
  float x = 0.0F;

  /** Vertical position of the vertex in 3D scene space. */
  float y = 0.0F;

  /** Depth position of the vertex in 3D scene space. */
  float z = 0.0F;

  /** Red color channel for this vertex. */
  float r = 1.0F;

  /** Green color channel for this vertex. */
  float g = 1.0F;

  /** Blue color channel for this vertex. */
  float b = 1.0F;

  /** Optional alpha channel used by the renderer when blending is enabled. */
  float a = 1.0F;
};

/**
 * Stores a generic RGBA color. This is used for window clear colors and other scene-wide settings.
 */
struct ColorRgba {
  /** Red component of the color. */
  float r = 0.08F;

  /** Green component of the color. */
  float g = 0.09F;

  /** Blue component of the color. */
  float b = 0.12F;

  /** Alpha component of the color. */
  float a = 1.0F;
};

/**
 * Stores one three-dimensional vector. This is intentionally simple so the JSON structure stays
 * beginner-friendly.
 */
struct Vector3Value {
  /** X component of the vector. */
  float x = 0.0F;

  /** Y component of the vector. */
  float y = 0.0F;

  /** Z component of the vector. */
  float z = 0.0F;
};

/**
 * Stores the camera configuration that the 3D renderer needs to build a view and projection matrix.
 */
struct Camera3D {
  /** Position of the virtual camera in 3D world space. */
  Vector3Value position{2.5F, 2.0F, 2.5F};

  /** Point in 3D world space that the camera should look toward. */
  Vector3Value target{0.0F, 0.0F, 0.0F};

  /** Direction that should count as “up” for the camera. */
  Vector3Value up{0.0F, 1.0F, 0.0F};

  /** Vertical field of view for perspective projection, expressed in degrees. */
  float fovYDegrees = 60.0F;

  /** Distance from the camera to the near clipping plane. */
  float nearPlane = 0.1F;

  /** Distance from the camera to the far clipping plane. */
  float farPlane = 100.0F;
};

/**
 * Represents the complete payload for a 2D scene.
 */
struct Scene2D {
  /** Primitive type that tells the renderer whether vertices represent points, lines, or triangles.
   */
  PrimitiveType primitiveType = PrimitiveType::Triangles;

  /** Pixel size used when the primitive type is points. */
  float pointSize = 8.0F;

  /** Requested line width used when the primitive type is lines. */
  float lineWidth = 2.0F;

  /** Background color used when clearing the render window. */
  ColorRgba clearColor{};

  /** Vertex list for the 2D scene payload. */
  std::vector<Vertex2D> vertices;
};

/**
 * Represents the complete payload for a 3D scene.
 */
struct Scene3D {
  /** Primitive type that tells the renderer whether vertices represent points, lines, or triangles.
   */
  PrimitiveType primitiveType = PrimitiveType::Triangles;

  /** Pixel size used when the primitive type is points. */
  float pointSize = 8.0F;

  /** Requested line width used when the primitive type is lines. */
  float lineWidth = 2.0F;

  /** Background color used when clearing the render window. */
  ColorRgba clearColor{};

  /** Camera settings used to build the 3D view and projection matrices. */
  Camera3D camera{};

  /** Vertex list for the 3D scene payload. */
  std::vector<Vertex3D> vertices;

  /** Optional index buffer used for indexed drawing. */
  std::vector<std::uint32_t> indices;
};

/**
 * Wraps either a 2D scene or a 3D scene into one type that the rest of the application can pass
 * around.
 */
using ScenePayload = std::variant<Scene2D, Scene3D>;

/**
 * Represents one validated scene submission exactly as the application understands it after JSON
 * parsing.
 */
struct SceneDocument {
  /** Whether this document is a 2D scene or a 3D scene. */
  SceneKind kind = SceneKind::TwoDimensional;

  /** The validated scene payload itself. */
  ScenePayload payload = Scene2D{};

  /** Raw JSON text originally submitted by the caller. */
  std::string originalJson;
};

/**
 * Represents one versioned scene currently stored by the application.
 */
struct SceneSnapshot {
  /** Monotonically increasing version number assigned by the scene store. */
  std::uint64_t version = 0;

  /** The validated scene document currently stored for rendering. */
  SceneDocument document{};

  /** Human-readable note describing where the snapshot came from. */
  std::string sourceLabel = "bootstrap";

  /** UTC timestamp recording when this snapshot became active. */
  std::chrono::system_clock::time_point updatedAtUtc = std::chrono::system_clock::now();
};

/**
 * Represents one validation or parsing failure in a human-readable, beginner-friendly way.
 */
struct ValidationError {
  /** JSON-path-like location describing where the problem happened. */
  std::string path;

  /** Beginner-friendly description of what was wrong. */
  std::string message;
};

/**
 * Represents the result of parsing JSON into a scene document.
 */
struct SceneParseResult {
  /** Whether parsing and validation completed successfully. */
  bool succeeded = false;

  /** The validated scene, present only when parsing succeeded. */
  std::optional<SceneDocument> scene;

  /** One or more errors explaining why parsing failed. */
  std::vector<ValidationError> errors;
};

/**
 * Represents one vertex in the exact layout uploaded to the GPU.
 */
struct RenderVertex {
  /** Horizontal GPU-space position component. */
  float x = 0.0F;

  /** Vertical GPU-space position component. */
  float y = 0.0F;

  /** Depth GPU-space position component. */
  float z = 0.0F;

  /** Red color channel used by the shader. */
  float r = 1.0F;

  /** Green color channel used by the shader. */
  float g = 1.0F;

  /** Blue color channel used by the shader. */
  float b = 1.0F;

  /** Alpha color channel used by the shader. */
  float a = 1.0F;
};

/**
 * Represents a scene transformed into a renderer-friendly format. Both 2D and 3D scenes end up here
 * so the GPU upload path can stay simple.
 */
struct RenderScene {
  /** Whether the scene should be rendered as 2D or 3D. */
  SceneKind kind = SceneKind::TwoDimensional;

  /** Primitive type used for the draw call. */
  PrimitiveType primitiveType = PrimitiveType::Triangles;

  /** Point size passed to the shader when drawing points. */
  float pointSize = 8.0F;

  /** Line width requested for line primitives. */
  float lineWidth = 2.0F;

  /** Background color used to clear the frame. */
  ColorRgba clearColor{};

  /** Camera settings used only for 3D scenes. */
  Camera3D camera{};

  /** Flattened vertex buffer uploaded directly to the GPU. */
  std::vector<RenderVertex> vertices;

  /** Optional flattened index buffer uploaded directly to the GPU. */
  std::vector<std::uint32_t> indices;
};

/**
 * Converts a scene kind to the string value used by the API and documentation.
 */
std::string ToString(SceneKind kind);

/**
 * Converts a primitive type to the string value used by the API and documentation.
 */
std::string ToString(PrimitiveType primitiveType);

/**
 * Parses a primitive type string into the enum used internally by the program.
 */
std::optional<PrimitiveType> PrimitiveTypeFromString(const std::string& value);
} // namespace halcyn::domain
