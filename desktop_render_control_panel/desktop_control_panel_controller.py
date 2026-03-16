"""Controller logic for the native desktop render control panel.

This module is the "brain" behind the desktop window.  The Tkinter UI asks
questions such as:

- "What presets exist?"
- "What does the current preview scene look like?"
- "Please start streaming scenes every 125 milliseconds."

The controller answers those questions without exposing the GUI to lower-level
details such as HTTP request formatting, audio-device state, or cross-thread
bookkeeping.
"""

from __future__ import annotations

import copy
import json
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from desktop_render_control_panel.audio_input_service import (
    AudioDeviceDescriptor,
    AudioSignalSnapshot,
    DesktopAudioInputService,
)
from desktop_render_control_panel.desktop_control_scene_builder import (
    DEFAULT_DESKTOP_PRESET_ID,
    build_catalog_payload,
    build_default_request_payload,
    build_scene_bundle,
)
from desktop_render_control_panel.render_api_client import RenderApiClient, RenderApiResponse


def _current_utc_timestamp_iso8601() -> str:
    """Return a readable UTC timestamp for status snapshots and diagnostics."""

    return datetime.now(timezone.utc).isoformat()


@dataclass
class DesktopLiveStreamSnapshot:
    """Describe the current live-stream state owned by the desktop panel."""

    status: str = "stopped"
    cadence_ms: int = 125
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
    """Minimal client interface the controller needs from a renderer API client."""

    def health(self, host: str, port: int) -> RenderApiResponse:
        ...

    def validate_scene(self, host: str, port: int, scene_json: str) -> RenderApiResponse:
        ...

    def apply_scene(self, host: str, port: int, scene_json: str) -> RenderApiResponse:
        ...


class AudioInputServiceProtocol(Protocol):
    """Minimal audio-service interface the controller needs."""

    def devices(self) -> list[AudioDeviceDescriptor]:
        ...

    def refresh_devices(self) -> list[AudioDeviceDescriptor]:
        ...

    def snapshot(self) -> AudioSignalSnapshot:
        ...

    def start_capture(self, device_identifier: str) -> AudioSignalSnapshot:
        ...

    def stop_capture(self) -> AudioSignalSnapshot:
        ...

    def close(self) -> None:
        ...


class DesktopRenderControlPanelController:
    """Own the non-visual behavior behind the desktop control panel.

    The Tk window should not know how to:
    - talk HTTP
    - analyze audio
    - merge scene-control payloads
    - run a continuous live-stream loop

    Keeping those jobs here makes the behavior testable without trying to
    drive a real GUI in unit tests.
    """

    def __init__(
        self,
        render_api_client: RenderApiClientProtocol | None = None,
        audio_input_service: AudioInputServiceProtocol | None = None,
    ) -> None:
        # One lock guards all mutable controller state so the Tkinter thread,
        # audio callback thread, and live-stream worker never partially step on
        # each other's updates.
        self._render_api_client = render_api_client or RenderApiClient()
        self._audio_input_service = audio_input_service or DesktopAudioInputService()
        self._lock = threading.Lock()
        self._current_request_payload = build_default_request_payload(DEFAULT_DESKTOP_PRESET_ID)
        self._live_stream_snapshot = DesktopLiveStreamSnapshot()
        self._live_stream_thread: threading.Thread | None = None
        self._stop_live_stream_event = threading.Event()

    def catalog_payload(self) -> dict[str, Any]:
        """Return preset and input metadata for the desktop control panel."""

        return build_catalog_payload()

    def current_request_payload(self) -> dict[str, Any]:
        """Return a deep copy of the editable control payload."""

        with self._lock:
            return copy.deepcopy(self._current_request_payload)

    def load_preset(self, preset_identifier: str) -> dict[str, Any]:
        """Replace the current scene preset while preserving target/cadence routing."""

        with self._lock:
            # Preset changes should feel like "swap the visual idea, keep my
            # current connection/session settings" rather than "reset the whole
            # application."
            previous_target = copy.deepcopy(self._current_request_payload.get("target", {}))
            previous_session = copy.deepcopy(self._current_request_payload.get("session", {}))
            self._current_request_payload = build_default_request_payload(preset_identifier)
            self._current_request_payload["target"] = (
                previous_target or self._current_request_payload["target"]
            )
            self._current_request_payload["session"] = (
                previous_session or self._current_request_payload["session"]
            )
            self._live_stream_snapshot.cadence_ms = int(
                self._current_request_payload["session"]["cadenceMs"]
            )
            return copy.deepcopy(self._current_request_payload)

    def update_request_payload(self, update: dict[str, Any]) -> dict[str, Any]:
        """Deep-merge a partial UI update into the current control payload."""

        with self._lock:
            _deep_merge(self._current_request_payload, update)
            requested_cadence_in_milliseconds = (
                self._current_request_payload.get("session", {}).get("cadenceMs", 125)
            )
            self._live_stream_snapshot.cadence_ms = _clamp_int(
                requested_cadence_in_milliseconds,
                125,
                40,
                1000,
            )
            return copy.deepcopy(self._current_request_payload)

    def update_pointer_signal(self, normalized_x: float, normalized_y: float, speed: float) -> None:
        """Store the latest pointer-pad sample from the desktop UI."""

        with self._lock:
            signals_payload = self._current_request_payload.setdefault("signals", {})
            pointer_payload = signals_payload.setdefault("pointer", {})
            pointer_payload["x"] = _clamp_float(normalized_x, 0.5, 0.0, 1.0)
            pointer_payload["y"] = _clamp_float(normalized_y, 0.5, 0.0, 1.0)
            pointer_payload["speed"] = _clamp_float(speed, 0.0, 0.0, 1.0)

    def audio_devices(self) -> list[AudioDeviceDescriptor]:
        """Return the currently known audio input devices."""

        return self._audio_input_service.devices()

    def refresh_audio_devices(self) -> list[AudioDeviceDescriptor]:
        """Re-enumerate audio input devices."""

        return self._audio_input_service.refresh_devices()

    def audio_snapshot(self) -> AudioSignalSnapshot:
        """Return the latest audio-analysis snapshot."""

        return self._audio_input_service.snapshot()

    def start_audio_capture(self, device_identifier: str) -> AudioSignalSnapshot:
        """Start capturing from one chosen audio input device."""

        return self._audio_input_service.start_capture(device_identifier)

    def stop_audio_capture(self) -> AudioSignalSnapshot:
        """Stop capturing audio."""

        return self._audio_input_service.stop_capture()

    def preview_scene_bundle(self) -> dict[str, Any]:
        """Build the current scene without validating or applying it."""

        return build_scene_bundle(self._build_effective_payload())

    def validate_current_scene(self) -> dict[str, Any]:
        """Validate the current preview scene against the live Halcyn API."""

        preview_bundle = self.preview_scene_bundle()
        target = preview_bundle["target"]
        scene_json = json.dumps(preview_bundle["scene"], separators=(",", ":"))
        response = self._render_api_client.validate_scene(
            host=str(target["host"]),
            port=int(target["port"]),
            scene_json=scene_json,
        )
        return {
            "status": "validated" if response.status == 200 else "validation-failed",
            "bundle": preview_bundle,
            "response": response,
        }

    def apply_current_scene(self) -> dict[str, Any]:
        """Apply the current preview scene once."""

        preview_bundle = self.preview_scene_bundle()
        return self._apply_preview_bundle(preview_bundle)

    def health_check(self) -> RenderApiResponse:
        """Query the live Halcyn API health endpoint."""

        current_request_payload = self.current_request_payload()
        target = current_request_payload.get("target", {})
        host = str(target.get("host", "127.0.0.1"))
        port = int(target.get("port", 8080))
        return self._render_api_client.health(host=host, port=port)

    def live_stream_snapshot(self) -> dict[str, Any]:
        """Return the latest live-stream counters and status."""

        with self._lock:
            return copy.deepcopy(self._live_stream_snapshot.to_dict())

    def start_live_stream(self) -> dict[str, Any]:
        """Start the continuous live-stream loop if it is not already running."""

        with self._lock:
            if self._live_stream_thread is not None and self._live_stream_thread.is_alive():
                return copy.deepcopy(self._live_stream_snapshot.to_dict())

            self._stop_live_stream_event = threading.Event()
            self._live_stream_snapshot.status = "starting"
            self._live_stream_snapshot.last_error = ""
            self._live_stream_snapshot.last_started_at_utc = _current_utc_timestamp_iso8601()
            self._live_stream_thread = threading.Thread(
                target=self._run_live_stream_loop,
                daemon=True,
            )
            self._live_stream_thread.start()
            return copy.deepcopy(self._live_stream_snapshot.to_dict())

    def stop_live_stream(self) -> dict[str, Any]:
        """Stop the live-stream loop."""

        with self._lock:
            live_stream_thread = self._live_stream_thread
            if live_stream_thread is None or not live_stream_thread.is_alive():
                self._live_stream_snapshot.status = "stopped"
                if self._live_stream_snapshot.last_stopped_at_utc is None:
                    self._live_stream_snapshot.last_stopped_at_utc = (
                        _current_utc_timestamp_iso8601()
                    )
                return copy.deepcopy(self._live_stream_snapshot.to_dict())

            self._live_stream_snapshot.status = "stopping"
            self._stop_live_stream_event.set()

        live_stream_thread.join(timeout=2.0)
        with self._lock:
            if self._live_stream_thread is None or not self._live_stream_thread.is_alive():
                self._live_stream_snapshot.status = "stopped"
                self._live_stream_snapshot.last_stopped_at_utc = (
                    _current_utc_timestamp_iso8601()
                )
            return copy.deepcopy(self._live_stream_snapshot.to_dict())

    def close(self) -> None:
        """Stop background activity during application shutdown."""

        self.stop_live_stream()
        self._audio_input_service.close()

    def _run_live_stream_loop(self) -> None:
        """Continuously regenerate and apply scenes until stopped.

        The controller does not keep one precomputed scene and replay it.  It
        rebuilds the scene every loop so time, pointer motion, and live audio
        can keep influencing the result.
        """

        with self._lock:
            self._live_stream_snapshot.status = "running"

        try:
            while not self._stop_live_stream_event.is_set():
                loop_started_at = time.perf_counter()
                preview_bundle = self.preview_scene_bundle()
                apply_result = self._apply_preview_bundle(preview_bundle)
                self._record_live_stream_attempt(
                    preview_bundle=preview_bundle,
                    apply_result=apply_result,
                )

                effective_cadence_in_milliseconds = self.live_stream_snapshot()["cadence_ms"]
                elapsed_seconds = time.perf_counter() - loop_started_at
                remaining_seconds = max(
                    0.0,
                    effective_cadence_in_milliseconds / 1000.0 - elapsed_seconds,
                )
                self._stop_live_stream_event.wait(remaining_seconds)
        except Exception as error:  # pragma: no cover - depends on timing and machine failures.
            with self._lock:
                self._live_stream_snapshot.status = "error"
                self._live_stream_snapshot.last_error = str(error)
                self._live_stream_snapshot.last_submission_reason = "exception"
                self._live_stream_snapshot.last_stopped_at_utc = (
                    _current_utc_timestamp_iso8601()
                )
        finally:
            with self._lock:
                if self._live_stream_snapshot.status != "error":
                    self._live_stream_snapshot.status = "stopped"
                    self._live_stream_snapshot.last_stopped_at_utc = (
                        _current_utc_timestamp_iso8601()
                    )
                self._live_stream_thread = None

    def _apply_preview_bundle(self, preview_bundle: dict[str, Any]) -> dict[str, Any]:
        """Submit one already-generated preview bundle to the live renderer."""

        target = preview_bundle["target"]
        scene_json = json.dumps(preview_bundle["scene"], separators=(",", ":"))
        response = self._render_api_client.apply_scene(
            host=str(target["host"]),
            port=int(target["port"]),
            scene_json=scene_json,
        )
        if response.status in (200, 202):
            status = "applied"
        elif response.status == 400:
            status = "validation-failed"
        elif response.status == 0:
            status = "offline"
        else:
            status = "apply-failed"

        return {
            "status": status,
            "bundle": preview_bundle,
            "response": response,
            "networkBytes": len(scene_json.encode("utf-8")),
        }

    def _build_effective_payload(self) -> dict[str, Any]:
        """Inject fresh time and audio data into the editable control payload.

        The GUI stores a user-editable payload, but some parts of that payload
        should be "live" rather than static.  Time always moves forward, and
        the latest audio snapshot changes whenever capture is active.
        """

        with self._lock:
            effective_request_payload = copy.deepcopy(self._current_request_payload)
            cadence_in_milliseconds = int(
                effective_request_payload.get("session", {}).get("cadenceMs", 125)
            )
            self._live_stream_snapshot.cadence_ms = _clamp_int(
                cadence_in_milliseconds,
                125,
                40,
                1000,
            )

        signals = effective_request_payload.setdefault("signals", {})
        signals["epochSeconds"] = time.time()
        audio_snapshot = self._audio_input_service.snapshot()
        signals["audio"] = {
            "level": audio_snapshot.level,
            "bass": audio_snapshot.bass,
            "mid": audio_snapshot.mid,
            "treble": audio_snapshot.treble,
        }
        return effective_request_payload

    def _record_live_stream_attempt(
        self,
        *,
        preview_bundle: dict[str, Any],
        apply_result: dict[str, Any],
    ) -> None:
        response = apply_result["response"]
        with self._lock:
            self._live_stream_snapshot.frames_attempted += 1
            self._live_stream_snapshot.last_analysis = preview_bundle["analysis"]
            self._live_stream_snapshot.last_submission_status = response.status
            self._live_stream_snapshot.last_submission_reason = response.reason

            if apply_result["status"] == "applied":
                self._live_stream_snapshot.frames_applied += 1
                self._live_stream_snapshot.last_error = ""
                self._live_stream_snapshot.last_applied_at_utc = (
                    _current_utc_timestamp_iso8601()
                )
                return

            self._live_stream_snapshot.frames_failed += 1
            self._live_stream_snapshot.last_error = response.body[:500]


def _deep_merge(target: dict[str, Any], update: dict[str, Any]) -> None:
    """Recursively merge nested dictionaries in-place.

    This lets the UI submit tiny partial edits such as
    `{"settings": {"speed": 1.5}}` without rebuilding the entire payload by
    hand every time a single slider moves.
    """

    for key, value in update.items():
        if isinstance(value, dict):
            child = target.get(key)
            if not isinstance(child, dict):
                child = {}
                target[key] = child
            _deep_merge(child, value)
        else:
            target[key] = value


def _clamp_float(value: object, default: float, lower: float, upper: float) -> float:
    """Coerce a value to float and keep it inside an allowed range."""

    if not isinstance(value, (bool, int, float, str)):
        coerced = default
    else:
        try:
            coerced = float(value)
        except (TypeError, ValueError):
            coerced = default
    return max(lower, min(upper, coerced))


def _clamp_int(value: object, default: int, lower: int, upper: int) -> int:
    """Coerce a value to int and keep it inside an allowed range."""

    if not isinstance(value, (bool, int, float, str)):
        coerced = default
    else:
        try:
            coerced = int(value)
        except (TypeError, ValueError):
            coerced = default
    return max(lower, min(upper, coerced))
