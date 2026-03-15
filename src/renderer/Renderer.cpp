#include "renderer/Renderer.hpp"

#include <glad/gl.h>
#include <glm/ext/matrix_clip_space.hpp>
#include <glm/ext/matrix_transform.hpp>
#include <glm/mat4x4.hpp>

#include <algorithm>
#include <chrono>
#include <cstddef>
#include <limits>
#include <stdexcept>
#include <thread>
#include <utility>

namespace halcyn::renderer {
namespace {
constexpr const char* kVertexShaderSource = R"(
#version 330 core
layout (location = 0) in vec3 aPosition;
layout (location = 1) in vec4 aColor;

uniform mat4 uSceneMatrix;
uniform float uPointSize;

out vec4 vColor;

void main()
{
  gl_Position = uSceneMatrix * vec4(aPosition, 1.0);
  gl_PointSize = uPointSize;
  vColor = aColor;
}
)";

constexpr const char* kFragmentShaderSource = R"(
#version 330 core
in vec4 vColor;

out vec4 fragColor;

void main()
{
  fragColor = vColor;
}
)";
} // namespace

Renderer::Renderer(RendererConfig rendererConfiguration,
                   std::shared_ptr<core::SceneStore> sceneStore,
                   std::shared_ptr<core::RuntimeLog> runtimeLog)
    : rendererConfiguration_(std::move(rendererConfiguration)), sceneStore_(std::move(sceneStore)),
      runtimeLog_(std::move(runtimeLog)) {}

Renderer::~Renderer() {
  DestroyOpenGlResources();
}

void Renderer::Run() {
  InitializeWindow();
  InitializeOpenGlResources();

  if (runtimeLog_ != nullptr) {
    runtimeLog_->Write(core::LogLevel::Info, "renderer", "Render loop started.");
  }

  const auto frameDuration =
      std::chrono::duration_cast<std::chrono::steady_clock::duration>(std::chrono::duration<double>(
          1.0 / static_cast<double>(rendererConfiguration_.targetFramesPerSecond)));

  while (!glfwWindowShouldClose(renderWindow_)) {
    const auto frameStart = std::chrono::steady_clock::now();

    const auto currentSceneSnapshot = sceneStore_->GetCurrent();
    if (currentSceneSnapshot->version != uploadedSceneVersion_) {
      // The scene store is the authoritative shared state. The renderer only copies
      // from it when the version changes so we avoid rebuilding GPU buffers every frame.
      uploadedRenderScene_ = domain::BuildRenderScene(currentSceneSnapshot->document);
      UploadSceneToGpu(uploadedRenderScene_);
      uploadedSceneVersion_ = currentSceneSnapshot->version;

      if (runtimeLog_ != nullptr) {
        runtimeLog_->Write(core::LogLevel::Info, "renderer",
                           "Uploaded scene version " +
                               std::to_string(currentSceneSnapshot->version) + " to GPU buffers.");
      }
    }

    DrawScene(uploadedRenderScene_);
    glfwSwapBuffers(renderWindow_);
    glfwPollEvents();

    // Halcyn uses a simple sleep-until cadence rather than a more complex fixed/variable
    // timestep system. That is enough here because rendering is the main loop activity.
    const auto nextFrameStart = frameStart + frameDuration;
    if (std::chrono::steady_clock::now() < nextFrameStart) {
      std::this_thread::sleep_until(nextFrameStart);
    }
  }

  if (runtimeLog_ != nullptr) {
    runtimeLog_->Write(core::LogLevel::Info, "renderer", "Render loop stopped.");
  }
}

void Renderer::InitializeWindow() {
  if (glfwInit() != GLFW_TRUE) {
    throw std::runtime_error("GLFW failed to initialize. The renderer cannot create a GPU window.");
  }

  // Requesting a known OpenGL version up front makes later shader and buffer code
  // much more predictable because we know which core features are available.
  glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
  glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
  glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
  glfwWindowHint(GLFW_DEPTH_BITS, 24);

  renderWindow_ =
      glfwCreateWindow(rendererConfiguration_.windowWidth, rendererConfiguration_.windowHeight,
                       rendererConfiguration_.windowTitle.c_str(), nullptr, nullptr);
  if (renderWindow_ == nullptr) {
    glfwTerminate();
    throw std::runtime_error(
        "GLFW could not create the window. Check that the machine supports OpenGL 3.3.");
  }

  glfwMakeContextCurrent(renderWindow_);
  glfwSwapInterval(1);

  if (gladLoadGL(reinterpret_cast<GLADloadfunc>(glfwGetProcAddress)) == 0) {
    glfwDestroyWindow(renderWindow_);
    renderWindow_ = nullptr;
    glfwTerminate();
    throw std::runtime_error("glad failed to load OpenGL function pointers.");
  }
}

void Renderer::InitializeOpenGlResources() {
  // Alpha blending and program-controlled point sizes are global state toggles
  // the simple Halcyn shaders rely on every frame.
  glEnable(GL_BLEND);
  glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
  glEnable(GL_PROGRAM_POINT_SIZE);

  sceneShaderProgram_ = std::make_unique<ShaderProgram>(kVertexShaderSource, kFragmentShaderSource);

  glGenVertexArrays(1, &vertexArrayObjectHandle_);
  glGenBuffers(1, &vertexBufferObjectHandle_);
  glGenBuffers(1, &elementBufferObjectHandle_);

  glBindVertexArray(vertexArrayObjectHandle_);
  glBindBuffer(GL_ARRAY_BUFFER, vertexBufferObjectHandle_);
  glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, elementBufferObjectHandle_);

  glEnableVertexAttribArray(0);
  glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(domain::RenderVertex),
                        reinterpret_cast<void*>(offsetof(domain::RenderVertex, x)));

  glEnableVertexAttribArray(1);
  glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, sizeof(domain::RenderVertex),
                        reinterpret_cast<void*>(offsetof(domain::RenderVertex, r)));

  glBindVertexArray(0);
}

void Renderer::DestroyOpenGlResources() {
  if (elementBufferObjectHandle_ != 0) {
    glDeleteBuffers(1, &elementBufferObjectHandle_);
    elementBufferObjectHandle_ = 0;
  }

  if (vertexBufferObjectHandle_ != 0) {
    glDeleteBuffers(1, &vertexBufferObjectHandle_);
    vertexBufferObjectHandle_ = 0;
  }

  if (vertexArrayObjectHandle_ != 0) {
    glDeleteVertexArrays(1, &vertexArrayObjectHandle_);
    vertexArrayObjectHandle_ = 0;
  }

  sceneShaderProgram_.reset();

  if (renderWindow_ != nullptr) {
    glfwDestroyWindow(renderWindow_);
    renderWindow_ = nullptr;
    glfwTerminate();
  }
}

void Renderer::UploadSceneToGpu(const domain::RenderScene& renderScene) {
  // Uploading replaces the entire vertex/index buffers with the latest snapshot.
  // That is simpler than partial updates and is completely fine for the scene sizes
  // Halcyn currently targets.
  glBindVertexArray(vertexArrayObjectHandle_);

  glBindBuffer(GL_ARRAY_BUFFER, vertexBufferObjectHandle_);
  glBufferData(GL_ARRAY_BUFFER,
               static_cast<GLsizeiptr>(renderScene.vertices.size() * sizeof(domain::RenderVertex)),
               renderScene.vertices.data(), GL_DYNAMIC_DRAW);

  glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, elementBufferObjectHandle_);
  glBufferData(GL_ELEMENT_ARRAY_BUFFER,
               static_cast<GLsizeiptr>(renderScene.indices.size() * sizeof(std::uint32_t)),
               renderScene.indices.data(), GL_DYNAMIC_DRAW);

  glBindVertexArray(0);
}

void Renderer::DrawScene(const domain::RenderScene& renderScene) const {
  int framebufferWidth = 0;
  int framebufferHeight = 0;
  glfwGetFramebufferSize(renderWindow_, &framebufferWidth, &framebufferHeight);
  glViewport(0, 0, framebufferWidth, framebufferHeight);

  glClearColor(renderScene.clearColor.r, renderScene.clearColor.g, renderScene.clearColor.b,
               renderScene.clearColor.a);
  glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

  // Depth testing only matters for 3D scenes. Disabling it for 2D keeps draw order
  // straightforward and avoids unnecessary state influencing flat scenes.
  if (renderScene.kind == domain::SceneKind::ThreeDimensional) {
    glEnable(GL_DEPTH_TEST);
  } else {
    glDisable(GL_DEPTH_TEST);
  }

  sceneShaderProgram_->Use();
  sceneShaderProgram_->SetMatrix4("uSceneMatrix", BuildSceneMatrix(renderScene));
  sceneShaderProgram_->SetFloat("uPointSize", renderScene.pointSize);

  glLineWidth(renderScene.lineWidth);
  glBindVertexArray(vertexArrayObjectHandle_);

  if (!renderScene.indices.empty()) {
    glDrawElements(ToOpenGlPrimitive(renderScene.primitiveType),
                   static_cast<GLsizei>(renderScene.indices.size()), GL_UNSIGNED_INT, nullptr);
  } else {
    glDrawArrays(ToOpenGlPrimitive(renderScene.primitiveType), 0,
                 static_cast<GLsizei>(renderScene.vertices.size()));
  }

  glBindVertexArray(0);
}

glm::mat4 Renderer::BuildSceneMatrix(const domain::RenderScene& renderScene) const {
  if (renderScene.kind == domain::SceneKind::TwoDimensional) {
    return Build2DSceneMatrix(renderScene);
  }

  return Build3DSceneMatrix(renderScene);
}

glm::mat4 Renderer::Build2DSceneMatrix(const domain::RenderScene& renderScene) const {
  if (renderScene.vertices.empty()) {
    return glm::mat4(1.0F);
  }

  // A 2D scene can contain arbitrary coordinates, so we first compute the scene's
  // bounding box and then build an orthographic camera that frames that box nicely.
  float minX = std::numeric_limits<float>::max();
  float maxX = std::numeric_limits<float>::lowest();
  float minY = std::numeric_limits<float>::max();
  float maxY = std::numeric_limits<float>::lowest();

  for (const domain::RenderVertex& vertex : renderScene.vertices) {
    minX = std::min(minX, vertex.x);
    maxX = std::max(maxX, vertex.x);
    minY = std::min(minY, vertex.y);
    maxY = std::max(maxY, vertex.y);
  }

  float width = maxX - minX;
  float height = maxY - minY;

  if (width < 0.001F) {
    // Perfectly vertical or single-point scenes would otherwise produce a near-zero
    // width and an unusable projection volume, so we pad them into something drawable.
    width = 2.0F;
    minX -= 1.0F;
    maxX += 1.0F;
  }

  if (height < 0.001F) {
    height = 2.0F;
    minY -= 1.0F;
    maxY += 1.0F;
  }

  float paddingX = std::max(width * 0.10F, 0.25F);
  float paddingY = std::max(height * 0.10F, 0.25F);

  minX -= paddingX;
  maxX += paddingX;
  minY -= paddingY;
  maxY += paddingY;

  int framebufferWidth = 1;
  int framebufferHeight = 1;
  glfwGetFramebufferSize(renderWindow_, &framebufferWidth, &framebufferHeight);

  const float windowAspect = static_cast<float>(std::max(framebufferWidth, 1)) /
                             static_cast<float>(std::max(framebufferHeight, 1));
  const float sceneWidth = maxX - minX;
  const float sceneHeight = maxY - minY;
  const float sceneAspect = sceneWidth / sceneHeight;

  // After adding content padding, we expand whichever axis is too small so the
  // final orthographic box matches the actual window aspect ratio without stretching.
  if (sceneAspect < windowAspect) {
    const float targetWidth = sceneHeight * windowAspect;
    const float expandBy = (targetWidth - sceneWidth) * 0.5F;
    minX -= expandBy;
    maxX += expandBy;
  } else {
    const float targetHeight = sceneWidth / windowAspect;
    const float expandBy = (targetHeight - sceneHeight) * 0.5F;
    minY -= expandBy;
    maxY += expandBy;
  }

  return glm::ortho(minX, maxX, minY, maxY, -10.0F, 10.0F);
}

glm::mat4 Renderer::Build3DSceneMatrix(const domain::RenderScene& renderScene) const {
  int framebufferWidth = 1;
  int framebufferHeight = 1;
  glfwGetFramebufferSize(renderWindow_, &framebufferWidth, &framebufferHeight);
  const float aspect = static_cast<float>(std::max(framebufferWidth, 1)) /
                       static_cast<float>(std::max(framebufferHeight, 1));

  const glm::vec3 cameraPosition(renderScene.camera.position.x, renderScene.camera.position.y,
                                 renderScene.camera.position.z);
  const glm::vec3 cameraTarget(renderScene.camera.target.x, renderScene.camera.target.y,
                               renderScene.camera.target.z);
  const glm::vec3 cameraUp(renderScene.camera.up.x, renderScene.camera.up.y,
                           renderScene.camera.up.z);

  // The final scene matrix is the standard 3D pipeline:
  // model -> view -> projection. Our model matrix is identity for now because
  // scenes already arrive in world space.
  const glm::mat4 projection =
      glm::perspective(glm::radians(renderScene.camera.fovYDegrees), aspect,
                       renderScene.camera.nearPlane, renderScene.camera.farPlane);
  const glm::mat4 view = glm::lookAt(cameraPosition, cameraTarget, cameraUp);
  const glm::mat4 model(1.0F);
  return projection * view * model;
}

GLenum Renderer::ToOpenGlPrimitive(domain::PrimitiveType primitiveType) const {
  switch (primitiveType) {
  case domain::PrimitiveType::Points:
    return GL_POINTS;
  case domain::PrimitiveType::Lines:
    return GL_LINES;
  case domain::PrimitiveType::Triangles:
    return GL_TRIANGLES;
  }

  return GL_TRIANGLES;
}
} // namespace halcyn::renderer
