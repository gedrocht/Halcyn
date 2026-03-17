"""Build one Halcyn Visualizer scene from one chosen live data source.

This module is the translation layer behind the unified desktop Visualizer
Studio. Its central beginner-friendly question is:

"Given one live source of data, how do we turn it into the one scene the
Visualizer should show right now?"
"""

from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass
from typing import Any

from desktop_render_control_panel.desktop_control_scene_builder import (
    DEFAULT_DESKTOP_PRESET_ID,
)
from desktop_render_control_panel.desktop_control_scene_builder import (
    build_catalog_payload as build_preset_scene_catalog_payload,
)
from desktop_render_control_panel.desktop_control_scene_builder import (
    build_default_request_payload as build_default_preset_scene_request_payload,
)
from desktop_render_control_panel.desktop_control_scene_builder import (
    build_scene_bundle as build_preset_scene_bundle,
)
from desktop_shared_control_support.audio_input_service import AudioSignalSnapshot
from desktop_spectrograph_control_panel.spectrograph_scene_builder import (
    EXAMPLE_INPUT_DOCUMENTS,
    build_spectrograph_scene_result,
    flatten_generic_json_value,
)
from desktop_spectrograph_control_panel.spectrograph_scene_builder import (
    build_catalog_payload as build_bar_wall_catalog_payload,
)
from desktop_spectrograph_control_panel.spectrograph_scene_builder import (
    build_default_request_payload as build_default_bar_wall_request_payload,
)

DEFAULT_VISUALIZER_HOST = "127.0.0.1"
DEFAULT_VISUALIZER_PORT = 8080
DEFAULT_SOURCE_MODE = "json_document"
DEFAULT_SCENE_MODE = "preset_scene"
DEFAULT_PLAIN_TEXT_SOURCE = "Halcyn"
DEFAULT_RANDOM_SEED = 7
DEFAULT_RANDOM_VALUE_COUNT = 128
DEFAULT_RANDOM_MINIMUM = 0.0
DEFAULT_RANDOM_MAXIMUM = 255.0
DEFAULT_LIVE_CADENCE_MS = 125
SUPPORTED_SOURCE_MODES = (
    "json_document",
    "plain_text",
    "random_values",
    "audio_device",
    "pointer_pad",
)
SUPPORTED_SCENE_MODES = ("preset_scene", "bar_wall_scene")


@dataclass(frozen=True)
class CollectedSourceData:
    """Describe the current live source snapshot in several reusable forms."""

    source_mode: str
    numeric_values: list[float]
    bar_wall_source_json_text: str
    preset_scene_signal_payload: dict[str, Any]
    analysis: dict[str, Any]


@dataclass(frozen=True)
class VisualizerPreviewBundle:
    """Describe the one preview scene currently built for the Visualizer."""

    normalized_request_payload: dict[str, Any]
    collected_source_data: CollectedSourceData
    scene_mode: str
    target: dict[str, Any]
    scene: dict[str, Any]
    analysis: dict[str, Any]
    next_bar_wall_rolling_history_values: list[float]


def build_catalog_payload() -> dict[str, Any]:
    """Return the metadata that helps Visualizer Studio build its UI."""

    preset_scene_catalog_payload = build_preset_scene_catalog_payload()
    bar_wall_catalog_payload = build_bar_wall_catalog_payload()
    return {
        "status": "ok",
        "sceneModes": [
            {
                "id": "preset_scene",
                "name": "Preset scene",
                "summary": "Drive the original 2D and 3D preset families with live signals.",
            },
            {
                "id": "bar_wall_scene",
                "name": "Bar wall",
                "summary": (
                    "Turn generic live data into a rolling normalized field "
                    "of colored 3D bars."
                ),
            },
        ],
        "sourceModes": [
            {
                "id": "json_document",
                "name": "JSON document",
                "summary": "Flatten arbitrary JSON into one numeric value stream.",
            },
            {
                "id": "plain_text",
                "name": "Plain text",
                "summary": "Convert text into UTF-8 byte values.",
            },
            {
                "id": "random_values",
                "name": "Random values",
                "summary": "Generate a deterministic pseudo-random numeric stream.",
            },
            {
                "id": "audio_device",
                "name": "Audio device",
                "summary": "Use live input or output capture from a local audio device.",
            },
            {
                "id": "pointer_pad",
                "name": "Pointer pad",
                "summary": "Use pointer position and motion as the live data source.",
            },
        ],
        "presetScenes": preset_scene_catalog_payload["presets"],
        "barWallShaderStyles": bar_wall_catalog_payload["shaderStyles"],
        "barWallExamples": bar_wall_catalog_payload["examples"],
        "defaults": {
            "host": DEFAULT_VISUALIZER_HOST,
            "port": DEFAULT_VISUALIZER_PORT,
            "sceneMode": DEFAULT_SCENE_MODE,
            "sourceMode": DEFAULT_SOURCE_MODE,
            "liveCadenceMs": DEFAULT_LIVE_CADENCE_MS,
        },
    }


def build_default_request_payload() -> dict[str, Any]:
    """Return the full editable request payload for Visualizer Studio."""

    default_bar_wall_request_payload = build_default_bar_wall_request_payload()
    return {
        "target": {
            "host": DEFAULT_VISUALIZER_HOST,
            "port": DEFAULT_VISUALIZER_PORT,
        },
        "sceneMode": DEFAULT_SCENE_MODE,
        "source": {
            "mode": DEFAULT_SOURCE_MODE,
            "jsonText": EXAMPLE_INPUT_DOCUMENTS["numeric_wave"],
            "plainText": DEFAULT_PLAIN_TEXT_SOURCE,
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
        "presetScene": {
            "presetId": DEFAULT_DESKTOP_PRESET_ID,
            "useEpoch": True,
            "useNoise": True,
        },
        "barWallScene": {
            "render": dict(default_bar_wall_request_payload["render"]),
            "range": dict(default_bar_wall_request_payload["range"]),
        },
        "session": {
            "cadenceMs": DEFAULT_LIVE_CADENCE_MS,
        },
    }


def build_visualizer_preview_bundle(
    request_payload: dict[str, Any],
    *,
    audio_signal_snapshot: AudioSignalSnapshot | None = None,
    bar_wall_rolling_history_values: list[float] | None = None,
) -> VisualizerPreviewBundle:
    """Build one Visualizer preview scene from the current operator payload."""

    normalized_request_payload = _normalize_request_payload(request_payload)
    collected_source_data = collect_source_data(
        normalized_request_payload,
        audio_signal_snapshot=audio_signal_snapshot,
    )
    scene_mode = str(normalized_request_payload["sceneMode"])

    if scene_mode == "bar_wall_scene":
        bar_wall_build_result = _build_bar_wall_scene_result(
            normalized_request_payload,
            collected_source_data,
            bar_wall_rolling_history_values=bar_wall_rolling_history_values,
        )
        analysis = dict(bar_wall_build_result.analysis)
        analysis["sceneMode"] = "bar_wall_scene"
        analysis["sourceMode"] = collected_source_data.source_mode
        return VisualizerPreviewBundle(
            normalized_request_payload=normalized_request_payload,
            collected_source_data=collected_source_data,
            scene_mode=scene_mode,
            target=normalized_request_payload["target"],
            scene=bar_wall_build_result.scene,
            analysis=analysis,
            next_bar_wall_rolling_history_values=list(
                bar_wall_build_result.next_rolling_history_values
            ),
        )

    preset_scene_bundle = _build_preset_scene_preview_bundle(
        normalized_request_payload,
        collected_source_data,
    )
    analysis = dict(preset_scene_bundle["analysis"])
    analysis["sceneMode"] = "preset_scene"
    analysis["sourceMode"] = collected_source_data.source_mode
    return VisualizerPreviewBundle(
        normalized_request_payload=normalized_request_payload,
        collected_source_data=collected_source_data,
        scene_mode=scene_mode,
        target=normalized_request_payload["target"],
        scene=preset_scene_bundle["scene"],
        analysis=analysis,
        next_bar_wall_rolling_history_values=list(bar_wall_rolling_history_values or []),
    )


def collect_source_data(
    normalized_request_payload: dict[str, Any],
    *,
    audio_signal_snapshot: AudioSignalSnapshot | None = None,
) -> CollectedSourceData:
    """Collect one reusable source snapshot from the chosen source mode."""

    source_payload = normalized_request_payload["source"]
    source_mode = str(source_payload["mode"])
    numeric_values: list[float]
    bar_wall_source_json_text: str

    if source_mode == "plain_text":
        plain_text = str(source_payload["plainText"])
        numeric_values = [float(byte_value) for byte_value in plain_text.encode("utf-8")]
        bar_wall_source_json_text = json.dumps({"text": plain_text})
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
        bar_wall_source_json_text = json.dumps({"values": numeric_values})
    elif source_mode == "audio_device":
        safe_audio_signal_snapshot = audio_signal_snapshot or AudioSignalSnapshot()
        numeric_values = _audio_snapshot_to_numeric_values(safe_audio_signal_snapshot)
        bar_wall_source_json_text = json.dumps(
            {
                "audio": {
                    "deviceName": safe_audio_signal_snapshot.device_name,
                    "deviceFlow": source_payload["audio"]["deviceFlow"],
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
        bar_wall_source_json_text = json.dumps(
            {
                "pointer": {
                    "x": pointer_x_position,
                    "y": pointer_y_position,
                    "speed": pointer_speed,
                }
            }
        )
    else:
        json_text = str(source_payload["jsonText"]).strip()
        parsed_json_value = _parse_json_document(json_text)
        numeric_values = flatten_generic_json_value(parsed_json_value)
        bar_wall_source_json_text = json_text

    if not numeric_values:
        numeric_values = [0.0]

    return CollectedSourceData(
        source_mode=source_mode,
        numeric_values=numeric_values,
        bar_wall_source_json_text=bar_wall_source_json_text,
        preset_scene_signal_payload=_build_preset_scene_signal_payload(
            normalized_request_payload=normalized_request_payload,
            source_mode=source_mode,
            numeric_values=numeric_values,
            audio_signal_snapshot=audio_signal_snapshot,
            pointer_payload=source_payload["pointer"],
        ),
        analysis=_build_source_analysis(
            source_mode=source_mode,
            numeric_values=numeric_values,
            audio_signal_snapshot=audio_signal_snapshot,
            pointer_payload=source_payload["pointer"],
        ),
    )


def _normalize_request_payload(request_payload: dict[str, Any]) -> dict[str, Any]:
    """Merge arbitrary caller data into one safe, complete request payload."""

    normalized_request_payload = build_default_request_payload()
    _deep_merge(normalized_request_payload, request_payload)

    normalized_request_payload["target"]["host"] = (
        str(normalized_request_payload["target"].get("host", DEFAULT_VISUALIZER_HOST)).strip()
        or DEFAULT_VISUALIZER_HOST
    )
    normalized_request_payload["target"]["port"] = _clamp_int(
        normalized_request_payload["target"].get("port"),
        DEFAULT_VISUALIZER_PORT,
        1,
        65535,
    )

    normalized_scene_mode = str(
        normalized_request_payload.get("sceneMode", DEFAULT_SCENE_MODE)
    ).strip().lower()
    if normalized_scene_mode not in SUPPORTED_SCENE_MODES:
        normalized_scene_mode = DEFAULT_SCENE_MODE
    normalized_request_payload["sceneMode"] = normalized_scene_mode

    source_payload = normalized_request_payload["source"]
    normalized_source_mode = str(source_payload.get("mode", DEFAULT_SOURCE_MODE)).strip().lower()
    if normalized_source_mode not in SUPPORTED_SOURCE_MODES:
        normalized_source_mode = DEFAULT_SOURCE_MODE
    source_payload["mode"] = normalized_source_mode
    source_payload["jsonText"] = str(
        source_payload.get("jsonText", EXAMPLE_INPUT_DOCUMENTS["numeric_wave"])
    ).strip() or EXAMPLE_INPUT_DOCUMENTS["numeric_wave"]
    source_payload["plainText"] = str(source_payload.get("plainText", DEFAULT_PLAIN_TEXT_SOURCE))
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
    normalized_audio_device_flow = (
        str(source_payload["audio"].get("deviceFlow", "output")).strip().lower()
    )
    if normalized_audio_device_flow not in {"input", "output"}:
        normalized_audio_device_flow = "output"
    source_payload["audio"]["deviceFlow"] = normalized_audio_device_flow
    source_payload["audio"]["deviceIdentifier"] = str(
        source_payload["audio"].get("deviceIdentifier", "")
    )

    preset_scene_catalog_payload = build_preset_scene_catalog_payload()
    valid_preset_identifiers = {
        preset_entry["id"] for preset_entry in preset_scene_catalog_payload["presets"]
    }
    selected_preset_identifier = str(
        normalized_request_payload["presetScene"].get("presetId", DEFAULT_DESKTOP_PRESET_ID)
    )
    if selected_preset_identifier not in valid_preset_identifiers:
        selected_preset_identifier = DEFAULT_DESKTOP_PRESET_ID
    normalized_request_payload["presetScene"]["presetId"] = selected_preset_identifier
    normalized_request_payload["presetScene"]["useEpoch"] = bool(
        normalized_request_payload["presetScene"].get("useEpoch", True)
    )
    normalized_request_payload["presetScene"]["useNoise"] = bool(
        normalized_request_payload["presetScene"].get("useNoise", True)
    )

    default_bar_wall_request_payload = build_default_bar_wall_request_payload()
    supported_shader_styles = set(build_bar_wall_catalog_payload()["shaderStyles"])
    normalized_shader_style = str(
        normalized_request_payload["barWallScene"]["render"].get(
            "shaderStyle",
            default_bar_wall_request_payload["render"]["shaderStyle"],
        )
    ).strip().lower()
    if normalized_shader_style not in supported_shader_styles:
        normalized_shader_style = str(default_bar_wall_request_payload["render"]["shaderStyle"])
    normalized_request_payload["barWallScene"]["render"]["shaderStyle"] = normalized_shader_style
    normalized_request_payload["barWallScene"]["render"]["barGridSize"] = _clamp_int(
        normalized_request_payload["barWallScene"]["render"].get("barGridSize"),
        int(default_bar_wall_request_payload["render"]["barGridSize"]),
        2,
        24,
    )
    normalized_request_payload["barWallScene"]["render"]["antiAliasing"] = bool(
        normalized_request_payload["barWallScene"]["render"].get("antiAliasing", True)
    )
    normalized_request_payload["barWallScene"]["range"]["mode"] = (
        "manual"
        if str(
            normalized_request_payload["barWallScene"]["range"].get("mode", "automatic")
        ).strip().lower()
        == "manual"
        else "automatic"
    )
    normalized_request_payload["barWallScene"]["range"]["manualMinimum"] = _clamp_float(
        normalized_request_payload["barWallScene"]["range"].get("manualMinimum"),
        float(default_bar_wall_request_payload["range"]["manualMinimum"]),
        -1_000_000.0,
        1_000_000.0,
    )
    normalized_request_payload["barWallScene"]["range"]["manualMaximum"] = _clamp_float(
        normalized_request_payload["barWallScene"]["range"].get("manualMaximum"),
        float(default_bar_wall_request_payload["range"]["manualMaximum"]),
        -1_000_000.0,
        1_000_000.0,
    )
    if (
        normalized_request_payload["barWallScene"]["range"]["manualMaximum"]
        <= normalized_request_payload["barWallScene"]["range"]["manualMinimum"]
    ):
        normalized_request_payload["barWallScene"]["range"]["manualMaximum"] = (
            normalized_request_payload["barWallScene"]["range"]["manualMinimum"] + 1.0
        )
    normalized_request_payload["barWallScene"]["range"]["rollingHistoryValueCount"] = _clamp_int(
        normalized_request_payload["barWallScene"]["range"].get("rollingHistoryValueCount"),
        int(default_bar_wall_request_payload["range"]["rollingHistoryValueCount"]),
        32,
        50_000,
    )
    normalized_request_payload["barWallScene"]["range"]["standardDeviationMultiplier"] = (
        _clamp_float(
            normalized_request_payload["barWallScene"]["range"].get(
                "standardDeviationMultiplier"
            ),
            float(default_bar_wall_request_payload["range"]["standardDeviationMultiplier"]),
            0.1,
            6.0,
        )
    )

    normalized_request_payload["session"]["cadenceMs"] = _clamp_int(
        normalized_request_payload["session"].get("cadenceMs"),
        DEFAULT_LIVE_CADENCE_MS,
        40,
        2000,
    )
    return normalized_request_payload


def _parse_json_document(json_text: str) -> Any:
    """Parse one Visualizer Studio JSON document with friendly errors."""

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as error:
        raise ValueError(
            "Visualizer Studio could not parse the provided JSON document. "
            f"Line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error


def _audio_snapshot_to_numeric_values(audio_signal_snapshot: AudioSignalSnapshot) -> list[float]:
    """Expand one audio snapshot into a longer numeric stream for downstream builders."""

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
    """Build a readable summary of the current source values for the UI."""

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


def _build_preset_scene_preview_bundle(
    normalized_request_payload: dict[str, Any],
    collected_source_data: CollectedSourceData,
) -> dict[str, Any]:
    """Build the original preset-scene family using live source signals."""

    preset_scene_request_payload = build_default_preset_scene_request_payload(
        str(normalized_request_payload["presetScene"]["presetId"])
    )
    preset_scene_request_payload["target"] = dict(normalized_request_payload["target"])
    preset_scene_request_payload["signals"] = collected_source_data.preset_scene_signal_payload
    preset_scene_request_payload["session"]["cadenceMs"] = normalized_request_payload["session"][
        "cadenceMs"
    ]
    preset_scene_bundle = build_preset_scene_bundle(preset_scene_request_payload)
    preset_scene_bundle["analysis"]["sourceMode"] = collected_source_data.source_mode
    preset_scene_bundle["analysis"]["sourceValueCount"] = len(collected_source_data.numeric_values)
    return preset_scene_bundle


def _build_bar_wall_scene_result(
    normalized_request_payload: dict[str, Any],
    collected_source_data: CollectedSourceData,
    *,
    bar_wall_rolling_history_values: list[float] | None,
) -> Any:
    """Build the bar-wall scene family using the current generic source data."""

    default_bar_wall_request_payload = build_default_bar_wall_request_payload()
    bar_wall_request_payload = {
        "target": dict(normalized_request_payload["target"]),
        "externalAudioBridge": dict(default_bar_wall_request_payload["externalAudioBridge"]),
        "data": {"jsonText": collected_source_data.bar_wall_source_json_text},
        "render": dict(normalized_request_payload["barWallScene"]["render"]),
        "range": dict(normalized_request_payload["barWallScene"]["range"]),
        "session": {"cadenceMs": normalized_request_payload["session"]["cadenceMs"]},
    }
    return build_spectrograph_scene_result(
        bar_wall_request_payload,
        rolling_history_values=bar_wall_rolling_history_values,
    )


def _build_preset_scene_signal_payload(
    *,
    normalized_request_payload: dict[str, Any],
    source_mode: str,
    numeric_values: list[float],
    audio_signal_snapshot: AudioSignalSnapshot | None,
    pointer_payload: dict[str, Any],
) -> dict[str, Any]:
    """Translate the source snapshot into the live signals used by preset scenes."""

    use_epoch_signal = bool(normalized_request_payload["presetScene"]["useEpoch"])
    use_noise_signal = bool(normalized_request_payload["presetScene"]["useNoise"])

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
            "manual": {"drive": _clamp_float(audio_signal_snapshot.level, 0.0, 0.0, 2.0)},
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
    """Summarize one numeric stream into the smaller live signals preset scenes need."""

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
