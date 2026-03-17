"""Controller logic for the native desktop spectrograph control panel.

The window code should focus on widgets and user interaction. This controller
keeps the operational logic separate:

- building spectrograph scenes from generic JSON
- tracking the rolling statistical history
- talking to the live renderer API
- managing a simple live-stream worker thread
- receiving optional external JSON updates from helper desktop tools

That last bullet is new and important. The spectrograph control panel is now
the place where render behavior is tuned, while helper tools can feed it new
data sources. That keeps the app-to-app boundary explicit instead of trying to
smuggle values directly into Tkinter widgets.
"""

from __future__ import annotations

import copy
import json
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from desktop_shared_control_support.activity_log import DesktopActivityLogger
from desktop_shared_control_support.render_api_client import RenderApiClient, RenderApiResponse
from desktop_spectrograph_control_panel.external_data_bridge_server import (
    SpectrographExternalDataBridgeServer,
)
from desktop_spectrograph_control_panel.spectrograph_scene_builder import (
    SpectrographBuildResult,
    build_catalog_payload,
    build_default_request_payload,
    build_spectrograph_scene_result,
)


def _current_utc_timestamp_iso8601() -> str:
    """Return a readable UTC timestamp for status reporting."""

    return datetime.now(timezone.utc).isoformat()


@dataclass
class SpectrographLiveStreamSnapshot:
    """Describe the current live-stream worker state."""

    status: str = "stopped"
    cadence_ms: int = 250
    frames_attempted: int = 0
    frames_applied: int = 0
    frames_failed: int = 0
    last_submission_status: int | None = None
    last_submission_reason: str = "idle"
    last_error: str = ""
    last_started_at_utc: str | None = None
    last_stopped_at_utc: str | None = None
    last_applied_at_utc: str | None = None
    last_analysis: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready copy of the live-stream status."""

        return asdict(self)


@dataclass
class ExternalSourceStatus:
    """Describe whether the spectrograph panel is receiving external data."""

    enabled: bool = False
    latest_source_label: str = ""
    latest_received_at_utc: str = ""
    latest_json_text: str = ""
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready copy of the external-source state."""

        return asdict(self)


class RenderApiClientProtocol(Protocol):
    """Minimal renderer-client surface used by the controller."""

    def health(self, host: str, port: int) -> RenderApiResponse:
        ...

    def validate_scene(self, host: str, port: int, scene_json: str) -> RenderApiResponse:
        ...

    def apply_scene(self, host: str, port: int, scene_json: str) -> RenderApiResponse:
        ...


class DesktopSpectrographControlPanelController:
    """Own the non-visual behavior behind the desktop spectrograph panel."""

    def __init__(
        self,
        render_api_client: RenderApiClientProtocol | None = None,
        activity_logger: DesktopActivityLogger | None = None,
    ) -> None:
        self._render_api_client = render_api_client or RenderApiClient()
        self._activity_logger = activity_logger or DesktopActivityLogger(
            application_name="bars-studio"
        )
        self._lock = threading.Lock()
        self._current_request_payload = build_default_request_payload()
        self._rolling_history_values: list[float] = []
        self._live_stream_snapshot = SpectrographLiveStreamSnapshot(
            cadence_ms=int(self._current_request_payload["session"]["cadenceMs"])
        )
        self._external_source_status = ExternalSourceStatus(
            enabled=bool(self._current_request_payload["externalAudioBridge"]["enabled"])
        )
        self._live_stream_thread: threading.Thread | None = None
        self._stop_live_stream_event = threading.Event()
        self._external_data_bridge_server = self._build_external_data_bridge_server()
        self._external_data_bridge_status = self._start_external_data_bridge_server()

    def catalog_payload(self) -> dict[str, Any]:
        """Return metadata that helps the window build selectors and example buttons."""

        return build_catalog_payload()

    def current_request_payload(self) -> dict[str, Any]:
        """Return a deep copy of the editable payload."""

        with self._lock:
            return copy.deepcopy(self._current_request_payload)

    def update_request_payload(self, update: dict[str, Any]) -> dict[str, Any]:
        """Deep-merge a partial UI update into the current payload."""

        with self._lock:
            _deep_merge(self._current_request_payload, update)
            self._live_stream_snapshot.cadence_ms = _safe_int(
                self._current_request_payload.get("session", {}).get("cadenceMs"),
                250,
            )
            self._external_source_status.enabled = bool(
                self._current_request_payload.get("externalAudioBridge", {}).get("enabled", False)
            )
            should_restart_bridge = self._bridge_configuration_changed()
        if should_restart_bridge:
            self._external_data_bridge_status = self._restart_external_data_bridge_server()
        return self.current_request_payload()

    def replace_request_payload(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        """Replace the payload using a freshly normalized saved-settings document."""

        with self._lock:
            self._current_request_payload = build_default_request_payload()
            _deep_merge(self._current_request_payload, copy.deepcopy(request_payload))
            self._live_stream_snapshot.cadence_ms = _safe_int(
                self._current_request_payload.get("session", {}).get("cadenceMs"),
                250,
            )
            self._external_source_status.enabled = bool(
                self._current_request_payload.get("externalAudioBridge", {}).get("enabled", False)
            )
        self._external_data_bridge_status = self._restart_external_data_bridge_server()
        return self.current_request_payload()

    def reset_to_defaults(self) -> dict[str, Any]:
        """Restore the full default payload and clear the rolling value history."""

        with self._lock:
            self._current_request_payload = build_default_request_payload()
            self._rolling_history_values = []
            self._live_stream_snapshot = SpectrographLiveStreamSnapshot(
                cadence_ms=int(self._current_request_payload["session"]["cadenceMs"])
            )
            self._external_source_status = ExternalSourceStatus(
                enabled=bool(self._current_request_payload["externalAudioBridge"]["enabled"])
            )
        self._external_data_bridge_status = self._restart_external_data_bridge_server()
        return self.current_request_payload()

    def settings_document(self) -> dict[str, Any]:
        """Return a versioned document suitable for saving to disk."""

        return {
            "formatVersion": 1,
            "savedAtUtc": _current_utc_timestamp_iso8601(),
            "requestPayload": self.current_request_payload(),
        }

    def load_settings_document(self, settings_document: dict[str, Any]) -> dict[str, Any]:
        """Load either a versioned settings document or a raw request payload."""

        request_payload = settings_document.get("requestPayload", settings_document)
        if not isinstance(request_payload, dict):
            raise ValueError("The selected settings file did not contain a request payload object.")
        return self.replace_request_payload(request_payload)

    def preview_scene_result(self) -> SpectrographBuildResult:
        """Build the current scene using manual JSON or the latest external source."""

        with self._lock:
            request_payload = copy.deepcopy(self._current_request_payload)
            rolling_history_values = list(self._rolling_history_values)
            external_json_text = self._external_source_status.latest_json_text
            external_source_enabled = self._external_source_status.enabled

        if external_source_enabled and external_json_text:
            request_payload["data"]["jsonText"] = external_json_text

        return build_spectrograph_scene_result(request_payload, rolling_history_values)

    def health(self) -> RenderApiResponse:
        """Check whether the target renderer is reachable."""

        preview_result = self.preview_scene_result()
        return self._render_api_client.health(
            host=str(preview_result.target["host"]),
            port=int(preview_result.target["port"]),
        )

    def validate_current_scene(self) -> dict[str, Any]:
        """Validate the current spectrograph scene against the live renderer."""

        preview_result = self.preview_scene_result()
        response = self._render_api_client.validate_scene(
            host=str(preview_result.target["host"]),
            port=int(preview_result.target["port"]),
            scene_json=json.dumps(preview_result.scene, separators=(",", ":")),
        )
        return {
            "status": "validated" if response.status == 200 else "validation-failed",
            "buildResult": preview_result,
            "response": response,
        }

    def apply_current_scene(self) -> dict[str, Any]:
        """Apply the current scene once.

        When the renderer accepts the scene, the controller also commits the
        source values into the rolling history so the next automatic range
        calculation can learn from the newly accepted frame.
        """

        preview_result = self.preview_scene_result()
        response = self._render_api_client.apply_scene(
            host=str(preview_result.target["host"]),
            port=int(preview_result.target["port"]),
            scene_json=json.dumps(preview_result.scene, separators=(",", ":")),
        )
        if response.status == 202:
            with self._lock:
                self._rolling_history_values = list(preview_result.next_rolling_history_values)

        return {
            "status": "applied" if response.status == 202 else "apply-failed",
            "buildResult": preview_result,
            "response": response,
        }

    def live_stream_snapshot(self) -> dict[str, Any]:
        """Return a copy of the live-stream status."""

        with self._lock:
            return self._live_stream_snapshot.to_dict()

    def external_source_status(self) -> dict[str, Any]:
        """Return the current external-source state shown in the UI."""

        with self._lock:
            status_copy = self._external_source_status.to_dict()
        status_copy["bridge"] = self.external_data_bridge_status()
        return status_copy

    def external_data_bridge_status(self) -> dict[str, Any]:
        """Return the current local bridge server status."""

        with self._lock:
            return copy.deepcopy(self._external_data_bridge_status)

    def start_live_stream(self) -> dict[str, Any]:
        """Start repeatedly applying the current spectrograph scene."""

        with self._lock:
            if self._live_stream_thread is not None and self._live_stream_thread.is_alive():
                return self._live_stream_snapshot.to_dict()

            self._stop_live_stream_event.clear()
            self._live_stream_snapshot.status = "running"
            self._live_stream_snapshot.cadence_ms = _safe_int(
                self._current_request_payload.get("session", {}).get("cadenceMs"),
                250,
            )
            self._live_stream_snapshot.last_error = ""
            self._live_stream_snapshot.last_started_at_utc = _current_utc_timestamp_iso8601()
            self._live_stream_thread = threading.Thread(
                target=self._run_live_stream_loop,
                name="desktop-spectrograph-live-stream",
                daemon=True,
            )
            self._live_stream_thread.start()
            self._activity_logger.log(
                component_name="live-stream",
                level="INFO",
                message="Started the Bars Studio live stream.",
                details={"cadenceMs": self._live_stream_snapshot.cadence_ms},
            )
            return self._live_stream_snapshot.to_dict()

    def stop_live_stream(self) -> dict[str, Any]:
        """Request a clean stop for the live-stream worker."""

        live_stream_thread: threading.Thread | None
        with self._lock:
            self._stop_live_stream_event.set()
            live_stream_thread = self._live_stream_thread

        if live_stream_thread is not None:
            live_stream_thread.join(timeout=2.0)

        with self._lock:
            self._live_stream_thread = None
            self._live_stream_snapshot.status = "stopped"
            self._live_stream_snapshot.last_stopped_at_utc = _current_utc_timestamp_iso8601()
            stopped_snapshot = self._live_stream_snapshot.to_dict()
        self._activity_logger.log(
            component_name="live-stream",
            level="INFO",
            message="Stopped the Bars Studio live stream.",
            details={
                "framesAttempted": stopped_snapshot["frames_attempted"],
                "framesApplied": stopped_snapshot["frames_applied"],
                "framesFailed": stopped_snapshot["frames_failed"],
            },
        )
        return stopped_snapshot

    def close(self) -> None:
        """Shut down the live-stream worker and local bridge during application exit."""

        self.stop_live_stream()
        self._external_data_bridge_status = self._stop_external_data_bridge_server()

    def _run_live_stream_loop(self) -> None:
        """Apply frames in a loop until the caller requests a stop."""

        last_applied_scene_json = ""
        while not self._stop_live_stream_event.is_set():
            frame_started_at = time.monotonic()
            try:
                preview_result = self.preview_scene_result()
                scene_json = json.dumps(preview_result.scene, separators=(",", ":"))
                if scene_json == last_applied_scene_json:
                    response = RenderApiResponse(True, 202, "Skipped", '{"status":"unchanged"}', {})
                else:
                    response = self._render_api_client.apply_scene(
                        host=str(preview_result.target["host"]),
                        port=int(preview_result.target["port"]),
                        scene_json=scene_json,
                    )
                with self._lock:
                    self._live_stream_snapshot.frames_attempted += 1
                    self._live_stream_snapshot.last_submission_status = response.status
                    self._live_stream_snapshot.last_submission_reason = response.reason
                    self._live_stream_snapshot.last_analysis = preview_result.analysis
                    if response.status == 202:
                        last_applied_scene_json = scene_json
                        self._rolling_history_values = list(
                            preview_result.next_rolling_history_values
                        )
                        self._live_stream_snapshot.frames_applied += 1
                        self._live_stream_snapshot.last_applied_at_utc = (
                            _current_utc_timestamp_iso8601()
                        )
                    else:
                        self._live_stream_snapshot.frames_failed += 1
                        self._live_stream_snapshot.last_error = response.body or response.reason
            except Exception as error:  # pragma: no cover - thread timing varies by environment.
                with self._lock:
                    self._live_stream_snapshot.frames_attempted += 1
                    self._live_stream_snapshot.frames_failed += 1
                    self._live_stream_snapshot.status = "error"
                    self._live_stream_snapshot.last_error = str(error)
                break

            with self._lock:
                cadence_ms = self._live_stream_snapshot.cadence_ms

            elapsed_seconds = time.monotonic() - frame_started_at
            remaining_seconds = max(0.0, (cadence_ms / 1000.0) - elapsed_seconds)
            if remaining_seconds > 0.0:
                self._stop_live_stream_event.wait(remaining_seconds)

    def _build_external_data_bridge_server(self) -> SpectrographExternalDataBridgeServer:
        """Create the local bridge server for helper desktop tools."""

        bridge_settings = self._current_request_payload["externalAudioBridge"]
        return SpectrographExternalDataBridgeServer(
            host=str(bridge_settings["host"]),
            port=int(bridge_settings["port"]),
            on_external_json_received=self._accept_external_json_from_bridge,
        )

    def _start_external_data_bridge_server(self) -> dict[str, Any]:
        """Start the local bridge server and convert startup failures into status."""

        try:
            started_status = self._external_data_bridge_server.start()
            self._activity_logger.log(
                component_name="external-json-bridge",
                level="INFO",
                message="Started the Bars Studio external JSON bridge.",
                details=started_status,
            )
            return started_status
        except Exception as error:
            error_message = str(error)
            with self._lock:
                self._external_source_status.last_error = error_message
            self._activity_logger.log(
                component_name="external-json-bridge",
                level="ERROR",
                message="Could not start the Bars Studio external JSON bridge.",
                details={"error": error_message},
            )
            return {
                "host": str(self._current_request_payload["externalAudioBridge"]["host"]),
                "port": int(self._current_request_payload["externalAudioBridge"]["port"]),
                "listening": False,
                "last_received_at_utc": "",
                "last_source_label": "",
                "last_payload_size_bytes": 0,
                "last_error": error_message,
            }

    def _stop_external_data_bridge_server(self) -> dict[str, Any]:
        """Stop the local bridge server and return its final status snapshot."""

        try:
            return self._external_data_bridge_server.stop()
        except Exception as error:
            return {
                "host": str(self._current_request_payload["externalAudioBridge"]["host"]),
                "port": int(self._current_request_payload["externalAudioBridge"]["port"]),
                "listening": False,
                "last_received_at_utc": "",
                "last_source_label": "",
                "last_payload_size_bytes": 0,
                "last_error": str(error),
            }

    def _restart_external_data_bridge_server(self) -> dict[str, Any]:
        """Recreate the bridge server after settings or defaults change."""

        self._stop_external_data_bridge_server()
        self._external_data_bridge_server = self._build_external_data_bridge_server()
        return self._start_external_data_bridge_server()

    def _bridge_configuration_changed(self) -> bool:
        """Return whether the payload no longer matches the active bridge server."""

        configured_bridge = self._current_request_payload["externalAudioBridge"]
        current_status = self._external_data_bridge_status
        return (
            str(configured_bridge["host"]) != str(current_status.get("host", ""))
            or int(configured_bridge["port"]) != int(current_status.get("port", 0))
        )

    def _accept_external_json_from_bridge(self, json_text: str, source_label: str) -> None:
        """Record the most recent externally supplied JSON document.

        The bridge server calls this on a worker thread whenever a helper tool,
        such as the dedicated audio-source panel, posts fresh data. The
        controller stores the payload as plain text because the existing
        spectrograph builder already knows how to validate, flatten, and analyze
        generic JSON text.
        """

        with self._lock:
            self._external_source_status.latest_json_text = json_text
            self._external_source_status.latest_source_label = source_label
            self._external_source_status.latest_received_at_utc = _current_utc_timestamp_iso8601()
            self._external_source_status.last_error = ""
        self._activity_logger.log(
            component_name="external-json-bridge",
            level="INFO",
            message="Received external JSON for Bars Studio.",
            details={
                "sourceLabel": source_label,
                "payloadSizeBytes": len(json_text.encode("utf-8")),
            },
        )


def _safe_int(value: Any, fallback: int) -> int:
    """Convert one value to an int without throwing from the controller layer."""

    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> None:
    """Recursively merge one nested dictionary into another."""

    for key, value in update.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
