#pragma once

#include "scene_description/SceneTypes.hpp"

#include <vector>

/**
 * @file
 * @brief Declares semantic validation and render-scene conversion helpers.
 */

namespace halcyn::scene_description {
/**
 * @brief Performs semantic validation after parsing.
 *
 * @param document The typed scene document to validate.
 * @return Zero or more validation errors describing any problems that make the scene unsafe or
 * nonsensical to render.
 *
 * @details
 * Parsing answers: "Can this JSON be read into C++ objects?"
 *
 * Semantic validation answers: "Do those objects describe a sensible scene?"
 *
 * Examples of rules enforced here:
 *
 * - primitive counts must line up with the selected draw mode
 * - point size and line width must be positive
 * - index values must stay within the vertex array
 * - 3D camera settings must define a usable camera basis
 *
 * Separating validation from parsing keeps both stages easier to reason about. The parser can focus
 * on shape and types, while this function can focus on rendering correctness.
 */
std::vector<ValidationError> ValidateSceneDocument(const SceneDocument& document);

/**
 * @brief Converts a validated scene document into the flat vertex format uploaded to OpenGL.
 *
 * @param document The validated scene document to convert.
 * @return A renderer-friendly @ref RenderScene.
 *
 * @details
 * This function is the bridge between the scene-description layer and the renderer.
 *
 * Why it exists:
 *
 * - the human-facing JSON model is nice for authors and tools
 * - the renderer wants one predictable vertex/index layout
 * - keeping the conversion in one place means the renderer does not need to know about every detail
 *   of the original JSON model
 *
 * For example, 2D vertices are promoted into the shared render format by supplying `z = 0`.
 */
RenderScene BuildRenderScene(const SceneDocument& document);
} // namespace halcyn::scene_description
