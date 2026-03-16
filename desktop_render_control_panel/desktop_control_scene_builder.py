"""Build 2D and 3D scenes for the desktop render control panel.

The browser Scene Studio already knows how to generate several 3D presets.
The desktop control panel reuses those 3D generators, then adds desktop-only
2D presets and a slightly richer catalog so one native app can switch between
2D and 3D instantly.

This module is intentionally "scene language first."  It takes a friendly,
editable control payload and turns that into the exact scene JSON shape the
renderer already understands.
"""

from __future__ import annotations

import math
import string
import time
from dataclasses import dataclass
from typing import Any

from browser_control_center import scene_studio_scene_builder

DEFAULT_DESKTOP_PRESET_ID = "signal-weave-2d"


@dataclass(frozen=True)
class DesktopPresetDefinition:
    """Describe one desktop control panel preset.

    Attributes:
        preset_id: Stable identifier used in payloads and tests.
        name: Friendly display name shown in the GUI.
        scene_type: Either "2d" or "3d" so the UI can filter quickly.
        summary: Short description used in catalogs and docs.
        emphasis: Tiny hint about the signals that shape the preset most.
        defaults: Settings that become the starting values for this preset.
    """

    preset_id: str
    name: str
    scene_type: str
    summary: str
    emphasis: str
    defaults: dict[str, Any]

    def catalog_entry(self) -> dict[str, Any]:
        """Convert the preset into JSON-ready metadata for the desktop UI."""

        return {
            "id": self.preset_id,
            "name": self.name,
            "sceneType": self.scene_type,
            "summary": self.summary,
            "emphasis": self.emphasis,
            "defaults": self.defaults,
        }


DESKTOP_ONLY_PRESETS: dict[str, DesktopPresetDefinition] = {
    "signal-weave-2d": DesktopPresetDefinition(
        preset_id="signal-weave-2d",
        name="Signal Weave 2D",
        scene_type="2d",
        summary=(
            "A responsive line field for waveform-like 2D motion "
            "and audio-reactive color drift."
        ),
        emphasis="epoch + pointer + audio",
        defaults={
            "density": 96,
            "pointSize": 6.0,
            "lineWidth": 3.0,
            "speed": 1.1,
            "gain": 1.1,
            "manualDrive": 0.35,
            "background": "#07111f",
            "primaryColor": "#6ed6ff",
            "secondaryColor": "#ffd080",
        },
    ),
    "pulse-grid-2d": DesktopPresetDefinition(
        preset_id="pulse-grid-2d",
        name="Pulse Grid 2D",
        scene_type="2d",
        summary=(
            "A pulsing point lattice that is easy to read while tuning "
            "timing and gain controls."
        ),
        emphasis="epoch + noise + manual",
        defaults={
            "density": 144,
            "pointSize": 8.0,
            "lineWidth": 2.0,
            "speed": 0.9,
            "gain": 1.0,
            "manualDrive": 0.45,
            "background": "#0d1322",
            "primaryColor": "#89ffb8",
            "secondaryColor": "#7fa7ff",
        },
    ),
}

DESKTOP_SOURCE_CATALOG: list[dict[str, str]] = [
    {
        "id": "epoch",
        "name": "Unix time",
        "description": "A continuously changing phase source derived from epoch seconds.",
    },
    {
        "id": "noise",
        "name": "Noise",
        "description": (
            "Deterministic pseudo-random variation that keeps scenes "
            "from feeling frozen."
        ),
    },
    {
        "id": "pointer",
        "name": "Pointer pad",
        "description": (
            "Normalized pointer position and speed captured inside "
            "the desktop control panel."
        ),
    },
    {
        "id": "audio",
        "name": "Audio input device",
        "description": (
            "Real local audio-device analysis routed into level, bass, "
            "mid, and treble bands."
        ),
    },
    {
        "id": "manual",
        "name": "Manual drive",
        "description": (
            "A deterministic fallback slider that works even when "
            "no live input is active."
        ),
    },
]


def build_catalog_payload() -> dict[str, Any]:
    """Return preset and source metadata for the desktop control panel.

    The UI uses this payload to decide:

    - which presets belong under the 2D picker
    - which presets belong under the 3D picker
    - which signal sources can be explained to the user
    - what the starting preset/host/port/cadence should be
    """

    browser_presets = [
        {
            **browser_preset.catalog_entry(),
            "sceneType": "3d",
        }
        for browser_preset in scene_studio_scene_builder.PRESETS.values()
    ]
    desktop_presets = [preset.catalog_entry() for preset in DESKTOP_ONLY_PRESETS.values()]

    return {
        "status": "ok",
        "presets": desktop_presets + browser_presets,
        "sources": DESKTOP_SOURCE_CATALOG,
        "defaults": {
            "presetId": DEFAULT_DESKTOP_PRESET_ID,
            "target": {
                "host": scene_studio_scene_builder.DEFAULT_TARGET_HOST,
                "port": scene_studio_scene_builder.DEFAULT_TARGET_PORT,
            },
            "session": {"cadenceMs": scene_studio_scene_builder.DEFAULT_AUTO_APPLY_MS},
        },
    }


def build_default_request_payload(preset_id: str = DEFAULT_DESKTOP_PRESET_ID) -> dict[str, Any]:
    """Return a full control payload ready for editing by the desktop UI.

    Returning a complete payload instead of a sparse one keeps the UI simpler.
    Every slider, checkbox, and color field can always assume its backing value
    exists.
    """

    safe_preset_id = preset_id if preset_id in _all_presets() else DEFAULT_DESKTOP_PRESET_ID
    defaults = _preset_defaults(safe_preset_id)

    return {
        "presetId": safe_preset_id,
        "target": {
            "host": scene_studio_scene_builder.DEFAULT_TARGET_HOST,
            "port": scene_studio_scene_builder.DEFAULT_TARGET_PORT,
        },
        "settings": {
            "density": int(defaults["density"]),
            "pointSize": float(defaults["pointSize"]),
            "lineWidth": float(defaults["lineWidth"]),
            "speed": float(defaults["speed"]),
            "gain": float(defaults["gain"]),
            "manualDrive": float(defaults["manualDrive"]),
            "background": str(defaults["background"]),
            "primaryColor": str(defaults["primaryColor"]),
            "secondaryColor": str(defaults["secondaryColor"]),
        },
        "signals": {
            "useEpoch": True,
            "useNoise": True,
            "usePointer": True,
            "useAudio": False,
            "pointer": {"x": 0.5, "y": 0.5, "speed": 0.0},
            "audio": {"level": 0.0, "bass": 0.0, "mid": 0.0, "treble": 0.0},
            "manual": {"drive": float(defaults["manualDrive"])},
            "noiseSeed": 1.0,
            "epochSeconds": time.time(),
        },
        "session": {"cadenceMs": scene_studio_scene_builder.DEFAULT_AUTO_APPLY_MS},
    }


def build_scene_bundle(request_payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize one desktop request and return the generated scene plus metadata.

    A *bundle* contains more than the final scene JSON. It also includes the
    chosen preset metadata, normalized settings, normalized signals, the target
    renderer host/port, and a tiny analysis summary for the preview UI.
    """

    preset_id = str(request_payload.get("presetId", DEFAULT_DESKTOP_PRESET_ID))
    if preset_id in scene_studio_scene_builder.PRESETS:
        # The existing browser Scene Studio already owns these 3D generators, so we
        # defer to that code instead of maintaining two slightly-different copies.
        browser_bundle = scene_studio_scene_builder.build_scene_bundle(request_payload)
        browser_bundle["preset"]["sceneType"] = "3d"
        browser_bundle["analysis"]["sceneType"] = browser_bundle["scene"]["sceneType"]
        return browser_bundle

    if preset_id not in DESKTOP_ONLY_PRESETS:
        preset_id = DEFAULT_DESKTOP_PRESET_ID

    settings_payload = request_payload.get("settings", {})
    settings = _normalize_settings(
        preset_id,
        settings_payload if isinstance(settings_payload, dict) else {},
    )
    signals_payload = request_payload.get("signals", {})
    signals = _normalize_signals(
        signals_payload if isinstance(signals_payload, dict) else {},
        settings,
    )
    target_payload = request_payload.get("target", {})
    target = _normalize_target(target_payload if isinstance(target_payload, dict) else {})

    if preset_id == "pulse-grid-2d":
        scene = _generate_pulse_grid_2d(settings, signals)
    else:
        scene = _generate_signal_weave_2d(settings, signals)

    return {
        "status": "ok",
        "preset": DESKTOP_ONLY_PRESETS[preset_id].catalog_entry(),
        "target": target,
        "settings": settings,
        "signals": signals,
        "scene": scene,
        "analysis": _scene_analysis(scene, preset_id, signals),
    }


def preset_ids_for_scene_type(scene_type: str) -> list[str]:
    """Return preset identifiers for the chosen 2D or 3D mode."""

    safe_scene_type = scene_type.strip().lower()
    catalog = build_catalog_payload()["presets"]
    return [preset["id"] for preset in catalog if preset["sceneType"] == safe_scene_type]


def _all_presets() -> dict[str, DesktopPresetDefinition | Any]:
    """Return one lookup table containing both desktop and shared browser presets."""

    return {**DESKTOP_ONLY_PRESETS, **scene_studio_scene_builder.PRESETS}


def _preset_defaults(preset_id: str) -> dict[str, Any]:
    """Return the default settings for the chosen preset identifier."""

    if preset_id in DESKTOP_ONLY_PRESETS:
        return DESKTOP_ONLY_PRESETS[preset_id].defaults
    if preset_id in scene_studio_scene_builder.PRESETS:
        return scene_studio_scene_builder.PRESETS[preset_id].defaults
    return DESKTOP_ONLY_PRESETS[DEFAULT_DESKTOP_PRESET_ID].defaults


def _normalize_target(target_payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize the renderer host/port pair sent from the desktop control panel."""

    return {
        "host": (
            str(target_payload.get("host", scene_studio_scene_builder.DEFAULT_TARGET_HOST)).strip()
            or scene_studio_scene_builder.DEFAULT_TARGET_HOST
        ),
        "port": _clamp_int(
            target_payload.get("port", scene_studio_scene_builder.DEFAULT_TARGET_PORT),
            scene_studio_scene_builder.DEFAULT_TARGET_PORT,
            1,
            65535,
        ),
    }


def _normalize_settings(preset_id: str, settings_payload: dict[str, Any]) -> dict[str, Any]:
    """Merge desktop-provided settings with the chosen preset defaults."""

    defaults = _preset_defaults(preset_id)
    return {
        "density": _clamp_int(settings_payload.get("density"), int(defaults["density"]), 24, 320),
        "pointSize": _clamp_float(
            settings_payload.get("pointSize"),
            float(defaults["pointSize"]),
            1.0,
            24.0,
        ),
        "lineWidth": _clamp_float(
            settings_payload.get("lineWidth"),
            float(defaults["lineWidth"]),
            1.0,
            8.0,
        ),
        "speed": _clamp_float(settings_payload.get("speed"), float(defaults["speed"]), 0.1, 4.0),
        "gain": _clamp_float(settings_payload.get("gain"), float(defaults["gain"]), 0.1, 3.0),
        "manualDrive": _clamp_float(
            settings_payload.get("manualDrive"),
            float(defaults["manualDrive"]),
            0.0,
            2.0,
        ),
        "background": _normalize_hex_color(
            settings_payload.get("background"),
            str(defaults["background"]),
        ),
        "primaryColor": _normalize_hex_color(
            settings_payload.get("primaryColor"),
            str(defaults["primaryColor"]),
        ),
        "secondaryColor": _normalize_hex_color(
            settings_payload.get("secondaryColor"),
            str(defaults["secondaryColor"]),
        ),
    }


def _normalize_signals(signals_payload: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    """Turn raw desktop signal input into one consistent signal dictionary.

    This is the point where "whatever the UI happened to send" becomes one
    predictable shape that the scene generators can trust.
    """

    pointer_payload = signals_payload.get("pointer", {})
    pointer = pointer_payload if isinstance(pointer_payload, dict) else {}
    audio_payload = signals_payload.get("audio", {})
    audio = audio_payload if isinstance(audio_payload, dict) else {}
    manual_payload = signals_payload.get("manual", {})
    manual = manual_payload if isinstance(manual_payload, dict) else {}

    use_epoch = _coerce_bool(signals_payload.get("useEpoch"), True)
    use_noise = _coerce_bool(signals_payload.get("useNoise"), True)
    use_pointer = _coerce_bool(signals_payload.get("usePointer"), True)
    use_audio = _coerce_bool(signals_payload.get("useAudio"), False)

    epoch_seconds = _coerce_float(signals_payload.get("epochSeconds"), time.time())
    noise_seed = _coerce_float(signals_payload.get("noiseSeed"), 1.0)

    pointer_x = 0.5
    pointer_y = 0.5
    pointer_speed = 0.0
    if use_pointer:
        pointer_x = _clamp_float(pointer.get("x"), 0.5, 0.0, 1.0)
        pointer_y = _clamp_float(pointer.get("y"), 0.5, 0.0, 1.0)
        pointer_speed = _clamp_float(pointer.get("speed"), 0.0, 0.0, 1.0)

    audio_level = 0.0
    audio_bass = 0.0
    audio_mid = 0.0
    audio_treble = 0.0
    if use_audio:
        audio_level = _clamp_float(audio.get("level"), 0.0, 0.0, 1.0)
        audio_bass = _clamp_float(audio.get("bass"), audio_level, 0.0, 1.0)
        audio_mid = _clamp_float(audio.get("mid"), audio_level, 0.0, 1.0)
        audio_treble = _clamp_float(audio.get("treble"), audio_level, 0.0, 1.0)

    manual_drive = _clamp_float(
        manual.get("drive"),
        float(settings["manualDrive"]),
        0.0,
        2.0,
    )
    if "manualDrive" in signals_payload:
        manual_drive = _clamp_float(signals_payload.get("manualDrive"), manual_drive, 0.0, 2.0)

    noise_phase = _sample_noise_value(epoch_seconds * 0.31 + noise_seed * 7.9) if use_noise else 0.0
    energy = _clamp_float(
        manual_drive * 0.45
        + pointer_speed * 0.35
        + audio_level * 0.95
        + noise_phase * 0.25,
        0.0,
        0.0,
        2.2,
    )

    active_sources = ["manual"]
    if use_epoch:
        active_sources.append("epoch")
    if use_noise:
        active_sources.append("noise")
    if use_pointer:
        active_sources.append("pointer")
    if use_audio:
        active_sources.append("audio")

    return {
        "useEpoch": use_epoch,
        "useNoise": use_noise,
        "usePointer": use_pointer,
        "useAudio": use_audio,
        "epochSeconds": epoch_seconds,
        "timePhase": epoch_seconds if use_epoch else 0.0,
        "noiseSeed": noise_seed,
        "noisePhase": noise_phase,
        "pointerX": pointer_x,
        "pointerY": pointer_y,
        "pointerSpeed": pointer_speed,
        "audioLevel": audio_level,
        "audioBass": audio_bass,
        "audioMid": audio_mid,
        "audioTreble": audio_treble,
        "manualDrive": manual_drive,
        "energy": energy,
        "activeSources": active_sources,
    }


def _generate_signal_weave_2d(settings: dict[str, Any], signals: dict[str, Any]) -> dict[str, Any]:
    """Build a 2D line scene that behaves like a live oscilloscope ribbon.

    This preset is easiest to think of as "one animated ribbon sampled across a
    horizontal axis."  Time, pointer position, audio, and noise all bend that
    ribbon in different ways.
    """

    density = max(24, int(settings["density"]))
    speed = float(settings["speed"])
    gain = float(settings["gain"])
    background = _build_rgba_color_dictionary(str(settings["background"]))
    primary = _hex_color_to_rgb_triplet(str(settings["primaryColor"]))
    secondary = _hex_color_to_rgb_triplet(str(settings["secondaryColor"]))
    time_phase = float(signals["timePhase"])
    pointer_x = float(signals["pointerX"])
    pointer_y = float(signals["pointerY"])
    audio_level = float(signals["audioLevel"])
    audio_treble = float(signals["audioTreble"])
    energy = float(signals["energy"])
    noise_phase = float(signals["noisePhase"])

    control_points: list[tuple[float, float, float]] = []
    for point_index in range(density):
        progress = point_index / max(density - 1, 1)
        local_noise = _sample_noise_value(point_index * 0.63 + noise_phase * 9.1)
        x_position = (progress - 0.5) * 1.92
        # Each term bends the ribbon for a different reason:
        # - time moves the whole pattern continuously
        # - pointer shifts the wave count and phase
        # - audio nudges the ribbon upward/downward
        # - noise keeps it from feeling mechanically perfect
        y_position = (
            0.52 * math.sin(progress * math.tau * (2.0 + pointer_x * 3.0) + time_phase * speed)
            + 0.18 * math.cos(progress * math.tau * 5.0 - pointer_y * math.tau)
            + (audio_level - 0.5) * 0.5
            + (local_noise - 0.5) * 0.22
        )
        blend = _fractional_part(
            progress + audio_treble * 0.35 + local_noise * 0.25 + energy * 0.1
        )
        control_points.append((x_position, y_position, blend))

    vertices = []
    for start_point, end_point in zip(control_points, control_points[1:], strict=False):
        start_color = _blend_rgb_triplets(primary, secondary, start_point[2])
        end_color = _blend_rgb_triplets(primary, secondary, end_point[2])
        vertices.append(
            _two_dimensional_vertex(start_point[0], start_point[1], start_color, alpha=1.0)
        )
        vertices.append(_two_dimensional_vertex(end_point[0], end_point[1], end_color, alpha=1.0))

    return {
        "sceneType": "2d",
        "primitive": "lines",
        "pointSize": round(float(settings["pointSize"]), 3),
        "lineWidth": round(float(settings["lineWidth"]) + gain * 0.45, 3),
        "clearColor": background,
        "vertices": vertices,
        "indices": [],
    }


def _generate_pulse_grid_2d(settings: dict[str, Any], signals: dict[str, Any]) -> dict[str, Any]:
    """Build a 2D point grid for tuning dense motion and color breathing.

    This preset spreads the scene across a full lattice, which makes it useful
    when you want to see how a control affects the whole frame instead of a
    single ribbon or orbit.
    """

    density = int(settings["density"])
    speed = float(settings["speed"])
    gain = float(settings["gain"])
    background = _build_rgba_color_dictionary(str(settings["background"]))
    primary = _hex_color_to_rgb_triplet(str(settings["primaryColor"]))
    secondary = _hex_color_to_rgb_triplet(str(settings["secondaryColor"]))
    time_phase = float(signals["timePhase"])
    pointer_x = float(signals["pointerX"])
    pointer_y = float(signals["pointerY"])
    audio_bass = float(signals["audioBass"])
    audio_mid = float(signals["audioMid"])
    energy = float(signals["energy"])
    noise_phase = float(signals["noisePhase"])

    grid_size = max(5, int(math.sqrt(density)))
    vertices = []
    for grid_y_index in range(grid_size):
        for grid_x_index in range(grid_size):
            horizontal_progress_ratio = grid_x_index / max(grid_size - 1, 1)
            vertical_progress_ratio = grid_y_index / max(grid_size - 1, 1)
            local_noise = _sample_noise_value(
                grid_x_index * 0.81 + grid_y_index * 1.19 + noise_phase * 8.7
            )
            x_position = (
                (horizontal_progress_ratio - 0.5) * 1.9
                + math.sin(time_phase * speed + vertical_progress_ratio * math.tau) * 0.03
            )
            y_position = (
                (vertical_progress_ratio - 0.5) * 1.9
                + math.cos(time_phase * speed + horizontal_progress_ratio * math.tau) * 0.03
            )
            pulse = (
                math.sin(time_phase * speed * 1.4 + horizontal_progress_ratio * math.tau * 3.0)
                + math.cos(time_phase * speed * 0.7 + vertical_progress_ratio * math.tau * 2.0)
            ) * 0.5
            # Pointer influence acts like a gentle field distortion instead of
            # directly replacing the grid coordinates. That keeps the preset
            # readable while still making pointer motion feel responsive.
            x_position += (pointer_x - 0.5) * 0.22 * pulse
            y_position += (pointer_y - 0.5) * 0.22 * pulse
            blend = _fractional_part(
                (horizontal_progress_ratio + vertical_progress_ratio) * 0.5
                + local_noise * 0.35
                + audio_mid * 0.4
            )
            alpha = _clamp_float(0.55 + audio_bass * 0.35 + energy * 0.08, 0.8, 0.25, 1.0)
            vertices.append(
                _two_dimensional_vertex(
                    round(x_position, 5),
                    round(y_position, 5),
                    _blend_rgb_triplets(primary, secondary, blend),
                    alpha=round(alpha, 5),
                )
            )

    return {
        "sceneType": "2d",
        "primitive": "points",
        "pointSize": round(float(settings["pointSize"]) + gain * 0.8, 3),
        "lineWidth": round(float(settings["lineWidth"]), 3),
        "clearColor": background,
        "vertices": vertices,
        "indices": [],
    }


def _two_dimensional_vertex(
    x_position: float,
    y_position: float,
    color: tuple[float, float, float],
    alpha: float,
) -> dict[str, float]:
    """Return one JSON-ready 2D vertex record."""

    red, green, blue = color
    return {
        "x": round(x_position, 5),
        "y": round(y_position, 5),
        "r": round(red, 5),
        "g": round(green, 5),
        "b": round(blue, 5),
        "a": round(alpha, 5),
    }


def _scene_analysis(
    scene: dict[str, Any],
    preset_id: str,
    signals: dict[str, Any],
) -> dict[str, Any]:
    """Summarize the generated scene so the UI can show lightweight diagnostics."""

    vertices = scene.get("vertices", [])
    indices = scene.get("indices", [])
    return {
        "presetId": preset_id,
        "sceneType": scene.get("sceneType", "unknown"),
        "primitive": scene.get("primitive", "unknown"),
        "vertexCount": len(vertices) if isinstance(vertices, list) else 0,
        "indexCount": len(indices) if isinstance(indices, list) else 0,
        "activeSources": signals.get("activeSources", []),
        "energy": round(float(signals["energy"]), 4),
    }


def _sample_noise_value(seed: float) -> float:
    """Return one deterministic pseudo-random value for a floating-point seed."""

    return _fractional_part(math.sin(seed * 127.1) * 43758.5453123)

def _fractional_part(value: float) -> float:
    """Return only the fractional part of a floating-point number."""

    return value - math.floor(value)


def _hex_color_to_rgb_triplet(value: str) -> tuple[float, float, float]:
    """Convert a hex color such as `#ff8800` into normalized RGB floats."""

    normalized = _normalize_hex_color(value, "#ffffff").removeprefix("#")
    return (
        round(int(normalized[0:2], 16) / 255.0, 5),
        round(int(normalized[2:4], 16) / 255.0, 5),
        round(int(normalized[4:6], 16) / 255.0, 5),
    )


def _build_rgba_color_dictionary(value: str) -> dict[str, float]:
    """Convert a hex color into the RGBA dictionary shape the scene JSON uses."""

    red, green, blue = _hex_color_to_rgb_triplet(value)
    return {"r": red, "g": green, "b": blue, "a": 1.0}


def _blend_rgb_triplets(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
    blend: float,
) -> tuple[float, float, float]:
    """Blend two RGB colors using a 0..1 mix ratio."""

    safe_blend = _clamp_float(blend, 0.0, 0.0, 1.0)
    return (
        round(first[0] + (second[0] - first[0]) * safe_blend, 5),
        round(first[1] + (second[1] - first[1]) * safe_blend, 5),
        round(first[2] + (second[2] - first[2]) * safe_blend, 5),
    )


def _normalize_hex_color(value: object, fallback: str) -> str:
    """Normalize user-provided colors into a lowercase `#rrggbb` string."""

    candidate = str(value or "").strip()
    if candidate.startswith("#"):
        candidate = candidate[1:]
    if len(candidate) == 3:
        candidate = "".join(character * 2 for character in candidate)
    if len(candidate) != 6 or any(character not in string.hexdigits for character in candidate):
        return fallback
    return f"#{candidate.lower()}"


def _clamp_float(value: object, default: float, lower: float, upper: float) -> float:
    """Coerce a value to float and keep it inside a safe range."""

    return max(lower, min(upper, _coerce_float(value, default)))


def _clamp_int(value: object, default: int, lower: int, upper: int) -> int:
    """Coerce a value to int and keep it inside a safe range."""

    if not isinstance(value, (bool, int, float, str)):
        coerced = default
    else:
        try:
            coerced = int(value)
        except ValueError:
            coerced = default
    return max(lower, min(upper, coerced))


def _coerce_float(value: object, default: float) -> float:
    """Coerce a float-like value without throwing errors into the UI path."""

    if not isinstance(value, (bool, int, float, str)):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _coerce_bool(value: object, default: bool) -> bool:
    """Interpret common truthy and falsy strings/numbers from UI payloads."""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default
