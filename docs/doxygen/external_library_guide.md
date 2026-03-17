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

## Tkinter

Halcyn uses **Tkinter** for both native desktop operator tools:

- the desktop render control panel
- the desktop spectrograph control panel
- the shared data-source panel

Where it appears:

- `desktop_render_control_panel.desktop_control_panel_window`
- `desktop_spectrograph_control_panel.spectrograph_control_panel_window`
- `desktop_multi_renderer_data_source_panel.multi_renderer_data_source_window`

Official documentation:

- [Tkinter overview](https://docs.python.org/3/library/tkinter.html)
- [Themed widgets (`tkinter.ttk`)](https://docs.python.org/3/library/tkinter.ttk.html)
- [ScrolledText widget](https://docs.python.org/3/library/tkinter.scrolledtext.html)
- [Color chooser dialog](https://docs.python.org/3/library/tkinter.colorchooser.html)
- [File dialogs (`tkinter.filedialog`)](https://docs.python.org/3/library/dialog.html#tkinter.filedialog)

Why Halcyn uses it:

- it is included with standard Python on Windows
- it keeps the desktop operator tool lightweight and easy to run locally
- it is beginner-friendly enough to study without pulling in a large GUI framework

## urllib.request

Halcyn uses **urllib.request** for the desktop operator tools' small HTTP
clients.

Where it appears:

- `desktop_render_control_panel.render_api_client`
- `desktop_shared_control_support.render_api_client`
- `desktop_spectrograph_audio_source_panel.spectrograph_external_bridge_client`

Official documentation:

- [urllib.request](https://docs.python.org/3/library/urllib.request.html)
- [urllib.error](https://docs.python.org/3/library/urllib.error.html)

Why Halcyn uses it:

- the desktop panel only needs a handful of simple HTTP calls
- the standard library keeps that code dependency-light
- it is easier for a beginner to study when the client layer is built on familiar Python docs

## http.server

Halcyn uses the standard-library **http.server** module for the local
spectrograph external-data bridge that helper desktop tools can post into.

Where it appears:

- `desktop_spectrograph_control_panel.external_data_bridge_server`

Official documentation:

- [http.server](https://docs.python.org/3/library/http.server.html)
- [BaseHTTPRequestHandler](https://docs.python.org/3/library/http.server.html#http.server.BaseHTTPRequestHandler)
- [ThreadingHTTPServer](https://docs.python.org/3/library/http.server.html#http.server.ThreadingHTTPServer)

Why Halcyn uses it:

- the bridge only needs a tiny local-only POST endpoint
- the standard library keeps the helper-app boundary easy to study
- it lets the spectrograph control panel receive external JSON without pulling
  in another server dependency

## Python json and statistics

Halcyn uses the standard-library **json** module, **random** module, and a
handful of simple statistics concepts in the desktop spectrograph control panel
and the shared data-source panel.

Where it appears:

- `desktop_spectrograph_control_panel.spectrograph_scene_builder`
- `desktop_spectrograph_control_panel.spectrograph_control_panel_controller`
- `desktop_multi_renderer_data_source_panel.multi_renderer_data_source_builder`
- `desktop_multi_renderer_data_source_panel.multi_renderer_data_source_controller`

Official documentation:

- [json](https://docs.python.org/3/library/json.html)
- [random](https://docs.python.org/3/library/random.html)
- [statistics](https://docs.python.org/3/library/statistics.html)
- [str.encode](https://docs.python.org/3/library/stdtypes.html#str.encode)

Why Halcyn uses them:

- the spectrograph tool needs to parse generic JSON without taking on another
  dependency
- the range model is easier for beginners to study when it is written in
  ordinary Python terms such as mean and standard deviation
- converting strings to UTF-8 byte values makes text payloads usable without
  inventing a custom binary protocol
- the shared data-source panel uses `random.Random` for deterministic synthetic
  input streams so tests and tutorials can reproduce the same behavior

## ctypes and Windows waveIn

Halcyn uses **ctypes** plus the Windows **waveIn** APIs as a fallback way to enumerate desktop
audio input devices when the optional `sounddevice` package is not installed yet.

Where it appears:

- `desktop_render_control_panel.audio_input_service.WindowsWaveInListingBackend`

Official documentation:

- [ctypes](https://docs.python.org/3/library/ctypes.html)
- [`waveInGetNumDevs`](https://learn.microsoft.com/windows/win32/api/mmeapi/nf-mmeapi-waveingetnumdevs)
- [`waveInGetDevCapsW`](https://learn.microsoft.com/windows/win32/api/mmeapi/nf-mmeapi-waveingetdevcapsw)

Why Halcyn uses it:

- it lets the desktop panel show Windows input devices even before live capture is configured
- it gives the operator better feedback than an empty device list
- it keeps the fallback dependency-light because it uses platform APIs that already exist on Windows

## sounddevice

Halcyn uses **sounddevice** as an optional bridge to real local microphone and line-input devices
for the desktop render control panel.

Where it appears:

- `desktop_render_control_panel.audio_input_service`
- `desktop_spectrograph_audio_source_panel.spectrograph_audio_source_controller`

Official documentation:

- [sounddevice documentation home](https://python-sounddevice.readthedocs.io/)
- [Checking hardware / querying devices](https://python-sounddevice.readthedocs.io/en/latest/api/checking-hardware.html)
- [InputStream reference](https://python-sounddevice.readthedocs.io/en/latest/api/streams.html)

Why Halcyn uses it:

- it exposes local audio devices through PortAudio without requiring a browser permission flow
- it keeps the desktop tool useful even when a user wants the operator surface beside the renderer
- it is optional, so the rest of the desktop control panel still works if audio capture is unavailable

## soundcard

Halcyn uses **soundcard** as an optional Windows-friendly way to capture desktop output loopback
audio for the desktop render control panel.

Where it appears:

- `desktop_render_control_panel.audio_input_service.SoundCardLoopbackOutputCaptureBackend`
- `desktop_spectrograph_audio_source_panel.spectrograph_audio_source_controller`

Official documentation:

- [soundcard documentation home](https://soundcard.readthedocs.io/)
- [all_speakers](https://soundcard.readthedocs.io/en/latest/#soundcard.all_speakers)
- [all_microphones, including loopback capture](https://soundcard.readthedocs.io/en/latest/#soundcard.all_microphones)
- [get_microphone](https://soundcard.readthedocs.io/en/latest/#soundcard.get_microphone)
- [Recorder interface](https://soundcard.readthedocs.io/en/latest/#soundcard._Recorder.record)

Why Halcyn uses it:

- the `sounddevice` / PortAudio build on this machine does not expose reliable WASAPI loopback
  capture for output devices
- `soundcard` gives the desktop panel a straightforward, speaker-oriented loopback path
- it lets the operator choose "what the computer is currently playing" as a render-driving signal
