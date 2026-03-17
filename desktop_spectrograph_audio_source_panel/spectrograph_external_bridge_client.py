"""Small HTTP client for the spectrograph control panel's local external-data bridge."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class SpectrographExternalBridgeResponse:
    """Describe one bridge-delivery attempt."""

    ok: bool
    status: int
    reason: str
    body: str


class SpectrographExternalBridgeClient:
    """Send generated JSON documents to the spectrograph control panel bridge."""

    def deliver_json_text(
        self,
        *,
        host: str,
        port: int,
        path: str,
        source_label: str,
        json_text: str,
    ) -> SpectrographExternalBridgeResponse:
        """POST one generated JSON document to the local bridge endpoint."""

        request_body = json.dumps(
            {
                "sourceLabel": source_label,
                "jsonText": json_text,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        request = urllib.request.Request(
            url=f"http://{host}:{port}{path}",
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
        except Exception as error:
            return SpectrographExternalBridgeResponse(
                ok=False,
                status=0,
                reason=type(error).__name__,
                body=str(error),
            )
