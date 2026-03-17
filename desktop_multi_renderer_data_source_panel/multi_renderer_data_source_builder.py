"""Turn live source inputs into scenes for one or two Halcyn renderer targets.

This module is the translation layer for the new shared data-source desktop
tool.  It answers a beginner-friendly question:

"If I have some live data, how do I turn it into something both renderers can
understand?"

The answer happens in stages:

1. Normalize the operator's editable request payload.
2. Gather source values from JSON, plain text, random generation, audio, or
   pointer movement.
3. Summarize those source values into reusable signal information.
4. Build a classic Halcyn scene request when the classic target is enabled.
5. Build a spectrograph scene request when the spectrograph target is enabled.

Nothing here talks to the network directly.  The output is a pair of
renderer-ready scene bundles that higher layers can preview, validate, or apply
through the shared renderer API client.
"""

from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass
from typing import Any

from desktop_multi_renderer_data_source_panel import __doc__ as _package_docstring
from desktop_render_control_panel.desktop_control_scene_builder import (
    DEFAULT_DESKTOP_PRESET_ID,
)
from desktop_render_control_panel.desktop_control_scene_builder import (
    build_catalog_payload as build_classic_catalog_payload,
)
from desktop_render_control_panel.desktop_control_scene_builder import (
    build_default_request_payload as build_default_classic_request_payload,
)
from desktop_render_control_panel.desktop_control_scene_builder import (
    build_scene_bundle as build_classic_scene_bundle,
)
from desktop_shared_control_support.audio_input_service import AudioSignalSnapshot
from desktop_spectrograph_control_panel.spectrograph_scene_builder import (
    EXAMPLE_INPUT_DOCUMENTS,
    SpectrographBuildResult,
    build_spectrograph_scene_result,
    flatten_generic_json_value,
)
from desktop_spectrograph_control_panel.spectrograph_scene_builder import (
    build_catalog_payload as build_spectrograph_catalog_payload,
)
from desktop_spectrograph_control_panel.spectrograph_scene_builder import (
    build_default_request_payload as build_default_spectrograph_request_payload,
)

DEFAULT_SOURCE_MODE = "json_document"
DEFAULT_PLAIN_TEXT_INPUT = "Halcyn"
DEFAULT_RANDOM_VALUE_COUNT = 128
DEFAULT_RANDOM_SEED = 7
DEFAULT_RANDOM_MINIMUM = 0.0
DEFAULT_RANDOM_MAXIMUM = 255.0
DEFAULT_SHARED_LIVE_CADENCE_MS = 125
DEFAULT_EXTERNAL_JSON_BRIDGE_HOST = "127.0.0.1"
DEFAULT_EXTERNAL_JSON_BRIDGE_PORT = 8092
SUPPORTED_SOURCE_MODES = (
    "json_document",
    "plain_text",
    "random_values",
    "audio_device",
    "pointer_pad",
    "external_json_bridge",
)


@dataclass(frozen=True)
class CollectedSourceData:
    """Describe the live source data gathered for one preview/apply cycle.

    Attributes:
        source_mode: Which input mode produced this data.
        numeric_values: The flattened numeric stream used to derive signals.
        spectrograph_source_json_text: JSON text that the spectrograph builder
            can ingest directly.
        classic_signal_payload: Renderer-agnostic source values reshaped into
            the signal structure that the classic desktop scene builder expects.
        analysis: Operator-friendly summary text and statistics for the UI.
    """

    source_mode: str
    numeric_values: list[float]
    spectrograph_source_json_text: str
    classic_signal_payload: dict[str, Any]
    analysis: dict[str, Any]


@dataclass(frozen=True)
class MultiRendererPreviewBundle:
    """Describe one shared-source preview across one or two target renderers."""

    normalized_request_payload: dict[str, Any]
    collected_source_data: CollectedSourceData
    classic_scene_bundle: dict[str, Any] | None
    spectrograph_build_result: SpectrographBuildResult | None


def build_catalog_payload() -> dict[str, Any]:
    """Return metadata used to populate the shared data-source panel.

    The window uses this payload to build source-mode pickers, classic preset
    selectors, and spectrograph render-style choices from one consistent source
    of truth.
    """

    classic_catalog_payload = build_classic_catalog_payload()
    spectrograph_catalog_payload = build_spectrograph_catalog_payload()
    return {
        "status": "ok",
        "sourceModes": [
            {
                "id": "json_document",
                "name": "JSON document",
                "summary": (
                    "Parse arbitrary JSON and flatten all numeric, boolean, and string "
                    "content into one value stream."
                ),
            },
            {
                "id": "plain_text",
                "name": "Plain text",
                "summary": "Convert plain text into UTF-8 byte values.",
            },
            {
                "id": "random_values",
                "name": "Random values",
                "summary": "Generate deterministic pseudo-random numeric samples.",
            },
            {
                "id": "audio_device",
                "name": "Audio device",
                "summary": "Use live local audio capture as the data source.",
            },
            {
                "id": "pointer_pad",
                "name": "Pointer pad",
                "summary": "Use pointer position and speed from the desktop UI.",
            },
            {
                "id": "external_json_bridge",
                "name": "External feed",
                "summary": (
                    "Use the newest JSON document delivered by another local desktop helper "
                    "tool such as the audio sender."
                ),
            },
        ],
        "classicPresets": classic_catalog_payload["presets"],
        "spectrographShaderStyles": spectrograph_catalog_payload["shaderStyles"],
        "spectrographExamples": spectrograph_catalog_payload["examples"],
        "defaults": {
            "sourceMode": DEFAULT_SOURCE_MODE,
            "liveCadenceMs": DEFAULT_SHARED_LIVE_CADENCE_MS,
            "externalJsonBridgeHost": DEFAULT_EXTERNAL_JSON_BRIDGE_HOST,
            "externalJsonBridgePort": DEFAULT_EXTERNAL_JSON_BRIDGE_PORT,
        },
        "packageSummary": (_package_docstring or "").strip(),
    }


def build_default_request_payload() -> dict[str, Any]:
    """Return the full editable payload for the shared data-source panel.

    A complete payload lets the GUI keep every field bound to a predictable
    backing value, even before the user clicks anything.
    """

    default_classic_request_payload = build_default_classic_request_payload(
        DEFAULT_DESKTOP_PRESET_ID
    )
    default_spectrograph_request_payload = build_default_spectrograph_request_payload()
    return {
        "source": {
            "mode": DEFAULT_SOURCE_MODE,
            "jsonText": EXAMPLE_INPUT_DOCUMENTS["numeric_wave"],
            "plainText": DEFAULT_PLAIN_TEXT_INPUT,
            "random": {
                "seed": DEFAULT_RANDOM_SEED,
                "count": DEFAULT_RANDOM_VALUE_COUNT,
                "minimum": DEFAULT_RANDOM_MINIMUM,
                "maximum": DEFAULT_RANDOM_MAXIMUM,
            },
            "pointer": {
                "x": 0.5,
                "y": 0.5,
                "speed": 0.0,
            },
            "audio": {
                "deviceFlow": "output",
                "deviceIdentifier": "",
            },
        },
        "targets": {
            "classic": {
                "enabled": True,
                "host": default_classic_request_payload["target"]["host"],
                "port": default_classic_request_payload["target"]["port"],
            },
            "spectrograph": {
                "enabled": False,
                "host": default_spectrograph_request_payload["target"]["host"],
                "port": default_spectrograph_request_payload["target"]["port"],
            },
        },
        "externalJsonBridge": {
            "host": DEFAULT_EXTERNAL_JSON_BRIDGE_HOST,
            "port": DEFAULT_EXTERNAL_JSON_BRIDGE_PORT,
        },
        "classicRender": {
            "presetId": DEFAULT_DESKTOP_PRESET_ID,
            "useEpoch": True,
            "useNoise": True,
        },
        "spectrographRender": dict(default_spectrograph_request_payload["render"]),
        "spectrographRange": dict(default_spectrograph_request_payload["range"]),
        "session": {
            "cadenceMs": DEFAULT_SHARED_LIVE_CADENCE_MS,
        },
    }


def build_multi_renderer_preview_bundle(
    request_payload: dict[str, Any],
    audio_signal_snapshot: AudioSignalSnapshot | None = None,
    spectrograph_rolling_history_values: list[float] | None = None,
    latest_external_json_text: str = "",
) -> MultiRendererPreviewBundle:
    """Build preview-ready classic and spectrograph scenes from one data source."""

    normalized_request_payload = _normalize_request_payload(request_payload)
    collected_source_data = collect_source_data(
        normalized_request_payload,
        audio_signal_snapshot=audio_signal_snapshot,
        latest_external_json_text=latest_external_json_text,
    )

    classic_scene_bundle = None
    if normalized_request_payload["targets"]["classic"]["enabled"]:
        classic_scene_bundle = _build_classic_scene_bundle(
            normalized_request_payload,
            collected_source_data,
        )

    spectrograph_build_result = None
    if normalized_request_payload["targets"]["spectrograph"]["enabled"]:
        spectrograph_build_result = _build_spectrograph_build_result(
            normalized_request_payload,
            collected_source_data,
            spectrograph_rolling_history_values=spectrograph_rolling_history_values,
        )

    return MultiRendererPreviewBundle(
        normalized_request_payload=normalized_request_payload,
        collected_source_data=collected_source_data,
        classic_scene_bundle=classic_scene_bundle,
        spectrograph_build_result=spectrograph_build_result,
    )


def collect_source_data(
    normalized_request_payload: dict[str, Any],
    audio_signal_snapshot: AudioSignalSnapshot | None = None,
    latest_external_json_text: str = "",
) -> CollectedSourceData:
    """Collect one normalized source snapshot from the chosen input mode."""

    source_payload = normalized_request_payload["source"]
    source_mode = source_payload["mode"]
    numeric_values: list[float]
    spectrograph_source_json_text: str

    if source_mode == "plain_text":
        plain_text = str(source_payload["plainText"])
        numeric_values = [float(byte_value) for byte_value in plain_text.encode("utf-8")]
        spectrograph_source_json_text = json.dumps({"text": plain_text})
    elif source_mode == "random_values":
        random_settings = source_payload["random"]
        deterministic_random = random.Random(int(random_settings["seed"]))
        numeric_values = [
            deterministic_random.uniform(
                float(random_settings["minimum"]),
                float(random_settings["maximum"]),
            )
            for _ in range(int(random_settings["count"]))
        ]
        spectrograph_source_json_text = json.dumps({"values": numeric_values})
    elif source_mode == "audio_device":
        safe_audio_signal_snapshot = audio_signal_snapshot or AudioSignalSnapshot()
        numeric_values = _audio_snapshot_to_numeric_values(safe_audio_signal_snapshot)
        spectrograph_source_json_text = json.dumps(
            {
                "audio": {
                    "deviceName": safe_audio_signal_snapshot.device_name,
                    "level": safe_audio_signal_snapshot.level,
                    "bass": safe_audio_signal_snapshot.bass,
                    "mid": safe_audio_signal_snapshot.mid,
                    "treble": safe_audio_signal_snapshot.treble,
                }
            }
        )
    elif source_mode == "pointer_pad":
        pointer_payload = source_payload["pointer"]
        pointer_x_position = float(pointer_payload["x"])
        pointer_y_position = float(pointer_payload["y"])
        pointer_speed = float(pointer_payload["speed"])
        numeric_values = []
        for repeated_step_index in range(64):
            repeated_step_ratio = repeated_step_index / 63 if repeated_step_index else 0.0
            numeric_values.extend(
                [
                    pointer_x_position * 255.0,
                    pointer_y_position * 255.0,
                    pointer_speed * 255.0,
                    repeated_step_ratio * (pointer_x_position + pointer_y_position) * 127.5,
                ]
            )
        spectrograph_source_json_text = json.dumps(
            {
                "pointer": {
                    "x": pointer_x_position,
                    "y": pointer_y_position,
                    "speed": pointer_speed,
                }
            }
        )
    elif source_mode == "external_json_bridge":
        spectrograph_source_json_text = latest_external_json_text.strip() or json.dumps(
            {
                "status": "waiting-for-external-data",
                "message": (
                    "This source mode follows the newest JSON document received through "
                    "the local desktop bridge."
                ),
            }
        )
        parsed_json_value = _parse_json_document(spectrograph_source_json_text)
        numeric_values = flatten_generic_json_value(parsed_json_value)
    else:
        json_text = str(source_payload["jsonText"]).strip()
        parsed_json_value = _parse_json_document(json_text)
        numeric_values = flatten_generic_json_value(parsed_json_value)
        spectrograph_source_json_text = json_text

    if not numeric_values:
        numeric_values = [0.0]

    source_analysis = _build_source_analysis(
        source_mode=source_mode,
        numeric_values=numeric_values,
        audio_signal_snapshot=audio_signal_snapshot,
        pointer_payload=source_payload["pointer"],
    )
    classic_signal_payload = _build_classic_signal_payload(
        normalized_request_payload=normalized_request_payload,
        source_mode=source_mode,
        numeric_values=numeric_values,
        audio_signal_snapshot=audio_signal_snapshot,
        pointer_payload=source_payload["pointer"],
    )
    return CollectedSourceData(
        source_mode=source_mode,
        numeric_values=numeric_values,
        spectrograph_source_json_text=spectrograph_source_json_text,
        classic_signal_payload=classic_signal_payload,
        analysis=source_analysis,
    )


def _normalize_request_payload(request_payload: dict[str, Any]) -> dict[str, Any]:
    """Merge arbitrary caller data into one safe, complete payload."""

    normalized_request_payload = build_default_request_payload()
    _deep_merge(normalized_request_payload, request_payload)

    source_payload = normalized_request_payload["source"]
    normalized_source_mode = str(source_payload.get("mode", DEFAULT_SOURCE_MODE)).strip().lower()
    if normalized_source_mode not in SUPPORTED_SOURCE_MODES:
        normalized_source_mode = DEFAULT_SOURCE_MODE
    source_payload["mode"] = normalized_source_mode
    source_payload["jsonText"] = str(
        source_payload.get("jsonText", EXAMPLE_INPUT_DOCUMENTS["numeric_wave"])
    ).strip() or EXAMPLE_INPUT_DOCUMENTS["numeric_wave"]
    source_payload["plainText"] = str(source_payload.get("plainText", DEFAULT_PLAIN_TEXT_INPUT))
    source_payload["random"]["seed"] = _clamp_int(
        source_payload["random"].get("seed"),
        DEFAULT_RANDOM_SEED,
        0,
        1_000_000,
    )
    source_payload["random"]["count"] = _clamp_int(
        source_payload["random"].get("count"),
        DEFAULT_RANDOM_VALUE_COUNT,
        4,
        4096,
    )
    source_payload["random"]["minimum"] = _clamp_float(
        source_payload["random"].get("minimum"),
        DEFAULT_RANDOM_MINIMUM,
        -1_000_000.0,
        1_000_000.0,
    )
    source_payload["random"]["maximum"] = _clamp_float(
        source_payload["random"].get("maximum"),
        DEFAULT_RANDOM_MAXIMUM,
        -1_000_000.0,
        1_000_000.0,
    )
    if source_payload["random"]["maximum"] <= source_payload["random"]["minimum"]:
        source_payload["random"]["maximum"] = source_payload["random"]["minimum"] + 1.0

    source_payload["pointer"]["x"] = _clamp_float(source_payload["pointer"].get("x"), 0.5, 0.0, 1.0)
    source_payload["pointer"]["y"] = _clamp_float(source_payload["pointer"].get("y"), 0.5, 0.0, 1.0)
    source_payload["pointer"]["speed"] = _clamp_float(
        source_payload["pointer"].get("speed"),
        0.0,
        0.0,
        1.0,
    )
    normalized_device_flow = (
        str(source_payload["audio"].get("deviceFlow", "output")).strip().lower()
    )
    if normalized_device_flow not in {"input", "output"}:
        normalized_device_flow = "output"
    source_payload["audio"]["deviceFlow"] = normalized_device_flow
    source_payload["audio"]["deviceIdentifier"] = str(
        source_payload["audio"].get("deviceIdentifier", "")
    )

    classic_catalog_payload = build_classic_catalog_payload()
    valid_classic_preset_identifiers = {
        preset_entry["id"] for preset_entry in classic_catalog_payload["presets"]
    }
    normalized_classic_preset_identifier = str(
        normalized_request_payload["classicRender"].get("presetId", DEFAULT_DESKTOP_PRESET_ID)
    )
    if normalized_classic_preset_identifier not in valid_classic_preset_identifiers:
        normalized_classic_preset_identifier = DEFAULT_DESKTOP_PRESET_ID
    normalized_request_payload["classicRender"]["presetId"] = normalized_classic_preset_identifier
    normalized_request_payload["classicRender"]["useEpoch"] = bool(
        normalized_request_payload["classicRender"].get("useEpoch", True)
    )
    normalized_request_payload["classicRender"]["useNoise"] = bool(
        normalized_request_payload["classicRender"].get("useNoise", True)
    )

    for target_key, default_payload in (
        ("classic", build_default_classic_request_payload(DEFAULT_DESKTOP_PRESET_ID)),
        ("spectrograph", build_default_spectrograph_request_payload()),
    ):
        target_payload = normalized_request_payload["targets"][target_key]
        target_payload["enabled"] = bool(target_payload.get("enabled", target_key == "classic"))
        target_payload["host"] = str(
            target_payload.get("host", default_payload["target"]["host"])
        ).strip() or str(default_payload["target"]["host"])
        target_payload["port"] = _clamp_int(
            target_payload.get("port"),
            int(default_payload["target"]["port"]),
            1,
            65535,
        )

    normalized_request_payload["session"]["cadenceMs"] = _clamp_int(
        normalized_request_payload["session"].get("cadenceMs"),
        DEFAULT_SHARED_LIVE_CADENCE_MS,
        40,
        2000,
    )
    normalized_request_payload["externalJsonBridge"]["host"] = (
        str(
            normalized_request_payload["externalJsonBridge"].get(
                "host",
                DEFAULT_EXTERNAL_JSON_BRIDGE_HOST,
            )
        ).strip()
        or DEFAULT_EXTERNAL_JSON_BRIDGE_HOST
    )
    normalized_request_payload["externalJsonBridge"]["port"] = _clamp_int(
        normalized_request_payload["externalJsonBridge"].get("port"),
        DEFAULT_EXTERNAL_JSON_BRIDGE_PORT,
        1,
        65535,
    )
    return normalized_request_payload


def _parse_json_document(json_text: str) -> Any:
    """Parse one operator-supplied JSON document with friendly errors."""

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as error:
        raise ValueError(
            "The shared data source panel could not parse the provided JSON document. "
            f"Line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error


def _audio_snapshot_to_numeric_values(audio_signal_snapshot: AudioSignalSnapshot) -> list[float]:
    """Expand one audio analysis snapshot into a richer numeric stream.

    The source panel only gets four coarse audio-band values from the capture
    layer.  Repeating them in a simple pattern gives the spectrograph builder a
    longer stream to group while keeping the meaning easy to explain.
    """

    audio_value_pattern = [
        float(audio_signal_snapshot.level) * 255.0,
        float(audio_signal_snapshot.bass) * 255.0,
        float(audio_signal_snapshot.mid) * 255.0,
        float(audio_signal_snapshot.treble) * 255.0,
    ]
    repeated_audio_values: list[float] = []
    for _ in range(32):
        repeated_audio_values.extend(audio_value_pattern)
    return repeated_audio_values


def _build_source_analysis(
    *,
    source_mode: str,
    numeric_values: list[float],
    audio_signal_snapshot: AudioSignalSnapshot | None,
    pointer_payload: dict[str, Any],
) -> dict[str, Any]:
    """Build a readable operator-facing summary of the current source values."""

    observed_minimum = min(numeric_values)
    observed_maximum = max(numeric_values)
    average_value = sum(numeric_values) / len(numeric_values)
    if source_mode == "audio_device" and audio_signal_snapshot is not None:
        details = (
            f"Audio device: {audio_signal_snapshot.device_name or 'not selected'}, "
            f"capturing={audio_signal_snapshot.capturing}, level={audio_signal_snapshot.level:.2f}"
        )
    elif source_mode == "pointer_pad":
        details = (
            f"Pointer x={float(pointer_payload['x']):.2f}, "
            f"y={float(pointer_payload['y']):.2f}, "
            f"speed={float(pointer_payload['speed']):.2f}"
        )
    elif source_mode == "external_json_bridge":
        details = (
            "Following the newest JSON document delivered through the local desktop bridge."
        )
    else:
        details = f"First values: {numeric_values[:8]}"

    return {
        "sourceMode": source_mode,
        "valueCount": len(numeric_values),
        "observedMinimum": observed_minimum,
        "observedMaximum": observed_maximum,
        "averageValue": average_value,
        "details": details,
    }


def _build_classic_scene_bundle(
    normalized_request_payload: dict[str, Any],
    collected_source_data: CollectedSourceData,
) -> dict[str, Any]:
    """Build the classic renderer scene bundle for the current source snapshot."""

    classic_request_payload = build_default_classic_request_payload(
        str(normalized_request_payload["classicRender"]["presetId"])
    )
    classic_request_payload["target"] = {
        "host": normalized_request_payload["targets"]["classic"]["host"],
        "port": normalized_request_payload["targets"]["classic"]["port"],
    }
    classic_request_payload["signals"] = collected_source_data.classic_signal_payload
    classic_request_payload["session"]["cadenceMs"] = normalized_request_payload["session"][
        "cadenceMs"
    ]
    classic_scene_bundle = build_classic_scene_bundle(classic_request_payload)
    classic_scene_bundle["analysis"]["sourceMode"] = collected_source_data.source_mode
    classic_scene_bundle["analysis"]["sourceValueCount"] = len(collected_source_data.numeric_values)
    return classic_scene_bundle


def _build_spectrograph_build_result(
    normalized_request_payload: dict[str, Any],
    collected_source_data: CollectedSourceData,
    spectrograph_rolling_history_values: list[float] | None,
) -> SpectrographBuildResult:
    """Build the spectrograph renderer scene bundle for the current source snapshot."""

    spectrograph_request_payload = build_default_spectrograph_request_payload()
    spectrograph_request_payload["target"] = {
        "host": normalized_request_payload["targets"]["spectrograph"]["host"],
        "port": normalized_request_payload["targets"]["spectrograph"]["port"],
    }
    spectrograph_request_payload["data"]["jsonText"] = (
        collected_source_data.spectrograph_source_json_text
    )
    spectrograph_request_payload["render"] = dict(normalized_request_payload["spectrographRender"])
    spectrograph_request_payload["range"] = dict(normalized_request_payload["spectrographRange"])
    spectrograph_request_payload["session"]["cadenceMs"] = normalized_request_payload["session"][
        "cadenceMs"
    ]
    return build_spectrograph_scene_result(
        spectrograph_request_payload,
        rolling_history_values=spectrograph_rolling_history_values,
    )


def _build_classic_signal_payload(
    *,
    normalized_request_payload: dict[str, Any],
    source_mode: str,
    numeric_values: list[float],
    audio_signal_snapshot: AudioSignalSnapshot | None,
    pointer_payload: dict[str, Any],
) -> dict[str, Any]:
    """Translate one source snapshot into the signal shape used by classic scenes."""

    use_epoch_signal = bool(normalized_request_payload["classicRender"]["useEpoch"])
    use_noise_signal = bool(normalized_request_payload["classicRender"]["useNoise"])

    if source_mode == "audio_device" and audio_signal_snapshot is not None:
        return {
            "useEpoch": use_epoch_signal,
            "useNoise": use_noise_signal,
            "usePointer": False,
            "useAudio": True,
            "pointer": {"x": 0.5, "y": 0.5, "speed": 0.0},
            "audio": {
                "level": _clamp_float(audio_signal_snapshot.level, 0.0, 0.0, 1.0),
                "bass": _clamp_float(audio_signal_snapshot.bass, 0.0, 0.0, 1.0),
                "mid": _clamp_float(audio_signal_snapshot.mid, 0.0, 0.0, 1.0),
                "treble": _clamp_float(audio_signal_snapshot.treble, 0.0, 0.0, 1.0),
            },
            "manual": {
                "drive": _clamp_float(audio_signal_snapshot.level, 0.0, 0.0, 2.0),
            },
            "noiseSeed": 1.0 + _clamp_float(audio_signal_snapshot.level, 0.0, 0.0, 1.0) * 10.0,
            "epochSeconds": time.time(),
        }

    if source_mode == "pointer_pad":
        pointer_x_position = _clamp_float(pointer_payload.get("x"), 0.5, 0.0, 1.0)
        pointer_y_position = _clamp_float(pointer_payload.get("y"), 0.5, 0.0, 1.0)
        pointer_speed = _clamp_float(pointer_payload.get("speed"), 0.0, 0.0, 1.0)
        return {
            "useEpoch": use_epoch_signal,
            "useNoise": use_noise_signal,
            "usePointer": True,
            "useAudio": False,
            "pointer": {
                "x": pointer_x_position,
                "y": pointer_y_position,
                "speed": pointer_speed,
            },
            "audio": {"level": 0.0, "bass": 0.0, "mid": 0.0, "treble": 0.0},
            "manual": {"drive": pointer_speed},
            "noiseSeed": 1.0 + (pointer_x_position * 2.0) + (pointer_y_position * 3.0),
            "epochSeconds": time.time(),
        }

    derived_signal_profile = _build_normalized_signal_profile_from_numeric_values(numeric_values)
    return {
        "useEpoch": use_epoch_signal,
        "useNoise": use_noise_signal,
        "usePointer": True,
        "useAudio": True,
        "pointer": {
            "x": derived_signal_profile["pointerX"],
            "y": derived_signal_profile["pointerY"],
            "speed": derived_signal_profile["pointerSpeed"],
        },
        "audio": {
            "level": derived_signal_profile["level"],
            "bass": derived_signal_profile["bass"],
            "mid": derived_signal_profile["mid"],
            "treble": derived_signal_profile["treble"],
        },
        "manual": {"drive": derived_signal_profile["manualDrive"]},
        "noiseSeed": 1.0 + derived_signal_profile["noiseSeedOffset"],
        "epochSeconds": time.time(),
    }


def _build_normalized_signal_profile_from_numeric_values(
    numeric_values: list[float],
) -> dict[str, float]:
    """Summarize a numeric stream into the smaller control signals used by classic scenes."""

    observed_minimum = min(numeric_values)
    observed_maximum = max(numeric_values)
    value_range = observed_maximum - observed_minimum
    if value_range <= 1e-9:
        normalized_values = [0.5 for _ in numeric_values]
    else:
        normalized_values = [
            _clamp_float((numeric_value - observed_minimum) / value_range, 0.5, 0.0, 1.0)
            for numeric_value in numeric_values
        ]

    first_third = normalized_values[: max(1, len(normalized_values) // 3)]
    second_third = normalized_values[
        max(1, len(normalized_values) // 3) : max(2, (len(normalized_values) * 2) // 3)
    ]
    final_third = normalized_values[max(2, (len(normalized_values) * 2) // 3) :]

    overall_level = _average(normalized_values)
    pointer_x_position = normalized_values[0] if normalized_values else 0.5
    pointer_y_position = normalized_values[1] if len(normalized_values) > 1 else overall_level
    pointer_speed = abs(normalized_values[-1] - normalized_values[0]) if normalized_values else 0.0

    return {
        "level": overall_level,
        "bass": _average(first_third),
        "mid": _average(second_third),
        "treble": _average(final_third),
        "pointerX": pointer_x_position,
        "pointerY": pointer_y_position,
        "pointerSpeed": pointer_speed,
        "manualDrive": overall_level,
        "noiseSeedOffset": sum(normalized_values[:8]),
    }


def _average(values: list[float]) -> float:
    """Return the average of a list, or zero when the list is empty."""

    if not values:
        return 0.0
    return sum(values) / len(values)


def _clamp_int(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    """Convert one value to an integer and clamp it into a safe range."""

    try:
        converted_value = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, converted_value))


def _clamp_float(value: Any, fallback: float, minimum: float, maximum: float) -> float:
    """Convert one value to a float and clamp it into a safe range."""

    try:
        converted_value = float(value)
    except (TypeError, ValueError):
        return fallback
    if math.isnan(converted_value) or math.isinf(converted_value):
        return fallback
    return max(minimum, min(maximum, converted_value))


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> None:
    """Recursively merge nested dictionaries in place."""

    for key, value in update.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
