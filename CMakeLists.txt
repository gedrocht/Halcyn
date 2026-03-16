cmake_minimum_required(VERSION 3.24)

project(
  Halcyn
  VERSION 1.0.0
  DESCRIPTION "GPU-rendered JSON-driven 2D and 3D graphics viewer with an HTTP API"
  LANGUAGES C CXX
)

include(CTest)
include(FetchContent)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

set_property(GLOBAL PROPERTY USE_FOLDERS ON)

option(HALCYN_ENABLE_TESTS "Build the Halcyn unit test target." ON)
option(HALCYN_WARNINGS_AS_ERRORS "Treat compiler warnings as build failures for Halcyn targets." ON)

# Prevent dependency projects from building their own examples or tests. This keeps
# configure and build output focused on the app itself.
set(GLFW_BUILD_DOCS OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(CATCH_INSTALL_DOCS OFF CACHE BOOL "" FORCE)
set(CATCH_INSTALL_EXTRAS OFF CACHE BOOL "" FORCE)
set(HTTPLIB_INSTALL OFF CACHE BOOL "" FORCE)
set(HTTPLIB_TEST OFF CACHE BOOL "" FORCE)

FetchContent_Declare(
  glfw
  GIT_REPOSITORY https://github.com/glfw/glfw.git
  GIT_TAG a74efa0d5628b74adc0426af4c5710e287fa7c2c # 3.4
)

FetchContent_Declare(
  glm
  GIT_REPOSITORY https://github.com/g-truc/glm.git
  GIT_TAG 0af55ccecd98d4e5a8d1fad7de25ba429d60e863 # 1.0.1
)

FetchContent_Declare(
  nlohmann_json
  GIT_REPOSITORY https://github.com/nlohmann/json.git
  GIT_TAG 9cca280a4d0ccf0c08f47a99aa71d1b0e52f8d03 # v3.11.3
)

FetchContent_Declare(
  cpp_httplib
  GIT_REPOSITORY https://github.com/yhirose/cpp-httplib.git
  GIT_TAG af56b7ec0ba9d18b788ed064f76d936eb52c5db5 # v0.16.3
)

FetchContent_Declare(
  catch2
  GIT_REPOSITORY https://github.com/catchorg/Catch2.git
  GIT_TAG 1ea016810728365d3af3648aeefa683a10ff830e # v3.6.0
)

FetchContent_Declare(
  glad
  GIT_REPOSITORY https://github.com/Dav1dde/glad.git
  GIT_TAG 73db193f853e2ee079bf3ca8a64aa2eaf6459043 # v2.0.8
  SOURCE_SUBDIR cmake
)

FetchContent_MakeAvailable(glfw glm nlohmann_json cpp_httplib catch2 glad)

find_package(OpenGL REQUIRED)

glad_add_library(halcyn_glad REPRODUCIBLE API gl:core=3.3)

function(halcyn_configure_target target_name)
  target_include_directories(
    "${target_name}"
    PUBLIC
      "${PROJECT_SOURCE_DIR}/src"
  )

  target_compile_definitions(
    "${target_name}"
    PRIVATE
      NOMINMAX
      WIN32_LEAN_AND_MEAN
  )

  if(MSVC)
    target_compile_options("${target_name}" PRIVATE /W4 /WX /permissive- /EHsc /Zc:__cplusplus)
  else()
    target_compile_options("${target_name}" PRIVATE -Wall -Wextra -Wpedantic)
    if(HALCYN_WARNINGS_AS_ERRORS)
      target_compile_options("${target_name}" PRIVATE -Werror)
    endif()
  endif()

  if(HALCYN_WARNINGS_AS_ERRORS)
    set_target_properties("${target_name}" PROPERTIES COMPILE_WARNING_AS_ERROR ON)
  endif()
endfunction()

set(HALCYN_SCENE_DESCRIPTION_HEADERS
  src/scene_description/SceneLimits.hpp
  src/scene_description/SceneFactory.hpp
  src/scene_description/SceneJsonCodec.hpp
  src/scene_description/SceneTypes.hpp
  src/scene_description/SceneValidation.hpp
)

set(HALCYN_SCENE_DESCRIPTION_SOURCES
  src/scene_description/SceneFactory.cpp
  src/scene_description/SceneJsonCodec.cpp
  src/scene_description/SceneValidation.cpp
)

add_library(
  halcyn_scene_description STATIC
  ${HALCYN_SCENE_DESCRIPTION_HEADERS}
  ${HALCYN_SCENE_DESCRIPTION_SOURCES}
)
add_library(Halcyn::SceneDescription ALIAS halcyn_scene_description)
halcyn_configure_target(halcyn_scene_description)
target_link_libraries(
  halcyn_scene_description
  PUBLIC
    nlohmann_json::nlohmann_json
)

set(HALCYN_SHARED_RUNTIME_HEADERS
  src/shared_runtime/RuntimeLog.hpp
  src/shared_runtime/SceneStore.hpp
)

set(HALCYN_SHARED_RUNTIME_SOURCES
  src/shared_runtime/RuntimeLog.cpp
  src/shared_runtime/SceneStore.cpp
)

add_library(
  halcyn_shared_runtime STATIC
  ${HALCYN_SHARED_RUNTIME_HEADERS}
  ${HALCYN_SHARED_RUNTIME_SOURCES}
)
add_library(Halcyn::SharedRuntime ALIAS halcyn_shared_runtime)
halcyn_configure_target(halcyn_shared_runtime)
target_link_libraries(
  halcyn_shared_runtime
  PUBLIC
    Halcyn::SceneDescription
)

set(HALCYN_HTTP_API_HEADERS
  src/http_api/ApiServer.hpp
)

set(HALCYN_HTTP_API_SOURCES
  src/http_api/ApiServer.cpp
)

add_library(halcyn_http_api STATIC ${HALCYN_HTTP_API_HEADERS} ${HALCYN_HTTP_API_SOURCES})
add_library(Halcyn::HttpApi ALIAS halcyn_http_api)
halcyn_configure_target(halcyn_http_api)
target_link_libraries(
  halcyn_http_api
  PUBLIC
    Halcyn::SharedRuntime
    httplib::httplib
)

set(HALCYN_OPENGL_RENDERER_HEADERS
  src/opengl_renderer/Renderer.hpp
  src/opengl_renderer/ShaderProgram.hpp
)

set(HALCYN_OPENGL_RENDERER_SOURCES
  src/opengl_renderer/Renderer.cpp
  src/opengl_renderer/ShaderProgram.cpp
)

add_library(
  halcyn_opengl_renderer STATIC
  ${HALCYN_OPENGL_RENDERER_HEADERS}
  ${HALCYN_OPENGL_RENDERER_SOURCES}
)
add_library(Halcyn::OpenGLRenderer ALIAS halcyn_opengl_renderer)
halcyn_configure_target(halcyn_opengl_renderer)
target_link_libraries(
  halcyn_opengl_renderer
  PUBLIC
    Halcyn::SharedRuntime
    glm::glm
    glfw
    halcyn_glad
  PRIVATE
    OpenGL::GL
)
target_compile_definitions(
  halcyn_opengl_renderer
  PUBLIC
    GLFW_INCLUDE_NONE
)

set(HALCYN_DESKTOP_APP_HEADERS
  src/desktop_app/Application.hpp
)

set(HALCYN_DESKTOP_APP_SOURCES
  src/desktop_app/Application.cpp
)

add_library(
  halcyn_desktop_app_support STATIC
  ${HALCYN_DESKTOP_APP_HEADERS}
  ${HALCYN_DESKTOP_APP_SOURCES}
)
add_library(Halcyn::DesktopAppSupport ALIAS halcyn_desktop_app_support)
halcyn_configure_target(halcyn_desktop_app_support)
target_link_libraries(
  halcyn_desktop_app_support
  PUBLIC
    Halcyn::HttpApi
    Halcyn::OpenGLRenderer
)

add_executable(halcyn_desktop_app src/main.cpp)
halcyn_configure_target(halcyn_desktop_app)
target_link_libraries(halcyn_desktop_app PRIVATE Halcyn::DesktopAppSupport)
set_target_properties(halcyn_desktop_app PROPERTIES OUTPUT_NAME halcyn_app)

add_executable(halcyn_spectrograph_app src/spectrograph_main.cpp)
halcyn_configure_target(halcyn_spectrograph_app)
target_link_libraries(halcyn_spectrograph_app PRIVATE Halcyn::DesktopAppSupport)
set_target_properties(halcyn_spectrograph_app PROPERTIES OUTPUT_NAME halcyn_spectrograph_app)

if(HALCYN_ENABLE_TESTS)
  add_executable(
    halcyn_tests
    tests/ApiServerTests.cpp
    tests/SceneJsonCodecTests.cpp
    tests/SceneValidationTests.cpp
    tests/SceneStoreTests.cpp
  )

  halcyn_configure_target(halcyn_tests)
  target_link_libraries(
    halcyn_tests
    PRIVATE
      Catch2::Catch2WithMain
      Halcyn::HttpApi
      Halcyn::SharedRuntime
      Halcyn::SceneDescription
  )

  include(Catch)
  catch_discover_tests(halcyn_tests)
endif()
