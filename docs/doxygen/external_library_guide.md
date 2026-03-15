# External Library Guide

Halcyn is intentionally small, but it still relies on several external libraries. This page explains
which ones are used, what job each library performs, and where to find the official documentation
for the exact features the code uses.

## GLFW

Halcyn uses **GLFW** to create the desktop window, create an OpenGL context, and drive the basic
event loop.

Where it appears:

- `halcyn::opengl_renderer::Renderer::InitializeWindow`
- `halcyn::opengl_renderer::Renderer::Run`
- `halcyn::opengl_renderer::Renderer::DrawScene`

Official documentation:

- [GLFW documentation home](https://www.glfw.org/documentation.html)
- [Window guide](https://www.glfw.org/docs/latest/window_guide.html)
- [Context guide](https://www.glfw.org/docs/latest/context_guide.html)
- [glfwInit / library initialization reference](https://www.glfw.org/docs/latest/group__init.html)
- [Window reference, including `glfwCreateWindow`](https://www.glfw.org/docs/latest/group__window.html)
- [Context reference, including `glfwMakeContextCurrent` and `glfwSwapInterval`](https://www.glfw.org/docs/latest/group__context.html)

Why Halcyn uses it:

- it gives a straightforward cross-platform window and context API
- it is a common beginner-friendly choice for OpenGL learning and small tools
- it pairs cleanly with glad for OpenGL function loading

## glad

Halcyn uses **glad** to load OpenGL function pointers after a context exists.

Where it appears:

- `halcyn::opengl_renderer::Renderer::InitializeWindow`

Official documentation:

- [glad repository](https://github.com/Dav1dde/glad)
- [glad C quickstart wiki](https://github.com/Dav1dde/glad/wiki/C)

The important idea:

- OpenGL functions beyond the platform's base headers are not automatically usable just because a
  program includes `<glad/gl.h>`
- a context must exist first
- then `gladLoadGL(...)` resolves the function addresses for that context

## OpenGL

Halcyn uses core OpenGL 3.3 calls for buffer creation, shader compilation, attribute setup, and
drawing.

Where it appears:

- `halcyn::opengl_renderer::Renderer`
- `halcyn::opengl_renderer::ShaderProgram`

Official documentation:

- [OpenGL Wiki home](https://wikis.khronos.org/opengl/Main_Page)
- [Vertex Specification](https://wikis.khronos.org/opengl/Vertex_Specification)
- [Buffer Object](https://wikis.khronos.org/opengl/Buffer_Object)
- [Shader Compilation](https://wikis.khronos.org/opengl/Shader_Compilation)
- [`glUseProgram`](https://wikis.khronos.org/opengl/GLAPI/glUseProgram)
- [`glUniform` family, including matrix and float uniforms](https://wikis.khronos.org/opengl/GLAPI/glUniform)
- [Primitive rendering overview](https://wikis.khronos.org/opengl/primitive)

Useful mapping from Halcyn concepts to OpenGL concepts:

- `RenderVertex` -> vertex attribute layout
- `vertexArrayObjectHandle_` -> remembers attribute binding state
- `vertexBufferObjectHandle_` -> stores vertex data on the GPU
- `elementBufferObjectHandle_` -> stores index data on the GPU
- `ShaderProgram` -> linked vertex/fragment shader program

## GLM

Halcyn uses **GLM** for matrix math such as orthographic projection, perspective projection, camera
view matrices, and conversion of matrix objects into raw pointers for OpenGL uniforms.

Where it appears:

- `halcyn::opengl_renderer::Renderer::Build2DSceneMatrix`
- `halcyn::opengl_renderer::Renderer::Build3DSceneMatrix`
- `halcyn::opengl_renderer::ShaderProgram::SetMatrix4`

Official documentation:

- [GLM API index](https://glm.g-truc.net/0.9.9/api/index.html)
- [`glm::ortho` and `glm::perspective` in GLM_EXT_matrix_clip_space](https://glm.g-truc.net/0.9.9/api/a00665.html)
- [`glm::lookAt` in GLM_EXT_matrix_transform](https://glm.g-truc.net/0.9.9/api/a00668.html)
- [`glm::value_ptr` in GLM_GTC_type_ptr](https://glm.g-truc.net/0.9.9/api/a00305.html)

Why Halcyn uses it:

- writing camera and projection math by hand is error-prone and distracting
- GLM mirrors familiar GLSL/OpenGL-style naming
- it keeps the renderer focused on intent rather than matrix bookkeeping

## nlohmann/json

Halcyn uses **nlohmann/json** to parse incoming JSON text and serialize scene snapshots and API
responses.

Where it appears:

- `halcyn::scene_description::SceneJsonCodec`
- `halcyn::http_api::ApiServer`

Official documentation:

- [Library overview](https://nlohmann.github.io/json/api/basic_json/)
- [`json::parse`](https://nlohmann.github.io/json/api/basic_json/parse/)
- [`json::dump`](https://nlohmann.github.io/json/api/basic_json/dump/)
- [`json::get`](https://nlohmann.github.io/json/api/basic_json/get/)
- [`json::object`](https://nlohmann.github.io/json/api/basic_json/object/)

Why Halcyn uses it:

- it keeps JSON parsing readable in ordinary C++ code
- it supports both structured parsing and convenient response-building
- it is well documented and widely used

## cpp-httplib

Halcyn uses **cpp-httplib** as its embedded HTTP server.

Where it appears:

- `halcyn::http_api::ApiServer`

Official documentation:

- [cpp-httplib repository and README](https://github.com/yhirose/cpp-httplib)

The code in Halcyn relies especially on:

- route registration with `Get` and `Post`
- socket binding with `bind_to_port` and `bind_to_any_port`
- `listen_after_bind`
- `wait_until_ready`
- `set_payload_max_length`
- `set_logger`

Why Halcyn uses it:

- it is a single-header HTTP library, which keeps build complexity low
- it is easy to read in a beginner-oriented project
- it is a good fit for a small local control API

## Catch2

Halcyn uses **Catch2** for the native C++ test suite.

Where it appears:

- `tests/`

Official documentation:

- [Catch2 documentation](https://catch2-temp.readthedocs.io/en/latest/)

Why this matters even in the Doxygen docs:

- many class and function examples are mirrored by tests
- if you want to see "how the code is really expected to behave," the tests are often the most
  precise executable examples in the repository
