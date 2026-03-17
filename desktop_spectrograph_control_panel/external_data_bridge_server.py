"""Local HTTP bridge that lets helper tools feed live data into the spectrograph panel.

The spectrograph control panel already knows how to turn generic JSON text into
bar-grid scenes. This bridge gives other local tools one tiny, well-documented
way to supply that JSON text without directly reaching into Tkinter widgets or
controller internals.

The supported contract is intentionally small:

- send an HTTP `POST` request to `/external-data`
- include JSON with a `jsonText` string
- optionally include a human-readable `sourceLabel`

That keeps the app-to-app story beginner-friendly: one tool generates source
data, the control panel receives it, and the existing spectrograph builder does
the rest.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _current_utc_timestamp_iso8601() -> str:
    """Return a readable UTC timestamp for diagnostics and status labels."""

    return datetime.now(timezone.utc).isoformat()


@dataclass
class SpectrographExternalDataBridgeStatus:
    """Describe the current state of the local bridge server."""

    host: str
    port: int
    listening: bool = False
    last_received_at_utc: str = ""
    last_source_label: str = ""
    last_payload_size_bytes: int = 0
    last_error: str = ""

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-ready bridge status snapshot."""

        return asdict(self)


class SpectrographExternalDataBridgeServer:
    """Listen for external JSON updates destined for the spectrograph panel."""

    _supported_paths = frozenset({"/external-data", "/external-data/"})

    def __init__(
        self,
        host: str,
        port: int,
        on_external_json_received: Callable[[str, str], None],
    ) -> None:
        self._host = host
        self._port = port
        self._on_external_json_received = on_external_json_received
        self._status_lock = threading.Lock()
        self._status = SpectrographExternalDataBridgeStatus(host=host, port=port)
        self._http_server: ThreadingHTTPServer | None = None
        self._serve_thread: threading.Thread | None = None

    def start(self) -> dict[str, object]:
        """Start the background HTTP listener if it is not already running."""

        if self._http_server is not None:
            return self.status()

        bridge_server = self

        class ExternalDataRequestHandler(BaseHTTPRequestHandler):
            """Handle the tiny local bridge protocol for external data updates."""

            def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler naming contract.
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
                    bridge_server._accept_external_json(
                        json_text=json_text,
                        source_label=source_label or "external-source",
                        payload_size_bytes=len(request_body_bytes),
                    )
                except Exception as error:
                    bridge_server._set_error(str(error))
                    self._write_json_response(
                        500,
                        {
                            "status": "rejected",
                            "message": str(error),
                        },
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
                # Quiet local bridge noise. The controller exposes structured
                # status already, so stderr request logs add more clutter than value.
                del format, args

            def _write_json_response(
                self,
                status_code: int,
                body: dict[str, object],
            ) -> None:
                encoded_body = json.dumps(body, separators=(",", ":")).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded_body)))
                self.end_headers()
                self.wfile.write(encoded_body)

        self._http_server = ThreadingHTTPServer(
            (self._host, self._port),
            ExternalDataRequestHandler,
        )
        self._serve_thread = threading.Thread(
            target=self._http_server.serve_forever,
            name="spectrograph-external-data-bridge",
            daemon=True,
        )
        self._serve_thread.start()

        with self._status_lock:
            self._status.host = self._host
            self._status.port = int(self._http_server.server_port)
            self._status.listening = True
            self._status.last_error = ""

        return self.status()

    def stop(self) -> dict[str, object]:
        """Stop the listener and return the final bridge status snapshot."""

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

    def status(self) -> dict[str, object]:
        """Return a copy of the current bridge status."""

        with self._status_lock:
            return self._status.to_dict()

    def _accept_external_json(
        self,
        *,
        json_text: str,
        source_label: str,
        payload_size_bytes: int,
    ) -> None:
        """Record one received payload and forward it to the controller callback."""

        self._on_external_json_received(json_text, source_label)
        with self._status_lock:
            self._status.last_received_at_utc = _current_utc_timestamp_iso8601()
            self._status.last_source_label = source_label
            self._status.last_payload_size_bytes = payload_size_bytes
            self._status.last_error = ""

    def _set_error(self, error_message: str) -> None:
        """Remember the last bridge error for UI status reporting."""

        with self._status_lock:
            self._status.last_error = error_message
