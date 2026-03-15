/**
 * @file
 * @brief Implements the small RAII wrapper around OpenGL shader compilation and program linking.
 *
 * @details
 * This file isolates the shader lifecycle so the renderer can talk in terms of "use this program"
 * and "set this uniform" instead of scattering OpenGL program-management code across the render
 * loop.
 *
 * Helpful external references:
 *
 * - [OpenGL shader compilation overview](https://wikis.khronos.org/opengl/Shader_Compilation)
 * - [`glUseProgram`](https://wikis.khronos.org/opengl/GLAPI/glUseProgram)
 * - [`glUniform` family](https://wikis.khronos.org/opengl/GLAPI/glUniform)
 * - [`glm::value_ptr`](https://glm.g-truc.net/0.9.9/api/a00305.html)
 */

#include "opengl_renderer/ShaderProgram.hpp"

#include <glm/gtc/type_ptr.hpp>

#include <stdexcept>
#include <vector>

namespace halcyn::opengl_renderer {
ShaderProgram::ShaderProgram(const std::string& vertexShaderSource,
                             const std::string& fragmentShaderSource) {
  // OpenGL shaders are built in two phases: compile each stage individually, then
  // link those stages into one executable GPU program.
  const GLuint vertexShader = CompileShader(GL_VERTEX_SHADER, vertexShaderSource);
  const GLuint fragmentShader = CompileShader(GL_FRAGMENT_SHADER, fragmentShaderSource);

  shaderProgramHandle_ = glCreateProgram();
  glAttachShader(shaderProgramHandle_, vertexShader);
  glAttachShader(shaderProgramHandle_, fragmentShader);
  glLinkProgram(shaderProgramHandle_);

  GLint linked = GL_FALSE;
  glGetProgramiv(shaderProgramHandle_, GL_LINK_STATUS, &linked);
  if (linked != GL_TRUE) {
    GLint informationLogLength = 0;
    glGetProgramiv(shaderProgramHandle_, GL_INFO_LOG_LENGTH, &informationLogLength);
    std::vector<char> informationLogBuffer(static_cast<std::size_t>(informationLogLength));
    glGetProgramInfoLog(shaderProgramHandle_, informationLogLength, nullptr,
                        informationLogBuffer.data());

    glDeleteShader(vertexShader);
    glDeleteShader(fragmentShader);
    glDeleteProgram(shaderProgramHandle_);
    throw std::runtime_error("Failed to link the shader program: " +
                             std::string(informationLogBuffer.data()));
  }

  // Once the program is linked successfully, the standalone shader objects are no
  // longer needed because the program already contains their compiled code.
  glDeleteShader(vertexShader);
  glDeleteShader(fragmentShader);
}

ShaderProgram::~ShaderProgram() {
  if (shaderProgramHandle_ != 0) {
    glDeleteProgram(shaderProgramHandle_);
  }
}

void ShaderProgram::Use() const {
  glUseProgram(shaderProgramHandle_);
}

void ShaderProgram::SetMatrix4(const char* uniformName, const glm::mat4& value) const {
  glUniformMatrix4fv(GetUniformLocation(uniformName), 1, GL_FALSE, glm::value_ptr(value));
}

void ShaderProgram::SetFloat(const char* uniformName, float value) const {
  glUniform1f(GetUniformLocation(uniformName), value);
}

GLuint ShaderProgram::CompileShader(GLenum shaderType, const std::string& source) const {
  const GLuint shaderHandle = glCreateShader(shaderType);
  const char* shaderSourceText = source.c_str();
  glShaderSource(shaderHandle, 1, &shaderSourceText, nullptr);
  glCompileShader(shaderHandle);

  GLint compiled = GL_FALSE;
  glGetShaderiv(shaderHandle, GL_COMPILE_STATUS, &compiled);
  if (compiled != GL_TRUE) {
    GLint informationLogLength = 0;
    glGetShaderiv(shaderHandle, GL_INFO_LOG_LENGTH, &informationLogLength);
    std::vector<char> informationLogBuffer(static_cast<std::size_t>(informationLogLength));
    glGetShaderInfoLog(shaderHandle, informationLogLength, nullptr, informationLogBuffer.data());
    glDeleteShader(shaderHandle);
    throw std::runtime_error("Failed to compile a shader stage: " +
                             std::string(informationLogBuffer.data()));
  }

  return shaderHandle;
}

GLint ShaderProgram::GetUniformLocation(const char* uniformName) const {
  return glGetUniformLocation(shaderProgramHandle_, uniformName);
}
} // namespace halcyn::opengl_renderer
