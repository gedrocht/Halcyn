#pragma once

#include "opengl_renderer/ShaderProgram.hpp"
#include "scene_description/SceneValidation.hpp"
#include "shared_runtime/RuntimeLog.hpp"
#include "shared_runtime/SceneStore.hpp"

#include <GLFW/glfw3.h>
#include <glm/mat4x4.hpp>

#include <memory>
#include <string>

/**
 * @file
 * @brief Declares the OpenGL renderer that owns the window, GPU resources, and frame loop.
 */

namespace halcyn::opengl_renderer {
/**
 * @brief Holds the runtime settings for the render window and frame pacing.
 */
struct RendererConfig {
  /** Sets the width of the render window in pixels. */
  int windowWidth = 1280;

  /** Sets the height of the render window in pixels. */
  int windowHeight = 720;

  /** Sets the target refresh rate used for frame pacing in the main draw loop. */
  int targetFramesPerSecond = 60;

  /** Sets the text shown in the window title bar. */
  std::string windowTitle = "Halcyn";
};

/**
 * @brief Owns the OpenGL window, GPU buffers, shaders, and draw loop.
 *
 * @details
 * This class is responsible for turning the current scene snapshot into pixels.
 *
 * Its job can be summarized like this:
 *
 * 1. create a GLFW window and OpenGL context
 * 2. load OpenGL function pointers with glad
 * 3. create the shader program and GPU buffers
 * 4. watch the shared scene store for version changes
 * 5. upload new scene data only when the version changes
 * 6. draw the current scene every frame
 *
 * Important external references:
 *
 * - [GLFW documentation](https://www.glfw.org/documentation.html)
 * - [GLFW window guide](https://www.glfw.org/docs/latest/window_guide.html)
 * - [GLFW context guide](https://www.glfw.org/docs/latest/context_guide.html)
 * - [glad quickstart](https://github.com/Dav1dde/glad/wiki/C)
 * - [OpenGL Vertex Specification](https://wikis.khronos.org/opengl/Vertex_Specification)
 * - [OpenGL Buffer Object overview](https://wikis.khronos.org/opengl/Buffer_Object)
 * - [GLM matrix transform docs](https://glm.g-truc.net/0.9.9/api/a00668.html)
 * - [GLM clip-space docs](https://glm.g-truc.net/0.9.9/api/a00665.html)
 */
class Renderer {
public:
  /**
   * @brief Builds the renderer with access to the shared scene store and runtime log.
   *
   * @param rendererConfiguration Window title, size, and frame-rate settings.
   * @param sceneStore Shared scene store that the renderer reads from.
   * @param runtimeLog Shared runtime log for diagnostics.
   */
  Renderer(RendererConfig rendererConfiguration,
           std::shared_ptr<shared_runtime::SceneStore> sceneStore,
           std::shared_ptr<shared_runtime::RuntimeLog> runtimeLog);

  /**
   * @brief Releases OpenGL resources and shuts down GLFW.
   */
  ~Renderer();

  Renderer(const Renderer&) = delete;
  Renderer& operator=(const Renderer&) = delete;

  /**
   * @brief Starts the render loop and keeps drawing until the window closes.
   *
   * @details
   * This is the renderer's main lifecycle entry point. It performs setup once, then repeats this
   * loop:
   *
   * - fetch the latest scene snapshot
   * - upload GPU buffers if the scene version changed
   * - draw the current frame
   * - swap buffers
   * - poll window events
   * - sleep until the next frame boundary
   */
  void Run();

private:
  /**
   * @brief Creates the GLFW window and OpenGL context.
   *
   * @details
   * This is where Halcyn requests an OpenGL 3.3 core profile, creates the window, makes the context
   * current, and then asks glad to load function pointers for that context.
   */
  void InitializeWindow();

  /**
   * @brief Configures global OpenGL state and compiles the shader program.
   *
   * @details
   * This method also creates the vertex array object and the buffer objects that later receive
   * scene data. It is the "one-time GPU setup" phase.
   */
  void InitializeOpenGlResources();

  /**
   * @brief Releases GPU objects owned directly by the renderer.
   */
  void DestroyOpenGlResources();

  /**
   * @brief Uploads the latest scene into OpenGL vertex and index buffers.
   *
   * @param renderScene The render-friendly scene produced by `BuildRenderScene`.
   */
  void UploadSceneToGpu(const scene_description::RenderScene& renderScene);

  /**
   * @brief Draws the scene currently stored in GPU buffers.
   *
   * @param renderScene The render-friendly scene currently mirrored in GPU buffers.
   */
  void DrawScene(const scene_description::RenderScene& renderScene) const;

  /**
   * @brief Builds the final model-view-projection matrix for the submitted scene.
   *
   * @param renderScene The render-friendly scene that determines whether 2D or 3D logic is used.
   * @return The final matrix uploaded to the shader uniform `uSceneMatrix`.
   */
  [[nodiscard]] glm::mat4 BuildSceneMatrix(const scene_description::RenderScene& renderScene) const;

  /**
   * @brief Builds an orthographic projection that fits the full 2D scene inside the window.
   *
   * @param renderScene The 2D render scene whose bounds should be framed.
   * @return A matrix built with GLM's orthographic helpers.
   */
  [[nodiscard]] glm::mat4
  Build2DSceneMatrix(const scene_description::RenderScene& renderScene) const;

  /**
   * @brief Builds the perspective view-projection matrix used for 3D scenes.
   *
   * @param renderScene The 3D render scene whose camera settings should be used.
   * @return A matrix built from `glm::perspective`, `glm::lookAt`, and an identity model matrix.
   */
  [[nodiscard]] glm::mat4
  Build3DSceneMatrix(const scene_description::RenderScene& renderScene) const;

  /**
   * @brief Converts the app's primitive enum into the OpenGL draw mode.
   *
   * @param primitiveType The scene-description primitive choice.
   * @return The matching OpenGL enum such as `GL_POINTS`, `GL_LINES`, or `GL_TRIANGLES`.
   */
  [[nodiscard]] GLenum ToOpenGlPrimitive(scene_description::PrimitiveType primitiveType) const;

  /** Stores the chosen window settings. */
  RendererConfig rendererConfiguration_;

  /** Points at the shared scene store. */
  std::shared_ptr<shared_runtime::SceneStore> sceneStore_;

  /** Stores runtime log messages for the browser dashboard and console output. */
  std::shared_ptr<shared_runtime::RuntimeLog> runtimeLog_;

  /** Stores the current GLFW window. */
  GLFWwindow* renderWindow_ = nullptr;

  /** Stores the GPU shader program used for both 2D and 3D scenes. */
  std::unique_ptr<ShaderProgram> sceneShaderProgram_;

  /** Stores the main vertex array object. */
  GLuint vertexArrayObjectHandle_ = 0;

  /** Stores the vertex buffer object. */
  GLuint vertexBufferObjectHandle_ = 0;

  /** Stores the index buffer object. */
  GLuint elementBufferObjectHandle_ = 0;

  /**
   * Tracks the last scene version uploaded to the GPU so unchanged frames avoid
   * unnecessary uploads.
   */
  std::uint64_t uploadedSceneVersion_ = 0;

  /** Stores the last renderable scene uploaded to the GPU. */
  scene_description::RenderScene uploadedRenderScene_{};
};
} // namespace halcyn::opengl_renderer
