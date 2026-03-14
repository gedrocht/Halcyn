#pragma once

#include "domain/SceneTypes.hpp"

#include <vector>

namespace halcyn::domain {
/**
 * Performs semantic validation after parsing. This catches mistakes such as invalid primitive sizes
 * or bad indices.
 */
std::vector<ValidationError> ValidateSceneDocument(const SceneDocument& document);

/**
 * Converts a validated scene document into the flat vertex format uploaded to OpenGL.
 */
RenderScene BuildRenderScene(const SceneDocument& document);
} // namespace halcyn::domain
