"""Controller logic for the shared multi-renderer data-source desktop app.

The window should only worry about widgets, button clicks, and value bindings.
This controller owns the harder operational jobs:

- capturing audio safely
- remembering the editable request payload
- converting one source snapshot into one or two renderer scene payloads
- validating or applying those scenes through Halcyn's renderer API
- keeping a background live-stream loop running at a chosen cadence

That split makes the logic far easier to test and far easier for a beginner to
read in pieces.
"""

from __future__ import annotations

import copy
import json
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from desktop_multi_renderer_data_source_panel.multi_renderer_data_source_builder import (
    MultiRendererPreviewBundle,
    build_catalog_payload,
    build_default_request_payload,
    build_multi_renderer_preview_bundle,
)
from desktop_shared_control_support.activity_log import DesktopActivityLogger
from desktop_shared_control_support.audio_input_service import (
    AudioDeviceDescriptor,
    AudioSignalSnapshot,
    DesktopAudioInputService,
)
from desktop_shared_control_support.local_json_bridge import LocalJsonBridgeServer
from desktop_shared_control_support.render_api_client import RenderApiClient, RenderApiResponse


def _current_utc_timestamp_iso8601() -> str:
    """Return a readable UTC timestamp for status displays and diagnostics."""

    return datetime.now(timezone.utc).isoformat()


@dataclass
class MultiRendererLiveStreamSnapshot:
    """Describe the current background streaming worker state."""

    status: str = "stopped"
    cadence_ms: int = 125
    cycles_attempted: int = 0
    classic_frames_applied: int = 0
    spectrograph_frames_applied: int = 0
    failed_target_count: int = 0
    last_submission_statuses: dict[str, int] = field(default_factory=dict)
    last_error: str = ""
    last_started_at_utc: str | None = None
    last_stopped_at_utc: str | None = None
    last_applied_at_utc: str | None = None
    last_source_analysis: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready copy of the live-stream status."""

        return asdict(self)


@dataclass
class MultiRendererExternalSourceStatus:
    """Describe the newest JSON document received through the local bridge."""

    latest_source_label: str = ""
    latest_received_at_utc: str = ""
    latest_json_text: str = ""
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready copy of the external-source state."""

        return asdict(self)


class RenderApiClientProtocol(Protocol):
    """Small renderer-client surface required by this controller."""

    def health(self, host: str, port: int) -> RenderApiResponse: ...

    def validate_scene(self, host: str, port: int, scene_json: str) -> RenderApiResponse: ...

    def apply_scene(self, host: str, port: int, scene_json: str) -> RenderApiResponse: ...


class AudioInputServiceProtocol(Protocol):
    """Small audio-service surface required by this controller."""

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


class MultiRendererDataSourceController:
    """Own the non-visual behavior behind the shared data-source panel."""

    def __init__(
        self,
        render_api_client: RenderApiClientProtocol | None = None,
        audio_input_service: AudioInputServiceProtocol | None = None,
        activity_logger: DesktopActivityLogger | None = None,
    ) -> None:
        self._render_api_client = render_api_client or RenderApiClient()
        self._audio_input_service = audio_input_service or DesktopAudioInputService()
        self._activity_logger = activity_logger or DesktopActivityLogger(
            application_name="signal-router"
        )
        self._lock = threading.Lock()
        self._current_request_payload = build_default_request_payload()
        self._live_stream_snapshot = MultiRendererLiveStreamSnapshot(
            cadence_ms=int(self._current_request_payload["session"]["cadenceMs"])
        )
        self._live_stream_thread: threading.Thread | None = None
        self._stop_live_stream_event = threading.Event()
        self._spectrograph_rolling_history_values: list[float] = []
        self._external_source_status = MultiRendererExternalSourceStatus()
        self._external_json_bridge_server = self._build_external_json_bridge_server()
        self._external_json_bridge_status = self._start_external_json_bridge_server()

    def catalog_payload(self) -> dict[str, Any]:
        """Return metadata used to build the desktop window."""

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
                125,
            )
            should_restart_bridge = self._external_json_bridge_configuration_changed()
            updated_payload = copy.deepcopy(self._current_request_payload)
        if should_restart_bridge:
            self._external_json_bridge_status = self._restart_external_json_bridge_server()
        return updated_payload

    def replace_request_payload(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        """Replace the current payload with a normalized saved document."""

        with self._lock:
            self._current_request_payload = build_default_request_payload()
            _deep_merge(self._current_request_payload, copy.deepcopy(request_payload))
            self._live_stream_snapshot.cadence_ms = _safe_int(
                self._current_request_payload.get("session", {}).get("cadenceMs"),
                125,
            )
            updated_payload = copy.deepcopy(self._current_request_payload)
        self._external_json_bridge_status = self._restart_external_json_bridge_server()
        return updated_payload

    def reset_to_defaults(self) -> dict[str, Any]:
        """Restore the default payload and clear spectrograph history."""

        with self._lock:
            self._current_request_payload = build_default_request_payload()
            self._spectrograph_rolling_history_values = []
            self._external_source_status = MultiRendererExternalSourceStatus()
            self._live_stream_snapshot = MultiRendererLiveStreamSnapshot(
                cadence_ms=int(self._current_request_payload["session"]["cadenceMs"])
            )
            updated_payload = copy.deepcopy(self._current_request_payload)
        self._external_json_bridge_status = self._restart_external_json_bridge_server()
        return updated_payload

    def settings_document(self) -> dict[str, Any]:
        """Return a versioned settings document suitable for saving to disk."""

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
        """Refresh the available device list for one input or output flow."""

        safe_device_flow = (
            device_flow
            or self.current_request_payload()["source"]["audio"]["deviceFlow"]
        )
        return self._audio_input_service.refresh_devices(safe_device_flow)

    def audio_snapshot(self) -> AudioSignalSnapshot:
        """Return the latest audio snapshot known to the audio service."""

        return self._audio_input_service.snapshot()

    def start_audio_capture(
        self,
        device_identifier: str | None = None,
        device_flow: str | None = None,
    ) -> AudioSignalSnapshot:
        """Start audio capture on the selected device and remember that selection."""

        request_payload = self.current_request_payload()
        chosen_device_identifier = device_identifier or str(
            request_payload["source"]["audio"].get("deviceIdentifier", "")
        )
        chosen_device_flow = device_flow or str(
            request_payload["source"]["audio"].get("deviceFlow", "output")
        )
        if not chosen_device_identifier:
            raise ValueError("Choose an audio device before starting capture.")
        snapshot = self._audio_input_service.start_capture(
            chosen_device_identifier,
            chosen_device_flow,
        )
        self._activity_logger.log(
            component_name="audio-capture",
            level="INFO",
            message="Started audio capture for the shared signal router.",
            details={
                "deviceIdentifier": chosen_device_identifier,
                "deviceFlow": chosen_device_flow,
            },
        )
        self.update_request_payload(
            {
                "source": {
                    "audio": {
                        "deviceIdentifier": chosen_device_identifier,
                        "deviceFlow": chosen_device_flow,
                    }
                }
            }
        )
        return snapshot

    def stop_audio_capture(self) -> AudioSignalSnapshot:
        """Stop audio capture and return the resulting idle snapshot."""

        stopped_snapshot = self._audio_input_service.stop_capture()
        self._activity_logger.log(
            component_name="audio-capture",
            level="INFO",
            message="Stopped audio capture for the shared signal router.",
            details={
                "deviceIdentifier": stopped_snapshot.device_identifier,
                "deviceName": stopped_snapshot.device_name,
            },
        )
        return stopped_snapshot

    def update_pointer_signal(self, normalized_x: float, normalized_y: float, speed: float) -> None:
        """Store the latest pointer-pad sample sent by the window."""

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

    def preview_bundle(self) -> MultiRendererPreviewBundle:
        """Build the current preview bundle without mutating live state."""

        with self._lock:
            request_payload = copy.deepcopy(self._current_request_payload)
            spectrograph_rolling_history_values = list(self._spectrograph_rolling_history_values)
            latest_external_json_text = self._external_source_status.latest_json_text
        return build_multi_renderer_preview_bundle(
            request_payload=request_payload,
            audio_signal_snapshot=self._audio_input_service.snapshot(),
            spectrograph_rolling_history_values=spectrograph_rolling_history_values,
            latest_external_json_text=latest_external_json_text,
        )

    def health_selected_targets(self) -> dict[str, Any]:
        """Run renderer health checks for whichever targets are enabled."""

        preview_bundle = self.preview_bundle()
        responses: dict[str, RenderApiResponse] = {}
        normalized_request_payload = preview_bundle.normalized_request_payload
        if normalized_request_payload["targets"]["classic"]["enabled"]:
            responses["classic"] = self._render_api_client.health(
                host=str(normalized_request_payload["targets"]["classic"]["host"]),
                port=int(normalized_request_payload["targets"]["classic"]["port"]),
            )
        if normalized_request_payload["targets"]["spectrograph"]["enabled"]:
            responses["spectrograph"] = self._render_api_client.health(
                host=str(normalized_request_payload["targets"]["spectrograph"]["host"]),
                port=int(normalized_request_payload["targets"]["spectrograph"]["port"]),
            )
        return {
            "status": _summarize_multi_target_status(
                responses,
                success_statuses={200},
                success_label="healthy",
                failure_label="health-check-failed",
            ),
            "previewBundle": preview_bundle,
            "responses": responses,
        }

    def validate_selected_targets(self) -> dict[str, Any]:
        """Validate the currently selected targets against live renderer APIs."""

        preview_bundle = self.preview_bundle()
        responses = self._submit_preview_bundle(preview_bundle, submission_kind="validate")
        return {
            "status": _summarize_multi_target_status(
                responses,
                success_statuses={200},
                success_label="validated",
                failure_label="validation-failed",
            ),
            "previewBundle": preview_bundle,
            "responses": responses,
        }

    def apply_selected_targets(self) -> dict[str, Any]:
        """Apply the currently selected targets and commit spectrograph history on success."""

        preview_bundle = self.preview_bundle()
        responses = self._submit_preview_bundle(preview_bundle, submission_kind="apply")
        if (
            preview_bundle.spectrograph_build_result is not None
            and responses.get("spectrograph") is not None
            and responses["spectrograph"].status == 202
        ):
            with self._lock:
                self._spectrograph_rolling_history_values = list(
                    preview_bundle.spectrograph_build_result.next_rolling_history_values
                )

        return {
            "status": _summarize_multi_target_status(
                responses,
                success_statuses={202},
                success_label="applied",
                failure_label="apply-failed",
            ),
            "previewBundle": preview_bundle,
            "responses": responses,
        }

    def live_stream_snapshot(self) -> dict[str, Any]:
        """Return a copy of the current live-stream worker state."""

        with self._lock:
            return self._live_stream_snapshot.to_dict()

    def external_source_status(self) -> dict[str, Any]:
        """Return the latest external-source state together with bridge status."""

        with self._lock:
            external_source_status = self._external_source_status.to_dict()
            bridge_status = copy.deepcopy(self._external_json_bridge_status)
        external_source_status["bridge"] = bridge_status
        return external_source_status

    def start_live_stream(self) -> dict[str, Any]:
        """Start repeatedly applying the selected targets at the chosen cadence."""

        with self._lock:
            if self._live_stream_thread is not None and self._live_stream_thread.is_alive():
                return self._live_stream_snapshot.to_dict()

            self._stop_live_stream_event.clear()
            self._live_stream_snapshot.status = "running"
            self._live_stream_snapshot.cadence_ms = _safe_int(
                self._current_request_payload.get("session", {}).get("cadenceMs"),
                125,
            )
            self._live_stream_snapshot.last_error = ""
            self._live_stream_snapshot.last_started_at_utc = _current_utc_timestamp_iso8601()
            self._live_stream_thread = threading.Thread(
                target=self._run_live_stream_loop,
                name="desktop-multi-renderer-data-source-live-stream",
                daemon=True,
            )
            self._live_stream_thread.start()
            self._activity_logger.log(
                component_name="live-stream",
                level="INFO",
                message="Started the shared signal-router live stream.",
                details={"cadenceMs": self._live_stream_snapshot.cadence_ms},
            )
            return self._live_stream_snapshot.to_dict()

    def stop_live_stream(self) -> dict[str, Any]:
        """Request a clean stop for the background live-stream worker."""

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
            message="Stopped the shared signal-router live stream.",
            details={
                "cyclesAttempted": stopped_snapshot["cycles_attempted"],
                "classicFramesApplied": stopped_snapshot["classic_frames_applied"],
                "spectrographFramesApplied": stopped_snapshot["spectrograph_frames_applied"],
            },
        )
        return stopped_snapshot

    def close(self) -> None:
        """Shut down background work and release audio resources on exit."""

        self.stop_live_stream()
        self._external_json_bridge_status = self._stop_external_json_bridge_server()
        self._audio_input_service.close()

    def _build_external_json_bridge_server(self) -> LocalJsonBridgeServer:
        """Create the local bridge that lets helper apps send JSON into this studio."""

        bridge_settings = self._current_request_payload["externalJsonBridge"]
        return LocalJsonBridgeServer(
            host=str(bridge_settings["host"]),
            port=int(bridge_settings["port"]),
            on_json_received=self._accept_external_json_from_bridge,
        )

    def _start_external_json_bridge_server(self) -> dict[str, Any]:
        """Start the local bridge and convert startup failures into status data."""

        try:
            started_status = self._external_json_bridge_server.start()
            self._activity_logger.log(
                component_name="external-json-bridge",
                level="INFO",
                message="Started the shared signal-router external JSON bridge.",
                details=started_status,
            )
            return started_status
        except Exception as error:
            error_message = str(error)
            self._activity_logger.log(
                component_name="external-json-bridge",
                level="ERROR",
                message="Could not start the shared signal-router external JSON bridge.",
                details={"error": error_message},
            )
            return {
                "host": str(self._current_request_payload["externalJsonBridge"]["host"]),
                "port": int(self._current_request_payload["externalJsonBridge"]["port"]),
                "listening": False,
                "last_received_at_utc": "",
                "last_source_label": "",
                "last_payload_size_bytes": 0,
                "last_error": error_message,
            }

    def _stop_external_json_bridge_server(self) -> dict[str, Any]:
        """Stop the local bridge and return its final status snapshot."""

        try:
            return self._external_json_bridge_server.stop()
        except Exception as error:
            return {
                "host": str(self._current_request_payload["externalJsonBridge"]["host"]),
                "port": int(self._current_request_payload["externalJsonBridge"]["port"]),
                "listening": False,
                "last_received_at_utc": "",
                "last_source_label": "",
                "last_payload_size_bytes": 0,
                "last_error": str(error),
            }

    def _restart_external_json_bridge_server(self) -> dict[str, Any]:
        """Recreate the bridge server after its host or port settings change."""

        self._stop_external_json_bridge_server()
        self._external_json_bridge_server = self._build_external_json_bridge_server()
        return self._start_external_json_bridge_server()

    def _external_json_bridge_configuration_changed(self) -> bool:
        """Return whether the payload no longer matches the active bridge server."""

        configured_bridge = self._current_request_payload["externalJsonBridge"]
        current_status = self._external_json_bridge_status
        return (
            str(configured_bridge["host"]) != str(current_status.get("host", ""))
            or int(configured_bridge["port"]) != int(current_status.get("port", 0))
        )

    def _accept_external_json_from_bridge(self, json_text: str, source_label: str) -> None:
        """Record the newest external JSON document sent into the signal router."""

        with self._lock:
            self._external_source_status.latest_json_text = json_text
            self._external_source_status.latest_source_label = source_label
            self._external_source_status.latest_received_at_utc = _current_utc_timestamp_iso8601()
            self._external_source_status.last_error = ""

        self._activity_logger.log(
            component_name="external-json-bridge",
            level="INFO",
            message="Received external JSON for the shared signal router.",
            details={
                "sourceLabel": source_label,
                "payloadSizeBytes": len(json_text.encode("utf-8")),
            },
        )

    def _submit_preview_bundle(
        self,
        preview_bundle: MultiRendererPreviewBundle,
        submission_kind: str,
        unchanged_scene_json_by_target: dict[str, str] | None = None,
    ) -> dict[str, RenderApiResponse]:
        """Send preview scenes to the enabled targets for validation or apply."""

        responses: dict[str, RenderApiResponse] = {}
        if preview_bundle.classic_scene_bundle is not None:
            classic_target = preview_bundle.normalized_request_payload["targets"]["classic"]
            classic_scene_json = json.dumps(
                preview_bundle.classic_scene_bundle["scene"],
                separators=(",", ":"),
            )
            if (
                submission_kind == "apply"
                and unchanged_scene_json_by_target is not None
                and unchanged_scene_json_by_target.get("classic") == classic_scene_json
            ):
                responses["classic"] = RenderApiResponse(
                    True,
                    202,
                    "Skipped",
                    '{"status":"unchanged"}',
                    {},
                )
            elif submission_kind == "validate":
                responses["classic"] = self._render_api_client.validate_scene(
                    host=str(classic_target["host"]),
                    port=int(classic_target["port"]),
                    scene_json=classic_scene_json,
                )
            else:
                responses["classic"] = self._render_api_client.apply_scene(
                    host=str(classic_target["host"]),
                    port=int(classic_target["port"]),
                    scene_json=classic_scene_json,
                )

        if preview_bundle.spectrograph_build_result is not None:
            spectrograph_target = preview_bundle.normalized_request_payload["targets"][
                "spectrograph"
            ]
            spectrograph_scene_json = json.dumps(
                preview_bundle.spectrograph_build_result.scene,
                separators=(",", ":"),
            )
            if (
                submission_kind == "apply"
                and unchanged_scene_json_by_target is not None
                and unchanged_scene_json_by_target.get("spectrograph") == spectrograph_scene_json
            ):
                responses["spectrograph"] = RenderApiResponse(
                    True,
                    202,
                    "Skipped",
                    '{"status":"unchanged"}',
                    {},
                )
            elif submission_kind == "validate":
                responses["spectrograph"] = self._render_api_client.validate_scene(
                    host=str(spectrograph_target["host"]),
                    port=int(spectrograph_target["port"]),
                    scene_json=spectrograph_scene_json,
                )
            else:
                responses["spectrograph"] = self._render_api_client.apply_scene(
                    host=str(spectrograph_target["host"]),
                    port=int(spectrograph_target["port"]),
                    scene_json=spectrograph_scene_json,
                )
        return responses

    def _run_live_stream_loop(self) -> None:
        """Continuously apply the selected targets until the caller requests a stop."""

        last_submitted_scene_json_by_target: dict[str, str] = {}
        while not self._stop_live_stream_event.is_set():
            cycle_started_at = time.monotonic()
            try:
                preview_bundle = self.preview_bundle()
                current_scene_json_by_target: dict[str, str] = {}
                if preview_bundle.classic_scene_bundle is not None:
                    current_scene_json_by_target["classic"] = json.dumps(
                        preview_bundle.classic_scene_bundle["scene"],
                        separators=(",", ":"),
                    )
                if preview_bundle.spectrograph_build_result is not None:
                    current_scene_json_by_target["spectrograph"] = json.dumps(
                        preview_bundle.spectrograph_build_result.scene,
                        separators=(",", ":"),
                    )

                responses = self._submit_preview_bundle(
                    preview_bundle,
                    submission_kind="apply",
                    unchanged_scene_json_by_target=last_submitted_scene_json_by_target,
                )
                for target_name, response in responses.items():
                    if response.reason in {"Accepted", "Skipped"}:
                        last_submitted_scene_json_by_target[target_name] = (
                            current_scene_json_by_target.get(target_name, "")
                        )
                with self._lock:
                    self._live_stream_snapshot.cycles_attempted += 1
                    self._live_stream_snapshot.last_source_analysis = (
                        preview_bundle.collected_source_data.analysis
                    )
                    self._live_stream_snapshot.last_submission_statuses = {
                        target_name: response.status for target_name, response in responses.items()
                    }
                    if (
                        preview_bundle.spectrograph_build_result is not None
                        and responses.get("spectrograph") is not None
                        and responses["spectrograph"].status == 202
                    ):
                        self._spectrograph_rolling_history_values = list(
                            preview_bundle.spectrograph_build_result.next_rolling_history_values
                        )

                    if responses.get("classic") is not None and responses["classic"].status == 202:
                        self._live_stream_snapshot.classic_frames_applied += 1
                    if (
                        responses.get("spectrograph") is not None
                        and responses["spectrograph"].status == 202
                    ):
                        self._live_stream_snapshot.spectrograph_frames_applied += 1
                    for response in responses.values():
                        if response.status != 202:
                            self._live_stream_snapshot.failed_target_count += 1
                            self._live_stream_snapshot.last_error = response.body or response.reason
                    self._live_stream_snapshot.last_applied_at_utc = (
                        _current_utc_timestamp_iso8601()
                    )
            except Exception as error:  # pragma: no cover - live thread timing varies by machine.
                with self._lock:
                    self._live_stream_snapshot.cycles_attempted += 1
                    self._live_stream_snapshot.failed_target_count += 1
                    self._live_stream_snapshot.status = "error"
                    self._live_stream_snapshot.last_error = str(error)
                break

            with self._lock:
                cadence_ms = self._live_stream_snapshot.cadence_ms

            elapsed_seconds = time.monotonic() - cycle_started_at
            remaining_seconds = max(0.0, (cadence_ms / 1000.0) - elapsed_seconds)
            if remaining_seconds > 0.0:
                self._stop_live_stream_event.wait(remaining_seconds)


def _summarize_multi_target_status(
    responses: dict[str, RenderApiResponse],
    *,
    success_statuses: set[int],
    success_label: str,
    failure_label: str,
) -> str:
    """Summarize one set of target responses into a single high-level label."""

    if not responses:
        return "no-targets-selected"
    if all(response.status in success_statuses for response in responses.values()):
        return success_label
    return failure_label


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
            _deep_merge(base[key], value)
        else:
            base[key] = value
