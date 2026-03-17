"""Shared structured activity logging for Halcyn desktop and browser tools.

This module provides one simple, append-only JSON-lines journal that multiple
processes can write to at the same time:

- the native C++ Visualizer
- the browser-based Control Center
- the unified desktop Operator Console

The goal is not to replace each tool's local status labels or small in-memory
buffers. The goal is to give the whole workflow one common activity timeline
that a browser-based monitoring page can read, sort, and filter.

Helpful references:

- JSON Lines format: https://jsonlines.org/
- Python `json` module: https://docs.python.org/3/library/json.html
- Python `pathlib` module: https://docs.python.org/3/library/pathlib.html
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ACTIVITY_JOURNAL_RELATIVE_PATH = Path("artifacts/runtime-activity/halcyn-activity.jsonl")


def utc_now_iso8601() -> str:
    """Return the current UTC time in a stable ISO 8601 form."""

    return datetime.now(timezone.utc).isoformat()


def get_default_activity_journal_path(project_root: Path | None = None) -> Path:
    """Return the shared activity-journal path used by Halcyn tools.

    The preferred source of truth is the ``HALCYN_ACTIVITY_LOG_PATH``
    environment variable so that launcher scripts can guarantee every process
    writes to the same file.

    If that variable is not set, the function falls back to a repository-local
    path under ``artifacts/runtime-activity``. That keeps local manual runs
    useful even when a process was not launched through one of the helper
    scripts.
    """

    configured_path_text = os.environ.get("HALCYN_ACTIVITY_LOG_PATH", "").strip()
    if configured_path_text:
        return Path(configured_path_text).expanduser().resolve()

    resolved_project_root = project_root
    if resolved_project_root is None:
        resolved_project_root = Path(__file__).resolve().parents[1]
    return (resolved_project_root / DEFAULT_ACTIVITY_JOURNAL_RELATIVE_PATH).resolve()


@dataclass(frozen=True)
class ActivityJournalEntry:
    """Describe one structured event in the shared Halcyn activity journal."""

    timestamp_utc: str
    source_app: str
    component: str
    level: str
    message: str
    process_id: int
    extra: dict[str, Any] = field(default_factory=dict)


class ActivityJournal:
    """Append structured events to the shared JSON-lines activity journal."""

    def __init__(
        self,
        *,
        source_app: str,
        project_root: Path | None = None,
        journal_path: Path | None = None,
    ) -> None:
        self._source_app = source_app
        self._journal_path = journal_path or get_default_activity_journal_path(project_root)
        self._lock = threading.Lock()
        self._journal_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def journal_path(self) -> Path:
        """Return the filesystem path of the shared journal."""

        return self._journal_path

    def write(
        self,
        *,
        component: str,
        level: str,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> ActivityJournalEntry:
        """Append one structured event to the journal.

        The file is written in append-only mode so multiple processes can
        contribute to the same log without coordinating through a server.
        """

        entry = ActivityJournalEntry(
            timestamp_utc=utc_now_iso8601(),
            source_app=self._source_app,
            component=component,
            level=level.upper(),
            message=message,
            process_id=os.getpid(),
            extra=dict(extra or {}),
        )

        with self._lock:
            with self._journal_path.open("a", encoding="utf-8") as journal_file:
                journal_file.write(json.dumps(asdict(entry), separators=(",", ":")) + "\n")

        return entry


def read_recent_activity_entries(
    *,
    journal_path: Path | None = None,
    project_root: Path | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Read the newest structured activity entries from the shared journal.

    The reader is intentionally tolerant. If a line is malformed or partially
    written, it is skipped so the monitoring UI still has the best complete data
    available.
    """

    safe_limit = max(1, int(limit))
    resolved_journal_path = journal_path or get_default_activity_journal_path(project_root)
    if not resolved_journal_path.exists():
        return []

    collected_entries: list[dict[str, Any]] = []
    for raw_line in resolved_journal_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            parsed_entry = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed_entry, dict):
            collected_entries.append(parsed_entry)

    return collected_entries[-safe_limit:]
