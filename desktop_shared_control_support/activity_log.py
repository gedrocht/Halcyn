"""Shared structured activity logging for desktop Halcyn tools.

The desktop applications now share one small JSON-lines activity journal so a
person can inspect what happened across launchers, senders, and control panels
without guessing which process owns a problem.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_activity_log_write_lock = threading.Lock()


def _current_utc_timestamp_iso8601() -> str:
    """Return a readable UTC timestamp for activity entries."""

    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class DesktopActivityLogEntry:
    """Describe one structured desktop activity event."""

    recorded_at_utc: str
    application_name: str
    component_name: str
    level: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready dictionary copy of the entry."""

        return asdict(self)


class DesktopActivityLogger:
    """Append structured desktop activity events to a shared journal file."""

    def __init__(
        self,
        *,
        application_name: str,
        journal_file_path: Path | None = None,
    ) -> None:
        self._application_name = application_name
        self._journal_file_path = journal_file_path or get_default_desktop_activity_log_path()

    @property
    def journal_file_path(self) -> Path:
        """Return the file that stores the shared activity journal."""

        return self._journal_file_path

    def log(
        self,
        *,
        component_name: str,
        level: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> DesktopActivityLogEntry:
        """Append one structured activity event to the shared journal."""

        entry = DesktopActivityLogEntry(
            recorded_at_utc=_current_utc_timestamp_iso8601(),
            application_name=self._application_name,
            component_name=component_name,
            level=level.upper(),
            message=message,
            details=details or {},
        )

        journal_parent = self._journal_file_path.parent
        journal_parent.mkdir(parents=True, exist_ok=True)
        with _activity_log_write_lock:
            with self._journal_file_path.open("a", encoding="utf-8") as journal_file:
                journal_file.write(json.dumps(entry.to_dict(), separators=(",", ":")))
                journal_file.write("\n")
        return entry


def get_default_desktop_activity_log_path() -> Path:
    """Return the shared activity journal path for the current machine."""

    base_directory = os.environ.get("LOCALAPPDATA")
    if base_directory:
        return Path(base_directory) / "Halcyn" / "logs" / "desktop-activity.jsonl"
    return Path.home() / ".halcyn" / "logs" / "desktop-activity.jsonl"


def read_recent_desktop_activity_entries(
    *,
    journal_file_path: Path | None = None,
    limit: int = 400,
) -> list[DesktopActivityLogEntry]:
    """Return the newest activity entries from the shared journal."""

    safe_limit = max(1, int(limit))
    safe_journal_file_path = journal_file_path or get_default_desktop_activity_log_path()
    if not safe_journal_file_path.exists():
        return []

    raw_lines = safe_journal_file_path.read_text(encoding="utf-8").splitlines()
    parsed_entries: list[DesktopActivityLogEntry] = []
    for raw_line in raw_lines[-safe_limit:]:
        if not raw_line.strip():
            continue
        parsed_payload = json.loads(raw_line)
        parsed_entries.append(
            DesktopActivityLogEntry(
                recorded_at_utc=str(parsed_payload.get("recorded_at_utc", "")),
                application_name=str(parsed_payload.get("application_name", "")),
                component_name=str(parsed_payload.get("component_name", "")),
                level=str(parsed_payload.get("level", "INFO")),
                message=str(parsed_payload.get("message", "")),
                details=dict(parsed_payload.get("details", {})),
            )
        )
    return parsed_entries
