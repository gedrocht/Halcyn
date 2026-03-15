#include "api/ApiServer.hpp"

#include "domain/SceneValidation.hpp"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cstdlib>
#include <stdexcept>
#include <utility>

namespace halcyn::api {
namespace {
using json = nlohmann::json;
} // namespace

ApiServer::ApiServer(ApiServerConfig serverConfiguration,
                     std::shared_ptr<core::SceneStore> sceneStore,
                     std::shared_ptr<domain::SceneJsonCodec> sceneJsonCodec,
                     std::shared_ptr<core::RuntimeLog> runtimeLog)
    : serverConfiguration_(std::move(serverConfiguration)), sceneStore_(std::move(sceneStore)),
      sceneJsonCodec_(std::move(sceneJsonCodec)), runtimeLog_(std::move(runtimeLog)) {
  ConfigureRoutes();
}

ApiServer::~ApiServer() {
  Stop();
}

void ApiServer::Start() {
  if (serverIsRunning_) {
    return;
  }

  // The underlying HTTP library can reject large request bodies before our own
  // route handlers see them. We set that limit up front so oversized scene uploads
  // fail early and predictably.
  httpServer_.set_payload_max_length(serverConfiguration_.maxPayloadBytes);

  const int listeningPort =
      (serverConfiguration_.port == 0)
          ? httpServer_.bind_to_any_port(serverConfiguration_.host)
          : (httpServer_.bind_to_port(serverConfiguration_.host, serverConfiguration_.port)
                 ? serverConfiguration_.port
                 : -1);

  if (listeningPort <= 0) {
    throw std::runtime_error("The HTTP API could not bind to " + serverConfiguration_.host + ":" +
                             std::to_string(serverConfiguration_.port) + '.');
  }

  listeningPort_ = listeningPort;

  // listen_after_bind blocks until the server stops, so we run it on a dedicated
  // thread and keep the main application thread free for the renderer.
  serverThread_ = std::thread([this]() {
    const bool listenSucceeded = httpServer_.listen_after_bind();
    if (!listenSucceeded && runtimeLog_ != nullptr) {
      runtimeLog_->Write(core::LogLevel::Error, "api",
                         "The HTTP server stopped because listen_after_bind returned false.");
    }

    serverIsRunning_ = false;
    listeningPort_ = 0;
  });

  // Binding a socket and actually entering the listening loop are two different
  // phases. wait_until_ready gives us a clean hand-off point so callers do not
  // announce "server is ready" too early.
  httpServer_.wait_until_ready();
  if (!httpServer_.is_running()) {
    if (serverThread_.joinable()) {
      serverThread_.join();
    }

    throw std::runtime_error("The HTTP API failed to enter the listening state after binding.");
  }

  serverIsRunning_ = true;

  if (runtimeLog_ != nullptr) {
    runtimeLog_->Write(core::LogLevel::Info, "api",
                       "HTTP API listening on http://" + serverConfiguration_.host + ":" +
                           std::to_string(listeningPort));
  }
}

void ApiServer::Stop() {
  if (httpServer_.is_running()) {
    httpServer_.stop();
  }

  if (!serverThread_.joinable()) {
    serverIsRunning_ = false;
    listeningPort_ = 0;
    return;
  }

  serverThread_.join();

  serverIsRunning_ = false;
  listeningPort_ = 0;

  if (runtimeLog_ != nullptr) {
    runtimeLog_->Write(core::LogLevel::Info, "api", "HTTP API stopped.");
  }
}

bool ApiServer::IsRunning() const {
  return serverIsRunning_;
}

int ApiServer::GetBoundPort() const {
  return listeningPort_;
}

void ApiServer::ConfigureRoutes() {
  // The logger hook gives us a low-cost audit trail for every HTTP request. That
  // helps both manual debugging and the browser control plane's live logs view.
  httpServer_.set_logger(
      [this](const httplib::Request& request, const httplib::Response& response) {
        if (runtimeLog_ == nullptr) {
          return;
        }

        runtimeLog_->Write(core::LogLevel::Info, "http",
                           request.method + " " + request.path + " -> " +
                               std::to_string(response.status));
      });

  httpServer_.Get("/api/v1/health", [this](const httplib::Request&, httplib::Response& response) {
    // The health endpoint is intentionally small and cheap: it exposes the minimum
    // information an external tool needs to confirm that the app is alive and which
    // scene version is currently active.
    const auto currentSceneSnapshot = sceneStore_->GetCurrent();
    json responseBody{{"status", "ok"},
                      {"host", serverConfiguration_.host},
                      {"configuredPort", serverConfiguration_.port},
                      {"listeningPort", GetBoundPort()},
                      {"activeSceneVersion", currentSceneSnapshot->version},
                      {"activeSceneType", domain::ToString(currentSceneSnapshot->document.kind)},
                      {"activeSceneSource", currentSceneSnapshot->sourceLabel}};
    response.set_content(responseBody.dump(2), "application/json");
  });

  httpServer_.Get("/api/v1/scene", [this](const httplib::Request&, httplib::Response& response) {
    // Returning the exact active scene makes the API self-describing. A client can
    // ask "what are you drawing right now?" without keeping its own copy in sync.
    const auto currentSceneSnapshot = sceneStore_->GetCurrent();
    response.set_content(sceneJsonCodec_->Serialize(*currentSceneSnapshot), "application/json");
  });

  httpServer_.Get("/api/v1/runtime/limits",
                  [this](const httplib::Request&, httplib::Response& response) {
                    response.set_content(BuildRuntimeLimitsResponse(), "application/json");
                  });

  httpServer_.Get("/api/v1/runtime/logs",
                  [this](const httplib::Request& request, httplib::Response& response) {
                    // Logs can grow quickly, so the endpoint uses a capped "recent items"
                    // model instead of attempting to expose an unbounded history.
                    std::size_t limit = 200;
                    if (request.has_param("limit")) {
                      limit = static_cast<std::size_t>(
                          std::max(1, std::atoi(request.get_param_value("limit").c_str())));
                    }

                    response.set_content(BuildRuntimeLogResponse(limit), "application/json");
                  });

  httpServer_.Get(
      "/api/v1/examples/2d", [this](const httplib::Request&, httplib::Response& response) {
        const auto exampleSceneDocument = domain::CreateSample2DSceneDocument();
        auto exampleSnapshot = domain::SceneSnapshot{};
        exampleSnapshot.version = 0;
        exampleSnapshot.document = exampleSceneDocument;
        exampleSnapshot.sourceLabel = "built-in-example";
        response.set_content(sceneJsonCodec_->Serialize(exampleSnapshot), "application/json");
      });

  httpServer_.Get(
      "/api/v1/examples/3d", [this](const httplib::Request&, httplib::Response& response) {
        const auto exampleSceneDocument = domain::CreateSample3DSceneDocument();
        auto exampleSnapshot = domain::SceneSnapshot{};
        exampleSnapshot.version = 0;
        exampleSnapshot.document = exampleSceneDocument;
        exampleSnapshot.sourceLabel = "built-in-example";
        response.set_content(sceneJsonCodec_->Serialize(exampleSnapshot), "application/json");
      });

  httpServer_.Post("/api/v1/scene/validate", [this](const httplib::Request& request,
                                                    httplib::Response& response) {
    // Validation is intentionally separated from activation so tools can preview
    // "would this scene be accepted?" without changing what the renderer shows.
    const auto sceneParseResult = sceneJsonCodec_->Parse(request.body);
    if (!sceneParseResult.succeeded || !sceneParseResult.scene.has_value()) {
      response.status = 400;
      response.set_content(BuildValidationErrorResponse(sceneParseResult.errors),
                           "application/json");
      return;
    }

    const auto& sceneDocument = *sceneParseResult.scene;
    // Building the render scene here proves not only that the JSON is well-formed,
    // but also that it can be transformed into the normalized renderer payload.
    const domain::RenderScene renderScene = domain::BuildRenderScene(sceneDocument);
    json responseBody{{"status", "valid"},
                      {"sceneType", domain::ToString(sceneDocument.kind)},
                      {"vertexCount", renderScene.vertices.size()},
                      {"indexCount", renderScene.indices.size()},
                      {"message", "The payload is valid and can be activated."}};
    response.set_content(responseBody.dump(2), "application/json");
  });

  httpServer_.Post("/api/v1/scene", [this](const httplib::Request& request,
                                           httplib::Response& response) {
    // We accept requests that omit Content-Type for convenience during manual
    // testing, but if a caller does send the header it must agree with JSON.
    if (request.has_header("Content-Type") &&
        request.get_header_value("Content-Type").find("application/json") == std::string::npos) {
      response.status = 415;
      response.set_content(
          R"({"status":"unsupported-media-type","message":"Use Content-Type: application/json."})",
          "application/json");
      return;
    }

    const auto sceneParseResult = sceneJsonCodec_->Parse(request.body);
    if (!sceneParseResult.succeeded || !sceneParseResult.scene.has_value()) {
      if (runtimeLog_ != nullptr) {
        runtimeLog_->Write(core::LogLevel::Warning, "api",
                           "Rejected an invalid scene submission with " +
                               std::to_string(sceneParseResult.errors.size()) +
                               " validation errors.");
      }

      response.status = 400;
      response.set_content(BuildValidationErrorResponse(sceneParseResult.errors),
                           "application/json");
      return;
    }

    // Replacing the scene in the store is the moment a submitted scene becomes the
    // "next truth" for the renderer. The renderer notices the new version number on
    // the following frame and uploads it to the GPU.
    const auto updatedSceneSnapshot = sceneStore_->Replace(*sceneParseResult.scene, "http-post");
    if (runtimeLog_ != nullptr) {
      runtimeLog_->Write(core::LogLevel::Info, "api",
                         "Accepted scene version " + std::to_string(updatedSceneSnapshot->version) +
                             " (" + domain::ToString(updatedSceneSnapshot->document.kind) + ").");
    }

    json responseBody{{"status", "accepted"},
                      {"version", updatedSceneSnapshot->version},
                      {"sceneType", domain::ToString(updatedSceneSnapshot->document.kind)},
                      {"message", "The renderer will use this scene on the next frame."}};
    response.status = 202;
    response.set_content(responseBody.dump(2), "application/json");
  });
}

std::string
ApiServer::BuildValidationErrorResponse(const std::vector<domain::ValidationError>& errors) const {
  json body;
  body["status"] = "invalid-request";
  body["message"] = "The submitted JSON could not be turned into a valid scene.";
  body["errors"] = json::array();

  // We preserve the original machine-readable path for each error so tools and
  // humans alike can see exactly which part of the submitted JSON failed.
  for (const domain::ValidationError& error : errors) {
    body["errors"].push_back(json{{"path", error.path}, {"message", error.message}});
  }

  return body.dump(2);
}

std::string ApiServer::BuildRuntimeLogResponse(std::size_t limit) const {
  json body;
  body["status"] = "ok";
  body["entries"] = json::array();

  // The API keeps working even if no runtime log was wired in. In that case we
  // return an empty successful payload instead of turning "missing logs" into an error.
  if (runtimeLog_ == nullptr) {
    return body.dump(2);
  }

  const auto entries = runtimeLog_->GetRecent(limit);
  for (const auto& entry : entries) {
    body["entries"].push_back(json{
        {"sequence", entry.sequence},
        {"level", core::ToString(entry.level)},
        {"component", entry.component},
        {"message", entry.message},
        {"timestampUtcSeconds",
         std::chrono::duration_cast<std::chrono::seconds>(entry.timestampUtc.time_since_epoch())
             .count()}});
  }

  return body.dump(2);
}

std::string ApiServer::BuildRuntimeLimitsResponse() const {
  json body{{"status", "ok"},
            {"maxPayloadBytes", serverConfiguration_.maxPayloadBytes},
            {"maxVertices", domain::SceneLimits::kMaxVertexCount},
            {"maxIndices", domain::SceneLimits::kMaxIndexCount}};
  return body.dump(2);
}
} // namespace halcyn::api
