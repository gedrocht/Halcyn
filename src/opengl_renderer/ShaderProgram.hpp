#pragma once

#include <glad/gl.h>
#include <glm/mat4x4.hpp>

#include <string>

namespace halcyn::opengl_renderer {
/**
 * Wraps an OpenGL shader program so the rest of the renderer can compile, link, and use GPU shaders
 * without scattering raw OpenGL object management code everywhere.
 */
class ShaderProgram {
public:
  /**
   * Creates a linked shader program from a vertex shader source string and a fragment shader source
   * string.
   */
  ShaderProgram(const std::string& vertexShaderSource, const std::string& fragmentShaderSource);

  /**
   * Releases the GPU shader program.
   */
  ~ShaderProgram();

  ShaderProgram(const ShaderProgram&) = delete;
  ShaderProgram& operator=(const ShaderProgram&) = delete;

  /**
   * Makes this shader program the active program for future draw calls.
   */
  void Use() const;

  /**
   * Sends a 4x4 matrix uniform to the GPU.
   */
  void SetMatrix4(const char* uniformName, const glm::mat4& value) const;

  /**
   * Sends a floating-point uniform to the GPU.
   */
  void SetFloat(const char* uniformName, float value) const;

private:
  /**
   * Compiles one shader stage and returns the OpenGL shader object handle.
   */
  [[nodiscard]] GLuint CompileShader(GLenum shaderType, const std::string& source) const;

  /**
   * Returns the location of a uniform inside the linked program.
   */
  [[nodiscard]] GLint GetUniformLocation(const char* uniformName) const;

  /**
   * Stores the linked program object handle.
   */
  GLuint shaderProgramHandle_ = 0;
};
} // namespace halcyn::opengl_renderer
