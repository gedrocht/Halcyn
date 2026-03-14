#include "api/ApiServer.hpp"

#include "domain/SceneValidation.hpp"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cstdlib>
#include <stdexcept>
#include <utility>

namespace halcyn::api
{
namespace
{
using json = nlohmann::json;
}  // namespace

ApiServer::ApiServer(
  ApiServerConfig config,
  std::shared_ptr<core::SceneStore> sceneStore,
  std::shared_ptr<domain::SceneJsonCodec> codec,
  std::shared_ptr<core::RuntimeLog> runtimeLog)
  : config_(std::move(config)),
    sceneStore_(std::move(sceneStore)),
    codec_(std::move(codec)),
    runtimeLog_(std::move(runtimeLog))
{
  ConfigureRoutes();
}

ApiServer::~ApiServer()
{
  Stop();
}

void ApiServer::Start()
{
  if (isRunning_)
  {
    return;
  }

  server_.set_payload_max_length(config_.maxPayloadBytes);

  const int boundPort =
    (config_.port == 0) ? server_.bind_to_any_port(config_.host) : (server_.bind_to_port(config_.host, config_.port) ? config_.port : -1);

  if (boundPort <= 0)
  {
    throw std::runtime_error(
      "The HTTP API could not bind to " + config_.host + ":" + std::to_string(config_.port) + '.');
  }

  boundPort_ = boundPort;

  serverThread_ = std::thread(
    [this]()
    {
      const bool listenSucceeded = server_.listen_after_bind();
      if (!listenSucceeded && runtimeLog_ != nullptr)
      {
        runtimeLog_->Write(
          core::LogLevel::Error,
          "api",
          "The HTTP server stopped because listen_after_bind returned false.");
      }

      isRunning_ = false;
      boundPort_ = 0;
    });

  server_.wait_until_ready();
  if (!server_.is_running())
  {
    if (serverThread_.joinable())
    {
      serverThread_.join();
    }

    throw std::runtime_error("The HTTP API failed to enter the listening state after binding.");
  }

  isRunning_ = true;

  if (runtimeLog_ != nullptr)
  {
    runtimeLog_->Write(
      core::LogLevel::Info,
      "api",
      "HTTP API listening on http://" + config_.host + ":" + std::to_string(boundPort));
  }
}

void ApiServer::Stop()
{
  if (server_.is_running())
  {
    server_.stop();
  }

  if (!serverThread_.joinable())
  {
    isRunning_ = false;
    boundPort_ = 0;
    return;
  }

  serverThread_.join();

  isRunning_ = false;
  boundPort_ = 0;

  if (runtimeLog_ != nullptr)
  {
    runtimeLog_->Write(core::LogLevel::Info, "api", "HTTP API stopped.");
  }
}

bool ApiServer::IsRunning() const
{
  return isRunning_;
}

int ApiServer::GetBoundPort() const
{
  return boundPort_;
}

void ApiServer::ConfigureRoutes()
{
  server_.set_logger(
    [this](const httplib::Request& request, const httplib::Response& response)
    {
      if (runtimeLog_ == nullptr)
      {
        return;
      }

      runtimeLog_->Write(
        core::LogLevel::Info,
        "http",
        request.method + " " + request.path + " -> " + std::to_string(response.status));
    });

  server_.Get(
    "/api/v1/health",
    [this](const httplib::Request&, httplib::Response& response)
    {
      const auto snapshot = sceneStore_->GetCurrent();
      json body {
        {"status", "ok"},
        {"host", config_.host},
        {"configuredPort", config_.port},
        {"listeningPort", GetBoundPort()},
        {"activeSceneVersion", snapshot->version},
        {"activeSceneType", domain::ToString(snapshot->document.kind)},
        {"activeSceneSource", snapshot->sourceLabel}
      };
      response.set_content(body.dump(2), "application/json");
    });

  server_.Get(
    "/api/v1/scene",
    [this](const httplib::Request&, httplib::Response& response)
    {
      const auto snapshot = sceneStore_->GetCurrent();
      response.set_content(codec_->Serialize(*snapshot), "application/json");
    });

  server_.Get(
    "/api/v1/runtime/limits",
    [this](const httplib::Request&, httplib::Response& response)
    {
      response.set_content(BuildRuntimeLimitsResponse(), "application/json");
    });

  server_.Get(
    "/api/v1/runtime/logs",
    [this](const httplib::Request& request, httplib::Response& response)
    {
      std::size_t limit = 200;
      if (request.has_param("limit"))
      {
        limit = static_cast<std::size_t>(std::max(1, std::atoi(request.get_param_value("limit").c_str())));
      }

      response.set_content(BuildRuntimeLogResponse(limit), "application/json");
    });

  server_.Get(
    "/api/v1/examples/2d",
    [this](const httplib::Request&, httplib::Response& response)
    {
      const auto scene = domain::CreateSample2DSceneDocument();
      auto snapshot = domain::SceneSnapshot {};
      snapshot.version = 0;
      snapshot.document = scene;
      snapshot.sourceLabel = "built-in-example";
      response.set_content(codec_->Serialize(snapshot), "application/json");
    });

  server_.Get(
    "/api/v1/examples/3d",
    [this](const httplib::Request&, httplib::Response& response)
    {
      const auto scene = domain::CreateSample3DSceneDocument();
      auto snapshot = domain::SceneSnapshot {};
      snapshot.version = 0;
      snapshot.document = scene;
      snapshot.sourceLabel = "built-in-example";
      response.set_content(codec_->Serialize(snapshot), "application/json");
    });

  server_.Post(
    "/api/v1/scene/validate",
    [this](const httplib::Request& request, httplib::Response& response)
    {
      const auto parseResult = codec_->Parse(request.body);
      if (!parseResult.succeeded || !parseResult.scene.has_value())
      {
        response.status = 400;
        response.set_content(BuildValidationErrorResponse(parseResult.errors), "application/json");
        return;
      }

      const auto& scene = *parseResult.scene;
      const domain::RenderScene renderScene = domain::BuildRenderScene(scene);
      json body {
        {"status", "valid"},
        {"sceneType", domain::ToString(scene.kind)},
        {"vertexCount", renderScene.vertices.size()},
        {"indexCount", renderScene.indices.size()},
        {"message", "The payload is valid and can be activated."}
      };
      response.set_content(body.dump(2), "application/json");
    });

  server_.Post(
    "/api/v1/scene",
    [this](const httplib::Request& request, httplib::Response& response)
    {
      if (request.has_header("Content-Type") &&
          request.get_header_value("Content-Type").find("application/json") == std::string::npos)
      {
        response.status = 415;
        response.set_content(
          R"({"status":"unsupported-media-type","message":"Use Content-Type: application/json."})",
          "application/json");
        return;
      }

      const auto parseResult = codec_->Parse(request.body);
      if (!parseResult.succeeded || !parseResult.scene.has_value())
      {
        if (runtimeLog_ != nullptr)
        {
          runtimeLog_->Write(
            core::LogLevel::Warning,
            "api",
            "Rejected an invalid scene submission with " + std::to_string(parseResult.errors.size()) +
              " validation errors.");
        }

        response.status = 400;
        response.set_content(BuildValidationErrorResponse(parseResult.errors), "application/json");
        return;
      }

      const auto snapshot = sceneStore_->Replace(*parseResult.scene, "http-post");
      if (runtimeLog_ != nullptr)
      {
        runtimeLog_->Write(
          core::LogLevel::Info,
          "api",
          "Accepted scene version " + std::to_string(snapshot->version) + " (" +
            domain::ToString(snapshot->document.kind) + ").");
      }

      json body {
        {"status", "accepted"},
        {"version", snapshot->version},
        {"sceneType", domain::ToString(snapshot->document.kind)},
        {"message", "The renderer will use this scene on the next frame."}
      };
      response.status = 202;
      response.set_content(body.dump(2), "application/json");
    });
}

std::string ApiServer::BuildValidationErrorResponse(const std::vector<domain::ValidationError>& errors) const
{
  json body;
  body["status"] = "invalid-request";
  body["message"] = "The submitted JSON could not be turned into a valid scene.";
  body["errors"] = json::array();

  for (const domain::ValidationError& error : errors)
  {
    body["errors"].push_back(json {
      {"path", error.path},
      {"message", error.message}
    });
  }

  return body.dump(2);
}

std::string ApiServer::BuildRuntimeLogResponse(std::size_t limit) const
{
  json body;
  body["status"] = "ok";
  body["entries"] = json::array();

  if (runtimeLog_ == nullptr)
  {
    return body.dump(2);
  }

  const auto entries = runtimeLog_->GetRecent(limit);
  for (const auto& entry : entries)
  {
    body["entries"].push_back(json {
      {"sequence", entry.sequence},
      {"level", core::ToString(entry.level)},
      {"component", entry.component},
      {"message", entry.message},
      {"timestampUtcSeconds", std::chrono::duration_cast<std::chrono::seconds>(entry.timestampUtc.time_since_epoch())
                                 .count()}
    });
  }

  return body.dump(2);
}

std::string ApiServer::BuildRuntimeLimitsResponse() const
{
  json body {
    {"status", "ok"},
    {"maxPayloadBytes", config_.maxPayloadBytes},
    {"maxVertices", domain::SceneLimits::kMaxVertexCount},
    {"maxIndices", domain::SceneLimits::kMaxIndexCount}
  };
  return body.dump(2);
}
}  // namespace halcyn::api
