"""Controller logic for the native desktop spectrograph control panel.

The window code should focus on widgets and user interaction. This controller
keeps the operational logic separate:

- building spectrograph scenes from generic JSON
- tracking the rolling statistical history
- talking to the live renderer API
- managing a simple live-stream worker thread
"""

from __future__ import annotations

import copy
import json
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from desktop_render_control_panel.render_api_client import RenderApiClient, RenderApiResponse
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

    def __init__(self, render_api_client: RenderApiClientProtocol | None = None) -> None:
        self._render_api_client = render_api_client or RenderApiClient()
        self._lock = threading.Lock()
        self._current_request_payload = build_default_request_payload()
        self._rolling_history_values: list[float] = []
        self._live_stream_snapshot = SpectrographLiveStreamSnapshot(
            cadence_ms=int(self._current_request_payload["session"]["cadenceMs"])
        )
        self._live_stream_thread: threading.Thread | None = None
        self._stop_live_stream_event = threading.Event()

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
            return copy.deepcopy(self._current_request_payload)

    def replace_request_payload(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        """Replace the payload using a freshly normalized saved-settings document."""

        with self._lock:
            self._current_request_payload = build_default_request_payload()
            _deep_merge(self._current_request_payload, copy.deepcopy(request_payload))
            self._live_stream_snapshot.cadence_ms = _safe_int(
                self._current_request_payload.get("session", {}).get("cadenceMs"),
                250,
            )
            return copy.deepcopy(self._current_request_payload)

    def reset_to_defaults(self) -> dict[str, Any]:
        """Restore the full default payload and clear the rolling value history."""

        with self._lock:
            self._current_request_payload = build_default_request_payload()
            self._rolling_history_values = []
            self._live_stream_snapshot = SpectrographLiveStreamSnapshot(
                cadence_ms=int(self._current_request_payload["session"]["cadenceMs"])
            )
            return copy.deepcopy(self._current_request_payload)

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
        """Build the current scene without mutating rolling history."""

        with self._lock:
            request_payload = copy.deepcopy(self._current_request_payload)
            rolling_history_values = list(self._rolling_history_values)
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
            return self._live_stream_snapshot.to_dict()

    def close(self) -> None:
        """Shut down any live-stream worker during application exit."""

        self.stop_live_stream()

    def _run_live_stream_loop(self) -> None:
        """Apply frames in a loop until the caller requests a stop."""

        while not self._stop_live_stream_event.is_set():
            frame_started_at = time.monotonic()
            try:
                preview_result = self.preview_scene_result()
                response = self._render_api_client.apply_scene(
                    host=str(preview_result.target["host"]),
                    port=int(preview_result.target["port"]),
                    scene_json=json.dumps(preview_result.scene, separators=(",", ":")),
                )
                with self._lock:
                    self._live_stream_snapshot.frames_attempted += 1
                    self._live_stream_snapshot.last_submission_status = response.status
                    self._live_stream_snapshot.last_submission_reason = response.reason
                    self._live_stream_snapshot.last_analysis = preview_result.analysis
                    if response.status == 202:
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
