#pragma once

#include "scene_description/SceneTypes.hpp"

#include <memory>
#include <string>

namespace halcyn::scene_description {
/**
 * Parses JSON submitted by API clients into validated in-memory scene objects and can serialize a
 * stored scene back into JSON for diagnostics.
 */
class SceneJsonCodec {
public:
  /**
   * Parses raw JSON text into a validated scene document.
   */
  [[nodiscard]] SceneParseResult Parse(const std::string& jsonText) const;

  /**
   * Serializes a stored scene snapshot back into JSON text for API responses and debugging.
   */
  [[nodiscard]] std::string Serialize(const SceneSnapshot& snapshot) const;
};
} // namespace halcyn::scene_description
