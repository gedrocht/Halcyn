"""HTTP client helpers for the desktop render control panel."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RenderApiResponse:
    """Describe one HTTP round-trip to the live Halcyn API."""

    ok: bool
    status: int
    reason: str
    body: str
    headers: dict[str, str]

    def body_as_json(self) -> dict[str, Any] | None:
        """Decode the body as JSON when the response actually contains JSON."""

        if not self.body.strip():
            return None

        try:
            decoded = json.loads(self.body)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else {"value": decoded}


class RenderApiClient:
    """Small HTTP client focused on the routes the desktop panel needs most."""

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
        """Send one request to the live Halcyn renderer API."""

        normalized_path = request_path if request_path.startswith("/") else f"/{request_path}"
        request_url = f"http://{host}:{port}{normalized_path}"
        request_data = request_body.encode("utf-8") if request_body else None
        request = urllib.request.Request(request_url, data=request_data, method=method.upper())
        if request_body:
            request.add_header("Content-Type", content_type)

        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return RenderApiResponse(
                    ok=True,
                    status=response.status,
                    reason=response.reason,
                    body=response.read().decode("utf-8"),
                    headers=dict(response.headers.items()),
                )
        except urllib.error.HTTPError as error:
            return RenderApiResponse(
                ok=False,
                status=error.code,
                reason=error.reason,
                body=error.read().decode("utf-8"),
                headers=dict(error.headers.items()),
            )
        except Exception as error:  # pragma: no cover - network failures vary by machine.
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
