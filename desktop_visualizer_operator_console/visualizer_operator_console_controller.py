"""Controller logic for the unified desktop Visualizer Studio.

The window should focus on widgets, layout, and user interaction. This
controller owns the behavior that deserves isolated tests:

- keeping the editable request payload consistent
- collecting audio snapshots and pointer samples
- building preview scenes for either scene family
- talking to the singular renderer API
- running a background live-stream loop
- writing structured activity-log events
"""

from __future__ import annotations

import copy
import json
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from desktop_shared_control_support.activity_journal import ActivityJournal
from desktop_shared_control_support.audio_input_service import (
    AudioDeviceDescriptor,
    AudioSignalSnapshot,
    DesktopAudioInputService,
)
from desktop_shared_control_support.render_api_client import RenderApiClient, RenderApiResponse
from desktop_visualizer_operator_console.visualizer_operator_scene_builder import (
    DEFAULT_LIVE_CADENCE_MS,
    VisualizerPreviewBundle,
    build_catalog_payload,
    build_default_request_payload,
    build_visualizer_preview_bundle,
)


def _current_utc_timestamp_iso8601() -> str:
    """Return a readable UTC timestamp for status displays and diagnostics."""

    return datetime.now(timezone.utc).isoformat()


@dataclass
class VisualizerLiveStreamSnapshot:
    """Describe the current background streaming worker state."""

    status: str = "stopped"
    cadence_ms: int = DEFAULT_LIVE_CADENCE_MS
    frames_attempted: int = 0
    frames_applied: int = 0
    frames_failed: int = 0
    last_submission_status: int | None = None
    last_submission_reason: str = "idle"
    last_error: str = ""
    last_started_at_utc: str | None = None
    last_stopped_at_utc: str | None = None
    last_applied_at_utc: str | None = None
    last_preview_analysis: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready copy of the live-stream status."""

        return asdict(self)


class RenderApiClientProtocol(Protocol):
    """Small renderer-client surface required by the controller."""

    def health(self, host: str, port: int) -> RenderApiResponse: ...

    def validate_scene(self, host: str, port: int, scene_json: str) -> RenderApiResponse: ...

    def apply_scene(self, host: str, port: int, scene_json: str) -> RenderApiResponse: ...


class AudioInputServiceProtocol(Protocol):
    """Small audio-service surface required by the controller."""

    def devices(self, device_flow: str = "input") -> list[AudioDeviceDescriptor]: ...

    def refresh_devices(self, device_flow: str = "input") -> list[AudioDeviceDescriptor]: ...

    def snapshot(self) -> AudioSignalSnapshot: ...

    def start_capture(
        self,
        device_identifier: str,
        device_flow: str = "input",
    ) -> AudioSignalSnapshot: ...

    def stop_capture(self) -> AudioSignalSnapshot: ...

    def close(self) -> None: ...


class VisualizerOperatorConsoleController:
    """Own the non-visual behavior behind the unified desktop Visualizer Studio."""

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        render_api_client: RenderApiClientProtocol | None = None,
        audio_input_service: AudioInputServiceProtocol | None = None,
    ) -> None:
        self._project_root = project_root or Path(__file__).resolve().parents[1]
        self._render_api_client = render_api_client or RenderApiClient()
        self._audio_input_service = audio_input_service or DesktopAudioInputService()
        self._activity_journal = ActivityJournal(
            source_app="visualizer-studio",
            project_root=self._project_root,
        )
        self._lock = threading.Lock()
        self._current_request_payload = build_default_request_payload()
        self._live_stream_snapshot = VisualizerLiveStreamSnapshot(
            cadence_ms=int(self._current_request_payload["session"]["cadenceMs"])
        )
        self._live_stream_thread: threading.Thread | None = None
        self._stop_live_stream_event = threading.Event()
        self._bar_wall_rolling_history_values: list[float] = []
        self._log("INFO", "visualizer-studio", "Unified desktop Visualizer Studio initialized.")

    def _log(self, level: str, component: str, message: str) -> None:
        """Append one structured event to the shared activity journal."""

        self._activity_journal.write(component=component, level=level, message=message)

    def catalog_payload(self) -> dict[str, Any]:
        """Return metadata used to build selectors and defaults in the window."""

        return build_catalog_payload()

    def current_request_payload(self) -> dict[str, Any]:
        """Return a deep copy of the editable request payload."""

        with self._lock:
            return copy.deepcopy(self._current_request_payload)

    def update_request_payload(self, update: dict[str, Any]) -> dict[str, Any]:
        """Deep-merge one partial UI update into the current payload."""

        with self._lock:
            _deep_merge(self._current_request_payload, update)
            self._live_stream_snapshot.cadence_ms = _safe_int(
                self._current_request_payload.get("session", {}).get("cadenceMs"),
                DEFAULT_LIVE_CADENCE_MS,
            )
            return copy.deepcopy(self._current_request_payload)

    def replace_request_payload(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        """Replace the current payload with a normalized saved document."""

        with self._lock:
            self._current_request_payload = build_default_request_payload()
            _deep_merge(self._current_request_payload, copy.deepcopy(request_payload))
            self._live_stream_snapshot.cadence_ms = _safe_int(
                self._current_request_payload.get("session", {}).get("cadenceMs"),
                DEFAULT_LIVE_CADENCE_MS,
            )
            return copy.deepcopy(self._current_request_payload)

    def reset_to_defaults(self) -> dict[str, Any]:
        """Restore the default payload and clear rolling bar-wall history."""

        with self._lock:
            self._current_request_payload = build_default_request_payload()
            self._bar_wall_rolling_history_values = []
            self._live_stream_snapshot = VisualizerLiveStreamSnapshot(
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
        """Load either a full settings document or a raw request payload."""

        request_payload = settings_document.get("requestPayload", settings_document)
        if not isinstance(request_payload, dict):
            raise ValueError("The selected settings file did not contain a request payload object.")
        return self.replace_request_payload(request_payload)

    def refresh_audio_devices(self, device_flow: str | None = None) -> list[AudioDeviceDescriptor]:
        """Refresh the visible audio device list for one source flow."""

        selected_device_flow = device_flow or self.current_request_payload()["source"]["audio"][
            "deviceFlow"
        ]
        return self._audio_input_service.refresh_devices(str(selected_device_flow))

    def audio_snapshot(self) -> AudioSignalSnapshot:
        """Return the latest audio-analysis snapshot from the capture service."""

        return self._audio_input_service.snapshot()

    def start_audio_capture(
        self,
        device_identifier: str,
        device_flow: str = "input",
    ) -> AudioSignalSnapshot:
        """Start audio capture and remember the selected device."""

        audio_snapshot = self._audio_input_service.start_capture(device_identifier, device_flow)
        self.update_request_payload(
            {
                "source": {
                    "audio": {
                        "deviceIdentifier": device_identifier,
                        "deviceFlow": device_flow,
                    }
                }
            }
        )
        self._log(
            "INFO",
            "audio",
            (
                f"Started {device_flow} audio capture for "
                f"{audio_snapshot.device_name or device_identifier}."
            ),
        )
        return audio_snapshot

    def stop_audio_capture(self) -> AudioSignalSnapshot:
        """Stop active audio capture and return the idle snapshot."""

        audio_snapshot = self._audio_input_service.stop_capture()
        self._log("INFO", "audio", "Stopped audio capture.")
        return audio_snapshot

    def update_pointer_signal(self, normalized_x: float, normalized_y: float, speed: float) -> None:
        """Store the latest pointer-pad sample from the window."""

        self.update_request_payload(
            {
                "source": {
                    "pointer": {
                        "x": normalized_x,
                        "y": normalized_y,
                        "speed": speed,
                    }
                }
            }
        )

    def preview_bundle(self) -> VisualizerPreviewBundle:
        """Build the current preview scene without mutating the live renderer."""

        with self._lock:
            request_payload = copy.deepcopy(self._current_request_payload)
            bar_wall_rolling_history_values = list(self._bar_wall_rolling_history_values)
        return build_visualizer_preview_bundle(
            request_payload,
            audio_signal_snapshot=self._audio_input_service.snapshot(),
            bar_wall_rolling_history_values=bar_wall_rolling_history_values,
        )

    def health(self) -> RenderApiResponse:
        """Run one health check against the singular Visualizer API."""

        preview_bundle = self.preview_bundle()
        return self._render_api_client.health(
            host=str(preview_bundle.target["host"]),
            port=int(preview_bundle.target["port"]),
        )

    def validate_current_scene(self) -> dict[str, Any]:
        """Validate the current preview scene without applying it."""

        preview_bundle = self.preview_bundle()
        response = self._render_api_client.validate_scene(
            host=str(preview_bundle.target["host"]),
            port=int(preview_bundle.target["port"]),
            scene_json=json.dumps(preview_bundle.scene, separators=(",", ":")),
        )
        self._log(
            "INFO" if response.status == 200 else "WARNING",
            "visualizer-studio",
            (
                f"Validated {preview_bundle.scene_mode} with status "
                f"{response.status} {response.reason}."
            ),
        )
        return {
            "status": "validated" if response.status == 200 else "validation-failed",
            "previewBundle": preview_bundle,
            "response": response,
        }

    def apply_current_scene(self) -> dict[str, Any]:
        """Apply the current preview scene once."""

        preview_bundle = self.preview_bundle()
        response = self._render_api_client.apply_scene(
            host=str(preview_bundle.target["host"]),
            port=int(preview_bundle.target["port"]),
            scene_json=json.dumps(preview_bundle.scene, separators=(",", ":")),
        )
        if response.status == 202 and preview_bundle.scene_mode == "bar_wall_scene":
            with self._lock:
                self._bar_wall_rolling_history_values = list(
                    preview_bundle.next_bar_wall_rolling_history_values
                )

        self._log(
            "INFO" if response.status in (200, 202) else "ERROR",
            "visualizer-studio",
            f"Applied {preview_bundle.scene_mode} with status {response.status} {response.reason}.",
        )
        return {
            "status": "applied" if response.status in (200, 202) else "apply-failed",
            "previewBundle": preview_bundle,
            "response": response,
        }

    def live_stream_snapshot(self) -> dict[str, Any]:
        """Return a copy of the current live-stream worker state."""

        with self._lock:
            return copy.deepcopy(self._live_stream_snapshot.to_dict())

    def start_live_stream(self) -> dict[str, Any]:
        """Start repeatedly applying the current preview scene."""

        with self._lock:
            if self._live_stream_thread is not None and self._live_stream_thread.is_alive():
                return copy.deepcopy(self._live_stream_snapshot.to_dict())

            self._stop_live_stream_event.clear()
            self._live_stream_snapshot.status = "running"
            self._live_stream_snapshot.last_error = ""
            self._live_stream_snapshot.last_started_at_utc = _current_utc_timestamp_iso8601()
            self._live_stream_thread = threading.Thread(
                target=self._run_live_stream_loop,
                name="visualizer-studio-live-stream",
                daemon=True,
            )
            self._live_stream_thread.start()
            self._log("INFO", "visualizer-studio", "Started live streaming.")
            return copy.deepcopy(self._live_stream_snapshot.to_dict())

    def stop_live_stream(self) -> dict[str, Any]:
        """Request a clean stop for the live-stream worker."""

        with self._lock:
            self._stop_live_stream_event.set()
            live_stream_thread = self._live_stream_thread

        if live_stream_thread is not None:
            live_stream_thread.join(timeout=2.0)

        with self._lock:
            self._live_stream_thread = None
            self._live_stream_snapshot.status = "stopped"
            self._live_stream_snapshot.last_stopped_at_utc = _current_utc_timestamp_iso8601()
            snapshot = copy.deepcopy(self._live_stream_snapshot.to_dict())
        self._log("INFO", "visualizer-studio", "Stopped live streaming.")
        return snapshot

    def close(self) -> None:
        """Release background workers and audio resources during shutdown."""

        self.stop_live_stream()
        self._audio_input_service.close()
        self._log("INFO", "visualizer-studio", "Visualizer Studio shut down cleanly.")

    def _run_live_stream_loop(self) -> None:
        """Apply preview scenes in a loop until the caller requests a stop."""

        while not self._stop_live_stream_event.is_set():
            frame_started_at = time.monotonic()
            try:
                apply_result = self.apply_current_scene()
                response = apply_result["response"]
                preview_bundle = apply_result["previewBundle"]
                with self._lock:
                    self._live_stream_snapshot.frames_attempted += 1
                    self._live_stream_snapshot.last_submission_status = response.status
                    self._live_stream_snapshot.last_submission_reason = response.reason
                    self._live_stream_snapshot.last_preview_analysis = preview_bundle.analysis
                    if response.status in (200, 202):
                        self._live_stream_snapshot.frames_applied += 1
                        self._live_stream_snapshot.last_applied_at_utc = (
                            _current_utc_timestamp_iso8601()
                        )
                        self._live_stream_snapshot.last_error = ""
                    else:
                        self._live_stream_snapshot.frames_failed += 1
                        self._live_stream_snapshot.last_error = response.body or response.reason
            except Exception as error:  # pragma: no cover - timing varies by environment.
                with self._lock:
                    self._live_stream_snapshot.status = "error"
                    self._live_stream_snapshot.frames_failed += 1
                    self._live_stream_snapshot.last_error = str(error)
                self._log("ERROR", "visualizer-studio", f"Live stream loop failed: {error}")
                break

            with self._lock:
                cadence_ms = self._live_stream_snapshot.cadence_ms
            elapsed_seconds = time.monotonic() - frame_started_at
            remaining_seconds = max(0.0, (cadence_ms / 1000.0) - elapsed_seconds)
            if remaining_seconds > 0.0:
                self._stop_live_stream_event.wait(remaining_seconds)


def _safe_int(value: Any, fallback: int) -> int:
    """Convert one value to an integer without letting UI input crash the controller."""

    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> None:
    """Recursively merge nested dictionaries in place."""

    for key, value in update.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            nested_base_value = base[key]
            assert isinstance(nested_base_value, dict)
            _deep_merge(nested_base_value, value)
        else:
            base[key] = value
