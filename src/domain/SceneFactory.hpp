#pragma once

#include "domain/SceneTypes.hpp"

namespace halcyn::domain {
/**
 * Creates a colorful built-in scene so the window shows something useful even before the first API
 * call arrives.
 */
SceneDocument CreateDefaultSceneDocument();

/**
 * Creates a beginner-friendly sample 2D scene that can also be reused by tests and documentation.
 */
SceneDocument CreateSample2DSceneDocument();

/**
 * Creates a beginner-friendly sample 3D scene that can also be reused by tests and documentation.
 */
SceneDocument CreateSample3DSceneDocument();
} // namespace halcyn::domain
