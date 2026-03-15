"""Runtime services for the Halcyn browser-based control plane.

This module keeps the control-plane logic separate from raw HTTP request
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


def utc_now_iso() -> str:
    """Return the current UTC time in a browser-friendly ISO 8601 format."""

    return datetime.now(timezone.utc).isoformat()


@dataclass
class LogEntry:
    """Describe one control-plane log event.

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

    job_id: str
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

        return asdict(self)


@dataclass
class ManagedProcess:
    """Describe the long-running Halcyn app process managed by the control plane."""

    name: str
    command: list[str]
    working_directory: str
    status: str = "stopped"
    pid: int | None = None
    started_at_utc: str | None = None
    stopped_at_utc: str | None = None
    output_lines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert the process record into plain JSON-ready data."""

        return asdict(self)


class LogBuffer:
    """Keep a bounded in-memory log for the control plane itself."""

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


class ControlPlaneState:
    """Own the mutable state behind the browser-based control plane.

    This class is responsible for:
    - starting background jobs such as build/test/bootstrap
    - starting and stopping the Halcyn desktop app
    - collecting process output for the web UI
    - proxying requests into the Halcyn HTTP API
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.log_buffer = LogBuffer()
        self._jobs: dict[str, JobRecord] = {}
        self._job_counter = 1
        self._jobs_lock = threading.Lock()
        self._app_lock = threading.Lock()
        self._app_record = ManagedProcess(
            name="halcyn_app",
            command=[],
            working_directory=str(project_root),
        )
        self._app_process: subprocess.Popen[str] | None = None
        self.log_buffer.add("INFO", "control-plane", "Control plane state initialized.")

    def _refresh_app_process_state_locked(self) -> None:
        """Synchronize the managed-app record with the live subprocess state."""

        if self._app_process is None:
            return

        if self._app_process.poll() is None:
            return

        self._app_record.status = "stopped"
        if self._app_record.stopped_at_utc is None:
            self._app_record.stopped_at_utc = utc_now_iso()
        self._app_process = None

    def _next_job_id(self) -> str:
        """Return the next unique job identifier."""

        with self._jobs_lock:
            job_id = f"job-{self._job_counter:04d}"
            self._job_counter += 1
            return job_id

    def _append_job_output(self, job: JobRecord, line: str) -> None:
        """Append one output line to a job while keeping output bounded."""

        job.output_lines.append(line.rstrip())
        if len(job.output_lines) > 500:
            del job.output_lines[:-500]

    def _append_process_output(self, process_record: ManagedProcess, line: str) -> None:
        """Append one output line to the managed app process while keeping output bounded."""

        process_record.output_lines.append(line.rstrip())
        if len(process_record.output_lines) > 800:
            del process_record.output_lines[:-800]

    def _script_command(self, script_name: str, *arguments: str) -> list[str]:
        """Build a PowerShell command list for one repository script."""

        script_path = self.project_root / "scripts" / script_name
        return ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script_path), *arguments]

    def _start_job(self, kind: str, command: list[str], working_directory: Path) -> JobRecord:
        """Start one background job and capture its output for the UI."""

        job = JobRecord(
            job_id=self._next_job_id(),
            kind=kind,
            command=command,
            working_directory=str(working_directory),
        )

        with self._jobs_lock:
            self._jobs[job.job_id] = job

        self.log_buffer.add("INFO", "jobs", f"Queued {kind} job {job.job_id}.")

        def runner() -> None:
            """Run the subprocess, capture output, and update job status fields."""

            job.status = "running"
            job.started_at_utc = utc_now_iso()
            self.log_buffer.add("INFO", "jobs", f"Started {kind} job {job.job_id}.")

            try:
                process = subprocess.Popen(
                    command,
                    cwd=working_directory,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
            except Exception as error:  # pragma: no cover - startup failures vary by machine.
                job.status = "failed"
                job.finished_at_utc = utc_now_iso()
                job.exit_code = -1
                self._append_job_output(job, f"Failed to start process: {error}")
                self.log_buffer.add(
                    "ERROR",
                    "jobs",
                    f"{kind} job {job.job_id} failed to start: {error}",
                )
                return

            assert process.stdout is not None
            for line in process.stdout:
                self._append_job_output(job, line)
                self.log_buffer.add("INFO", kind, line.rstrip())

            process.wait()
            job.exit_code = process.returncode
            job.finished_at_utc = utc_now_iso()
            job.status = "succeeded" if process.returncode == 0 else "failed"
            self.log_buffer.add(
                "INFO" if process.returncode == 0 else "ERROR",
                "jobs",
                f"{kind} job {job.job_id} finished with exit code {process.returncode}.",
            )

        threading.Thread(target=runner, daemon=True).start()
        return job

    def start_bootstrap_job(self) -> JobRecord:
        """Start the prerequisite report job."""

        return self._start_job(
            "bootstrap",
            self._script_command("bootstrap.ps1"),
            self.project_root,
        )

    def start_build_job(self, configuration: str) -> JobRecord:
        """Start a build job for the chosen configuration."""

        return self._start_job(
            "build",
            self._script_command("build.ps1", "-Configuration", configuration),
            self.project_root,
        )

    def start_test_job(self, configuration: str) -> JobRecord:
        """Start the repository test suite."""

        return self._start_job(
            "test",
            self._script_command("test.ps1", "-Configuration", configuration),
            self.project_root,
        )

    def start_format_job(self) -> JobRecord:
        """Start the source-formatting job."""

        return self._start_job("format", self._script_command("format.ps1"), self.project_root)

    def start_code_docs_job(self) -> JobRecord:
        """Start the generated code-documentation job."""

        return self._start_job(
            "generate-code-docs",
            self._script_command("generate-code-docs.ps1"),
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
        fps: int,
        title: str,
    ) -> ManagedProcess:
        """Start the Halcyn desktop app under control-plane supervision."""

        with self._app_lock:
            self._refresh_app_process_state_locked()
            if self._app_process is not None and self._app_process.poll() is None:
                if self._app_record.status == "starting":
                    raise RuntimeError("The Halcyn app launch is already in progress.")
                raise RuntimeError("The Halcyn app is already running.")

            command = self._script_command(
                "run.ps1",
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
                str(fps),
                "-Title",
                title,
            )

            if scene_file.strip():
                command.extend(["-SceneFile", scene_file])

            self._app_record = ManagedProcess(
                name="halcyn_app",
                command=command,
                working_directory=str(self.project_root),
                status="starting",
                started_at_utc=utc_now_iso(),
            )

            process = subprocess.Popen(
                command,
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self._app_process = process
            self._app_record.pid = process.pid
            self.log_buffer.add(
                "INFO",
                "app",
                f"Started Halcyn app process tree via PID {process.pid}.",
            )

            def monitor() -> None:
                """Monitor the app process and keep the web UI state in sync."""

                assert process.stdout is not None
                for line in process.stdout:
                    if line.startswith("Starting "):
                        self._app_record.status = "running"
                    self._append_process_output(self._app_record, line)
                    self.log_buffer.add("INFO", "app", line.rstrip())

                process.wait()
                self._app_record.status = "stopped"
                self._app_record.stopped_at_utc = utc_now_iso()
                with self._app_lock:
                    self._app_process = None
                self.log_buffer.add(
                    "INFO" if process.returncode == 0 else "ERROR",
                    "app",
                    f"Halcyn app process exited with code {process.returncode}.",
                )

            threading.Thread(target=monitor, daemon=True).start()
            return self._app_record

    def stop_app(self) -> ManagedProcess:
        """Stop the managed Halcyn app process tree."""

        with self._app_lock:
            self._refresh_app_process_state_locked()
            process = self._app_process
            if process is None or process.poll() is not None:
                self._app_record.status = "stopped"
                return self._app_record

            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self._app_record.status = "stopping"
            self._app_record.stopped_at_utc = utc_now_iso()
            self.log_buffer.add(
                "INFO",
                "app",
                f"Requested stop for app process tree rooted at PID {process.pid}.",
            )
            return self._app_record

    def app_status(self) -> dict[str, Any]:
        """Return the current status of the managed Halcyn app."""

        with self._app_lock:
            self._refresh_app_process_state_locked()
            record = self._app_record.to_dict()
            record["is_alive"] = self._app_process is not None and self._app_process.poll() is None
            return record

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

        with self._jobs_lock:
            jobs = list(self._jobs.values())[-max(1, limit):]
            return [job.to_dict() for job in jobs]

    def run_api_request(
        self,
        host: str,
        port: int,
        method: str,
        path: str,
        body: str,
        content_type: str,
    ) -> dict[str, Any]:
        """Proxy one browser-issued request into the running Halcyn API."""

        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"http://{host}:{port}{normalized_path}"
        data = body.encode("utf-8") if body else None
        request = urllib.request.Request(url=url, data=data, method=method.upper())
        if body:
            request.add_header("Content-Type", content_type or "application/json")

        self.log_buffer.add(
            "INFO",
            "playground",
            f"Forwarding {method.upper()} {normalized_path} to the Halcyn API.",
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = response.read().decode("utf-8")
                return {
                    "ok": True,
                    "status": response.status,
                    "reason": response.reason,
                    "body": payload,
                    "headers": dict(response.headers.items()),
                }
        except urllib.error.HTTPError as error:
            payload = error.read().decode("utf-8")
            return {
                "ok": False,
                "status": error.code,
                "reason": error.reason,
                "body": payload,
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

        checks = []
        for method, path, body in [
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
            response = self.run_api_request(host, port, method, path, body, "application/json")
            checks.append(
                {
                    "method": method,
                    "path": path,
                    "status": response["status"],
                    "ok": response["status"] in (200, 202),
                }
            )

        all_passed = all(check["ok"] for check in checks)
        return {"status": "passed" if all_passed else "failed", "checks": checks}

    def summary(self) -> dict[str, Any]:
        """Return the combined dashboard payload used by the browser UI."""

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
                "generatedCodeDocs": "/generated-code-docs/index.html",
            },
        }
