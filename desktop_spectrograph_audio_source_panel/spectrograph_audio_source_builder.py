"""Build external-source payloads for the spectrograph control panel.

This module answers a focused question:

"If I have a rolling history of live audio snapshots, how should I package that
history so the spectrograph control panel can understand it?"

The control panel already knows how to flatten arbitrary JSON into numeric
values. That means this builder does not need a custom binary protocol or a
special renderer API. It just needs to produce a clear, generic JSON document
that preserves:

- the selected device information
- a rolling history of audio frames
- a friendly summary of what those frames contain
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from desktop_shared_control_support.audio_input_service import AudioSignalSnapshot

DEFAULT_BRIDGE_HOST = "127.0.0.1"
DEFAULT_BRIDGE_PORT = 8091
DEFAULT_BRIDGE_PATH = "/external-data"
DEFAULT_LIVE_CADENCE_MS = 125
DEFAULT_AUDIO_HISTORY_FRAME_COUNT = 72


@dataclass(frozen=True)
class SpectrographAudioSourcePreview:
    """Describe one preview of the outgoing audio-source document."""

    normalized_request_payload: dict[str, Any]
    generated_json_text: str
    bridge_request_body: dict[str, Any]
    analysis: dict[str, Any]


def build_catalog_payload() -> dict[str, Any]:
    """Return small metadata used to populate the desktop audio-source window."""

    return {
        "status": "ok",
        "deviceFlows": [
            {"id": "output", "name": "Output sources"},
            {"id": "input", "name": "Input sources"},
        ],
        "defaults": {
            "bridgeHost": DEFAULT_BRIDGE_HOST,
            "bridgePort": DEFAULT_BRIDGE_PORT,
            "bridgePath": DEFAULT_BRIDGE_PATH,
            "liveCadenceMs": DEFAULT_LIVE_CADENCE_MS,
            "historyFrameCount": DEFAULT_AUDIO_HISTORY_FRAME_COUNT,
        },
    }


def build_default_request_payload() -> dict[str, Any]:
    """Return the full editable payload used by the audio-source window."""

    return {
        "bridge": {
            "host": DEFAULT_BRIDGE_HOST,
            "port": DEFAULT_BRIDGE_PORT,
            "path": DEFAULT_BRIDGE_PATH,
            "sourceLabel": "Desktop spectrograph audio source panel",
        },
        "audio": {
            "deviceFlow": "output",
            "deviceIdentifier": "",
            "historyFrameCount": DEFAULT_AUDIO_HISTORY_FRAME_COUNT,
        },
        "session": {
            "cadenceMs": DEFAULT_LIVE_CADENCE_MS,
        },
    }


def build_audio_source_preview(
    request_payload: dict[str, Any],
    latest_audio_signal_snapshot: AudioSignalSnapshot,
    recent_audio_signal_snapshots: list[AudioSignalSnapshot],
) -> SpectrographAudioSourcePreview:
    """Build the outgoing bridge payload for one preview or send cycle."""

    normalized_request_payload = _normalize_request_payload(request_payload)
    generated_audio_json_document = _build_generated_audio_json_document(
        latest_audio_signal_snapshot=latest_audio_signal_snapshot,
        recent_audio_signal_snapshots=recent_audio_signal_snapshots,
        request_payload=normalized_request_payload,
    )
    generated_json_text = json.dumps(generated_audio_json_document, indent=2)
    bridge_request_body = {
        "sourceLabel": normalized_request_payload["bridge"]["sourceLabel"],
        "jsonText": generated_json_text,
    }
    analysis = {
        "deviceFlow": normalized_request_payload["audio"]["deviceFlow"],
        "deviceIdentifier": normalized_request_payload["audio"]["deviceIdentifier"],
        "deviceName": latest_audio_signal_snapshot.device_name,
        "frameCount": len(generated_audio_json_document["audioFrames"]),
        "currentLevel": generated_audio_json_document["summary"]["currentLevel"],
        "peakLevel": generated_audio_json_document["summary"]["peakLevel"],
        "averageLevel": generated_audio_json_document["summary"]["averageLevel"],
        "bridgeTarget": (
            f"{normalized_request_payload['bridge']['host']}:"
            f"{normalized_request_payload['bridge']['port']}"
            f"{normalized_request_payload['bridge']['path']}"
        ),
    }

    return SpectrographAudioSourcePreview(
        normalized_request_payload=normalized_request_payload,
        generated_json_text=generated_json_text,
        bridge_request_body=bridge_request_body,
        analysis=analysis,
    )


def _normalize_request_payload(request_payload: dict[str, Any]) -> dict[str, Any]:
    """Merge arbitrary caller data into the full request-payload shape."""

    normalized_request_payload = copy.deepcopy(build_default_request_payload())
    _deep_merge(normalized_request_payload, request_payload)

    normalized_request_payload["bridge"]["host"] = (
        str(normalized_request_payload["bridge"].get("host", DEFAULT_BRIDGE_HOST)).strip()
        or DEFAULT_BRIDGE_HOST
    )
    normalized_request_payload["bridge"]["port"] = _clamp_int(
        normalized_request_payload["bridge"].get("port"),
        DEFAULT_BRIDGE_PORT,
        1,
        65535,
    )
    normalized_request_payload["bridge"]["path"] = (
        str(normalized_request_payload["bridge"].get("path", DEFAULT_BRIDGE_PATH)).strip()
        or DEFAULT_BRIDGE_PATH
    )
    normalized_request_payload["bridge"]["sourceLabel"] = (
        str(
            normalized_request_payload["bridge"].get(
                "sourceLabel",
                "Desktop spectrograph audio source panel",
            )
        ).strip()
        or "Desktop spectrograph audio source panel"
    )

    normalized_device_flow = str(
        normalized_request_payload["audio"].get("deviceFlow", "output")
    ).lower()
    if normalized_device_flow not in {"input", "output"}:
        normalized_device_flow = "output"
    normalized_request_payload["audio"]["deviceFlow"] = normalized_device_flow
    normalized_request_payload["audio"]["deviceIdentifier"] = str(
        normalized_request_payload["audio"].get("deviceIdentifier", "")
    ).strip()
    normalized_request_payload["audio"]["historyFrameCount"] = _clamp_int(
        normalized_request_payload["audio"].get("historyFrameCount"),
        DEFAULT_AUDIO_HISTORY_FRAME_COUNT,
        4,
        256,
    )
    normalized_request_payload["session"]["cadenceMs"] = _clamp_int(
        normalized_request_payload["session"].get("cadenceMs"),
        DEFAULT_LIVE_CADENCE_MS,
        40,
        2000,
    )
    return normalized_request_payload


def _build_generated_audio_json_document(
    *,
    latest_audio_signal_snapshot: AudioSignalSnapshot,
    recent_audio_signal_snapshots: list[AudioSignalSnapshot],
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    """Build the generic JSON document consumed by the spectrograph panel.

    The document intentionally uses ordinary nested JSON so the spectrograph
    control panel can keep using its existing generic JSON flattener. The audio
    panel simply becomes one more JSON-producing source in the ecosystem.
    """

    audio_frames = [
        {
            "level": round(audio_frame.level, 6),
            "bass": round(audio_frame.bass, 6),
            "mid": round(audio_frame.mid, 6),
            "treble": round(audio_frame.treble, 6),
        }
        for audio_frame in recent_audio_signal_snapshots
    ]
    if not audio_frames:
        audio_frames = [{"level": 0.0, "bass": 0.0, "mid": 0.0, "treble": 0.0}]

    all_levels = [frame["level"] for frame in audio_frames]
    average_level = sum(all_levels) / len(all_levels)
    peak_level = max(all_levels)

    return {
        "sourceType": "spectrograph-audio-source-panel",
        "device": {
            "name": latest_audio_signal_snapshot.device_name,
            "identifier": latest_audio_signal_snapshot.device_identifier,
            "flow": request_payload["audio"]["deviceFlow"],
        },
        "summary": {
            "available": latest_audio_signal_snapshot.available,
            "capturing": latest_audio_signal_snapshot.capturing,
            "currentLevel": round(latest_audio_signal_snapshot.level, 6),
            "currentBass": round(latest_audio_signal_snapshot.bass, 6),
            "currentMid": round(latest_audio_signal_snapshot.mid, 6),
            "currentTreble": round(latest_audio_signal_snapshot.treble, 6),
            "averageLevel": round(average_level, 6),
            "peakLevel": round(peak_level, 6),
        },
        "audioFrames": audio_frames,
    }


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> None:
    """Recursively merge one nested dictionary into another."""

    for key, value in update.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            nested_base_value = base[key]
            assert isinstance(nested_base_value, dict)
            _deep_merge(nested_base_value, value)
        else:
            base[key] = value


def _clamp_int(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    """Convert one value to an int and clamp it into a safe range."""

    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return fallback
