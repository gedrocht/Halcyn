"""Shared desktop support surfaces used by multiple native operator apps.

This package exists so the desktop tools can share a small set of stable,
well-documented interfaces instead of reaching directly into one another's
implementation modules.

Right now it exposes:

- the small renderer HTTP client used by multiple desktop control panels
- the audio-device discovery and capture helpers used by live data tools

Keeping those pieces under one clearly named package makes the codebase easier
to teach: there is one obvious place to look for "desktop support plumbing"
that sits underneath the higher-level operator windows.
"""
