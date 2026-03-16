"""Audio-device enumeration and capture for the desktop render control panel.

This module keeps audio-specific concerns out of the rest of the desktop app.
The window only needs to know things like:

- "Which input devices are available?"
- "Start capture on this device."
- "What are the latest level, bass, mid, and treble values?"

Helpful library references:

- `sounddevice`: https://python-sounddevice.readthedocs.io/
- PortAudio device query model: https://python-sounddevice.readthedocs.io/en/latest/api/checking-hardware.html
- Python threading: https://docs.python.org/3/library/threading.html
"""

from __future__ import annotations

import importlib
import math
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class AudioDeviceDescriptor:
    """Describe one selectable desktop audio input device."""

    device_identifier: str
    name: str
    max_input_channels: int
    default_sample_rate: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AudioSignalSnapshot:
    """Describe the most recent analyzed audio snapshot.

    The desktop control panel keeps one of these snapshots around even when no
    audio stream is active so the UI always has one consistent state object to
    render.
    """

    backend_name: str = "unavailable"
    device_identifier: str = ""
    device_name: str = ""
    available: bool = False
    capturing: bool = False
    level: float = 0.0
    bass: float = 0.0
    mid: float = 0.0
    treble: float = 0.0
    updated_at_epoch_seconds: float = field(default_factory=time.time)
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AudioCaptureBackend(Protocol):
    """Protocol for pluggable audio backends.

    The controller and window only care about this small contract. That makes
    the real audio backend replaceable and much easier to test with fakes.
    """

    @property
    def backend_name(self) -> str:
        ...

    @property
    def availability_error(self) -> str:
        ...

    def list_input_devices(self) -> list[AudioDeviceDescriptor]:
        ...

    def open_input_stream(
        self,
        device_identifier: str,
        on_snapshot: Callable[[AudioSignalSnapshot], None],
    ) -> Callable[[], None]:
        ...


class UnavailableAudioCaptureBackend:
    """Fallback backend used when optional audio dependencies are missing.

    Instead of crashing the whole desktop panel when `sounddevice` is absent,
    the application can expose a clear "audio unavailable" state and keep every
    non-audio feature working.
    """

    def __init__(self, reason: str) -> None:
        self._reason = reason

    @property
    def backend_name(self) -> str:
        return "unavailable"

    @property
    def availability_error(self) -> str:
        return self._reason

    def list_input_devices(self) -> list[AudioDeviceDescriptor]:
        return []

    def open_input_stream(
        self,
        device_identifier: str,
        on_snapshot: Callable[[AudioSignalSnapshot], None],
    ) -> Callable[[], None]:
        raise RuntimeError(self._reason)


class SoundDeviceAudioCaptureBackend:
    """Real audio backend built on the optional sounddevice package.

    Official docs:
    https://python-sounddevice.readthedocs.io/
    """

    def __init__(self) -> None:
        self._sounddevice: Any | None = None
        self._availability_error = ""
        try:
            self._sounddevice = importlib.import_module("sounddevice")
        except Exception as error:  # pragma: no cover - depends on local environment.
            self._availability_error = (
                "Audio input requires the optional 'sounddevice' package. "
                f"Import failed with: {error}"
            )

    @property
    def backend_name(self) -> str:
        return "sounddevice"

    @property
    def availability_error(self) -> str:
        return self._availability_error

    def list_input_devices(self) -> list[AudioDeviceDescriptor]:
        """Enumerate selectable input devices from PortAudio."""

        if self._sounddevice is None:
            return []

        available_input_devices = []
        queried_device_descriptors = self._sounddevice.query_devices()
        for device_index, device_info in enumerate(queried_device_descriptors):
            max_input_channels = int(device_info.get("max_input_channels", 0) or 0)
            if max_input_channels < 1:
                continue
            available_input_devices.append(
                AudioDeviceDescriptor(
                    device_identifier=str(device_index),
                    name=str(device_info.get("name", f"Input device {device_index}")),
                    max_input_channels=max_input_channels,
                    default_sample_rate=int(device_info.get("default_samplerate", 44100) or 44100),
                )
            )
        return available_input_devices

    def open_input_stream(
        self,
        device_identifier: str,
        on_snapshot: Callable[[AudioSignalSnapshot], None],
    ) -> Callable[[], None]:
        """Open an input stream and call back with analyzed snapshots.

        `sounddevice` invokes our callback whenever a new chunk of audio
        arrives.  We immediately translate that raw sample block into the small
        control-oriented snapshot the rest of the app understands.
        """

        if self._sounddevice is None:
            raise RuntimeError(self._availability_error)

        device_index = int(device_identifier)
        device_info = self._sounddevice.query_devices(device_index, "input")
        sample_rate_hz = int(device_info.get("default_samplerate", 44100) or 44100)
        input_channel_count = max(
            1,
            min(int(device_info.get("max_input_channels", 1) or 1), 2),
        )
        device_name = str(device_info.get("name", f"Input device {device_identifier}"))

        def handle_audio_callback(
            input_data: Any,
            frame_count: int,
            time_info: Any,
            status: Any,
        ) -> None:
            status_text = str(status).strip() if str(status).strip() else ""
            raw_input_frames = input_data.tolist() if hasattr(input_data, "tolist") else input_data
            snapshot = analyze_audio_frames(
                raw_input_frames,
                sample_rate=sample_rate_hz,
                device_identifier=str(device_identifier),
                device_name=device_name,
                backend_name=self.backend_name,
                capturing=True,
                last_error=status_text,
            )
            on_snapshot(snapshot)

        stream = self._sounddevice.InputStream(
            device=device_index,
            channels=input_channel_count,
            samplerate=sample_rate_hz,
            callback=handle_audio_callback,
            blocksize=1024,
        )
        stream.start()

        def stop_stream() -> None:
            stream.stop()
            stream.close()

        return stop_stream


class DesktopAudioInputService:
    """High-level audio service used by the desktop control panel controller."""

    def __init__(self, backend: AudioCaptureBackend | None = None) -> None:
        self._backend = backend or create_default_audio_capture_backend()
        self._lock = threading.Lock()
        self._devices = self._backend.list_input_devices()
        self._stop_capture_callback: Callable[[], None] | None = None
        # The snapshot starts in a meaningful "nothing is capturing yet" state
        # so the GUI can always display one coherent sentence to the user.
        self._snapshot = AudioSignalSnapshot(
            backend_name=self._backend.backend_name,
            available=not bool(self._backend.availability_error),
            last_error=self._backend.availability_error,
        )

    def devices(self) -> list[AudioDeviceDescriptor]:
        """Return the most recently discovered input devices."""

        with self._lock:
            return list(self._devices)

    def refresh_devices(self) -> list[AudioDeviceDescriptor]:
        """Re-enumerate input devices from the active backend."""

        with self._lock:
            self._devices = self._backend.list_input_devices()
            self._snapshot.available = not bool(self._backend.availability_error)
            if self._backend.availability_error:
                self._snapshot.last_error = self._backend.availability_error
            return list(self._devices)

    def snapshot(self) -> AudioSignalSnapshot:
        """Return the latest audio-analysis snapshot."""

        with self._lock:
            return AudioSignalSnapshot(**self._snapshot.to_dict())

    def start_capture(self, device_identifier: str) -> AudioSignalSnapshot:
        """Start capturing audio from one selected device."""

        with self._lock:
            # Starting a new capture always replaces an older one. That keeps the
            # service model simple: at most one active device at a time.
            self._stop_capture_locked()

            def on_snapshot_available(snapshot: AudioSignalSnapshot) -> None:
                with self._lock:
                    self._snapshot = snapshot

            stop_capture_callback = self._backend.open_input_stream(
                device_identifier,
                on_snapshot_available,
            )
            selected_device = next(
                (
                    device
                    for device in self._devices
                    if device.device_identifier == device_identifier
                ),
                None,
            )
            self._stop_capture_callback = stop_capture_callback
            self._snapshot = AudioSignalSnapshot(
                backend_name=self._backend.backend_name,
                device_identifier=device_identifier,
                device_name=selected_device.name if selected_device else "",
                available=True,
                capturing=True,
                updated_at_epoch_seconds=time.time(),
            )
            return AudioSignalSnapshot(**self._snapshot.to_dict())

    def stop_capture(self) -> AudioSignalSnapshot:
        """Stop audio capture but preserve the last measured levels."""

        with self._lock:
            self._stop_capture_locked()
            return AudioSignalSnapshot(**self._snapshot.to_dict())

    def close(self) -> None:
        """Shut down the active capture stream during application exit."""

        with self._lock:
            self._stop_capture_locked()

    def _stop_capture_locked(self) -> None:
        """Stop the active stream while the caller already holds the service lock."""

        if self._stop_capture_callback is not None:
            self._stop_capture_callback()
            self._stop_capture_callback = None
        self._snapshot.capturing = False
        self._snapshot.updated_at_epoch_seconds = time.time()


def create_default_audio_capture_backend() -> AudioCaptureBackend:
    """Return the best available audio backend for the current machine.

    Today that means:

    1. try `sounddevice`
    2. if it is unavailable, return a backend that explains the problem clearly
    """

    backend = SoundDeviceAudioCaptureBackend()
    if backend.availability_error:
        return UnavailableAudioCaptureBackend(backend.availability_error)
    return backend


def analyze_audio_frames(
    raw_frames: Sequence[object],
    *,
    sample_rate: int,
    device_identifier: str,
    device_name: str,
    backend_name: str,
    capturing: bool,
    last_error: str = "",
) -> AudioSignalSnapshot:
    """Convert one audio callback block into the normalized control values the UI needs.

    The desktop control panel does not need studio-quality analysis. It needs a
    stable, friendly set of control values that scene presets can respond to.
    That is why this function reduces raw audio into:

    - one overall loudness level
    - one coarse bass measure
    - one coarse mid measure
    - one coarse treble measure
    """

    mono_samples = _mono_samples(raw_frames)
    if not mono_samples:
        return AudioSignalSnapshot(
            backend_name=backend_name,
            device_identifier=device_identifier,
            device_name=device_name,
            available=True,
            capturing=capturing,
            last_error=last_error,
        )

    downsampled_samples = _downsample_samples(mono_samples, max_samples=128)
    level = _calculate_normalized_level(downsampled_samples)
    bass, mid, treble = _estimate_frequency_band_levels(downsampled_samples, sample_rate)

    return AudioSignalSnapshot(
        backend_name=backend_name,
        device_identifier=device_identifier,
        device_name=device_name,
        available=True,
        capturing=capturing,
        level=level,
        bass=bass,
        mid=mid,
        treble=treble,
        updated_at_epoch_seconds=time.time(),
        last_error=last_error,
    )


def _mono_samples(raw_frames: Sequence[object]) -> list[float]:
    """Convert multi-channel callback data into a simple mono sample list."""

    mono_samples: list[float] = []
    for frame in raw_frames:
        if isinstance(frame, Sequence) and not isinstance(frame, (str, bytes, bytearray)):
            numeric_channels = [
                float(channel)
                for channel in frame
                if isinstance(channel, (int, float))
            ]
            if numeric_channels:
                mono_samples.append(sum(numeric_channels) / len(numeric_channels))
        elif isinstance(frame, (int, float)):
            mono_samples.append(float(frame))
    return mono_samples


def _downsample_samples(samples: list[float], max_samples: int) -> list[float]:
    """Trim very large sample blocks so analysis stays fast and predictable."""

    if len(samples) <= max_samples:
        return samples

    step = max(1, len(samples) // max_samples)
    return samples[::step][:max_samples]


def _calculate_normalized_level(samples: list[float]) -> float:
    """Convert raw amplitudes into a friendly 0..1 level meter."""

    if not samples:
        return 0.0

    mean_square = sum(sample * sample for sample in samples) / len(samples)
    root_mean_square = math.sqrt(mean_square)
    return max(0.0, min(1.0, root_mean_square * 5.0))


def _estimate_frequency_band_levels(
    samples: list[float],
    sample_rate: int,
) -> tuple[float, float, float]:
    """Estimate coarse bass, mid, and treble energy with a tiny DFT.

    This is intentionally simple rather than studio-grade. The goal is to give
    the render-control presets useful "shape" signals without bringing in a huge
    DSP stack just to power a control surface.
    """

    if len(samples) < 8:
        return 0.0, 0.0, 0.0

    frequency_band_magnitudes = {"bass": 0.0, "mid": 0.0, "treble": 0.0}
    sample_count = len(samples)
    highest_frequency = min(6000.0, sample_rate / 2.0)
    maximum_frequency_bin_to_sample = max(1, min(sample_count // 2, 48))

    for frequency_bin in range(1, maximum_frequency_bin_to_sample + 1):
        represented_frequency_hz = frequency_bin * sample_rate / sample_count
        if represented_frequency_hz > highest_frequency:
            break

        real_component = 0.0
        imaginary_component = 0.0
        for sample_index, sample in enumerate(samples):
            angle = -2.0 * math.pi * frequency_bin * sample_index / sample_count
            real_component += sample * math.cos(angle)
            imaginary_component += sample * math.sin(angle)

        magnitude = math.sqrt(
            real_component * real_component + imaginary_component * imaginary_component
        )
        if represented_frequency_hz < 250.0:
            frequency_band_magnitudes["bass"] += magnitude
        elif represented_frequency_hz < 2000.0:
            frequency_band_magnitudes["mid"] += magnitude
        else:
            frequency_band_magnitudes["treble"] += magnitude

    total_magnitude = (
        frequency_band_magnitudes["bass"]
        + frequency_band_magnitudes["mid"]
        + frequency_band_magnitudes["treble"]
    )
    if total_magnitude <= 1e-9:
        return 0.0, 0.0, 0.0

    return (
        max(0.0, min(1.0, frequency_band_magnitudes["bass"] / total_magnitude)),
        max(0.0, min(1.0, frequency_band_magnitudes["mid"] / total_magnitude)),
        max(0.0, min(1.0, frequency_band_magnitudes["treble"] / total_magnitude)),
    )
