"""Server-side live session management for Client Studio."""

from __future__ import annotations

import copy
import json
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from control_plane.client_studio import (
    DEFAULT_AUTO_APPLY_MS,
    DEFAULT_PRESET_ID,
    DEFAULT_TARGET_HOST,
    DEFAULT_TARGET_PORT,
    build_scene_bundle,
)

ApplyCallback = Callable[[str, int, str], dict[str, Any]]
LogCallback = Callable[[str, str, str], None]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ClientStudioLiveSnapshot:
    """Describe the current server-side live-stream session."""

    revision: int = 0
    status: str = "stopped"
    preset_id: str = DEFAULT_PRESET_ID
    target_host: str = DEFAULT_TARGET_HOST
    target_port: int = DEFAULT_TARGET_PORT
    cadence_ms: int = DEFAULT_AUTO_APPLY_MS
    frames_attempted: int = 0
    frames_applied: int = 0
    frames_failed: int = 0
    last_submission_status: int | None = None
    last_submission_reason: str = "idle"
    last_error: str = ""
    last_started_at_utc: str | None = None
    last_stopped_at_utc: str | None = None
    last_applied_at_utc: str | None = None
    last_network_bytes: int = 0
    last_analysis: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ClientStudioLiveSession:
    """Own the long-running server-side loop that streams scenes to Halcyn."""

    def __init__(
        self,
        apply_callback: ApplyCallback,
        log_callback: LogCallback,
        stop_join_timeout_seconds: float = 2.0,
    ) -> None:
        self._apply_callback = apply_callback
        self._log_callback = log_callback
        self._lock = threading.Lock()
        self._update_condition = threading.Condition(self._lock)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._stop_join_timeout_seconds = stop_join_timeout_seconds
        self._config = _default_live_payload()
        self._snapshot = ClientStudioLiveSnapshot()
        self._last_logged_failure: tuple[int | None, str] | None = None

    def snapshot(self) -> dict[str, Any]:
        """Return the current session state."""

        with self._lock:
            return copy.deepcopy(self._snapshot.to_dict())

    def wait_for_update(
        self,
        after_revision: int,
        timeout_seconds: float = 15.0,
    ) -> tuple[dict[str, Any], bool]:
        """Wait until the snapshot revision advances or the timeout expires."""

        with self._update_condition:
            changed = self._update_condition.wait_for(
                lambda: self._snapshot.revision > after_revision,
                timeout=timeout_seconds,
            )
            return copy.deepcopy(self._snapshot.to_dict()), changed

    def configure(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Update the desired preset, target, controls, and session cadence."""

        with self._lock:
            self._config = _merge_live_payload(self._config, payload)
            self._snapshot.preset_id = str(self._config.get("presetId", DEFAULT_PRESET_ID))
            target = self._config.get("target", {})
            self._snapshot.target_host = str(target.get("host", DEFAULT_TARGET_HOST))
            self._snapshot.target_port = int(target.get("port", DEFAULT_TARGET_PORT))
            session = self._config.get("session", {})
            self._snapshot.cadence_ms = int(session.get("cadenceMs", DEFAULT_AUTO_APPLY_MS))
            self._mark_updated_locked()
            return copy.deepcopy(self._snapshot.to_dict())

    def start(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Start the live session loop if it is not already running."""

        if payload:
            self.configure(payload)

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return copy.deepcopy(self._snapshot.to_dict())

            self._stop_event = threading.Event()
            self._snapshot.status = "starting"
            self._snapshot.last_started_at_utc = _utc_now_iso()
            self._snapshot.last_stopped_at_utc = None
            self._snapshot.last_error = ""
            self._last_logged_failure = None
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._mark_updated_locked()
            self._thread.start()

        self._log_callback("INFO", "client-studio", "Started the live Client Studio session.")
        return self.snapshot()

    def stop(self) -> dict[str, Any]:
        """Stop the live session loop and return the latest state."""

        thread: threading.Thread | None
        with self._lock:
            thread = self._thread
            if thread is None or not thread.is_alive():
                if self._snapshot.status not in {"stopped", "error"}:
                    self._snapshot.status = "stopped"
                if self._snapshot.last_stopped_at_utc is None:
                    self._snapshot.last_stopped_at_utc = _utc_now_iso()
                self._thread = None
                self._mark_updated_locked()
                return copy.deepcopy(self._snapshot.to_dict())

            self._snapshot.status = "stopping"
            self._stop_event.set()
            self._mark_updated_locked()

        thread.join(timeout=self._stop_join_timeout_seconds)

        with self._lock:
            stopped = self._thread is None or not self._thread.is_alive()
            if stopped:
                self._snapshot.status = "stopped"
                self._snapshot.last_stopped_at_utc = _utc_now_iso()
                self._mark_updated_locked()
            snapshot = copy.deepcopy(self._snapshot.to_dict())

        if stopped:
            self._log_callback("INFO", "client-studio", "Stopped the live Client Studio session.")
        else:
            self._log_callback(
                "WARNING",
                "client-studio",
                (
                    "Stop requested for the live Client Studio session, "
                    "but the current frame is still finishing."
                ),
            )
        return snapshot

    def close(self) -> None:
        """Stop the session during application shutdown."""

        self.stop()

    def _run_loop(self) -> None:
        with self._lock:
            self._snapshot.status = "running"
            self._mark_updated_locked()

        try:
            while not self._stop_event.is_set():
                frame_started = time.perf_counter()
                payload, cadence_ms = self._build_frame_payload()
                bundle = build_scene_bundle(payload)
                target = bundle["target"]
                scene_json = json.dumps(bundle["scene"], separators=(",", ":"))
                submission = self._apply_callback(target["host"], int(target["port"]), scene_json)
                self._record_frame(bundle["analysis"], submission, len(scene_json.encode("utf-8")))
                elapsed = time.perf_counter() - frame_started
                remaining_seconds = max(0.0, cadence_ms / 1000.0 - elapsed)
                self._stop_event.wait(remaining_seconds)
        except Exception as error:  # pragma: no cover - exercised via unit test timing.
            error_message = str(error)[:500]
            with self._lock:
                self._snapshot.status = "error"
                self._snapshot.last_error = error_message
                self._snapshot.last_submission_status = 0
                self._snapshot.last_submission_reason = "exception"
                self._snapshot.last_stopped_at_utc = _utc_now_iso()
                self._mark_updated_locked()
            self._log_callback(
                "ERROR",
                "client-studio",
                f"Live Client Studio session crashed: {error_message}",
            )
        finally:
            with self._lock:
                if self._snapshot.status != "error":
                    self._snapshot.status = "stopped"
                    self._snapshot.last_stopped_at_utc = _utc_now_iso()
                    self._mark_updated_locked()
                self._thread = None

    def _build_frame_payload(self) -> tuple[dict[str, Any], int]:
        with self._lock:
            payload = copy.deepcopy(self._config)
            cadence_ms = self._snapshot.cadence_ms

        signals = payload.setdefault("signals", {})
        signals["epochSeconds"] = time.time()
        return payload, cadence_ms

    def _record_frame(
        self,
        analysis: dict[str, Any],
        submission: dict[str, Any],
        network_bytes: int,
    ) -> None:
        submission_status = int(submission.get("status", 0) or 0)
        submission_reason = str(submission.get("reason", "unknown"))
        applied = submission_status in (200, 202)
        error_body = str(submission.get("body", ""))

        with self._lock:
            snapshot = self._snapshot
            snapshot.frames_attempted += 1
            snapshot.last_submission_status = submission_status
            snapshot.last_submission_reason = submission_reason
            snapshot.last_network_bytes = network_bytes
            snapshot.last_analysis = analysis

            if applied:
                snapshot.frames_applied += 1
                snapshot.last_applied_at_utc = _utc_now_iso()
                snapshot.last_error = ""
                self._last_logged_failure = None
                self._mark_updated_locked()
                return

            snapshot.frames_failed += 1
            snapshot.last_error = error_body[:500]
            self._mark_updated_locked()

        failure_key = (submission_status, submission_reason)
        if self._last_logged_failure != failure_key:
            self._last_logged_failure = failure_key
            self._log_callback(
                "ERROR",
                "client-studio",
                (
                    "Live Client Studio frame submission failed with "
                    f"{submission_status} {submission_reason}."
                ),
            )

    def _mark_updated_locked(self) -> None:
        self._snapshot.revision += 1
        self._update_condition.notify_all()


def _default_live_payload() -> dict[str, Any]:
    return {
        "presetId": DEFAULT_PRESET_ID,
        "target": {"host": DEFAULT_TARGET_HOST, "port": DEFAULT_TARGET_PORT},
        "settings": {
            "autoApplyMs": DEFAULT_AUTO_APPLY_MS,
        },
        "signals": {
            "useEpoch": True,
            "useNoise": True,
            "usePointer": True,
            "useAudio": False,
            "pointer": {"x": 0.5, "y": 0.5, "speed": 0.0},
            "audio": {"level": 0.0, "bass": 0.0, "mid": 0.0, "treble": 0.0},
            "manual": {"drive": 0.35},
        },
        "session": {"cadenceMs": DEFAULT_AUTO_APPLY_MS},
    }


def _merge_live_payload(existing: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(existing)

    preset_id = update.get("presetId")
    if isinstance(preset_id, str) and preset_id.strip():
        merged["presetId"] = preset_id.strip()

    for key in ("target", "settings", "signals", "session"):
        candidate = update.get(key)
        if isinstance(candidate, dict):
            target = merged.setdefault(key, {})
            _deep_merge(target, candidate)

    session = merged.setdefault("session", {})
    cadence_candidate = None
    incoming_session = update.get("session")
    if isinstance(incoming_session, dict):
        cadence_candidate = incoming_session.get("cadenceMs")
    if cadence_candidate is None:
        incoming_settings = update.get("settings")
        if isinstance(incoming_settings, dict):
            cadence_candidate = incoming_settings.get("autoApplyMs")

    session["cadenceMs"] = _clamp_int(cadence_candidate, DEFAULT_AUTO_APPLY_MS, 40, 1000)
    return merged


def _deep_merge(target: dict[str, Any], update: dict[str, Any]) -> None:
    for key, value in update.items():
        if isinstance(value, dict):
            child = target.get(key)
            if not isinstance(child, dict):
                child = {}
                target[key] = child
            _deep_merge(child, value)
        else:
            target[key] = value


def _clamp_int(value: Any, default: int, lower: int, upper: int) -> int:
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        coerced = default
    return max(lower, min(upper, coerced))
