"""Compatibility bridge server for the Bars Studio desktop panel.

The repository now has a shared local JSON bridge implementation in
``desktop_shared_control_support.local_json_bridge`` so desktop tools can all
exchange JSON in the same way.  This module keeps the older
``SpectrographExternalDataBridgeServer`` name alive so the Bars Studio code and
tests can stay beginner-readable while the implementation is shared.
"""

from __future__ import annotations

from collections.abc import Callable

from desktop_shared_control_support.local_json_bridge import (
    LocalJsonBridgeServer,
)
from desktop_shared_control_support.local_json_bridge import (
    LocalJsonBridgeStatus as SpectrographExternalDataBridgeStatus,
)


class SpectrographExternalDataBridgeServer(LocalJsonBridgeServer):
    """Receive external JSON updates for the Bars Studio control panel.

    The older spectrograph-specific controller/tests still construct this class
    with the keyword argument ``on_external_json_received``.  The shared bridge
    server expects ``on_json_received`` instead.  This wrapper keeps the older
    signature in place and simply forwards the callback to the shared server.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        on_external_json_received: Callable[[str, str], None],
    ) -> None:
        super().__init__(
            host=host,
            port=port,
            on_json_received=on_external_json_received,
        )


__all__ = [
    "SpectrographExternalDataBridgeServer",
    "SpectrographExternalDataBridgeStatus",
]
