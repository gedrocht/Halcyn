"""Shared renderer HTTP client surface for native desktop tools.

The project already had a small renderer API client inside the desktop render
control panel package.  The new multi-renderer data source panel needs the same
surface, so this shared module provides one clear import path for any desktop
tool that needs to talk to Halcyn's renderer HTTP API.

This module currently re-exports the existing implementation so we can improve
the package structure without forcing a risky rewrite of code that is already
well-tested.
"""

from __future__ import annotations

from desktop_render_control_panel.render_api_client import RenderApiClient, RenderApiResponse

__all__ = ["RenderApiClient", "RenderApiResponse"]
