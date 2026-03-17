"""Shared local-bridge helpers for desktop tools that exchange JSON documents.

The desktop tools in this repository intentionally avoid talking to each other
through direct widget access.  Instead, they use a tiny local HTTP contract:

1. one desktop tool generates a JSON document
2. it `POST`s that document to a loopback endpoint
3. another desktop tool receives the JSON and decides how to use it

That separation makes the system easier to reason about, easier to test, and
much friendlier for beginners because each application keeps one clear job.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


def _current_utc_timestamp_iso8601() -> str:
    """Return a readable UTC timestamp for diagnostics and status labels."""

    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class LocalJsonBridgeResponse:
    """Describe one attempt to deliver JSON to a local bridge endpoint."""

    ok: bool
    status: int
    reason: str
    body: str


@dataclass
class LocalJsonBridgeStatus:
    """Describe the current state of one local JSON bridge server."""

    host: str
    port: int
    listening: bool = False
    last_received_at_utc: str = ""
    last_source_label: str = ""
    last_payload_size_bytes: int = 0
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready snapshot of the bridge state."""

        return asdict(self)


class LocalJsonBridgeClient:
    """POST JSON text to a loopback bridge endpoint.

    The desktop tools talk only over loopback HTTP, so plain `http://` is the
    correct choice here.  The traffic never leaves the local machine, and that
    keeps the beginner workflow certificate-free.
    """

    def deliver_json_text(
        self,
        *,
        host: str,
        port: int,
        path: str,
        source_label: str,
        json_text: str,
    ) -> LocalJsonBridgeResponse:
        """POST one JSON document to the configured local bridge."""

        request_body = json.dumps(
            {
                "sourceLabel": source_label,
                "jsonText": json_text,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        request = urllib.request.Request(
            url=f"http://{host}:{port}{normalize_local_json_bridge_path(path)}",
            data=request_body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(request, timeout=5.0) as response:
                response_body = response.read().decode("utf-8")
                return LocalJsonBridgeResponse(
                    ok=200 <= int(response.status) < 300,
                    status=int(response.status),
                    reason=str(response.reason),
                    body=response_body,
                )
        except urllib.error.HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            return LocalJsonBridgeResponse(
                ok=False,
                status=int(error.code),
                reason=str(error.reason),
                body=error_body,
            )
        except Exception as error:  # pragma: no cover - platform/network detail varies.
            return LocalJsonBridgeResponse(
                ok=False,
                status=0,
                reason=type(error).__name__,
                body=str(error),
            )


class LocalJsonBridgeServer:
    """Listen for external JSON updates from another desktop tool."""

    _supported_paths = frozenset({"/external-data", "/external-data/"})

    def __init__(
        self,
        *,
        host: str,
        port: int,
        on_json_received: Callable[[str, str], None],
    ) -> None:
        self._host = host
        self._port = port
        self._on_json_received = on_json_received
        self._status_lock = threading.Lock()
        self._status = LocalJsonBridgeStatus(host=host, port=port)
        self._http_server: ThreadingHTTPServer | None = None
        self._serve_thread: threading.Thread | None = None

    def start(self) -> dict[str, Any]:
        """Start the background listener if it is not already running."""

        if self._http_server is not None:
            return self.status()

        bridge_server = self

        class LocalJsonBridgeRequestHandler(BaseHTTPRequestHandler):
            """Handle the small local bridge protocol for desktop helper apps."""

            def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API contract.
                if self.path not in bridge_server._supported_paths:
                    self._write_json_response(404, {"status": "not-found"})
                    return

                content_length = int(self.headers.get("Content-Length", "0") or 0)
                request_body_bytes = self.rfile.read(content_length)
                try:
                    request_body = json.loads(request_body_bytes.decode("utf-8"))
                except Exception as error:
                    bridge_server._set_error(
                        f"Could not parse external JSON payload: {error}"
                    )
                    self._write_json_response(
                        400,
                        {
                            "status": "invalid-request",
                            "message": "Body must be valid UTF-8 JSON.",
                        },
                    )
                    return

                json_text = request_body.get("jsonText")
                source_label = str(request_body.get("sourceLabel", "external-source")).strip()
                if not isinstance(json_text, str) or not json_text.strip():
                    self._write_json_response(
                        400,
                        {
                            "status": "invalid-request",
                            "message": "The request body must include a non-empty jsonText string.",
                        },
                    )
                    return

                try:
                    bridge_server._accept_json(
                        json_text=json_text,
                        source_label=source_label or "external-source",
                        payload_size_bytes=len(request_body_bytes),
                    )
                except Exception as error:
                    bridge_server._set_error(str(error))
                    self._write_json_response(
                        500,
                        {"status": "rejected", "message": str(error)},
                    )
                    return

                self._write_json_response(
                    202,
                    {
                        "status": "accepted",
                        "sourceLabel": source_label or "external-source",
                    },
                )

            def log_message(self, format: str, *args: object) -> None:
                # The receiving desktop apps already surface structured bridge
                # status, so raw request logs only add noise.
                del format, args

            def _write_json_response(
                self,
                status_code: int,
                body: dict[str, Any],
            ) -> None:
                encoded_body = json.dumps(body, separators=(",", ":")).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded_body)))
                self.end_headers()
                self.wfile.write(encoded_body)

        self._http_server = ThreadingHTTPServer(
            (self._host, self._port),
            LocalJsonBridgeRequestHandler,
        )
        self._serve_thread = threading.Thread(
            target=self._http_server.serve_forever,
            name="local-json-bridge-server",
            daemon=True,
        )
        self._serve_thread.start()

        with self._status_lock:
            self._status.host = self._host
            self._status.port = int(self._http_server.server_port)
            self._status.listening = True
            self._status.last_error = ""

        return self.status()

    def stop(self) -> dict[str, Any]:
        """Stop the listener and return the final status snapshot."""

        if self._http_server is not None:
            self._http_server.shutdown()
            self._http_server.server_close()
            self._http_server = None

        if self._serve_thread is not None:
            self._serve_thread.join(timeout=2.0)
            self._serve_thread = None

        with self._status_lock:
            self._status.listening = False

        return self.status()

    def status(self) -> dict[str, Any]:
        """Return a copy of the current bridge state."""

        with self._status_lock:
            return self._status.to_dict()

    def _accept_json(
        self,
        *,
        json_text: str,
        source_label: str,
        payload_size_bytes: int,
    ) -> None:
        """Record one received payload and forward it to the owning controller."""

        self._on_json_received(json_text, source_label)
        with self._status_lock:
            self._status.last_received_at_utc = _current_utc_timestamp_iso8601()
            self._status.last_source_label = source_label
            self._status.last_payload_size_bytes = payload_size_bytes
            self._status.last_error = ""

    def _set_error(self, error_message: str) -> None:
        """Remember the most recent bridge failure for UI diagnostics."""

        with self._status_lock:
            self._status.last_error = error_message


def normalize_local_json_bridge_path(path: str) -> str:
    """Return one safe bridge path with exactly one leading slash."""

    normalized_path = str(path).strip()
    if not normalized_path:
        return "/external-data"
    if not normalized_path.startswith("/"):
        normalized_path = f"/{normalized_path}"
    return normalized_path
