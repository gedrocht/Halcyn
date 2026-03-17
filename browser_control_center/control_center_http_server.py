"""HTTP server for the Halcyn browser-based Control Center."""

from __future__ import annotations

import json
import mimetypes
import socket
import sys
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from browser_control_center.control_center_state import ControlCenterState


def strip_powershell_provider_prefix(path_text: str) -> str:
    """Remove a PowerShell provider prefix so downstream tools see a plain filesystem path."""

    # PowerShell can stringify filesystem paths with a provider prefix like
    # "Microsoft.PowerShell.Core\\FileSystem::". Python, CMake, and browsers do not
    # understand that decoration, so we strip it at the edge.
    for prefix in (
        "Microsoft.PowerShell.Core\\FileSystem::",
        "Microsoft.PowerShell.Core/FileSystem::",
    ):
        if path_text.startswith(prefix):
            return path_text[len(prefix) :]

    return path_text


def normalize_project_root(project_root: str | Path) -> Path:
    """Normalize the project root path coming from PowerShell or argparse."""

    normalized_path = Path(strip_powershell_provider_prefix(str(project_root)))
    if normalized_path.is_absolute():
        return normalized_path

    # Relative paths are resolved here once so the rest of the Control Center can
    # assume it always holds one canonical project-root path object.
    return normalized_path.resolve()


class HalcynThreadingHTTPServer(ThreadingHTTPServer):
    """Threaded HTTP server with quieter handling for expected local browser disconnects."""

    daemon_threads = True

    def handle_error(
        self,
        request: socket.socket | tuple[bytes, socket.socket],
        client_address: tuple[str, int],
    ) -> None:
        """Ignore browser disconnect noise while preserving real Control Center errors."""

        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)):
            return

        super().handle_error(request, client_address)


class ControlCenterRequestHandler(BaseHTTPRequestHandler):
    """Serve the browser UI, docs, and JSON control endpoints."""

    state: ControlCenterState
    project_root: Path

    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        """Serialize a Python object to JSON and write it to the response."""

        # Pretty-printed JSON is slightly larger, but these endpoints are used by
        # humans and debugging tools more than high-throughput clients.
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, file_path: Path) -> None:
        """Serve one static file from disk if it exists."""

        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, f"File not found: {file_path.name}")
            return

        content = file_path.read_bytes()
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _begin_event_stream(self) -> None:
        """Start one Server-Sent Events response."""

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

    def _write_sse_event(self, event_name: str, payload: dict) -> None:
        """Write one JSON event into an open Server-Sent Events response."""

        message = (
            f"event: {event_name}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"
        ).encode()
        self.wfile.write(message)
        self.wfile.flush()

    def _write_sse_keepalive(self) -> None:
        """Write one SSE keepalive comment."""

        self.wfile.write(b": keepalive\n\n")
        self.wfile.flush()

    def _stream_scene_studio_session(self) -> None:
        """Keep streaming Scene Studio session snapshots until the browser disconnects."""

        self._begin_event_stream()
        revision = -1
        try:
            while True:
                # The live session object already knows how to block until something
                # changes. The HTTP layer's job is just to translate those updates into SSE.
                payload, changed = self.state.wait_for_scene_studio_session_update(
                    revision,
                    timeout_seconds=15.0,
                )
                if changed:
                    revision = int(payload["session"].get("revision", revision))
                    self._write_sse_event("session", payload)
                else:
                    self._write_sse_keepalive()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def _safe_relative_file(self, base_directory: Path, relative_path: str) -> Path | None:
        """Resolve a relative path beneath a fixed directory without allowing path traversal."""

        candidate = (base_directory / relative_path).resolve()
        try:
            candidate.relative_to(base_directory.resolve())
        except ValueError:
            return None

        return candidate

    def _read_json_body(self) -> dict:
        """Read and decode the current request body as JSON."""

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        return json.loads(raw_body.decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler requires this name.
        """Handle browser and API GET requests."""

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Route order matters. We match the most specific prefixes before falling
        # back to the more general "not found" case.
        if path == "/":
            return self._serve_file(
                self.project_root / "browser_control_center" / "static" / "index.html"
            )

        if path in {"/scene-studio", "/scene-studio/"}:
            return self._serve_file(
                self.project_root / "browser_scene_studio" / "static" / "index.html"
            )

        if path in {"/activity-monitor", "/activity-monitor/"}:
            return self._serve_file(
                self.project_root / "browser_control_center" / "static" / "activity-monitor.html"
            )

        if path.startswith("/static/"):
            relative_path = path.removeprefix("/static/")
            file_path = self._safe_relative_file(
                self.project_root / "browser_control_center" / "static",
                relative_path,
            )
            if file_path is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Invalid static asset path.")
                return
            return self._serve_file(file_path)

        if path.startswith("/scene-studio/static/"):
            relative_path = path.removeprefix("/scene-studio/static/")
            file_path = self._safe_relative_file(
                self.project_root / "browser_scene_studio" / "static",
                relative_path,
            )
            if file_path is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Invalid Scene Studio asset path.")
                return
            return self._serve_file(file_path)

        if path.startswith("/docs/"):
            relative_path = path.removeprefix("/docs/")
            file_path = self._safe_relative_file(self.project_root / "docs" / "site", relative_path)
            if file_path is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Invalid docs path.")
                return
            return self._serve_file(file_path)

        if path.startswith("/generated-code-docs/"):
            relative_path = path.removeprefix("/generated-code-docs/")
            file_path = self._safe_relative_file(
                self.project_root / "docs" / "generated" / "code-reference", relative_path
            )
            if file_path is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Invalid generated docs path.")
                return
            return self._serve_file(file_path)

        if path == "/api/system/summary":
            return self._send_json(self.state.summary())

        if path == "/api/jobs":
            return self._send_json({"status": "ok", "jobs": self.state.recent_jobs()})

        if path == "/api/logs":
            return self._send_json({"status": "ok", "entries": self.state.log_buffer.recent()})

        if path == "/api/activity-log":
            query_values = urllib.parse.parse_qs(parsed.query)
            limit = int(query_values.get("limit", ["300"])[0])
            level_filter = query_values.get("level", [""])[0]
            source_filter = query_values.get("source", [""])[0]
            search_text = query_values.get("search", [""])[0]
            return self._send_json(
                {
                    "status": "ok",
                    "entries": self.state.recent_activity_entries(
                        limit=limit,
                        level_filter=level_filter,
                        source_filter=source_filter,
                        search_text=search_text,
                    ),
                }
            )

        if path == "/api/app/status":
            return self._send_json({"status": "ok", "app": self.state.app_status()})

        if path == "/api/scene-studio/catalog":
            return self._send_json(self.state.scene_studio_catalog())

        if path == "/api/scene-studio/session":
            return self._send_json(self.state.scene_studio_session_status())

        if path == "/api/scene-studio/session/stream":
            return self._stream_scene_studio_session()

        self.send_error(HTTPStatus.NOT_FOUND, f"Unknown route: {path}")

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler requires this name.
        """Handle JSON control actions sent by the browser UI."""

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        try:
            payload = self._read_json_body()
        except json.JSONDecodeError as error:
            return self._send_json(
                {"status": "invalid-json", "message": str(error)},
                HTTPStatus.BAD_REQUEST,
            )

        try:
            # The POST routing is intentionally explicit rather than table-driven so
            # each endpoint's parameter handling stays obvious to beginners reading it.
            if path == "/api/jobs/bootstrap":
                job = self.state.start_bootstrap_job()
                return self._send_json(
                    {"status": "accepted", "job": job.to_dict()},
                    HTTPStatus.ACCEPTED,
                )

            if path == "/api/jobs/build":
                job = self.state.start_build_job(payload.get("configuration", "Debug"))
                return self._send_json(
                    {"status": "accepted", "job": job.to_dict()},
                    HTTPStatus.ACCEPTED,
                )

            if path == "/api/jobs/test":
                job = self.state.start_test_job(payload.get("configuration", "Debug"))
                return self._send_json(
                    {"status": "accepted", "job": job.to_dict()},
                    HTTPStatus.ACCEPTED,
                )

            if path == "/api/jobs/format":
                job = self.state.start_format_job()
                return self._send_json(
                    {"status": "accepted", "job": job.to_dict()},
                    HTTPStatus.ACCEPTED,
                )

            if path == "/api/jobs/generate-code-docs":
                job = self.state.start_code_docs_job()
                return self._send_json(
                    {"status": "accepted", "job": job.to_dict()},
                    HTTPStatus.ACCEPTED,
                )

            if path == "/api/app/start":
                app_record = self.state.start_app(
                    configuration=payload.get("configuration", "Debug"),
                    host=payload.get("host", "127.0.0.1"),
                    port=int(payload.get("port", 8080)),
                    sample=payload.get("sample", "default"),
                    scene_file=payload.get("sceneFile", ""),
                    width=int(payload.get("width", 1280)),
                    height=int(payload.get("height", 720)),
                    frames_per_second=int(payload.get("fps", 60)),
                    title=payload.get("title", "Halcyn"),
                )
                return self._send_json(
                    {"status": "accepted", "app": app_record.to_dict()},
                    HTTPStatus.ACCEPTED,
                )

            if path == "/api/app/stop":
                app_record = self.state.stop_app()
                return self._send_json(
                    {"status": "accepted", "app": app_record.to_dict()},
                    HTTPStatus.ACCEPTED,
                )

            if path == "/api/app/smoke":
                result = self.state.run_smoke_checks(
                    host=payload.get("host", "127.0.0.1"),
                    port=int(payload.get("port", 8080)),
                )
                return self._send_json(result)

            if path == "/api/playground/request":
                result = self.state.run_api_request(
                    host=payload.get("host", "127.0.0.1"),
                    port=int(payload.get("port", 8080)),
                    method=payload.get("method", "GET"),
                    request_path=payload.get("path", "/api/v1/health"),
                    request_body=payload.get("body", ""),
                    content_type=payload.get("contentType", "application/json"),
                )
                return self._send_json(result)

            if path == "/api/scene-studio/preview":
                result = self.state.preview_scene_studio_scene(payload)
                return self._send_json(result)

            if path == "/api/scene-studio/apply":
                result = self.state.apply_scene_studio_scene(payload)
                return self._send_json(
                    result,
                    HTTPStatus.ACCEPTED if result["status"] == "applied" else HTTPStatus.OK,
                )

            if path == "/api/scene-studio/session/configure":
                result = self.state.configure_scene_studio_session(payload)
                return self._send_json(result)

            if path == "/api/scene-studio/session/start":
                result = self.state.start_scene_studio_session(payload)
                return self._send_json(result, HTTPStatus.ACCEPTED)

            if path == "/api/scene-studio/session/stop":
                result = self.state.stop_scene_studio_session()
                return self._send_json(result, HTTPStatus.ACCEPTED)

            return self._send_json(
                {"status": "unknown-route", "message": f"Unknown route: {path}"},
                HTTPStatus.NOT_FOUND,
            )
        except RuntimeError as error:
            # RuntimeError is used for user-facing rejections such as "app already running".
            # Those are real conflicts, but not server bugs, so they return HTTP 409.
            return self._send_json(
                {"status": "rejected", "message": str(error)},
                HTTPStatus.CONFLICT,
            )
        except Exception as error:  # pragma: no cover - this protects the Control Center itself.
            self.state._record_log(
                "ERROR",
                "control-center",
                f"Unhandled Control Center error: {error}",
            )
            return self._send_json(
                {"status": "error", "message": str(error)},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def log_message(self, format: str, *args: object) -> None:
        """Silence the default per-request console logging in favor of the structured log buffer."""

        return


def create_control_center_server(host: str, port: int, project_root: Path) -> ThreadingHTTPServer:
    """Create a configured Control Center HTTP server."""

    state = ControlCenterState(project_root=project_root)

    class BoundHandler(ControlCenterRequestHandler):
        """Bind shared state into the request handler class."""

        pass

    BoundHandler.state = state
    BoundHandler.project_root = project_root

    return HalcynThreadingHTTPServer((host, port), BoundHandler)


def main() -> None:
    """Run the Control Center HTTP server as a standalone process."""

    import argparse

    parser = argparse.ArgumentParser(description="Run the Halcyn browser-based Control Center.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=9001, help="Port to bind.")
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root containing the Halcyn project.",
    )
    args = parser.parse_args()

    project_root = normalize_project_root(args.project_root)
    server = create_control_center_server(args.host, args.port, project_root)
    print(f"Halcyn Control Center listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
