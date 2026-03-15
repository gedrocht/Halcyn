#pragma once

#include <array>
#include <chrono>
#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <variant>
#include <vector>

/**
 * @file
 * @brief Defines the strongly typed scene model shared by the parser, validator, HTTP API,
 * renderer, and tests.
 *
 * @details
 * This file is the vocabulary of the whole application. Almost every interesting piece of Halcyn
 * eventually touches one or more of these types:
 *
 * - JSON parsing fills them in.
 * - validation checks whether their contents make sense.
 * - the shared runtime stores them in versioned snapshots.
 * - the renderer transforms them into GPU buffers.
 *
 * If you are new to the codebase, reading this file first is usually the easiest way to understand
 * what kind of data the rest of the system expects.
 *
 * Helpful companion pages:
 *
 * - @ref scene_json_guide.md "Scene JSON Guide"
 * - @ref usage_examples.md "Usage Examples"
 * - @ref external_library_guide.md "External Library Guide"
 */

namespace halcyn::scene_description {
/**
 * @brief Groups the data types and helper functions that describe what Halcyn should render.
 *
 * @details
 * A useful beginner mental model is:
 *
 * - `Scene2D` and `Scene3D` describe the *intent* of a scene.
 * - `SceneDocument` wraps one of those scenes together with metadata such as the original JSON.
 * - `SceneSnapshot` adds versioning and timestamps so the rest of the program can talk about "the
 *   currently active scene".
 * - `RenderScene` is the flattened form the OpenGL renderer actually uploads to the GPU.
 */

/**
 * @brief Describes whether an incoming scene should be interpreted as a 2D scene or a 3D scene.
 *
 * @details
 * This is intentionally a very small enum because the first big choice in the system is simply:
 *
 * - does the scene use a flat 2D camera model?
 * - or does it use a 3D camera with perspective projection?
 *
 * That one decision affects parsing, validation, matrix generation, and draw behavior.
 */
enum class SceneKind { TwoDimensional, ThreeDimensional };

/**
 * @brief Describes how the renderer should connect vertices into visible geometry.
 *
 * @details
 * This maps directly to OpenGL primitive modes. See:
 * [OpenGL primitive overview](https://wikis.khronos.org/opengl/primitive).
 */
enum class PrimitiveType { Points, Lines, Triangles };

/**
 * @brief Stores one vertex for a 2D scene.
 *
 * @details
 * A 2D vertex intentionally contains only the information Halcyn needs today:
 *
 * - position
 * - color
 *
 * There are no texture coordinates, normals, or tangents because Halcyn currently focuses on
 * simple unlit geometry. Keeping the vertex format small makes the JSON easier to write by hand and
 * makes the renderer easier to explain to beginners.
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
 * @brief Stores one vertex for a 3D scene.
 *
 * @details
 * This is the 3D sibling of @ref Vertex2D. It adds a `z` component, but it still deliberately
 * avoids more advanced mesh attributes because Halcyn is currently teaching and rendering simple
 * colored geometry rather than full lighting pipelines.
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
 * @brief Stores a generic RGBA color.
 *
 * @details
 * This is used for clear colors and other scene-wide settings. Halcyn uses normalized floating
 * point color channels because that lines up naturally with what OpenGL shaders expect.
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
 * @brief Stores one three-dimensional vector.
 *
 * @details
 * This project could use a math-library type such as `glm::vec3` directly, but keeping the scene
 * description layer free of external math-library types makes the JSON mapping easier to teach and
 * keeps the parser and validator independent from the renderer's implementation details.
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
 * @brief Stores the camera configuration that the 3D renderer needs.
 *
 * @details
 * In beginner terms, this camera answers three different questions:
 *
 * - Where is the camera? (`position`)
 * - What is it looking at? (`target`)
 * - Which direction should count as "up"? (`up`)
 *
 * The remaining fields control how the 3D view is projected:
 *
 * - `fovYDegrees` controls how wide the vertical field of view is.
 * - `nearPlane` and `farPlane` define the visible depth range.
 *
 * In the renderer, these values are later passed to GLM helpers such as
 * [`glm::lookAt`](https://glm.g-truc.net/0.9.9/api/a00668.html) and
 * [`glm::perspective`](https://glm.g-truc.net/0.9.9/api/a00665.html).
 */
struct Camera3D {
  /** Position of the virtual camera in 3D world space. */
  Vector3Value position{2.5F, 2.0F, 2.5F};

  /** Point in 3D world space that the camera should look toward. */
  Vector3Value target{0.0F, 0.0F, 0.0F};

  /** Direction that should count as "up" for the camera. */
  Vector3Value up{0.0F, 1.0F, 0.0F};

  /** Vertical field of view for perspective projection, expressed in degrees. */
  float fovYDegrees = 60.0F;

  /** Distance from the camera to the near clipping plane. */
  float nearPlane = 0.1F;

  /** Distance from the camera to the far clipping plane. */
  float farPlane = 100.0F;
};

/**
 * @brief Represents the complete payload for a 2D scene.
 *
 * @details
 * A `Scene2D` is the simplest complete drawable document in Halcyn. It says:
 *
 * - how vertices should be grouped into primitives
 * - how large points or lines should appear
 * - what color the window should be cleared to
 * - which vertices should be drawn
 *
 * Example:
 *
 * @code{.json}
 * {
 *   "sceneType": "2d",
 *   "primitive": "triangles",
 *   "clearColor": { "r": 0.05, "g": 0.07, "b": 0.11, "a": 1.0 },
 *   "vertices": [
 *     { "x": -0.8, "y": -0.6, "r": 1.0, "g": 0.2, "b": 0.2, "a": 1.0 },
 *     { "x": 0.0, "y": 0.7, "r": 0.2, "g": 0.9, "b": 0.7, "a": 1.0 },
 *     { "x": 0.8, "y": -0.4, "r": 0.2, "g": 0.5, "b": 1.0, "a": 1.0 }
 *   ]
 * }
 * @endcode
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
 * @brief Represents the complete payload for a 3D scene.
 *
 * @details
 * A `Scene3D` extends the 2D idea with:
 *
 * - a camera
 * - a real depth (`z`) coordinate
 * - an optional index buffer so vertices can be reused
 *
 * That makes it suitable for simple mesh-like data while keeping the JSON format readable.
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
 * @brief Wraps either a 2D scene or a 3D scene into one type.
 *
 * @details
 * This lets the application treat "a scene" as one concept while still preserving strong typing.
 * The parser decides which alternative is active, validation checks the matching rules, and the
 * renderer later uses @ref SceneKind to decide whether to build a 2D or 3D matrix.
 */
using ScenePayload = std::variant<Scene2D, Scene3D>;

/**
 * @brief Represents one validated scene submission after JSON parsing.
 *
 * @details
 * This is the main semantic scene type in the application.
 *
 * It is more than raw JSON because:
 *
 * - `kind` has already been parsed into an enum
 * - `payload` is already a typed 2D or 3D scene
 * - the document has already passed semantic validation when it reaches most of the system
 *
 * The original JSON is still kept so the program can echo it back in diagnostics or expose it to
 * tools that want the original submission text.
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
 * @brief Represents one versioned scene currently stored by the application.
 *
 * @details
 * The snapshot concept is important for concurrency.
 *
 * Instead of sharing a mutable scene object between threads, Halcyn shares immutable snapshots.
 * Each snapshot bundles:
 *
 * - the scene itself
 * - a version number
 * - a source label
 * - an activation timestamp
 *
 * That means readers can keep a stable pointer to a complete snapshot even while a newer snapshot
 * is being published.
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
 * @brief Represents one validation or parsing failure in a human-readable way.
 *
 * @details
 * Halcyn prefers reporting many understandable errors over failing fast with one terse exception.
 * That makes this type especially important for tools, tutorials, tests, and browser UIs.
 */
struct ValidationError {
  /** JSON-path-like location describing where the problem happened. */
  std::string path;

  /** Beginner-friendly description of what was wrong. */
  std::string message;
};

/**
 * @brief Represents the result of parsing JSON into a scene document.
 *
 * @details
 * A parse operation in Halcyn is intentionally non-throwing at the API boundary. Instead of making
 * callers catch exceptions for common input mistakes, the parser returns:
 *
 * - `succeeded = true` plus a `scene`, or
 * - `succeeded = false` plus one or more `errors`
 *
 * That makes it easy for HTTP handlers and browser tooling to display validation results directly.
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
 * @brief Represents one vertex in the exact layout uploaded to the GPU.
 *
 * @details
 * The renderer uses one unified vertex format for both 2D and 3D scenes. That keeps the GPU upload
 * and attribute-binding code simple because it does not need separate 2D and 3D buffer layouts.
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
 * @brief Represents a scene transformed into a renderer-friendly format.
 *
 * @details
 * The most important difference between `SceneDocument` and `RenderScene` is that `RenderScene` is
 * no longer trying to preserve the author-friendly JSON structure. It is trying to be convenient
 * for rendering:
 *
 * - 2D and 3D vertices share one flat format
 * - optional index data is stored exactly as the renderer wants it
 * - draw settings live next to the flattened buffers
 *
 * This is the bridge type between the human-facing data model and the GPU-facing data model.
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
 * @brief Converts a scene kind to the string value used by the API and documentation.
 *
 * @details
 * This helper keeps wire-format strings in one place so the JSON codec, API responses, tests, and
 * documentation all stay aligned.
 */
std::string ToString(SceneKind kind);

/**
 * @brief Converts a primitive type to the string value used by the API and documentation.
 *
 * @details
 * This is used when serializing scenes back to JSON or building beginner-friendly diagnostics.
 */
std::string ToString(PrimitiveType primitiveType);

/**
 * @brief Parses a primitive type string into the enum used internally by the program.
 *
 * @details
 * Example:
 *
 * @code{.cpp}
 * const auto primitiveType =
 *     halcyn::scene_description::PrimitiveTypeFromString("triangles");
 * if (primitiveType.has_value()) {
 *   // Use *primitiveType here.
 * }
 * @endcode
 */
std::optional<PrimitiveType> PrimitiveTypeFromString(const std::string& value);
} // namespace halcyn::scene_description
