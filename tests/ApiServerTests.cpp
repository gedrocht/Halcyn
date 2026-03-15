#include "http_api/ApiServer.hpp"
#include "scene_description/SceneFactory.hpp"
#include "scene_description/SceneJsonCodec.hpp"
#include "shared_runtime/RuntimeLog.hpp"
#include "shared_runtime/SceneStore.hpp"

#include <catch2/catch_test_macros.hpp>
#include <httplib.h>

namespace halcyn::tests {
TEST_CASE("ApiServer starts on an ephemeral port and exposes health information", "[api]") {
  auto sceneStore = std::make_shared<shared_runtime::SceneStore>(
      scene_description::CreateSample2DSceneDocument());
  auto sceneJsonCodec = std::make_shared<scene_description::SceneJsonCodec>();
  auto runtimeLog = std::make_shared<shared_runtime::RuntimeLog>(100);

  http_api::ApiServerConfig serverConfiguration;
  serverConfiguration.host = "127.0.0.1";
  serverConfiguration.port = 0;

  http_api::ApiServer apiServer(serverConfiguration, sceneStore, sceneJsonCodec, runtimeLog);
  apiServer.Start();

  REQUIRE(apiServer.IsRunning());
  REQUIRE(apiServer.GetBoundPort() > 0);

  httplib::Client httpClient("127.0.0.1", apiServer.GetBoundPort());
  httpClient.set_connection_timeout(5, 0);
  httpClient.set_read_timeout(5, 0);

  const auto healthResponse = httpClient.Get("/api/v1/health");
  REQUIRE(healthResponse);
  CHECK(healthResponse->status == 200);
  CHECK(healthResponse->body.find("\"status\": \"ok\"") != std::string::npos);

  apiServer.Stop();
  CHECK_FALSE(apiServer.IsRunning());
}

TEST_CASE("ApiServer validates scenes without activating them", "[api]") {
  auto sceneStore = std::make_shared<shared_runtime::SceneStore>(
      scene_description::CreateSample2DSceneDocument());
  auto sceneJsonCodec = std::make_shared<scene_description::SceneJsonCodec>();
  auto runtimeLog = std::make_shared<shared_runtime::RuntimeLog>(100);

  http_api::ApiServerConfig serverConfiguration;
  serverConfiguration.host = "127.0.0.1";
  serverConfiguration.port = 0;

  http_api::ApiServer apiServer(serverConfiguration, sceneStore, sceneJsonCodec, runtimeLog);
  apiServer.Start();

  httplib::Client httpClient("127.0.0.1", apiServer.GetBoundPort());
  httpClient.set_connection_timeout(5, 0);
  httpClient.set_read_timeout(5, 0);

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
      httpClient.Post("/api/v1/scene/validate", validScene, "application/json");
  REQUIRE(validateResponse);
  CHECK(validateResponse->status == 200);
  CHECK(validateResponse->body.find("\"status\": \"valid\"") != std::string::npos);

  const auto snapshotAfterValidation = sceneStore->GetCurrent();
  CHECK(snapshotAfterValidation->version == 1);

  apiServer.Stop();
}

TEST_CASE("ApiServer rejects invalid media types and invalid scenes", "[api]") {
  auto sceneStore = std::make_shared<shared_runtime::SceneStore>(
      scene_description::CreateSample2DSceneDocument());
  auto sceneJsonCodec = std::make_shared<scene_description::SceneJsonCodec>();
  auto runtimeLog = std::make_shared<shared_runtime::RuntimeLog>(100);

  http_api::ApiServerConfig serverConfiguration;
  serverConfiguration.host = "127.0.0.1";
  serverConfiguration.port = 0;

  http_api::ApiServer apiServer(serverConfiguration, sceneStore, sceneJsonCodec, runtimeLog);
  apiServer.Start();

  httplib::Client httpClient("127.0.0.1", apiServer.GetBoundPort());
  httpClient.set_connection_timeout(5, 0);
  httpClient.set_read_timeout(5, 0);

  const auto badMediaTypeResponse = httpClient.Post("/api/v1/scene", "{}", "text/plain");
  REQUIRE(badMediaTypeResponse);
  CHECK(badMediaTypeResponse->status == 415);

  const auto invalidSceneResponse =
      httpClient.Post("/api/v1/scene", R"({"sceneType":"3d","vertices":[]})", "application/json");
  REQUIRE(invalidSceneResponse);
  CHECK(invalidSceneResponse->status == 400);
  CHECK(invalidSceneResponse->body.find("\"invalid-request\"") != std::string::npos);

  apiServer.Stop();
}
} // namespace halcyn::tests
