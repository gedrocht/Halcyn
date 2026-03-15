#pragma once

#include "scene_description/SceneTypes.hpp"

#include <memory>
#include <string>

/**
 * @file
 * @brief Declares the JSON codec that translates between raw text and typed Halcyn scene objects.
 */

namespace halcyn::scene_description {
/**
 * @brief Parses JSON submitted by API clients into validated in-memory scene objects and can
 * serialize stored scenes back into JSON.
 *
 * @details
 * `SceneJsonCodec` is the gatekeeper between the outside world's text-based representation and the
 * application's typed representation.
 *
 * It answers two complementary questions:
 *
 * - **Parse:** "Can this JSON text become a valid Halcyn scene?"
 * - **Serialize:** "Can this stored scene snapshot be turned back into JSON so a human or tool can
 *   inspect it?"
 *
 * The class deliberately combines parsing and serialization because both operations need to agree
 * on the same wire format. Keeping them together reduces the risk that the project accidentally
 * accepts one shape of JSON but emits another.
 *
 * External documentation used by this class:
 *
 * - [nlohmann/json overview](https://nlohmann.github.io/json/api/basic_json/)
 * - [`json::parse`](https://nlohmann.github.io/json/api/basic_json/parse/)
 * - [`json::dump`](https://nlohmann.github.io/json/api/basic_json/dump/)
 * - [`json::get`](https://nlohmann.github.io/json/api/basic_json/get/)
 *
 * Example:
 *
 * @code{.cpp}
 * halcyn::scene_description::SceneJsonCodec sceneJsonCodec;
 *
 * const auto sceneParseResult = sceneJsonCodec.Parse(R"({
 *   "sceneType": "2d",
 *   "primitive": "triangles",
 *   "vertices": [
 *     { "x": -0.5, "y": -0.5, "r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0 },
 *     { "x":  0.0, "y":  0.5, "r": 0.0, "g": 1.0, "b": 0.0, "a": 1.0 },
 *     { "x":  0.5, "y": -0.5, "r": 0.0, "g": 0.0, "b": 1.0, "a": 1.0 }
 *   ]
 * })");
 *
 * if (sceneParseResult.succeeded) {
 *   // sceneParseResult.scene now contains a validated SceneDocument.
 * }
 * @endcode
 */
class SceneJsonCodec {
public:
  /**
   * @brief Parses raw JSON text into a validated scene document.
   *
   * @param jsonText The full request body or file contents containing one JSON scene object.
   * @return A @ref SceneParseResult containing either a validated scene or one or more readable
   * validation errors.
   *
   * @details
   * Parsing happens in stages:
   *
   * 1. Enforce a hard payload-size limit.
   * 2. Parse the JSON text into a JSON DOM.
   * 3. Check the top-level structure and required fields.
   * 4. Convert raw JSON values into typed C++ scene objects.
   * 5. Run semantic validation on the resulting scene.
   *
   * That staged design matters because it lets the code distinguish between:
   *
   * - malformed JSON
   * - structurally wrong but syntactically valid JSON
   * - structurally valid scene data that still does not make semantic sense to render
   */
  [[nodiscard]] SceneParseResult Parse(const std::string& jsonText) const;

  /**
   * @brief Serializes a stored scene snapshot back into JSON text.
   *
   * @param snapshot The versioned scene snapshot that should be emitted as JSON.
   * @return A pretty-printed JSON string suitable for API responses, diagnostics, and tutorials.
   *
   * @details
   * Serialization includes both scene geometry and snapshot metadata such as:
   *
   * - version number
   * - source label
   * - activation time
   *
   * That makes the output useful for more than rendering. It also supports debugging, browser
   * tooling, and documentation examples.
   */
  [[nodiscard]] std::string Serialize(const SceneSnapshot& snapshot) const;
};
} // namespace halcyn::scene_description
