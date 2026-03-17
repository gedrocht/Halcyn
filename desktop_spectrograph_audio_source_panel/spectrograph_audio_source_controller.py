"""Controller logic for the desktop spectrograph audio-source panel.

This controller sits between the Tkinter window and the lower-level helpers.
Its responsibilities are:

- managing the editable request payload
- asking the shared audio service for devices and snapshots
- keeping a rolling history of recent audio frames
- turning that history into the generic JSON document expected by the
  spectrograph control panel
- sending that document to the local external-data bridge on demand or on a
  repeating cadence
"""

from __future__ import annotations

import copy
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from desktop_shared_control_support.audio_input_service import (
    AudioDeviceDescriptor,
    AudioSignalSnapshot,
    DesktopAudioInputService,
)
from desktop_spectrograph_audio_source_panel.spectrograph_audio_source_builder import (
    SpectrographAudioSourcePreview,
    build_audio_source_preview,
    build_catalog_payload,
    build_default_request_payload,
)
from desktop_spectrograph_audio_source_panel.spectrograph_external_bridge_client import (
    SpectrographExternalBridgeClient,
    SpectrographExternalBridgeResponse,
)


def _current_utc_timestamp_iso8601() -> str:
    """Return a readable UTC timestamp for UI status fields."""

    return datetime.now(timezone.utc).isoformat()


@dataclass
class AudioBridgeLiveSendSnapshot:
    """Describe the current repeating-send worker state."""

    status: str = "stopped"
    cadence_ms: int = 125
    deliveries_attempted: int = 0
    deliveries_succeeded: int = 0
    deliveries_failed: int = 0
    last_error: str = ""
    last_status_code: int | None = None
    last_reason: str = "idle"
    last_started_at_utc: str = ""
    last_sent_at_utc: str = ""
    last_stopped_at_utc: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready copy of the live-send state."""

        return asdict(self)


class AudioInputServiceProtocol(Protocol):
    """Small audio-service surface required by the controller."""

    def devices(self, device_flow: str = "input") -> list[AudioDeviceDescriptor]:
        ...

    def refresh_devices(self, device_flow: str = "input") -> list[AudioDeviceDescriptor]:
        ...

    def snapshot(self) -> AudioSignalSnapshot:
        ...

    def start_capture(
        self,
        device_identifier: str,
        device_flow: str = "input",
    ) -> AudioSignalSnapshot:
        ...

    def stop_capture(self) -> AudioSignalSnapshot:
        ...

    def close(self) -> None:
        ...


class SpectrographExternalBridgeClientProtocol(Protocol):
    """Small bridge-client surface required by the controller."""

    def deliver_json_text(
        self,
        *,
        host: str,
        port: int,
        path: str,
        source_label: str,
        json_text: str,
    ) -> SpectrographExternalBridgeResponse:
        ...


class DesktopSpectrographAudioSourceController:
    """Own the non-visual behavior behind the spectrograph audio-source panel."""

    def __init__(
        self,
        audio_input_service: AudioInputServiceProtocol | None = None,
        spectrograph_external_bridge_client: SpectrographExternalBridgeClientProtocol | None = None,
    ) -> None:
        self._audio_input_service = audio_input_service or DesktopAudioInputService()
        self._spectrograph_external_bridge_client = (
            spectrograph_external_bridge_client or SpectrographExternalBridgeClient()
        )
        self._lock = threading.Lock()
        self._current_request_payload = build_default_request_payload()
        self._recent_audio_signal_snapshots: list[AudioSignalSnapshot] = []
        self._live_send_snapshot = AudioBridgeLiveSendSnapshot(
            cadence_ms=int(self._current_request_payload["session"]["cadenceMs"])
        )
        self._stop_live_send_event = threading.Event()
        self._live_send_thread: threading.Thread | None = None

    def catalog_payload(self) -> dict[str, Any]:
        """Return metadata that helps the window build device-flow selectors."""

        return build_catalog_payload()

    def current_request_payload(self) -> dict[str, Any]:
        """Return a deep copy of the editable payload."""

        with self._lock:
            return copy.deepcopy(self._current_request_payload)

    def update_request_payload(self, update: dict[str, Any]) -> dict[str, Any]:
        """Deep-merge a partial UI update into the current payload."""

        with self._lock:
            _deep_merge(self._current_request_payload, update)
            self._live_send_snapshot.cadence_ms = _safe_int(
                self._current_request_payload.get("session", {}).get("cadenceMs"),
                125,
            )
            return copy.deepcopy(self._current_request_payload)

    def replace_request_payload(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        """Replace the current payload with a fresh saved document."""

        with self._lock:
            self._current_request_payload = build_default_request_payload()
            _deep_merge(self._current_request_payload, copy.deepcopy(request_payload))
            self._live_send_snapshot.cadence_ms = _safe_int(
                self._current_request_payload.get("session", {}).get("cadenceMs"),
                125,
            )
            return copy.deepcopy(self._current_request_payload)

    def reset_to_defaults(self) -> dict[str, Any]:
        """Restore the default payload and clear audio history."""

        with self._lock:
            self._current_request_payload = build_default_request_payload()
            self._recent_audio_signal_snapshots = []
            self._live_send_snapshot = AudioBridgeLiveSendSnapshot(
                cadence_ms=int(self._current_request_payload["session"]["cadenceMs"])
            )
            return copy.deepcopy(self._current_request_payload)

    def settings_document(self) -> dict[str, Any]:
        """Return a versioned settings document suitable for saving to disk."""

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

    def refresh_audio_devices(self, device_flow: str | None = None) -> list[AudioDeviceDescriptor]:
        """Refresh the available device list for the requested flow."""

        current_request_payload = self.current_request_payload()
        current_audio_settings = current_request_payload["audio"]
        safe_device_flow = device_flow or str(current_audio_settings["deviceFlow"])
        return self._audio_input_service.refresh_devices(safe_device_flow)

    def audio_snapshot(self) -> AudioSignalSnapshot:
        """Return the latest audio snapshot known to the audio service."""

        return self._audio_input_service.snapshot()

    def start_audio_capture(
        self,
        device_identifier: str | None = None,
        device_flow: str | None = None,
    ) -> AudioSignalSnapshot:
        """Start audio capture on the selected device and remember that choice."""

        request_payload = self.current_request_payload()
        current_audio_settings = request_payload["audio"]
        chosen_device_identifier = device_identifier or str(
            current_audio_settings["deviceIdentifier"]
        )
        chosen_device_flow = device_flow or str(
            current_audio_settings["deviceFlow"]
        )
        if not chosen_device_identifier:
            raise ValueError("Choose an audio device before starting capture.")

        started_snapshot = self._audio_input_service.start_capture(
            chosen_device_identifier,
            chosen_device_flow,
        )
        self.update_request_payload(
            {
                "audio": {
                    "deviceIdentifier": chosen_device_identifier,
                    "deviceFlow": chosen_device_flow,
                }
            }
        )
        self._remember_audio_snapshot(started_snapshot)
        return started_snapshot

    def stop_audio_capture(self) -> AudioSignalSnapshot:
        """Stop audio capture and return the idle snapshot."""

        return self._audio_input_service.stop_capture()

    def preview_payload(self) -> SpectrographAudioSourcePreview:
        """Build the outgoing bridge payload without delivering it."""

        latest_audio_signal_snapshot = self._audio_input_service.snapshot()
        self._remember_audio_snapshot(latest_audio_signal_snapshot)
        with self._lock:
            request_payload = copy.deepcopy(self._current_request_payload)
            recent_audio_signal_snapshots = list(self._recent_audio_signal_snapshots)
        return build_audio_source_preview(
            request_payload=request_payload,
            latest_audio_signal_snapshot=latest_audio_signal_snapshot,
            recent_audio_signal_snapshots=recent_audio_signal_snapshots,
        )

    def deliver_once(self) -> dict[str, Any]:
        """Send the current generated audio JSON document to the local bridge once."""

        preview = self.preview_payload()
        bridge_settings = preview.normalized_request_payload["bridge"]
        response = self._spectrograph_external_bridge_client.deliver_json_text(
            host=str(bridge_settings["host"]),
            port=int(bridge_settings["port"]),
            path=str(bridge_settings["path"]),
            source_label=str(bridge_settings["sourceLabel"]),
            json_text=preview.generated_json_text,
        )
        with self._lock:
            self._live_send_snapshot.deliveries_attempted += 1
            self._live_send_snapshot.last_status_code = response.status
            self._live_send_snapshot.last_reason = response.reason
            if response.ok:
                self._live_send_snapshot.deliveries_succeeded += 1
                self._live_send_snapshot.last_sent_at_utc = _current_utc_timestamp_iso8601()
                self._live_send_snapshot.last_error = ""
            else:
                self._live_send_snapshot.deliveries_failed += 1
                self._live_send_snapshot.last_error = response.body or response.reason

        return {
            "status": "delivered" if response.ok else "delivery-failed",
            "preview": preview,
            "response": response,
        }

    def live_send_snapshot(self) -> dict[str, Any]:
        """Return a copy of the repeating-send worker state."""

        with self._lock:
            return self._live_send_snapshot.to_dict()

    def start_live_send(self) -> dict[str, Any]:
        """Start the repeating bridge-delivery loop."""

        with self._lock:
            if self._live_send_thread is not None and self._live_send_thread.is_alive():
                return self._live_send_snapshot.to_dict()

            self._stop_live_send_event.clear()
            self._live_send_snapshot.status = "running"
            self._live_send_snapshot.cadence_ms = _safe_int(
                self._current_request_payload.get("session", {}).get("cadenceMs"),
                125,
            )
            self._live_send_snapshot.last_error = ""
            self._live_send_snapshot.last_started_at_utc = _current_utc_timestamp_iso8601()
            self._live_send_thread = threading.Thread(
                target=self._run_live_send_loop,
                name="desktop-spectrograph-audio-live-send",
                daemon=True,
            )
            self._live_send_thread.start()
            return self._live_send_snapshot.to_dict()

    def stop_live_send(self) -> dict[str, Any]:
        """Request a clean stop for the repeating-send worker."""

        live_send_thread: threading.Thread | None
        with self._lock:
            self._stop_live_send_event.set()
            live_send_thread = self._live_send_thread

        if live_send_thread is not None:
            live_send_thread.join(timeout=2.0)

        with self._lock:
            self._live_send_thread = None
            self._live_send_snapshot.status = "stopped"
            self._live_send_snapshot.last_stopped_at_utc = _current_utc_timestamp_iso8601()
            return self._live_send_snapshot.to_dict()

    def close(self) -> None:
        """Shut down capture and worker threads during application exit."""

        self.stop_live_send()
        self._audio_input_service.close()

    def _run_live_send_loop(self) -> None:
        """Deliver the current preview repeatedly until the caller requests a stop."""

        while not self._stop_live_send_event.is_set():
            cycle_started_at = time.monotonic()
            try:
                self.deliver_once()
            except Exception as error:  # pragma: no cover - thread timing varies by environment.
                with self._lock:
                    self._live_send_snapshot.status = "error"
                    self._live_send_snapshot.deliveries_failed += 1
                    self._live_send_snapshot.last_error = str(error)
                break

            with self._lock:
                cadence_ms = self._live_send_snapshot.cadence_ms

            elapsed_seconds = time.monotonic() - cycle_started_at
            remaining_seconds = max(0.0, (cadence_ms / 1000.0) - elapsed_seconds)
            if remaining_seconds > 0.0:
                self._stop_live_send_event.wait(remaining_seconds)

    def _remember_audio_snapshot(self, audio_signal_snapshot: AudioSignalSnapshot) -> None:
        """Append the latest snapshot to the rolling history buffer.

        The spectrograph control panel works best when it receives a rolling
        window of audio frames rather than a single four-number snapshot. This
        method keeps that history clipped to the user-selected frame count.
        """

        with self._lock:
            self._recent_audio_signal_snapshots.append(copy.deepcopy(audio_signal_snapshot))
            requested_history_frame_count = _safe_int(
                self._current_request_payload.get("audio", {}).get("historyFrameCount"),
                72,
            )
            self._recent_audio_signal_snapshots = self._recent_audio_signal_snapshots[
                -requested_history_frame_count:
            ]


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
            nested_base_value = base[key]
            assert isinstance(nested_base_value, dict)
            _deep_merge(nested_base_value, value)
        else:
            base[key] = value
