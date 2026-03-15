#include "http_api/ApiServer.hpp"
#include "scene_description/SceneFactory.hpp"
#include "scene_description/SceneJsonCodec.hpp"
#include "shared_runtime/RuntimeLog.hpp"
#include "shared_runtime/SceneStore.hpp"

#include <catch2/catch_test_macros.hpp>
#include <httplib.h>

namespace halcyn::tests {
TEST_CASE("ApiServer starts on an ephemeral port and exposes health information", "[api]") {
  auto store = std::make_shared<shared_runtime::SceneStore>(
      scene_description::CreateSample2DSceneDocument());
  auto codec = std::make_shared<scene_description::SceneJsonCodec>();
  auto runtimeLog = std::make_shared<shared_runtime::RuntimeLog>(100);

  http_api::ApiServerConfig config;
  config.host = "127.0.0.1";
  config.port = 0;

  http_api::ApiServer server(config, store, codec, runtimeLog);
  server.Start();

  REQUIRE(server.IsRunning());
  REQUIRE(server.GetBoundPort() > 0);

  httplib::Client client("127.0.0.1", server.GetBoundPort());
  client.set_connection_timeout(5, 0);
  client.set_read_timeout(5, 0);

  const auto response = client.Get("/api/v1/health");
  REQUIRE(response);
  CHECK(response->status == 200);
  CHECK(response->body.find("\"status\": \"ok\"") != std::string::npos);

  server.Stop();
  CHECK_FALSE(server.IsRunning());
}

TEST_CASE("ApiServer validates scenes without activating them", "[api]") {
  auto store = std::make_shared<shared_runtime::SceneStore>(
      scene_description::CreateSample2DSceneDocument());
  auto codec = std::make_shared<scene_description::SceneJsonCodec>();
  auto runtimeLog = std::make_shared<shared_runtime::RuntimeLog>(100);

  http_api::ApiServerConfig config;
  config.host = "127.0.0.1";
  config.port = 0;

  http_api::ApiServer server(config, store, codec, runtimeLog);
  server.Start();

  httplib::Client client("127.0.0.1", server.GetBoundPort());
  client.set_connection_timeout(5, 0);
  client.set_read_timeout(5, 0);

  const std::string validScene = R"({
    "sceneType": "2d",
    "primitive": "triangles",
    "vertices": [
      { "x": -1.0, "y": -1.0, "r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0 },
      { "x": 0.0, "y": 1.0, "r": 0.0, "g": 1.0, "b": 0.0, "a": 1.0 },
      { "x": 1.0, "y": -1.0, "r": 0.0, "g": 0.0, "b": 1.0, "a": 1.0 }
    ]
  })";

  const auto validateResponse =
      client.Post("/api/v1/scene/validate", validScene, "application/json");
  REQUIRE(validateResponse);
  CHECK(validateResponse->status == 200);
  CHECK(validateResponse->body.find("\"status\": \"valid\"") != std::string::npos);

  const auto snapshotAfterValidation = store->GetCurrent();
  CHECK(snapshotAfterValidation->version == 1);

  server.Stop();
}

TEST_CASE("ApiServer rejects invalid media types and invalid scenes", "[api]") {
  auto store = std::make_shared<shared_runtime::SceneStore>(
      scene_description::CreateSample2DSceneDocument());
  auto codec = std::make_shared<scene_description::SceneJsonCodec>();
  auto runtimeLog = std::make_shared<shared_runtime::RuntimeLog>(100);

  http_api::ApiServerConfig config;
  config.host = "127.0.0.1";
  config.port = 0;

  http_api::ApiServer server(config, store, codec, runtimeLog);
  server.Start();

  httplib::Client client("127.0.0.1", server.GetBoundPort());
  client.set_connection_timeout(5, 0);
  client.set_read_timeout(5, 0);

  const auto badMediaTypeResponse = client.Post("/api/v1/scene", "{}", "text/plain");
  REQUIRE(badMediaTypeResponse);
  CHECK(badMediaTypeResponse->status == 415);

  const auto invalidSceneResponse =
      client.Post("/api/v1/scene", R"({"sceneType":"3d","vertices":[]})", "application/json");
  REQUIRE(invalidSceneResponse);
  CHECK(invalidSceneResponse->status == 400);
  CHECK(invalidSceneResponse->body.find("\"invalid-request\"") != std::string::npos);

  server.Stop();
}
} // namespace halcyn::tests
