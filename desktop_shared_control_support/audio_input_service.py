"""Shared audio-device support for native desktop tools.

The desktop render control panel originally owned the audio capture helpers.
The new shared data-source tool needs the same functionality, so this module
provides one obvious import path for audio enumeration, capture, and analysis.

Like the shared render API client, this module currently re-exports the tested
implementation that already exists in the desktop render control panel package.
That keeps behavior stable while still giving the codebase a cleaner shared
structure.
"""

from __future__ import annotations

from desktop_render_control_panel.audio_input_service import (
    AudioCaptureBackend,
    AudioDeviceDescriptor,
    AudioSignalSnapshot,
    CompositeAudioCaptureBackend,
    DesktopAudioInputService,
    SoundCardLoopbackOutputCaptureBackend,
    SoundDeviceInputCaptureBackend,
    UnavailableAudioCaptureBackend,
    WindowsWaveInListingBackend,
    _initialize_windows_com_for_current_thread,
    analyze_audio_frames,
    create_default_audio_capture_backend,
)

__all__ = [
    "AudioCaptureBackend",
    "AudioDeviceDescriptor",
    "AudioSignalSnapshot",
    "CompositeAudioCaptureBackend",
    "DesktopAudioInputService",
    "SoundCardLoopbackOutputCaptureBackend",
    "SoundDeviceInputCaptureBackend",
    "UnavailableAudioCaptureBackend",
    "WindowsWaveInListingBackend",
    "_initialize_windows_com_for_current_thread",
    "analyze_audio_frames",
    "create_default_audio_capture_backend",
]
