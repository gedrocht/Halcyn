#pragma once

#include "scene_description/SceneTypes.hpp"

/**
 * @file
 * @brief Declares helpers that build small built-in scenes used by startup, documentation, and
 * tests.
 */

namespace halcyn::scene_description {
/**
 * @brief Creates a colorful built-in default scene.
 *
 * @return A valid scene document that the application can render immediately.
 *
 * @details
 * Halcyn always wants to have something valid to draw, even before the first API request arrives.
 * This helper provides that safety-net scene.
 *
 * The default scene currently delegates to the simpler 2D sample because it is the friendliest
 * first-render experience for beginners and the smallest "known good" graphics path.
 */
SceneDocument CreateDefaultSceneDocument();

/**
 * @brief Creates a beginner-friendly sample 2D scene.
 *
 * @return A fully populated 2D scene document together with matching original JSON text.
 *
 * @details
 * This helper is used in multiple roles:
 *
 * - startup fallback scene
 * - HTTP example payload
 * - documentation example
 * - test fixture
 *
 * Keeping those roles tied to one source of truth reduces drift between the code, the API, and the
 * docs.
 */
SceneDocument CreateSample2DSceneDocument();

/**
 * @brief Creates a beginner-friendly sample 3D scene.
 *
 * @return A fully populated 3D scene document together with matching original JSON text.
 *
 * @details
 * The built-in 3D sample exists so the project can demonstrate:
 *
 * - camera setup
 * - perspective projection
 * - indexed drawing
 * - depth testing
 *
 * without needing an external asset pipeline or mesh format.
 */
SceneDocument CreateSample3DSceneDocument();
} // namespace halcyn::scene_description
