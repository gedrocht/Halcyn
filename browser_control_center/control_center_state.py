"""Runtime services for the Halcyn browser-based Control Center.

This module keeps the Control Center logic separate from raw HTTP request
handling so it stays testable.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from browser_control_center.scene_studio_live_session import SceneStudioLiveSession
from browser_control_center.scene_studio_scene_builder import (
    build_catalog_payload,
    build_scene_bundle,
)


def utc_now_iso() -> str:
    """Return the current UTC time in a browser-friendly ISO 8601 format."""

    return datetime.now(timezone.utc).isoformat()


@dataclass
class LogEntry:
    """Describe one Control Center log event.

    Attributes:
        level: A short severity label such as INFO or ERROR.
        component: The subsystem that produced the log line.
        message: The human-readable log text.
        timestamp_utc: When the event happened, stored in UTC for consistency.
    """

    level: str
    component: str
    message: str
    timestamp_utc: str = field(default_factory=utc_now_iso)


@dataclass
class JobRecord:
    """Describe one background job such as build, test, or docs generation."""

    job_identifier: str
    kind: str
    command: list[str]
    working_directory: str
    status: str = "queued"
    started_at_utc: str | None = None
    finished_at_utc: str | None = None
    exit_code: int | None = None
    output_lines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert the job into plain JSON-ready data."""

        return {
            "job_id": self.job_identifier,
            "kind": self.kind,
            "command": self.command,
            "working_directory": self.working_directory,
            "status": self.status,
            "started_at_utc": self.started_at_utc,
            "finished_at_utc": self.finished_at_utc,
            "exit_code": self.exit_code,
            "output_lines": self.output_lines,
        }

    @property
    def job_id(self) -> str:
        """Preserve the older job_id attribute name for callers that still expect it."""

        return self.job_identifier

    @job_id.setter
    def job_id(self, value: str) -> None:
        """Allow older code paths to keep writing through the legacy attribute name."""

        self.job_identifier = value


@dataclass
class ManagedProcess:
    """Describe the long-running Halcyn app process managed by the Control Center."""

    name: str
    command: list[str]
    working_directory: str
    status: str = "stopped"
    process_identifier: int | None = None
    started_at_utc: str | None = None
    stopped_at_utc: str | None = None
    output_lines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert the process record into plain JSON-ready data."""

        return {
            "name": self.name,
            "command": self.command,
            "working_directory": self.working_directory,
            "status": self.status,
            "pid": self.process_identifier,
            "started_at_utc": self.started_at_utc,
            "stopped_at_utc": self.stopped_at_utc,
            "output_lines": self.output_lines,
        }

    @property
    def pid(self) -> int | None:
        """Preserve the older pid attribute name for callers that still expect it."""

        return self.process_identifier

    @pid.setter
    def pid(self, value: int | None) -> None:
        """Allow older code paths to keep writing through the legacy attribute name."""

        self.process_identifier = value


class LogBuffer:
    """Keep a bounded in-memory log for the Control Center itself."""

    def __init__(self, max_entries: int = 1000) -> None:
        self._max_entries = max_entries
        self._entries: deque[LogEntry] = deque(maxlen=max_entries)
        self._lock = threading.Lock()

    def add(self, level: str, component: str, message: str) -> None:
        """Append one new log entry."""

        with self._lock:
            self._entries.append(LogEntry(level=level, component=component, message=message))

    def recent(self, limit: int = 200) -> list[dict[str, Any]]:
        """Return the newest log entries up to the requested limit."""

        safe_limit = max(1, limit)
        with self._lock:
            return [asdict(entry) for entry in list(self._entries)[-safe_limit:]]


class ControlCenterState:
    """Own the mutable state behind the browser-based Control Center.

    This class is responsible for:
    - starting background jobs such as build/test/bootstrap
    - starting and stopping the Halcyn desktop app
    - collecting process output for the web UI
    - proxying requests into the Halcyn HTTP API
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.log_buffer = LogBuffer()
        self._job_records: dict[str, JobRecord] = {}
        self._next_job_number = 1
        self._job_records_lock = threading.Lock()
        self._managed_application_lock = threading.Lock()
        # The app record is the UI-facing description of the managed renderer process.
        # It exists even when no subprocess is running so the dashboard always has a
        # stable object shape to render.
        self._managed_application_record = ManagedProcess(
            name="halcyn_app",
            command=[],
            working_directory=str(project_root),
        )
        self._managed_application_process: subprocess.Popen[str] | None = None
        self._scene_studio_session = SceneStudioLiveSession(
            apply_callback=self._submit_scene_studio_scene,
            log_callback=self.log_buffer.add,
        )
        self.log_buffer.add("INFO", "control-center", "Control Center state initialized.")

    def _refresh_app_process_state_locked(self) -> None:
        """Synchronize the managed-app record with the live subprocess state."""

        # The browser can ask for app status at any moment. Instead of trusting that
        # older state is still accurate, we cheaply poll the subprocess and repair the
        # record if the process has already exited.
        if self._managed_application_process is None:
            return

        if self._managed_application_process.poll() is None:
            return

        self._managed_application_record.status = "stopped"
        if self._managed_application_record.stopped_at_utc is None:
            self._managed_application_record.stopped_at_utc = utc_now_iso()
        self._managed_application_process = None

    def _next_job_identifier(self) -> str:
        """Return the next unique job identifier."""

        with self._job_records_lock:
            job_identifier = f"job-{self._next_job_number:04d}"
            self._next_job_number += 1
            return job_identifier

    def _append_job_output(self, job: JobRecord, line: str) -> None:
        """Append one output line to a job while keeping output bounded."""

        job.output_lines.append(line.rstrip())
        # The dashboard only needs recent output. Trimming old lines keeps the control
        # plane from slowly growing forever in memory during long sessions.
        if len(job.output_lines) > 500:
            del job.output_lines[:-500]

    def _append_process_output(
        self,
        managed_process_record: ManagedProcess,
        line: str,
    ) -> None:
        """Append one output line to the managed app process while keeping output bounded."""

        managed_process_record.output_lines.append(line.rstrip())
        if len(managed_process_record.output_lines) > 800:
            del managed_process_record.output_lines[:-800]

    def _script_command(self, script_name: str, *arguments: str) -> list[str]:
        """Build a PowerShell command list for one repository script."""

        # Every long-running action in the browser UI ultimately delegates to one of
        # the repository's PowerShell scripts. Building commands in one helper keeps
        # their launch style consistent across jobs and the managed app.
        script_path = self.project_root / "scripts" / script_name
        return ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script_path), *arguments]

    def _start_job(
        self,
        kind: str,
        command_arguments: list[str],
        working_directory: Path,
    ) -> JobRecord:
        """Start one background job and capture its output for the UI."""

        job_record = JobRecord(
            job_identifier=self._next_job_identifier(),
            kind=kind,
            command=command_arguments,
            working_directory=str(working_directory),
        )

        with self._job_records_lock:
            self._job_records[job_record.job_identifier] = job_record

        self.log_buffer.add("INFO", "jobs", f"Queued {kind} job {job_record.job_identifier}.")

        def runner() -> None:
            """Run the subprocess, capture output, and update job status fields."""

            job_record.status = "running"
            job_record.started_at_utc = utc_now_iso()
            self.log_buffer.add("INFO", "jobs", f"Started {kind} job {job_record.job_identifier}.")

            try:
                # Jobs are intentionally launched with stdout and stderr merged so the
                # browser can present one time-ordered log stream instead of two separate ones.
                launched_process = subprocess.Popen(
                    command_arguments,
                    cwd=working_directory,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
            except Exception as error:  # pragma: no cover - startup failures vary by machine.
                job_record.status = "failed"
                job_record.finished_at_utc = utc_now_iso()
                job_record.exit_code = -1
                self._append_job_output(job_record, f"Failed to start process: {error}")
                self.log_buffer.add(
                    "ERROR",
                    "jobs",
                    f"{kind} job {job_record.job_identifier} failed to start: {error}",
                )
                return

            assert launched_process.stdout is not None
            for line in launched_process.stdout:
                self._append_job_output(job_record, line)
                self.log_buffer.add("INFO", kind, line.rstrip())

            launched_process.wait()
            job_record.exit_code = launched_process.returncode
            job_record.finished_at_utc = utc_now_iso()
            job_record.status = "succeeded" if launched_process.returncode == 0 else "failed"
            self.log_buffer.add(
                "INFO" if launched_process.returncode == 0 else "ERROR",
                "jobs",
                f"{kind} job {job_record.job_identifier} finished with exit code "
                f"{launched_process.returncode}.",
            )

        threading.Thread(target=runner, daemon=True).start()
        return job_record

    def start_bootstrap_job(self) -> JobRecord:
        """Start the prerequisite report job."""

        return self._start_job(
            "bootstrap",
            self._script_command("report-prerequisites.ps1"),
            self.project_root,
        )

    def start_build_job(self, configuration: str) -> JobRecord:
        """Start a build job for the chosen configuration."""

        return self._start_job(
            "build",
            self._script_command("build-halcyn-app.ps1", "-Configuration", configuration),
            self.project_root,
        )

    def start_test_job(self, configuration: str) -> JobRecord:
        """Start the repository test suite."""

        return self._start_job(
            "test",
            self._script_command("run-native-tests.ps1", "-Configuration", configuration),
            self.project_root,
        )

    def start_format_job(self) -> JobRecord:
        """Start the source-formatting job."""

        return self._start_job(
            "format", self._script_command("format-cpp-code.ps1"), self.project_root
        )

    def start_code_docs_job(self) -> JobRecord:
        """Start the generated code-documentation job."""

        return self._start_job(
            "generate-code-docs",
            self._script_command("generate-code-reference-docs.ps1"),
            self.project_root,
        )

    def start_app(
        self,
        configuration: str,
        host: str,
        port: int,
        sample: str,
        scene_file: str,
        width: int,
        height: int,
        frames_per_second: int = 60,
        title: str = "Halcyn",
        fps: int | None = None,
    ) -> ManagedProcess:
        """Start the Halcyn desktop app under Control Center supervision."""

        effective_frames_per_second = fps if fps is not None else frames_per_second

        with self._managed_application_lock:
            self._refresh_app_process_state_locked()
            if (
                self._managed_application_process is not None
                and self._managed_application_process.poll() is None
            ):
                if self._managed_application_record.status == "starting":
                    raise RuntimeError("The Halcyn app launch is already in progress.")
                raise RuntimeError("The Halcyn app is already running.")

            # The Control Center starts the app through launch-halcyn-app.ps1
            # instead of invoking the
            # executable directly, because the script already knows how to configure,
            # build, and run the chosen configuration correctly on Windows.
            launch_command = self._script_command(
                "launch-halcyn-app.ps1",
                "-Configuration",
                configuration,
                "-ApiHost",
                host,
                "-Port",
                str(port),
                "-Sample",
                sample,
                "-Width",
                str(width),
                "-Height",
                str(height),
                "-Fps",
                str(effective_frames_per_second),
                "-Title",
                title,
            )

            if scene_file.strip():
                launch_command.extend(["-SceneFile", scene_file])

            self._managed_application_record = ManagedProcess(
                name="halcyn_app",
                command=launch_command,
                working_directory=str(self.project_root),
                status="starting",
                started_at_utc=utc_now_iso(),
            )

            managed_application_process = subprocess.Popen(
                launch_command,
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self._managed_application_process = managed_application_process
            self._managed_application_record.process_identifier = managed_application_process.pid
            self.log_buffer.add(
                "INFO",
                "app",
                f"Started Halcyn app process tree via PID {managed_application_process.pid}.",
            )

            def monitor() -> None:
                """Monitor the app process and keep the web UI state in sync."""

                assert managed_application_process.stdout is not None
                for line in managed_application_process.stdout:
                    # launch-halcyn-app.ps1 prints a "Starting ..." line just before the renderer is
                    # truly launching. We use that as the transition from "starting"
                    # to "running" so the dashboard reflects the user's real experience.
                    if line.startswith("Starting "):
                        self._managed_application_record.status = "running"
                    self._append_process_output(self._managed_application_record, line)
                    self.log_buffer.add("INFO", "app", line.rstrip())

                managed_application_process.wait()
                self._managed_application_record.status = "stopped"
                self._managed_application_record.stopped_at_utc = utc_now_iso()
                with self._managed_application_lock:
                    self._managed_application_process = None
                self.log_buffer.add(
                    "INFO" if managed_application_process.returncode == 0 else "ERROR",
                    "app",
                    "Halcyn app process exited with code "
                    f"{managed_application_process.returncode}.",
                )

            threading.Thread(target=monitor, daemon=True).start()
            return self._managed_application_record

    def stop_app(self) -> ManagedProcess:
        """Stop the managed Halcyn app process tree."""

        with self._managed_application_lock:
            self._refresh_app_process_state_locked()
            managed_application_process = self._managed_application_process
            if (
                managed_application_process is None
                or managed_application_process.poll() is not None
            ):
                self._managed_application_record.status = "stopped"
                return self._managed_application_record

            # taskkill /T stops the whole child process tree, which matters because
            # PowerShell may have started build tools or the app beneath the wrapper process.
            subprocess.run(
                ["taskkill", "/PID", str(managed_application_process.pid), "/T", "/F"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self._managed_application_record.status = "stopping"
            self._managed_application_record.stopped_at_utc = utc_now_iso()
            self.log_buffer.add(
                "INFO",
                "app",
                "Requested stop for app process tree rooted at PID "
                f"{managed_application_process.pid}.",
            )
            return self._managed_application_record

    def app_status(self) -> dict[str, Any]:
        """Return the current status of the managed Halcyn app."""

        with self._managed_application_lock:
            self._refresh_app_process_state_locked()
            managed_application_status = self._managed_application_record.to_dict()
            managed_application_status["is_alive"] = (
                self._managed_application_process is not None
                and self._managed_application_process.poll() is None
            )
            return managed_application_status

    def available_tools(self) -> dict[str, dict[str, Any]]:
        """Inspect the local machine for the tools the project knows how to use."""

        def winget_binary_path(package_pattern: str, binary_name: str) -> str:
            winget_root = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
            if not winget_root.exists():
                return ""

            for package in sorted(winget_root.glob(package_pattern), reverse=True):
                for candidate in package.rglob(binary_name):
                    if candidate.is_file():
                        return str(candidate)

            return ""

        def known_tool_path(command_name: str) -> str:
            path = shutil.which(command_name)
            if path:
                return path

            # These fallbacks cover the most common Windows installation paths so the
            # Control Center can still give useful diagnostics when tools are not on PATH.
            candidate_paths = {
                "ninja": [r"C:\ProgramData\Chocolatey\bin\ninja.exe"],
                "clang-format": [r"C:\Program Files\LLVM\bin\clang-format.exe"],
                "doxygen": [
                    r"C:\Program Files\doxygen\bin\doxygen.exe",
                    r"C:\Strawberry\c\bin\doxygen.exe",
                ],
            }
            for candidate in candidate_paths.get(command_name, []):
                if Path(candidate).exists():
                    return candidate

            if command_name in {"clang-format", "clang++"}:
                visual_studio_match = visual_studio_llvm_path(f"{command_name}.exe")
                if visual_studio_match:
                    return visual_studio_match

            winget_match = {
                "ninja": winget_binary_path("Ninja-build.Ninja*", "ninja.exe"),
                "clang-format": winget_binary_path("LLVM.LLVM*", "clang-format.exe"),
                "clang++": winget_binary_path("LLVM.LLVM*", "clang++.exe"),
                "doxygen": winget_binary_path("DimitriVanHeesch.Doxygen*", "doxygen.exe"),
            }.get(command_name, "")
            return winget_match or ""

        def command_status(command_name: str) -> dict[str, Any]:
            path = known_tool_path(command_name)
            return {"available": bool(path), "path": path or ""}

        def visual_studio_compiler_status() -> dict[str, Any]:
            visual_studio = visual_studio_status()
            if not visual_studio["available"]:
                return {"available": False, "path": ""}

            if visual_studio["path"].lower().endswith("vsdevcmd.bat"):
                installation_root = Path(visual_studio["path"]).parents[2]
                compiler_roots = sorted(
                    (installation_root / "VC" / "Tools" / "MSVC").glob("*"),
                    reverse=True,
                )
                for compiler_root in compiler_roots:
                    # We pick the newest discovered MSVC toolset because that mirrors
                    # what Visual Studio itself would typically prefer.
                    candidate = compiler_root / "bin" / "Hostx64" / "x64" / "cl.exe"
                    if candidate.exists():
                        return {"available": True, "path": str(candidate)}

            return {"available": False, "path": ""}

        def visual_studio_llvm_path(binary_name: str) -> str:
            visual_studio = visual_studio_status()
            if not visual_studio["available"]:
                return ""

            installation_root = Path(visual_studio["path"]).parents[2]
            candidates = [
                installation_root / "VC" / "Tools" / "Llvm" / "bin" / binary_name,
                installation_root / "VC" / "Tools" / "Llvm" / "x64" / "bin" / binary_name,
                installation_root / "VC" / "Tools" / "Llvm" / "ARM64" / "bin" / binary_name,
            ]
            for candidate in candidates:
                if candidate.exists():
                    return str(candidate)

            return ""

        def visual_studio_status() -> dict[str, Any]:
            vswhere_path = Path(
                r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
            )
            if vswhere_path.exists():
                result = subprocess.run(
                    [
                        str(vswhere_path),
                        "-latest",
                        "-products",
                        "*",
                        "-requires",
                        "Microsoft.VisualStudio.Workload.NativeDesktop",
                        "-property",
                        "installationPath",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                installation_path = result.stdout.strip()
                if result.returncode == 0 and installation_path:
                    dev_cmd = Path(installation_path) / "Common7" / "Tools" / "VsDevCmd.bat"
                    resolved_path = str(dev_cmd if dev_cmd.exists() else Path(installation_path))
                    return {"available": True, "path": resolved_path}

            visual_studio_root = Path(r"C:\Program Files\Microsoft Visual Studio\2022")
            visual_studio_candidates = [
                visual_studio_root / "BuildTools" / "Common7" / "Tools" / "VsDevCmd.bat",
                visual_studio_root / "Community" / "Common7" / "Tools" / "VsDevCmd.bat",
                visual_studio_root / "Professional" / "Common7" / "Tools" / "VsDevCmd.bat",
                visual_studio_root / "Enterprise" / "Common7" / "Tools" / "VsDevCmd.bat",
            ]
            visual_studio_path = next(
                (str(path) for path in visual_studio_candidates if path.exists()),
                "",
            )
            return {"available": bool(visual_studio_path), "path": visual_studio_path}

        python_jinja2_available = False
        python_path = known_tool_path("python")
        if python_path:
            # report-prerequisites.ps1 depends on Jinja2 for code generation, so we test the
            # import directly instead of assuming "python exists" means it is ready.
            result = subprocess.run(
                [python_path, "-c", "import jinja2"],
                capture_output=True,
                text=True,
                check=False,
            )
            python_jinja2_available = result.returncode == 0

        return {
            "cmake": command_status("cmake"),
            "python": command_status("python"),
            "git": command_status("git"),
            "ninja": command_status("ninja"),
            "cl": command_status("cl") if shutil.which("cl") else visual_studio_compiler_status(),
            "clangpp": command_status("clang++"),
            "gpp": command_status("g++"),
            "doxygen": command_status("doxygen"),
            "clang_format": command_status("clang-format"),
            "python_jinja2": {"available": python_jinja2_available, "path": ""},
            "visual_studio_2022": visual_studio_status(),
        }

    def recent_jobs(self, limit: int = 25) -> list[dict[str, Any]]:
        """Return the newest background jobs."""

        with self._job_records_lock:
            recent_job_records = list(self._job_records.values())[-max(1, limit) :]
            return [job_record.to_dict() for job_record in recent_job_records]

    def scene_studio_catalog(self) -> dict[str, Any]:
        """Return the preset and input metadata for the browser-based Scene Studio."""

        return build_catalog_payload()

    def scene_studio_session_status(self) -> dict[str, Any]:
        """Return the status of the server-side live Scene Studio session."""

        return {"status": "ok", "session": self._scene_studio_session.snapshot()}

    def wait_for_scene_studio_session_update(
        self,
        after_revision: int,
        timeout_seconds: float = 15.0,
    ) -> tuple[dict[str, Any], bool]:
        """Wait for the live Scene Studio snapshot to change."""

        snapshot, changed = self._scene_studio_session.wait_for_update(
            after_revision,
            timeout_seconds=timeout_seconds,
        )
        return {"status": "ok", "session": snapshot}, changed

    def configure_scene_studio_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Update the live Scene Studio session without starting or stopping it."""

        # Configure is the "change knobs but keep current running state" operation.
        # That is different from start/stop so the browser can edit settings incrementally.
        snapshot = self._scene_studio_session.configure(payload)
        return {"status": "configured", "session": snapshot}

    def start_scene_studio_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Start the live Scene Studio streaming session."""

        snapshot = self._scene_studio_session.start(payload)
        return {"status": "accepted", "session": snapshot}

    def stop_scene_studio_session(self) -> dict[str, Any]:
        """Stop the live Scene Studio streaming session."""

        snapshot = self._scene_studio_session.stop()
        return {"status": "accepted", "session": snapshot}

    def preview_scene_studio_scene(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Generate one browser-authored scene without touching the live renderer."""

        # Preview generation lets the browser inspect what would be sent without
        # mutating the live scene currently shown by the renderer.
        scene_bundle = build_scene_bundle(payload)
        self.log_buffer.add(
            "INFO",
            "scene-studio",
            f"Generated preview for preset {scene_bundle['preset']['id']}.",
        )
        return scene_bundle

    def apply_scene_studio_scene(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Generate and submit one scene-studio scene to the live renderer."""

        scene_bundle = build_scene_bundle(payload)
        target_connection = scene_bundle["target"]
        scene_json = json.dumps(scene_bundle["scene"], separators=(",", ":"))

        submission = self.run_api_request(
            host=target_connection["host"],
            port=int(target_connection["port"]),
            method="POST",
            request_path="/api/v1/scene",
            request_body=scene_json,
            content_type="application/json",
        )
        if submission["status"] == 0:
            self.log_buffer.add(
                "ERROR",
                "scene-studio",
                "Could not reach the live Halcyn API while applying a scene-studio scene.",
            )
            return {
                "status": "offline",
                "preset": scene_bundle["preset"],
                "target": target_connection,
                "scene": scene_bundle["scene"],
                "analysis": scene_bundle["analysis"],
                "submission": submission,
            }

        if submission["status"] == 400:
            self.log_buffer.add(
                "WARNING",
                "scene-studio",
                "Rejected scene-studio scene "
                f"{scene_bundle['preset']['id']} during live submission.",
            )
            return {
                "status": "validation-failed",
                "preset": scene_bundle["preset"],
                "target": target_connection,
                "scene": scene_bundle["scene"],
                "analysis": scene_bundle["analysis"],
                "submission": submission,
                "networkBytes": len(scene_json.encode("utf-8")),
            }

        applied = submission["status"] in (200, 202)
        if not applied:
            self.log_buffer.add(
                "ERROR",
                "scene-studio",
                f"Failed to apply preset {scene_bundle['preset']['id']} to the live renderer.",
            )
            return {
                "status": "apply-failed",
                "preset": scene_bundle["preset"],
                "target": target_connection,
                "scene": scene_bundle["scene"],
                "analysis": scene_bundle["analysis"],
                "submission": submission,
                "networkBytes": len(scene_json.encode("utf-8")),
            }

        self.log_buffer.add(
            "INFO",
            "scene-studio",
            f"Applied preset {scene_bundle['preset']['id']} to "
            f"{target_connection['host']}:{target_connection['port']}.",
        )
        return {
            "status": "applied",
            "preset": scene_bundle["preset"],
            "target": target_connection,
            "scene": scene_bundle["scene"],
            "analysis": scene_bundle["analysis"],
            "submission": submission,
            "networkBytes": len(scene_json.encode("utf-8")),
        }

    def _submit_scene_studio_scene(self, host: str, port: int, scene_json: str) -> dict[str, Any]:
        """Submit one generated scene to the live Halcyn renderer."""

        return self.run_api_request(
            host=host,
            port=port,
            method="POST",
            request_path="/api/v1/scene",
            request_body=scene_json,
            content_type="application/json",
            timeout_seconds=2,
        )

    def run_api_request(
        self,
        host: str,
        port: int,
        method: str,
        request_path: str | None = None,
        request_body: str | None = None,
        content_type: str = "application/json",
        timeout_seconds: float = 10,
        path: str | None = None,
        body: str | None = None,
    ) -> dict[str, Any]:
        """Proxy one browser-issued request into the running Halcyn API."""

        effective_request_path = request_path if request_path is not None else path or "/"
        effective_request_body = request_body if request_body is not None else body or ""
        normalized_path = (
            effective_request_path
            if effective_request_path.startswith("/")
            else f"/{effective_request_path}"
        )
        request_url = f"http://{host}:{port}{normalized_path}"
        request_body_bytes = (
            effective_request_body.encode("utf-8") if effective_request_body else None
        )
        http_request = urllib.request.Request(
            url=request_url,
            data=request_body_bytes,
            method=method.upper(),
        )
        if effective_request_body:
            http_request.add_header("Content-Type", content_type or "application/json")

        self.log_buffer.add(
            "INFO",
            "playground",
            f"Forwarding {method.upper()} {normalized_path} to the Halcyn API.",
        )

        try:
            with urllib.request.urlopen(http_request, timeout=timeout_seconds) as http_response:
                response_body_text = http_response.read().decode("utf-8")
                return {
                    "ok": True,
                    "status": http_response.status,
                    "reason": http_response.reason,
                    "body": response_body_text,
                    "headers": dict(http_response.headers.items()),
                }
        except urllib.error.HTTPError as error:
            response_body_text = error.read().decode("utf-8")
            return {
                "ok": False,
                "status": error.code,
                "reason": error.reason,
                "body": response_body_text,
                "headers": dict(error.headers.items()),
            }
        except Exception as error:  # pragma: no cover - network errors vary by machine.
            return {
                "ok": False,
                "status": 0,
                "reason": "connection-error",
                "body": str(error),
                "headers": {},
            }

    def run_smoke_checks(self, host: str, port: int) -> dict[str, Any]:
        """Run a lightweight online smoke suite against the running Halcyn API."""

        smoke_check_results = []
        for method, request_path, request_body in [
            ("GET", "/api/v1/health", ""),
            ("GET", "/api/v1/runtime/limits", ""),
            (
                "POST",
                "/api/v1/scene/validate",
                json.dumps(
                    {
                        "sceneType": "2d",
                        "primitive": "triangles",
                        "vertices": [
                            {"x": -1.0, "y": -1.0, "r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0},
                            {"x": 0.0, "y": 1.0, "r": 0.0, "g": 1.0, "b": 0.0, "a": 1.0},
                            {"x": 1.0, "y": -1.0, "r": 0.0, "g": 0.0, "b": 1.0, "a": 1.0},
                        ],
                    }
                ),
            ),
        ]:
            response = self.run_api_request(
                host, port, method, request_path, request_body, "application/json"
            )
            smoke_check_results.append(
                {
                    "method": method,
                    "path": request_path,
                    "status": response["status"],
                    "ok": response["status"] in (200, 202),
                }
            )

        all_checks_passed = all(check["ok"] for check in smoke_check_results)
        return {
            "status": "passed" if all_checks_passed else "failed",
            "checks": smoke_check_results,
        }

    def summary(self) -> dict[str, Any]:
        """Return the combined dashboard payload used by the browser UI."""

        # The dashboard is intentionally hydrated by one broad summary payload so the
        # first page load can show a coherent snapshot before smaller live updates begin.
        return {
            "status": "ok",
            "projectRoot": str(self.project_root),
            "tools": self.available_tools(),
            "app": self.app_status(),
            "jobs": self.recent_jobs(),
            "logs": self.log_buffer.recent(),
            "docs": {
                "overview": "/docs/index.html",
                "tutorial": "/docs/tutorial.html",
                "api": "/docs/api.html",
                "architecture": "/docs/architecture.html",
                "testing": "/docs/testing.html",
                "codeDocsGuide": "/docs/code-docs.html",
                "fieldReference": "/docs/field-reference.html",
                "controlCenter": "/docs/control-center.html",
                "sceneStudioGuide": "/docs/scene-studio.html",
                "generatedCodeDocs": "/generated-code-docs/index.html",
                "sceneStudio": "/scene-studio/",
            },
        }
