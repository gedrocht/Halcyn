"""Compatibility bridge client for the Audio Sender desktop tool.

The project now has a shared local JSON bridge client, but the audio sender has
older tests and calling code that still refer to the spectrograph-specific
module and patch its local ``urllib`` import path.  Keeping that familiar
surface lets the codebase move to the shared implementation gradually without
making the beginner-facing tests harder to follow.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from desktop_shared_control_support.local_json_bridge import (
    LocalJsonBridgeResponse as SpectrographExternalBridgeResponse,
)
from desktop_shared_control_support.local_json_bridge import (
    normalize_local_json_bridge_path as _normalize_bridge_path,
)


class SpectrographExternalBridgeClient:
    """POST generated JSON documents to another local Halcyn desktop tool."""

    def deliver_json_text(
        self,
        *,
        host: str,
        port: int,
        path: str,
        source_label: str,
        json_text: str,
    ) -> SpectrographExternalBridgeResponse:
        """Send one JSON document to the selected bridge endpoint.

        This implementation intentionally mirrors the shared bridge client
        rather than aliasing it directly so that tests can still patch
        ``urllib.request.urlopen`` at this module path.
        """

        request_body = json.dumps(
            {
                "sourceLabel": source_label,
                "jsonText": json_text,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        request = urllib.request.Request(
            url=f"http://{host}:{port}{_normalize_bridge_path(path)}",
            data=request_body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(request, timeout=5.0) as response:
                response_body = response.read().decode("utf-8")
                return SpectrographExternalBridgeResponse(
                    ok=200 <= int(response.status) < 300,
                    status=int(response.status),
                    reason=str(response.reason),
                    body=response_body,
                )
        except urllib.error.HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            return SpectrographExternalBridgeResponse(
                ok=False,
                status=int(error.code),
                reason=str(error.reason),
                body=error_body,
            )
        except Exception as error:  # pragma: no cover - environment detail varies.
            return SpectrographExternalBridgeResponse(
                ok=False,
                status=0,
                reason=type(error).__name__,
                body=str(error),
            )


__all__ = [
    "SpectrographExternalBridgeClient",
    "SpectrographExternalBridgeResponse",
    "_normalize_bridge_path",
]
