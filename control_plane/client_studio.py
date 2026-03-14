"""Scene-generation helpers for the browser-based Client Studio."""

from __future__ import annotations

import math
import string
import time
from dataclasses import dataclass
from typing import Any

DEFAULT_PRESET_ID = "aurora-orbit"
DEFAULT_TARGET_HOST = "127.0.0.1"
DEFAULT_TARGET_PORT = 8080
DEFAULT_AUTO_APPLY_MS = 750


@dataclass(frozen=True)
class PresetDefinition:
    """Describe one client-studio preset and its default controls."""

    preset_id: str
    name: str
    summary: str
    emphasis: str
    defaults: dict[str, Any]

    def catalog_entry(self) -> dict[str, Any]:
        """Convert the preset into JSON-ready metadata for the browser UI."""

        return {
            "id": self.preset_id,
            "name": self.name,
            "summary": self.summary,
            "emphasis": self.emphasis,
            "defaults": self.defaults,
        }


PRESETS: dict[str, PresetDefinition] = {
    "aurora-orbit": PresetDefinition(
        preset_id="aurora-orbit",
        name="Aurora Orbit",
        summary="A drifting orbital point cloud that likes time, pointer motion, and color sweeps.",
        emphasis="epoch + pointer + noise",
        defaults={
            "density": 160,
            "pointSize": 8.0,
            "lineWidth": 2.0,
            "speed": 1.0,
            "gain": 1.0,
            "manualDrive": 0.35,
            "background": "#08131f",
            "primaryColor": "#5fe3ff",
            "secondaryColor": "#ffb75f",
        },
    ),
    "lattice-bloom": PresetDefinition(
        preset_id="lattice-bloom",
        name="Lattice Bloom",
        summary="A pulsing volumetric grid that turns steady inputs into organized depth waves.",
        emphasis="epoch + audio + manual drive",
        defaults={
            "density": 144,
            "pointSize": 6.0,
            "lineWidth": 2.0,
            "speed": 0.9,
            "gain": 1.2,
            "manualDrive": 0.45,
            "background": "#0d1020",
            "primaryColor": "#89ffb8",
            "secondaryColor": "#5f8cff",
        },
    ),
    "comet-ribbon": PresetDefinition(
        preset_id="comet-ribbon",
        name="Comet Ribbon",
        summary=(
            "A line-driven lissajous ribbon that responds well to motion bursts "
            "and microphone energy."
        ),
        emphasis="pointer + audio + epoch",
        defaults={
            "density": 96,
            "pointSize": 6.0,
            "lineWidth": 3.0,
            "speed": 1.1,
            "gain": 1.1,
            "manualDrive": 0.3,
            "background": "#140d1d",
            "primaryColor": "#ff7fd1",
            "secondaryColor": "#7fe7ff",
        },
    ),
}

SOURCE_CATALOG: list[dict[str, str]] = [
    {
        "id": "epoch",
        "name": "Unix time",
        "description": "A continuously changing phase source derived from epoch seconds.",
    },
    {
        "id": "noise",
        "name": "Noise",
        "description": "Deterministic pseudo-random variation so presets do not feel static.",
    },
    {
        "id": "pointer",
        "name": "Pointer",
        "description": "Normalized mouse position and movement speed captured in the browser.",
    },
    {
        "id": "audio",
        "name": "Microphone",
        "description": (
            "Browser-side microphone analysis routed into level and rough "
            "frequency bands."
        ),
    },
    {
        "id": "manual",
        "name": "Manual drive",
        "description": (
            "A direct fallback slider for when you want deterministic control "
            "without hardware input."
        ),
    },
]


def build_catalog_payload() -> dict[str, Any]:
    """Return the browser catalog used to populate the client UI."""

    return {
        "status": "ok",
        "presets": [preset.catalog_entry() for preset in PRESETS.values()],
        "sources": SOURCE_CATALOG,
        "defaults": {
            "presetId": DEFAULT_PRESET_ID,
            "target": {"host": DEFAULT_TARGET_HOST, "port": DEFAULT_TARGET_PORT},
            "autoApplyMs": DEFAULT_AUTO_APPLY_MS,
        },
    }


def build_scene_bundle(request_payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize one browser request and return the generated scene plus metadata."""

    preset_id = str(request_payload.get("presetId", DEFAULT_PRESET_ID))
    if preset_id not in PRESETS:
        preset_id = DEFAULT_PRESET_ID

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
    scene = _generate_scene(preset_id, settings, signals)

    return {
        "status": "ok",
        "preset": PRESETS[preset_id].catalog_entry(),
        "target": target,
        "settings": settings,
        "signals": signals,
        "scene": scene,
        "analysis": _scene_analysis(scene, preset_id, signals),
    }


def _normalize_target(target_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "host": (
            str(target_payload.get("host", DEFAULT_TARGET_HOST)).strip() or DEFAULT_TARGET_HOST
        ),
        "port": _clamp_int(
            target_payload.get("port", DEFAULT_TARGET_PORT),
            DEFAULT_TARGET_PORT,
            1,
            65535,
        ),
    }


def _normalize_settings(preset_id: str, settings_payload: dict[str, Any]) -> dict[str, Any]:
    defaults = PRESETS[preset_id].defaults
    return {
        "density": _clamp_int(
            settings_payload.get("density"),
            int(defaults["density"]),
            24,
            320,
        ),
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

    noise_phase = _noise_value(epoch_seconds * 0.27 + noise_seed * 9.13) if use_noise else 0.0
    energy = _clamp_float(
        manual_drive * 0.5 + pointer_speed * 0.4 + audio_level * 0.9 + noise_phase * 0.25,
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


def _generate_scene(
    preset_id: str,
    settings: dict[str, Any],
    signals: dict[str, Any],
) -> dict[str, Any]:
    if preset_id == "lattice-bloom":
        return _generate_lattice_bloom(settings, signals)
    if preset_id == "comet-ribbon":
        return _generate_comet_ribbon(settings, signals)
    return _generate_aurora_orbit(settings, signals)


def _generate_aurora_orbit(settings: dict[str, Any], signals: dict[str, Any]) -> dict[str, Any]:
    density = int(settings["density"])
    speed = float(settings["speed"])
    gain = float(settings["gain"])
    primary = _hex_to_rgb(str(settings["primaryColor"]))
    secondary = _hex_to_rgb(str(settings["secondaryColor"]))
    background = _rgba_dict(str(settings["background"]))
    time_phase = float(signals["timePhase"])
    pointer_x = float(signals["pointerX"])
    pointer_y = float(signals["pointerY"])
    audio_bass = float(signals["audioBass"])
    audio_mid = float(signals["audioMid"])
    audio_treble = float(signals["audioTreble"])
    energy = float(signals["energy"])
    noise_phase = float(signals["noisePhase"])

    vertices = []
    for index in range(density):
        progress = index / max(density - 1, 1)
        base_angle = progress * math.tau * (3.0 + gain * 0.7)
        orbit_angle = base_angle + time_phase * speed * 0.55
        local_noise = _noise_value(index * 0.71 + noise_phase * 13.0)
        radius = (
            0.46
            + 0.18 * math.sin(orbit_angle * 1.8 + pointer_x * math.tau)
            + 0.12 * math.cos(orbit_angle * 0.9 - pointer_y * math.tau)
            + local_noise * 0.16
            + energy * 0.1
        )
        x = radius * math.cos(orbit_angle + pointer_x * 0.8)
        y = (progress - 0.5) * 1.9 + 0.22 * math.sin(time_phase * 0.45 + progress * 11.0)
        z = radius * math.sin(orbit_angle) + 0.25 * math.cos(progress * 15.0 + audio_bass * 5.0)
        blend = _fract(progress + audio_mid * 0.4 + local_noise * 0.3 + audio_treble * 0.15)
        r, g, b = _mix_rgb(primary, secondary, blend)
        vertices.append(
            {
                "x": round(x, 5),
                "y": round(y, 5),
                "z": round(z, 5),
                "r": round(r, 5),
                "g": round(g, 5),
                "b": round(b, 5),
                "a": 1.0,
            }
        )

    return {
        "sceneType": "3d",
        "primitive": "points",
        "pointSize": round(float(settings["pointSize"]), 3),
        "lineWidth": round(float(settings["lineWidth"]), 3),
        "clearColor": background,
        "camera": _build_camera(signals, distance=3.1, vertical_bias=1.35),
        "vertices": vertices,
        "indices": [],
    }


def _generate_lattice_bloom(settings: dict[str, Any], signals: dict[str, Any]) -> dict[str, Any]:
    density = int(settings["density"])
    speed = float(settings["speed"])
    gain = float(settings["gain"])
    primary = _hex_to_rgb(str(settings["primaryColor"]))
    secondary = _hex_to_rgb(str(settings["secondaryColor"]))
    background = _rgba_dict(str(settings["background"]))
    time_phase = float(signals["timePhase"])
    pointer_y = float(signals["pointerY"])
    audio_level = float(signals["audioLevel"])
    audio_mid = float(signals["audioMid"])
    energy = float(signals["energy"])
    noise_phase = float(signals["noisePhase"])

    grid = max(5, int(math.sqrt(density)))
    vertices = []
    for gy in range(grid):
        for gx in range(grid):
            u = gx / max(grid - 1, 1)
            v = gy / max(grid - 1, 1)
            local_noise = _noise_value(gx * 0.93 + gy * 1.37 + noise_phase * 11.0)
            x = (u - 0.5) * 2.4
            y = (v - 0.5) * 2.1
            wave = math.sin(u * math.tau * 2.0 + time_phase * speed)
            ridge = math.cos(v * math.tau * 1.7 - time_phase * speed * 0.7)
            z = (wave + ridge) * (0.22 + audio_level * 0.5 + energy * 0.12)
            z += (pointer_y - 0.5) * 0.7 + (local_noise - 0.5) * 0.3
            blend = _fract((u + v) * 0.5 + local_noise * 0.4 + audio_mid * 0.3)
            r, g, b = _mix_rgb(primary, secondary, blend)
            vertices.append(
                {
                    "x": round(x, 5),
                    "y": round(y, 5),
                    "z": round(z, 5),
                    "r": round(r, 5),
                    "g": round(g, 5),
                    "b": round(b, 5),
                    "a": 1.0,
                }
            )

    return {
        "sceneType": "3d",
        "primitive": "points",
        "pointSize": round(float(settings["pointSize"]) + gain * 0.8, 3),
        "lineWidth": round(float(settings["lineWidth"]), 3),
        "clearColor": background,
        "camera": _build_camera(signals, distance=3.4, vertical_bias=1.55),
        "vertices": vertices,
        "indices": [],
    }


def _generate_comet_ribbon(settings: dict[str, Any], signals: dict[str, Any]) -> dict[str, Any]:
    density = max(24, int(settings["density"]))
    speed = float(settings["speed"])
    gain = float(settings["gain"])
    primary = _hex_to_rgb(str(settings["primaryColor"]))
    secondary = _hex_to_rgb(str(settings["secondaryColor"]))
    background = _rgba_dict(str(settings["background"]))
    time_phase = float(signals["timePhase"])
    pointer_x = float(signals["pointerX"])
    pointer_y = float(signals["pointerY"])
    audio_bass = float(signals["audioBass"])
    audio_treble = float(signals["audioTreble"])
    energy = float(signals["energy"])
    noise_phase = float(signals["noisePhase"])

    control_points: list[tuple[float, float, float, float]] = []
    for index in range(density):
        progress = index / max(density - 1, 1)
        local_noise = _noise_value(index * 0.49 + noise_phase * 7.0)
        angle = time_phase * speed * 0.8 + progress * math.tau * (2.2 + audio_treble * 1.4)
        radial = 0.9 + 0.18 * math.sin(progress * math.tau * 3.0 + energy)
        x = math.sin(angle * 1.1 + pointer_x * math.tau) * radial
        y = (progress - 0.5) * 2.4 + 0.26 * math.sin(angle * 2.0)
        z = math.cos(angle + pointer_y * math.tau) * (0.45 + audio_bass * 0.65 + local_noise * 0.18)
        blend = _fract(progress + local_noise * 0.5)
        control_points.append((x, y, z, blend))

    vertices = []
    for start, end in zip(control_points, control_points[1:], strict=False):
        start_color = _mix_rgb(primary, secondary, start[3])
        end_color = _mix_rgb(primary, secondary, end[3])
        vertices.append(_line_vertex(start, start_color))
        vertices.append(_line_vertex(end, end_color))

    return {
        "sceneType": "3d",
        "primitive": "lines",
        "pointSize": round(float(settings["pointSize"]), 3),
        "lineWidth": round(float(settings["lineWidth"]) + gain * 0.6, 3),
        "clearColor": background,
        "camera": _build_camera(signals, distance=3.0, vertical_bias=1.25),
        "vertices": vertices,
        "indices": [],
    }


def _line_vertex(
    point: tuple[float, float, float, float],
    color: tuple[float, float, float],
) -> dict[str, float]:
    x, y, z, _ = point
    r, g, b = color
    return {
        "x": round(x, 5),
        "y": round(y, 5),
        "z": round(z, 5),
        "r": round(r, 5),
        "g": round(g, 5),
        "b": round(b, 5),
        "a": 1.0,
    }


def _build_camera(signals: dict[str, Any], distance: float, vertical_bias: float) -> dict[str, Any]:
    pointer_x = float(signals["pointerX"])
    pointer_y = float(signals["pointerY"])
    energy = float(signals["energy"])

    return {
        "position": {
            "x": round(1.8 + (pointer_x - 0.5) * 1.8, 5),
            "y": round(vertical_bias + pointer_y * 1.2 + energy * 0.15, 5),
            "z": round(distance + energy * 0.8, 5),
        },
        "target": {
            "x": round((pointer_x - 0.5) * 0.35, 5),
            "y": round((pointer_y - 0.5) * 0.35, 5),
            "z": 0.0,
        },
        "up": {"x": 0.0, "y": 1.0, "z": 0.0},
        "fovYDegrees": 60.0,
        "nearPlane": 0.1,
        "farPlane": 100.0,
    }


def _scene_analysis(
    scene: dict[str, Any],
    preset_id: str,
    signals: dict[str, Any],
) -> dict[str, Any]:
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


def _noise_value(seed: float) -> float:
    return _fract(math.sin(seed * 127.1) * 43758.5453123)


def _fract(value: float) -> float:
    return value - math.floor(value)


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    normalized = _normalize_hex_color(value, "#ffffff").removeprefix("#")
    return (
        round(int(normalized[0:2], 16) / 255.0, 5),
        round(int(normalized[2:4], 16) / 255.0, 5),
        round(int(normalized[4:6], 16) / 255.0, 5),
    )


def _rgba_dict(value: str) -> dict[str, float]:
    r, g, b = _hex_to_rgb(value)
    return {"r": r, "g": g, "b": b, "a": 1.0}


def _mix_rgb(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
    blend: float,
) -> tuple[float, float, float]:
    safe_blend = _clamp_float(blend, 0.0, 0.0, 1.0)
    return (
        round(first[0] + (second[0] - first[0]) * safe_blend, 5),
        round(first[1] + (second[1] - first[1]) * safe_blend, 5),
        round(first[2] + (second[2] - first[2]) * safe_blend, 5),
    )


def _normalize_hex_color(value: object, fallback: str) -> str:
    candidate = str(value or "").strip()
    if candidate.startswith("#"):
        candidate = candidate[1:]
    if len(candidate) == 3:
        candidate = "".join(character * 2 for character in candidate)
    if len(candidate) != 6 or any(character not in string.hexdigits for character in candidate):
        return fallback
    return f"#{candidate.lower()}"


def _clamp_float(value: object, default: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, _coerce_float(value, default)))


def _clamp_int(value: object, default: int, lower: int, upper: int) -> int:
    if not isinstance(value, (bool, int, float, str)):
        coerced = default
    else:
        try:
            coerced = int(value)
        except ValueError:
            coerced = default
    return max(lower, min(upper, coerced))


def _coerce_float(value: object, default: float) -> float:
    if not isinstance(value, (bool, int, float, str)):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _coerce_bool(value: object, default: bool) -> bool:
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
