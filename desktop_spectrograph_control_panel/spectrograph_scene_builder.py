"""Build spectrograph-style 3D scenes from generic JSON input.

This module is the most domain-specific part of the new control suite.
Its job is to answer a practical question:

"If a user pastes almost any JSON document, how can we turn that into a
meaningful wall of 3D bars for the renderer?"

The code below does that in several stages:

1. Parse raw JSON text into Python values.
2. Flatten those values into one numeric stream.
3. Maintain a rolling statistical history so the active range can adapt.
4. Divide the numeric stream into equally sized bar groups.
5. Normalize each group into a 0..1 intensity.
6. Turn those intensities into a colored 3D bar grid scene.

The end product is still ordinary Halcyn scene JSON, which means the existing
native renderer and HTTP API can keep doing what they already do well.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

DEFAULT_SPECTROGRAPH_HOST = "127.0.0.1"
DEFAULT_SPECTROGRAPH_PORT = 8090
DEFAULT_BAR_GRID_SIZE = 8
DEFAULT_LIVE_CADENCE_MS = 250
DEFAULT_ROLLING_HISTORY_VALUE_COUNT = 4096
DEFAULT_STANDARD_DEVIATION_MULTIPLIER = 2.0
DEFAULT_FLOOR_HEIGHT = 0.08
DEFAULT_PEAK_HEIGHT = 3.4
MINIMUM_BAR_GRID_SIZE = 2
MAXIMUM_BAR_GRID_SIZE = 24
SUPPORTED_SHADER_STYLES = ("standard", "neon", "heatmap")

EXAMPLE_INPUT_DOCUMENTS: dict[str, str] = {
    "numeric_wave": json.dumps(
        {
            "values": [0.0, 1.0, 3.0, 1.5, 0.5, 2.5, 4.0, 2.0, 1.0, 0.25],
            "secondary": [4, 2, 1, 0, 3, 5, 2, 1],
        },
        indent=2,
    ),
    "nested_mixed": json.dumps(
        {
            "frames": [
                {"left": [0.2, 0.4, 0.6], "right": [0.1, 0.8, 0.3]},
                {"tag": "HELLO", "enabled": True},
                {"deep": {"values": [13, 21, 34, 55]}},
            ]
        },
        indent=2,
    ),
    "string_heavy": json.dumps(
        {
            "title": "Spectrograph",
            "subtitle": "Strings become byte values.",
            "notes": ["Color", "Range", "Bars", "Shader"],
        },
        indent=2,
    ),
}


@dataclass(frozen=True)
class SpectrographBuildResult:
    """Store the full result of turning one control payload into one scene.

    The control window needs more than just a final scene object. It also needs:

    - the normalized request payload that was actually used
    - statistics for the operator-facing status panel
    - the flattened values that fed the current frame
    - the next rolling-history buffer to use after a successful apply
    """

    normalized_request_payload: dict[str, Any]
    target: dict[str, Any]
    scene: dict[str, Any]
    analysis: dict[str, Any]
    flattened_source_values: list[float]
    next_rolling_history_values: list[float]


def build_catalog_payload() -> dict[str, Any]:
    """Return a small metadata catalog for the desktop spectrograph panel."""

    return {
        "status": "ok",
        "shaderStyles": list(SUPPORTED_SHADER_STYLES),
        "examples": [
            {
                "id": example_identifier,
                "name": example_identifier.replace("_", " ").title(),
                "jsonText": example_json_text,
            }
            for example_identifier, example_json_text in EXAMPLE_INPUT_DOCUMENTS.items()
        ],
        "defaults": {
            "host": DEFAULT_SPECTROGRAPH_HOST,
            "port": DEFAULT_SPECTROGRAPH_PORT,
            "barGridSize": DEFAULT_BAR_GRID_SIZE,
            "liveCadenceMs": DEFAULT_LIVE_CADENCE_MS,
        },
    }


def build_default_request_payload() -> dict[str, Any]:
    """Return a complete editable payload for the spectrograph control panel."""

    return {
        "target": {
            "host": DEFAULT_SPECTROGRAPH_HOST,
            "port": DEFAULT_SPECTROGRAPH_PORT,
        },
        "data": {
            "jsonText": EXAMPLE_INPUT_DOCUMENTS["numeric_wave"],
        },
        "render": {
            "barGridSize": DEFAULT_BAR_GRID_SIZE,
            "antiAliasing": True,
            "shaderStyle": "heatmap",
            "floorHeight": DEFAULT_FLOOR_HEIGHT,
            "peakHeight": DEFAULT_PEAK_HEIGHT,
        },
        "range": {
            "mode": "automatic",
            "manualMinimum": 0.0,
            "manualMaximum": 255.0,
            "rollingHistoryValueCount": DEFAULT_ROLLING_HISTORY_VALUE_COUNT,
            "standardDeviationMultiplier": DEFAULT_STANDARD_DEVIATION_MULTIPLIER,
        },
        "session": {
            "cadenceMs": DEFAULT_LIVE_CADENCE_MS,
        },
    }


def build_spectrograph_scene_result(
    request_payload: dict[str, Any],
    rolling_history_values: list[float] | None = None,
) -> SpectrographBuildResult:
    """Turn one editable request payload into a renderer-ready 3D bar scene."""

    normalized_request_payload = _normalize_request_payload(request_payload)
    parsed_input_document = _parse_json_text(
        normalized_request_payload["data"]["jsonText"],
    )
    flattened_source_values = flatten_generic_json_value(parsed_input_document)
    if not flattened_source_values:
        flattened_source_values = [0.0]

    prior_history_values = list(rolling_history_values or [])
    normalized_range_settings = normalized_request_payload["range"]
    next_rolling_history_values = _build_next_rolling_history_values(
        prior_history_values,
        flattened_source_values,
        rolling_history_value_count=int(normalized_range_settings["rollingHistoryValueCount"]),
    )

    rolling_statistics = _build_rolling_statistics(next_rolling_history_values)
    active_range_minimum, active_range_maximum, normalization_mode = _determine_active_range(
        normalized_range_settings,
        rolling_statistics,
    )

    bar_grid_size = int(normalized_request_payload["render"]["barGridSize"])
    grouped_bar_values = _group_values_for_bar_grid(
        flattened_source_values,
        target_bar_count=bar_grid_size * bar_grid_size,
    )

    normalized_group_values = []
    clipped_value_count = 0
    for grouped_value in grouped_bar_values:
        normalized_value = _normalize_value_into_range(
            grouped_value,
            active_range_minimum,
            active_range_maximum,
        )
        if grouped_value < active_range_minimum or grouped_value > active_range_maximum:
            clipped_value_count += 1
        normalized_group_values.append(normalized_value)

    scene = _build_three_dimensional_bar_scene(
        grouped_bar_values=grouped_bar_values,
        normalized_group_values=normalized_group_values,
        render_settings=normalized_request_payload["render"],
    )
    analysis = {
        "sourceValueCount": len(flattened_source_values),
        "rollingHistoryValueCount": len(next_rolling_history_values),
        "barGridSize": bar_grid_size,
        "barCount": len(grouped_bar_values),
        "groupSize": max(1, math.ceil(len(flattened_source_values) / len(grouped_bar_values))),
        "observedMinimum": rolling_statistics["observedMinimum"],
        "observedMaximum": rolling_statistics["observedMaximum"],
        "rollingMean": rolling_statistics["mean"],
        "rollingStandardDeviation": rolling_statistics["standardDeviation"],
        "activeRangeMinimum": active_range_minimum,
        "activeRangeMaximum": active_range_maximum,
        "rangeMode": normalization_mode,
        "clippedValueCount": clipped_value_count,
        "firstSourceValues": flattened_source_values[:12],
        "firstGroupedValues": grouped_bar_values[:12],
    }

    return SpectrographBuildResult(
        normalized_request_payload=normalized_request_payload,
        target=normalized_request_payload["target"],
        scene=scene,
        analysis=analysis,
        flattened_source_values=flattened_source_values,
        next_rolling_history_values=next_rolling_history_values,
    )


def flatten_generic_json_value(value: Any) -> list[float]:
    """Flatten arbitrary JSON-shaped data into one numeric stream.

    The conversion rules are intentionally simple and predictable:

    - numbers stay numbers
    - booleans become `1.0` or `0.0`
    - strings become UTF-8 byte values
    - arrays recurse over items in order
    - objects recurse over values in insertion order
    - `null` contributes no numeric values
    """

    collected_values: list[float] = []
    _append_flattened_values(value, collected_values)
    return collected_values


def _append_flattened_values(value: Any, collected_values: list[float]) -> None:
    """Append values recursively to one shared numeric collection."""

    if value is None:
        return

    if isinstance(value, bool):
        collected_values.append(1.0 if value else 0.0)
        return

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric_value = float(value)
        if math.isfinite(numeric_value):
            collected_values.append(numeric_value)
        return

    if isinstance(value, str):
        collected_values.extend(float(byte_value) for byte_value in value.encode("utf-8"))
        return

    if isinstance(value, list):
        for item in value:
            _append_flattened_values(item, collected_values)
        return

    if isinstance(value, dict):
        for nested_value in value.values():
            _append_flattened_values(nested_value, collected_values)
        return

    fallback_text = str(value)
    collected_values.extend(float(byte_value) for byte_value in fallback_text.encode("utf-8"))


def _parse_json_text(json_text: str) -> Any:
    """Parse the operator-supplied JSON text into Python values."""

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as error:
        raise ValueError(
            "The provided JSON data could not be parsed. "
            f"Line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error


def _normalize_request_payload(request_payload: dict[str, Any]) -> dict[str, Any]:
    """Merge arbitrary caller data into the spectrograph panel's full payload shape."""

    default_payload = build_default_request_payload()
    merged_payload = json.loads(json.dumps(default_payload))
    _deep_merge(merged_payload, request_payload)

    normalized_shader_style = str(merged_payload["render"].get("shaderStyle", "heatmap")).lower()
    if normalized_shader_style not in SUPPORTED_SHADER_STYLES:
        normalized_shader_style = "heatmap"

    range_mode = str(merged_payload["range"].get("mode", "automatic")).lower()
    if range_mode not in {"automatic", "manual"}:
        range_mode = "automatic"

    merged_payload["target"]["host"] = (
        str(merged_payload["target"].get("host", DEFAULT_SPECTROGRAPH_HOST)).strip()
        or DEFAULT_SPECTROGRAPH_HOST
    )
    merged_payload["target"]["port"] = _clamp_int(
        merged_payload["target"].get("port"),
        DEFAULT_SPECTROGRAPH_PORT,
        1,
        65535,
    )
    merged_payload["data"]["jsonText"] = str(merged_payload["data"].get("jsonText", "")).strip()
    if not merged_payload["data"]["jsonText"]:
        merged_payload["data"]["jsonText"] = EXAMPLE_INPUT_DOCUMENTS["numeric_wave"]

    merged_payload["render"]["barGridSize"] = _clamp_int(
        merged_payload["render"].get("barGridSize"),
        DEFAULT_BAR_GRID_SIZE,
        MINIMUM_BAR_GRID_SIZE,
        MAXIMUM_BAR_GRID_SIZE,
    )
    merged_payload["render"]["antiAliasing"] = bool(
        merged_payload["render"].get("antiAliasing", True)
    )
    merged_payload["render"]["shaderStyle"] = normalized_shader_style
    merged_payload["render"]["floorHeight"] = _clamp_float(
        merged_payload["render"].get("floorHeight"),
        DEFAULT_FLOOR_HEIGHT,
        0.02,
        1.0,
    )
    merged_payload["render"]["peakHeight"] = _clamp_float(
        merged_payload["render"].get("peakHeight"),
        DEFAULT_PEAK_HEIGHT,
        0.5,
        8.0,
    )

    merged_payload["range"]["mode"] = range_mode
    merged_payload["range"]["manualMinimum"] = _clamp_float(
        merged_payload["range"].get("manualMinimum"),
        0.0,
        -1_000_000.0,
        1_000_000.0,
    )
    merged_payload["range"]["manualMaximum"] = _clamp_float(
        merged_payload["range"].get("manualMaximum"),
        255.0,
        -1_000_000.0,
        1_000_000.0,
    )
    if merged_payload["range"]["manualMaximum"] <= merged_payload["range"]["manualMinimum"]:
        merged_payload["range"]["manualMaximum"] = merged_payload["range"]["manualMinimum"] + 1.0

    merged_payload["range"]["rollingHistoryValueCount"] = _clamp_int(
        merged_payload["range"].get("rollingHistoryValueCount"),
        DEFAULT_ROLLING_HISTORY_VALUE_COUNT,
        32,
        50_000,
    )
    merged_payload["range"]["standardDeviationMultiplier"] = _clamp_float(
        merged_payload["range"].get("standardDeviationMultiplier"),
        DEFAULT_STANDARD_DEVIATION_MULTIPLIER,
        0.1,
        6.0,
    )
    merged_payload["session"]["cadenceMs"] = _clamp_int(
        merged_payload["session"].get("cadenceMs"),
        DEFAULT_LIVE_CADENCE_MS,
        40,
        2000,
    )
    return merged_payload


def _build_next_rolling_history_values(
    prior_history_values: list[float],
    current_values: list[float],
    *,
    rolling_history_value_count: int,
) -> list[float]:
    """Append the latest values to the rolling history and trim to the requested size."""

    combined_values = list(prior_history_values) + list(current_values)
    if len(combined_values) <= rolling_history_value_count:
        return combined_values
    return combined_values[-rolling_history_value_count:]


def _build_rolling_statistics(rolling_history_values: list[float]) -> dict[str, float]:
    """Summarize the rolling numeric history with stable, beginner-readable fields."""

    if not rolling_history_values:
        return {
            "observedMinimum": 0.0,
            "observedMaximum": 1.0,
            "mean": 0.5,
            "standardDeviation": 0.25,
        }

    observed_minimum = min(rolling_history_values)
    observed_maximum = max(rolling_history_values)
    mean_value = sum(rolling_history_values) / len(rolling_history_values)
    variance = (
        sum((history_value - mean_value) ** 2 for history_value in rolling_history_values)
        / len(rolling_history_values)
    )
    standard_deviation = math.sqrt(variance)

    if standard_deviation < 1e-6:
        fallback_spread = max(1.0, abs(mean_value) * 0.1, observed_maximum - observed_minimum)
        standard_deviation = fallback_spread * 0.5

    return {
        "observedMinimum": observed_minimum,
        "observedMaximum": observed_maximum,
        "mean": mean_value,
        "standardDeviation": standard_deviation,
    }


def _determine_active_range(
    range_settings: dict[str, Any],
    rolling_statistics: dict[str, float],
) -> tuple[float, float, str]:
    """Choose the active normalization range from either manual or automatic settings."""

    if range_settings["mode"] == "manual":
        return (
            float(range_settings["manualMinimum"]),
            float(range_settings["manualMaximum"]),
            "manual",
        )

    mean_value = float(rolling_statistics["mean"])
    standard_deviation = float(rolling_statistics["standardDeviation"])
    multiplier = float(range_settings["standardDeviationMultiplier"])
    automatic_minimum = mean_value - (standard_deviation * multiplier)
    automatic_maximum = mean_value + (standard_deviation * multiplier)

    if automatic_maximum <= automatic_minimum:
        automatic_maximum = automatic_minimum + 1.0

    return automatic_minimum, automatic_maximum, "automatic"


def _group_values_for_bar_grid(source_values: list[float], target_bar_count: int) -> list[float]:
    """Compress an arbitrary-length numeric stream into exactly one value per bar."""

    if not source_values:
        return [0.0] * target_bar_count

    if len(source_values) < target_bar_count:
        repeated_values = [
            source_values[bar_index % len(source_values)]
            for bar_index in range(target_bar_count)
        ]
        return repeated_values

    base_group_size = len(source_values) // target_bar_count
    remainder_group_count = len(source_values) % target_bar_count
    grouped_values: list[float] = []
    current_value_index = 0

    for bar_index in range(target_bar_count):
        current_group_size = base_group_size + (1 if bar_index < remainder_group_count else 0)
        current_group = source_values[
            current_value_index : current_value_index + current_group_size
        ]
        current_value_index += current_group_size
        if current_group:
            grouped_values.append(sum(current_group) / len(current_group))
        else:
            grouped_values.append(0.0)

    return grouped_values


def _normalize_value_into_range(value: float, range_minimum: float, range_maximum: float) -> float:
    """Convert one numeric value into the normalized 0..1 range used for bar heights."""

    if range_maximum <= range_minimum:
        return 0.0

    normalized_value = (value - range_minimum) / (range_maximum - range_minimum)
    return max(0.0, min(1.0, normalized_value))


def _build_three_dimensional_bar_scene(
    *,
    grouped_bar_values: list[float],
    normalized_group_values: list[float],
    render_settings: dict[str, Any],
) -> dict[str, Any]:
    """Build the final Halcyn 3D scene JSON document."""

    bar_grid_size = int(render_settings["barGridSize"])
    floor_height = float(render_settings["floorHeight"])
    peak_height = float(render_settings["peakHeight"])
    cell_spacing = 0.92
    bar_width = 0.64
    bar_depth = 0.64
    vertices: list[dict[str, float]] = []
    indices: list[int] = []

    for bar_index, grouped_value in enumerate(grouped_bar_values):
        normalized_value = normalized_group_values[bar_index]
        row_index = bar_index // bar_grid_size
        column_index = bar_index % bar_grid_size
        bar_center_x = (
            float(column_index) - (float(bar_grid_size - 1) * 0.5)
        ) * cell_spacing
        bar_center_z = (
            float(row_index) - (float(bar_grid_size - 1) * 0.5)
        ) * cell_spacing
        bar_height = floor_height + (normalized_value * peak_height)
        bar_color = _build_bar_color(
            normalized_value=normalized_value,
            row_fraction=0.0 if bar_grid_size == 1 else row_index / (bar_grid_size - 1),
            column_fraction=0.0 if bar_grid_size == 1 else column_index / (bar_grid_size - 1),
            raw_grouped_value=grouped_value,
        )
        _append_bar_prism(
            vertices=vertices,
            indices=indices,
            center_x=bar_center_x,
            center_z=bar_center_z,
            width=bar_width,
            depth=bar_depth,
            height=bar_height,
            color=bar_color,
        )

    camera_distance = max(6.5, bar_grid_size * 0.95)
    camera_height = max(4.5, peak_height * 1.9)
    return {
        "sceneType": "3d",
        "primitive": "triangles",
        "clearColor": {"r": 0.03, "g": 0.04, "b": 0.08, "a": 1.0},
        "camera": {
            "position": {"x": camera_distance, "y": camera_height, "z": camera_distance},
            "target": {"x": 0.0, "y": peak_height * 0.45, "z": 0.0},
            "up": {"x": 0.0, "y": 1.0, "z": 0.0},
            "fovYDegrees": 52.0,
            "nearPlane": 0.1,
            "farPlane": 100.0,
        },
        "renderStyle": {
            "shader": str(render_settings["shaderStyle"]),
            "antiAliasing": bool(render_settings["antiAliasing"]),
        },
        "vertices": vertices,
        "indices": indices,
    }


def _append_bar_prism(
    *,
    vertices: list[dict[str, float]],
    indices: list[int],
    center_x: float,
    center_z: float,
    width: float,
    depth: float,
    height: float,
    color: tuple[float, float, float, float],
) -> None:
    """Append one rectangular prism to the shared scene buffers."""

    half_width = width * 0.5
    half_depth = depth * 0.5
    red, green, blue, alpha = color
    first_vertex_index = len(vertices)

    def build_vertex(x: float, y: float, z: float) -> dict[str, float]:
        return {
            "x": x,
            "y": y,
            "z": z,
            "r": red,
            "g": green,
            "b": blue,
            "a": alpha,
        }

    vertices.extend(
        [
            build_vertex(center_x - half_width, 0.0, center_z - half_depth),
            build_vertex(center_x + half_width, 0.0, center_z - half_depth),
            build_vertex(center_x + half_width, 0.0, center_z + half_depth),
            build_vertex(center_x - half_width, 0.0, center_z + half_depth),
            build_vertex(center_x - half_width, height, center_z - half_depth),
            build_vertex(center_x + half_width, height, center_z - half_depth),
            build_vertex(center_x + half_width, height, center_z + half_depth),
            build_vertex(center_x - half_width, height, center_z + half_depth),
        ]
    )

    cube_triangle_indices = [
        0,
        1,
        2,
        0,
        2,
        3,
        4,
        5,
        6,
        4,
        6,
        7,
        0,
        1,
        5,
        0,
        5,
        4,
        1,
        2,
        6,
        1,
        6,
        5,
        2,
        3,
        7,
        2,
        7,
        6,
        3,
        0,
        4,
        3,
        4,
        7,
    ]
    indices.extend(first_vertex_index + triangle_index for triangle_index in cube_triangle_indices)


def _build_bar_color(
    *,
    normalized_value: float,
    row_fraction: float,
    column_fraction: float,
    raw_grouped_value: float,
) -> tuple[float, float, float, float]:
    """Build one vertex color from the normalized data intensity.

    The color intentionally depends mostly on normalized intensity, but the row
    and column fractions add a small amount of spatial variation so the grid
    reads more clearly than a perfectly uniform color ramp.
    """

    del raw_grouped_value
    if normalized_value < 0.5:
        local_fraction = normalized_value / 0.5
        low_color = (0.08, 0.25, 0.86)
        middle_color = (0.18, 0.84, 0.68)
        base_red = _blend(low_color[0], middle_color[0], local_fraction)
        base_green = _blend(low_color[1], middle_color[1], local_fraction)
        base_blue = _blend(low_color[2], middle_color[2], local_fraction)
    else:
        local_fraction = (normalized_value - 0.5) / 0.5
        middle_color = (0.18, 0.84, 0.68)
        high_color = (1.0, 0.32, 0.08)
        base_red = _blend(middle_color[0], high_color[0], local_fraction)
        base_green = _blend(middle_color[1], high_color[1], local_fraction)
        base_blue = _blend(middle_color[2], high_color[2], local_fraction)

    spatial_lift = (row_fraction * 0.07) + (column_fraction * 0.05)
    return (
        min(1.0, base_red + spatial_lift),
        min(1.0, base_green + (column_fraction * 0.03)),
        min(1.0, base_blue + (row_fraction * 0.02)),
        1.0,
    )


def _blend(start_value: float, end_value: float, fraction: float) -> float:
    """Linearly interpolate between two floats."""

    return start_value + ((end_value - start_value) * fraction)


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> None:
    """Recursively merge `update` into `base` in place."""

    for key, value in update.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _clamp_int(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    """Convert one value to an int and clamp it into a safe range."""

    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return fallback


def _clamp_float(value: Any, fallback: float, minimum: float, maximum: float) -> float:
    """Convert one value to a float and clamp it into a safe range."""

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return fallback

    if not math.isfinite(numeric_value):
        return fallback
    return max(minimum, min(maximum, numeric_value))
