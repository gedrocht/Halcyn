"""Shared desktop support surfaces used by multiple native Halcyn tools.

This package exists so the desktop tools can share a small set of stable,
well-documented interfaces instead of reaching directly into one another's
implementation modules.

Right now it exposes:

- the small renderer HTTP client used by Visualizer Studio and related helpers
- the audio-device discovery and capture helpers used by live data tools
- the shared structured activity journal used by the browser monitor and
  desktop tools

Keeping those pieces under one clearly named package makes the codebase easier
to teach: there is one obvious place to look for "desktop support plumbing"
that sits underneath the higher-level operator windows.
"""
