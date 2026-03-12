#pragma once

#include "core/RuntimeLog.hpp"
#include "core/SceneStore.hpp"
#include "domain/SceneValidation.hpp"
#include "renderer/ShaderProgram.hpp"

#include <GLFW/glfw3.h>
#include <glm/mat4x4.hpp>

#include <memory>
#include <string>

namespace halcyn::renderer
{
/**
 * Holds the runtime settings for the render window and frame pacing.
 */
struct RendererConfig
{
  /**
   * Sets the width of the render window in pixels.
   */
  int windowWidth = 1280;

  /**
   * Sets the height of the render window in pixels.
   */
  int windowHeight = 720;

  /**
   * Sets the target refresh rate used for frame pacing in the main draw loop.
   */
  int targetFramesPerSecond = 60;

  /**
   * Sets the text shown in the window title bar.
   */
  std::string windowTitle = "Halcyn";
};

/**
 * Owns the OpenGL window, GPU buffers, shaders, and draw loop.
 */
class Renderer
{
public:
  /**
   * Builds the renderer with access to the shared scene store.
   */
  Renderer(
    RendererConfig config,
    std::shared_ptr<core::SceneStore> sceneStore,
    std::shared_ptr<core::RuntimeLog> runtimeLog);

  /**
   * Releases OpenGL resources and shuts down GLFW.
   */
  ~Renderer();

  Renderer(const Renderer&) = delete;
  Renderer& operator=(const Renderer&) = delete;

  /**
   * Starts the render loop and keeps drawing until the window closes.
   */
  void Run();

private:
  /**
   * Creates the GLFW window and OpenGL context.
   */
  void InitializeWindow();

  /**
   * Configures global OpenGL state and compiles the shader program.
   */
  void InitializeOpenGlResources();

  /**
   * Releases GPU objects owned directly by the renderer.
   */
  void DestroyOpenGlResources();

  /**
   * Uploads the latest scene into OpenGL vertex and index buffers.
   */
  void UploadSceneToGpu(const domain::RenderScene& renderScene);

  /**
   * Draws the scene currently stored in GPU buffers.
   */
  void DrawScene(const domain::RenderScene& renderScene) const;

  /**
   * Builds the final model-view-projection matrix for the submitted scene.
   */
  [[nodiscard]] glm::mat4 BuildSceneMatrix(const domain::RenderScene& renderScene) const;

  /**
   * Builds an orthographic projection that fits the full 2D scene inside the window.
   */
  [[nodiscard]] glm::mat4 Build2DSceneMatrix(const domain::RenderScene& renderScene) const;

  /**
   * Builds the perspective view-projection matrix used for 3D scenes.
   */
  [[nodiscard]] glm::mat4 Build3DSceneMatrix(const domain::RenderScene& renderScene) const;

  /**
   * Converts the app's primitive enum into the OpenGL draw mode.
   */
  [[nodiscard]] GLenum ToOpenGlPrimitive(domain::PrimitiveType primitiveType) const;

  /**
   * Stores the chosen window settings.
   */
  RendererConfig config_;

  /**
   * Points at the shared scene store.
   */
  std::shared_ptr<core::SceneStore> sceneStore_;

  /**
   * Stores runtime log messages for the browser dashboard and console output.
   */
  std::shared_ptr<core::RuntimeLog> runtimeLog_;

  /**
   * Stores the current GLFW window.
   */
  GLFWwindow* window_ = nullptr;

  /**
   * Stores the GPU shader program used for both 2D and 3D scenes.
   */
  std::unique_ptr<ShaderProgram> shaderProgram_;

  /**
   * Stores the main vertex array object.
   */
  GLuint vao_ = 0;

  /**
   * Stores the vertex buffer object.
   */
  GLuint vbo_ = 0;

  /**
   * Stores the index buffer object.
   */
  GLuint ebo_ = 0;

  /**
   * Tracks the last scene version uploaded to the GPU so unchanged frames avoid unnecessary uploads.
   */
  std::uint64_t uploadedSceneVersion_ = 0;

  /**
   * Stores the last renderable scene uploaded to the GPU.
   */
  domain::RenderScene uploadedRenderScene_ {};
};
}  // namespace halcyn::renderer
