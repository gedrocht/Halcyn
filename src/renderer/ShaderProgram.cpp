#include "renderer/ShaderProgram.hpp"

#include <glm/gtc/type_ptr.hpp>

#include <stdexcept>
#include <vector>

namespace halcyn::renderer {
ShaderProgram::ShaderProgram(const std::string& vertexShaderSource,
                             const std::string& fragmentShaderSource) {
  const GLuint vertexShader = CompileShader(GL_VERTEX_SHADER, vertexShaderSource);
  const GLuint fragmentShader = CompileShader(GL_FRAGMENT_SHADER, fragmentShaderSource);

  programId_ = glCreateProgram();
  glAttachShader(programId_, vertexShader);
  glAttachShader(programId_, fragmentShader);
  glLinkProgram(programId_);

  GLint linked = GL_FALSE;
  glGetProgramiv(programId_, GL_LINK_STATUS, &linked);
  if (linked != GL_TRUE) {
    GLint infoLogLength = 0;
    glGetProgramiv(programId_, GL_INFO_LOG_LENGTH, &infoLogLength);
    std::vector<char> infoLog(static_cast<std::size_t>(infoLogLength));
    glGetProgramInfoLog(programId_, infoLogLength, nullptr, infoLog.data());

    glDeleteShader(vertexShader);
    glDeleteShader(fragmentShader);
    glDeleteProgram(programId_);
    throw std::runtime_error("Failed to link the shader program: " + std::string(infoLog.data()));
  }

  glDeleteShader(vertexShader);
  glDeleteShader(fragmentShader);
}

ShaderProgram::~ShaderProgram() {
  if (programId_ != 0) {
    glDeleteProgram(programId_);
  }
}

void ShaderProgram::Use() const {
  glUseProgram(programId_);
}

void ShaderProgram::SetMatrix4(const char* uniformName, const glm::mat4& value) const {
  glUniformMatrix4fv(GetUniformLocation(uniformName), 1, GL_FALSE, glm::value_ptr(value));
}

void ShaderProgram::SetFloat(const char* uniformName, float value) const {
  glUniform1f(GetUniformLocation(uniformName), value);
}

GLuint ShaderProgram::CompileShader(GLenum shaderType, const std::string& source) const {
  const GLuint shader = glCreateShader(shaderType);
  const char* shaderSource = source.c_str();
  glShaderSource(shader, 1, &shaderSource, nullptr);
  glCompileShader(shader);

  GLint compiled = GL_FALSE;
  glGetShaderiv(shader, GL_COMPILE_STATUS, &compiled);
  if (compiled != GL_TRUE) {
    GLint infoLogLength = 0;
    glGetShaderiv(shader, GL_INFO_LOG_LENGTH, &infoLogLength);
    std::vector<char> infoLog(static_cast<std::size_t>(infoLogLength));
    glGetShaderInfoLog(shader, infoLogLength, nullptr, infoLog.data());
    glDeleteShader(shader);
    throw std::runtime_error("Failed to compile a shader stage: " + std::string(infoLog.data()));
  }

  return shader;
}

GLint ShaderProgram::GetUniformLocation(const char* uniformName) const {
  return glGetUniformLocation(programId_, uniformName);
}
} // namespace halcyn::renderer
