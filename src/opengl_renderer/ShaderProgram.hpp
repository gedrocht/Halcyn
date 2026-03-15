#pragma once

#include <glad/gl.h>
#include <glm/mat4x4.hpp>

#include <string>

/**
 * @file
 * @brief Declares a small RAII wrapper around an OpenGL shader program.
 */

namespace halcyn::opengl_renderer {
/**
 * @brief Wraps an OpenGL shader program so the rest of the renderer can work with a small C++ API
 * instead of raw shader lifecycle calls everywhere.
 *
 * @details
 * OpenGL shader setup normally involves several low-level steps:
 *
 * 1. create one shader object per stage
 * 2. upload source text
 * 3. compile each stage
 * 4. create one program object
 * 5. attach the compiled stages
 * 6. link the program
 * 7. use the linked program for draw calls
 *
 * This class centralizes that work so the renderer can express its intent more clearly.
 *
 * Helpful external references:
 *
 * - [OpenGL shader compilation overview](https://wikis.khronos.org/opengl/Shader_Compilation)
 * - [`glUseProgram`](https://wikis.khronos.org/opengl/GLAPI/glUseProgram)
 * - [`glUniform` family](https://wikis.khronos.org/opengl/GLAPI/glUniform)
 * - [`glm::value_ptr`](https://glm.g-truc.net/0.9.9/api/a00305.html)
 */
class ShaderProgram {
public:
  /**
   * @brief Creates a linked shader program from one vertex shader source string and one fragment
   * shader source string.
   *
   * @param vertexShaderSource GLSL source for the vertex stage.
   * @param fragmentShaderSource GLSL source for the fragment stage.
   *
   * @throws std::runtime_error if shader compilation or program linking fails.
   */
  ShaderProgram(const std::string& vertexShaderSource, const std::string& fragmentShaderSource);

  /**
   * @brief Releases the GPU shader program.
   */
  ~ShaderProgram();

  ShaderProgram(const ShaderProgram&) = delete;
  ShaderProgram& operator=(const ShaderProgram&) = delete;

  /**
   * @brief Makes this shader program the active program for future draw calls.
   */
  void Use() const;

  /**
   * @brief Sends a 4x4 matrix uniform to the GPU.
   *
   * @param uniformName Name of the GLSL uniform.
   * @param value Matrix value to upload.
   */
  void SetMatrix4(const char* uniformName, const glm::mat4& value) const;

  /**
   * @brief Sends a floating-point uniform to the GPU.
   *
   * @param uniformName Name of the GLSL uniform.
   * @param value Floating-point value to upload.
   */
  void SetFloat(const char* uniformName, float value) const;

private:
  /**
   * @brief Compiles one shader stage and returns the OpenGL shader object handle.
   *
   * @param shaderType OpenGL enum describing the shader stage, such as `GL_VERTEX_SHADER`.
   * @param source GLSL source code for the stage.
   * @return The compiled shader handle.
   */
  [[nodiscard]] GLuint CompileShader(GLenum shaderType, const std::string& source) const;

  /**
   * @brief Returns the location of a uniform inside the linked program.
   *
   * @param uniformName Name of the GLSL uniform variable.
   * @return The integer location returned by OpenGL.
   */
  [[nodiscard]] GLint GetUniformLocation(const char* uniformName) const;

  /** Stores the linked program object handle. */
  GLuint shaderProgramHandle_ = 0;
};
} // namespace halcyn::opengl_renderer
