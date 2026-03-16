"""HTTP client helpers for the desktop render control panel.

The desktop control panel only needs a tiny slice of Halcyn's HTTP surface, so
this module intentionally wraps just those routes instead of exposing a huge
generic client abstraction.

Helpful standard-library references:

- `urllib.request`: https://docs.python.org/3/library/urllib.request.html
- `urllib.error`: https://docs.python.org/3/library/urllib.error.html
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RenderApiResponse:
    """Describe one HTTP round-trip to the live Halcyn API.

    The desktop UI uses this object for two jobs:

    1. decide whether the request succeeded
    2. show a beginner-friendly status message without needing to know HTTP
       library details such as exception classes
    """

    ok: bool
    status: int
    reason: str
    body: str
    headers: dict[str, str]

    def body_as_json(self) -> dict[str, Any] | None:
        """Decode the body as JSON when the response actually contains JSON.

        Returning `None` is intentional here.  Many control-panel actions only
        need a readable status line, so callers should not be forced to handle a
        JSON parse exception just because an endpoint returned plain text.
        """

        if not self.body.strip():
            return None

        try:
            decoded = json.loads(self.body)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else {"value": decoded}


class RenderApiClient:
    """Small HTTP client focused on the routes the desktop panel needs most.

    This class keeps the higher-level controller free from low-level `urllib`
    details so the controller can talk in terms of "health check" and "apply
    scene" instead of "build a Request object and catch HTTPError".
    """

    def request(
        self,
        *,
        host: str,
        port: int,
        method: str,
        request_path: str,
        request_body: str = "",
        content_type: str = "application/json",
        timeout_seconds: float = 5.0,
    ) -> RenderApiResponse:
        """Send one request to the live Halcyn renderer API.

        The method always returns a `RenderApiResponse`, even for failures. That
        design keeps the calling code simple and predictable: the GUI can always
        inspect one response object instead of sometimes receiving a response
        and sometimes receiving an exception.
        """

        normalized_path = request_path if request_path.startswith("/") else f"/{request_path}"
        request_url = f"http://{host}:{port}{normalized_path}"
        request_data = request_body.encode("utf-8") if request_body else None
        request = urllib.request.Request(request_url, data=request_data, method=method.upper())
        if request_body:
            request.add_header("Content-Type", content_type)

        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                # Successful HTTP responses return a file-like object from which
                # we read the response body exactly once.
                return RenderApiResponse(
                    ok=True,
                    status=response.status,
                    reason=response.reason,
                    body=response.read().decode("utf-8"),
                    headers=dict(response.headers.items()),
                )
        except urllib.error.HTTPError as error:
            # HTTPError still represents a completed HTTP round-trip.  The
            # server may have returned useful JSON or plain-text details, so we
            # preserve that body for the UI.
            return RenderApiResponse(
                ok=False,
                status=error.code,
                reason=error.reason,
                body=error.read().decode("utf-8"),
                headers=dict(error.headers.items()),
                )
        except Exception as error:  # pragma: no cover - network failures vary by machine.
            # Connection failures happen before a real HTTP response exists, so
            # we synthesize a response-like object with status 0.  The UI treats
            # that as "offline or unreachable" instead of a protocol failure.
            return RenderApiResponse(
                ok=False,
                status=0,
                reason="connection-error",
                body=str(error),
                headers={},
            )

    def health(self, host: str, port: int) -> RenderApiResponse:
        """Fetch the renderer health endpoint."""

        return self.request(host=host, port=port, method="GET", request_path="/api/v1/health")

    def validate_scene(self, host: str, port: int, scene_json: str) -> RenderApiResponse:
        """Validate one scene without changing the live renderer."""

        return self.request(
            host=host,
            port=port,
            method="POST",
            request_path="/api/v1/scene/validate",
            request_body=scene_json,
        )

    def apply_scene(self, host: str, port: int, scene_json: str) -> RenderApiResponse:
        """Submit one scene to the live renderer."""

        return self.request(
            host=host,
            port=port,
            method="POST",
            request_path="/api/v1/scene",
            request_body=scene_json,
        )
