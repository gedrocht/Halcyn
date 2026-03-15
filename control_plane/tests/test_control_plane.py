"""Tests for the Halcyn browser-based control plane."""

from __future__ import annotations

import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar, cast
from unittest import mock

from control_plane.runtime import ControlPlaneState, JobRecord, ManagedProcess
from control_plane.server import (
    ControlPlaneRequestHandler,
    HalcynThreadingHTTPServer,
    create_server,
    normalize_project_root,
    strip_powershell_provider_prefix,
)


class _OkHandler(BaseHTTPRequestHandler):
    """Serve a tiny success response for run_api_request tests."""

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler requires this name.
        body = b'{"status":"ok"}'
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class _FakeProcess:
    """Minimal subprocess stand-in for control-plane tests."""

    def __init__(
        self,
        lines: list[str] | None = None,
        pid: int = 4321,
        returncode: int = 0,
    ) -> None:
        self.stdout = iter(lines or [])
        self.pid = pid
        self.returncode = returncode
        self._waited = False

    def wait(self) -> int:
        self._waited = True
        return self.returncode

    def poll(self) -> int | None:
        return self.returncode if self._waited else None


class _LiveProcess:
    """Minimal long-running subprocess stand-in for conflict-path tests."""

    def __init__(self, pid: int = 9999) -> None:
        self.pid = pid

    def poll(self) -> int | None:
        return None


class ControlPlaneServerTests(unittest.TestCase):
    """Exercise the HTTP surface of the control plane without needing the C++ toolchain."""

    project_root: ClassVar[Path]
    server: ClassVar[ThreadingHTTPServer]
    state: ClassVar[ControlPlaneState]
    thread: ClassVar[threading.Thread]
    base_url: ClassVar[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[2]
        cls.server = create_server("127.0.0.1", 0, cls.project_root)
        handler_class = cast(type[ControlPlaneRequestHandler], cls.server.RequestHandlerClass)
        cls.state = handler_class.state
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def _post_json(self, path: str, payload: object) -> tuple[int, dict]:
        """Send one JSON POST request to the in-process test server."""

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_root_serves_html(self) -> None:
        """The browser entry page should be reachable."""

        with urllib.request.urlopen(f"{self.base_url}/", timeout=5) as response:
            body = response.read().decode("utf-8")

        self.assertIn("Halcyn Control Plane", body)

    def test_summary_endpoint_returns_expected_sections(self) -> None:
        """The dashboard summary should return tools, docs, jobs, and app state."""

        with urllib.request.urlopen(f"{self.base_url}/api/system/summary", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["status"], "ok")
        self.assertIn("tools", payload)
        self.assertIn("docs", payload)
        self.assertIn("app", payload)
        self.assertIn("jobs", payload)

    def test_docs_route_serves_static_docs(self) -> None:
        """The static docs site should be reachable through the control plane."""

        with urllib.request.urlopen(f"{self.base_url}/docs/index.html", timeout=5) as response:
            body = response.read().decode("utf-8")

        self.assertIn("Halcyn", body)

    def test_jobs_logs_and_app_status_endpoints_return_payloads(self) -> None:
        """The diagnostic endpoints should return structured JSON payloads."""

        for path, expected_key in [
            ("/api/jobs", "jobs"),
            ("/api/logs", "entries"),
            ("/api/app/status", "app"),
        ]:
            with urllib.request.urlopen(f"{self.base_url}{path}", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(payload["status"], "ok")
            self.assertIn(expected_key, payload)

    def test_path_traversal_for_static_assets_is_rejected(self) -> None:
        """Static asset traversal attempts should not escape the static directory."""

        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(f"{self.base_url}/static/../server.py", timeout=5)

        self.assertEqual(context.exception.code, 404)

    def test_path_traversal_for_generated_docs_is_rejected(self) -> None:
        """Generated docs traversal attempts should not escape the docs directory."""

        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(f"{self.base_url}/generated-code-docs/../README.md", timeout=5)

        self.assertEqual(context.exception.code, 404)

    def test_unknown_route_returns_not_found(self) -> None:
        """Unknown routes should return a 404 instead of succeeding silently."""

        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(f"{self.base_url}/definitely-not-a-real-route", timeout=5)

        self.assertEqual(context.exception.code, 404)

    def test_invalid_json_returns_bad_request(self) -> None:
        """Malformed JSON payloads should be rejected with a 400 response."""

        request = urllib.request.Request(
            f"{self.base_url}/api/jobs/build",
            data=b"{",
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=5)

        self.assertEqual(context.exception.code, 400)

    def test_job_routes_accept_requests(self) -> None:
        """Job routes should forward accepted responses from the control-plane state."""

        # These routes are thin adapters over ControlPlaneState methods, so mocking
        # the state lets the test focus on the HTTP translation layer itself.
        for path, method_name in [
            ("/api/jobs/bootstrap", "start_bootstrap_job"),
            ("/api/jobs/build", "start_build_job"),
            ("/api/jobs/test", "start_test_job"),
            ("/api/jobs/format", "start_format_job"),
            ("/api/jobs/generate-code-docs", "start_code_docs_job"),
        ]:
            job = JobRecord(
                job_id="job-9999",
                kind="test",
                command=["powershell"],
                working_directory=str(self.project_root),
            )
            with mock.patch.object(self.state, method_name, return_value=job):
                status, payload = self._post_json(path, {"configuration": "Debug"})

            self.assertEqual(status, 202)
            self.assertEqual(payload["status"], "accepted")
            self.assertEqual(payload["job"]["job_id"], "job-9999")

    def test_app_routes_accept_requests(self) -> None:
        """App start and stop routes should serialize the returned process records."""

        app_record = ManagedProcess(
            name="halcyn_app",
            command=["powershell"],
            working_directory=str(self.project_root),
            status="running",
            pid=111,
        )
        with mock.patch.object(self.state, "start_app", return_value=app_record):
            status, payload = self._post_json("/api/app/start", {"configuration": "Debug"})
        self.assertEqual(status, 202)
        self.assertEqual(payload["app"]["pid"], 111)

        with mock.patch.object(self.state, "stop_app", return_value=app_record):
            status, payload = self._post_json("/api/app/stop", {})
        self.assertEqual(status, 202)
        self.assertEqual(payload["app"]["name"], "halcyn_app")

    def test_runtime_errors_are_reported_as_conflicts(self) -> None:
        """Expected runtime rejections should be surfaced as 409 responses."""

        with mock.patch.object(
            self.state,
            "start_app",
            side_effect=RuntimeError("already running"),
        ):
            request = urllib.request.Request(
                f"{self.base_url}/api/app/start",
                data=b"{}",
                method="POST",
                headers={"Content-Type": "application/json"},
            )

            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(request, timeout=5)

        self.assertEqual(context.exception.code, 409)
        payload = json.loads(context.exception.read().decode("utf-8"))
        self.assertEqual(payload["status"], "rejected")

    def test_unhandled_server_errors_are_reported_as_internal_errors(self) -> None:
        """Unexpected handler failures should return a structured 500 response."""

        with mock.patch.object(self.state, "start_build_job", side_effect=ValueError("boom")):
            request = urllib.request.Request(
                f"{self.base_url}/api/jobs/build",
                data=b"{}",
                method="POST",
                headers={"Content-Type": "application/json"},
            )

            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(request, timeout=5)

        self.assertEqual(context.exception.code, 500)
        payload = json.loads(context.exception.read().decode("utf-8"))
        self.assertEqual(payload["status"], "error")

    def test_smoke_and_playground_routes_forward_results(self) -> None:
        """The API lab and smoke routes should surface the state-layer responses."""

        with mock.patch.object(
            self.state,
            "run_smoke_checks",
            return_value={"status": "passed", "checks": []},
        ):
            status, payload = self._post_json("/api/app/smoke", {})
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "passed")

        playground_result = {
            "ok": True,
            "status": 200,
            "reason": "OK",
            "body": "{}",
            "headers": {},
        }
        with mock.patch.object(self.state, "run_api_request", return_value=playground_result):
            status, payload = self._post_json(
                "/api/playground/request",
                {"method": "GET", "path": "/api/v1/health"},
            )
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])

    def test_unknown_post_route_returns_not_found(self) -> None:
        """Unknown control-plane POST routes should return a 404 JSON response."""

        request = urllib.request.Request(
            f"{self.base_url}/api/not-real",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=5)

        self.assertEqual(context.exception.code, 404)
        payload = json.loads(context.exception.read().decode("utf-8"))
        self.assertEqual(payload["status"], "unknown-route")

    def test_project_root_normalization_strips_powershell_provider_prefix(self) -> None:
        """PowerShell provider-qualified paths should be normalized before server startup."""

        provider_path = r"Microsoft.PowerShell.Core\FileSystem::\\server\share\Halcyn"
        normalized = normalize_project_root(provider_path)

        self.assertEqual(strip_powershell_provider_prefix(provider_path), r"\\server\share\Halcyn")
        self.assertTrue(str(normalized).endswith(r"server\share\Halcyn"))

    def test_server_ignores_benign_connection_abort_errors(self) -> None:
        """Expected local browser disconnects should not spam stack traces."""

        server = HalcynThreadingHTTPServer(("127.0.0.1", 0), _OkHandler)
        try:
            with mock.patch.object(ThreadingHTTPServer, "handle_error") as patched:
                try:
                    raise ConnectionAbortedError("client went away")
                except ConnectionAbortedError:
                    server.handle_error(mock.Mock(), ("127.0.0.1", 12345))

            patched.assert_not_called()
        finally:
            server.server_close()


class ControlPlaneStateTests(unittest.TestCase):
    """Exercise the testable control-plane runtime logic directly."""

    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[2]
        self.state = ControlPlaneState(self.project_root)

    def _wait_for(self, predicate: Callable[[], bool], timeout_seconds: float = 2.0) -> None:
        """Poll until a background operation finishes or the test should fail."""

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if predicate():
                return
            time.sleep(0.02)
        self.fail("Timed out waiting for background control-plane work to finish.")

    def test_start_job_captures_output_and_success_status(self) -> None:
        """Background jobs should record output and successful completion."""

        fake_process = _FakeProcess(lines=["hello\n", "world\n"], returncode=0)
        with mock.patch("control_plane.runtime.subprocess.Popen", return_value=fake_process):
            job = self.state._start_job("bootstrap", ["powershell"], self.project_root)

        self._wait_for(lambda: job.status == "succeeded")
        self.assertEqual(job.exit_code, 0)
        self.assertEqual(job.output_lines, ["hello", "world"])

    def test_start_job_handles_process_start_failure(self) -> None:
        """Job startup failures should be captured instead of crashing the control plane."""

        with mock.patch("control_plane.runtime.subprocess.Popen", side_effect=OSError("boom")):
            job = self.state._start_job("bootstrap", ["powershell"], self.project_root)

        self._wait_for(lambda: job.status == "failed")
        self.assertEqual(job.exit_code, -1)
        self.assertIn("Failed to start process", job.output_lines[0])

    def test_start_job_helper_methods_delegate_to_shared_runner(self) -> None:
        """The public job helper methods should all route through _start_job."""

        with mock.patch.object(
            self.state,
            "_start_job",
            return_value=JobRecord("job-1", "kind", [], "."),
        ) as patched:
            self.state.start_bootstrap_job()
            self.state.start_build_job("Release")
            self.state.start_test_job("Debug")
            self.state.start_format_job()
            self.state.start_code_docs_job()

        self.assertEqual(patched.call_count, 5)

    def test_start_app_tracks_output_and_shutdown(self) -> None:
        """The managed app process should update status, capture output, and stop cleanly."""

        fake_process = _FakeProcess(lines=["booting\n"], pid=2468, returncode=0)
        with mock.patch("control_plane.runtime.subprocess.Popen", return_value=fake_process):
            record = self.state.start_app(
                "Debug",
                "127.0.0.1",
                8080,
                "default",
                "",
                1280,
                720,
                60,
                "Halcyn",
            )

        self.assertEqual(record.pid, 2468)
        self.assertIn("-ApiHost", record.command)
        self._wait_for(lambda: self.state.app_status()["status"] == "stopped")
        self.assertIn("booting", self.state.app_status()["output_lines"])

    def test_start_app_uses_api_host_argument_name(self) -> None:
        """The control plane should call run.ps1 with the current ApiHost parameter name."""

        fake_process = _FakeProcess(
            lines=["Starting Y:\\Halcyn\\build\\debug\\halcyn_app.exe\n"],
            returncode=0,
        )
        with mock.patch("control_plane.runtime.subprocess.Popen", return_value=fake_process):
            record = self.state.start_app(
                "Debug",
                "127.0.0.1",
                8080,
                "default",
                "",
                1280,
                720,
                60,
                "Halcyn",
            )

        self.assertIn("-ApiHost", record.command)
        self.assertNotIn("-Host", record.command)
        self._wait_for(lambda: self.state.app_status()["status"] == "stopped")

    def test_start_app_reports_launch_in_progress_when_wrapper_is_still_building(self) -> None:
        """A second launch attempt should explain that the app is still starting up."""

        self.state._app_process = cast(Any, _LiveProcess())
        self.state._app_record = ManagedProcess(
            name="halcyn_app",
            command=["powershell"],
            working_directory=str(self.project_root),
            status="starting",
        )

        with self.assertRaises(RuntimeError) as context:
            self.state.start_app(
                "Debug",
                "127.0.0.1",
                8080,
                "default",
                "",
                1280,
                720,
                60,
                "Halcyn",
            )

        self.assertIn("launch is already in progress", str(context.exception))

    def test_stop_app_requests_taskkill_for_running_process(self) -> None:
        """Stopping the app should send a taskkill request for the live process tree."""

        process = mock.Mock()
        process.pid = 777
        process.poll.return_value = None
        self.state._app_process = process

        with mock.patch("control_plane.runtime.subprocess.run") as patched_run:
            record = self.state.stop_app()

        patched_run.assert_called_once()
        self.assertEqual(record.status, "stopping")

    def test_stop_app_is_idempotent_when_nothing_is_running(self) -> None:
        """Stopping an already stopped app should not fail or fabricate a process."""

        record = self.state.stop_app()
        self.assertEqual(record.status, "stopped")
        self.assertIsNone(record.pid)

    def test_app_status_reports_live_process(self) -> None:
        """app_status should expose whether the managed process is currently alive."""

        process = mock.Mock()
        process.poll.return_value = None
        self.state._app_process = process
        self.state._app_record = ManagedProcess(
            name="halcyn_app",
            command=[],
            working_directory=".",
            status="running",
        )

        payload = self.state.app_status()
        self.assertTrue(payload["is_alive"])
        self.assertEqual(payload["status"], "running")

    def test_available_tools_prefers_vswhere_when_available(self) -> None:
        """Tool discovery should honor a vswhere-detected Visual Studio install."""

        def fake_run(args: list[str], **_: object) -> mock.Mock:
            if "vswhere.exe" in args[0]:
                return mock.Mock(returncode=0, stdout="D:\\VS\n")
            return mock.Mock(returncode=0, stdout="")

        def fake_exists(path: Path) -> bool:
            path_text = str(path)
            return "vswhere.exe" in path_text or "D:\\VS\\Common7\\Tools\\VsDevCmd.bat" in path_text

        with mock.patch("control_plane.runtime.shutil.which", return_value="python"):
            with mock.patch("control_plane.runtime.subprocess.run", side_effect=fake_run):
                with mock.patch("pathlib.Path.exists", fake_exists):
                    tools = self.state.available_tools()

        self.assertTrue(tools["visual_studio_2022"]["available"])
        self.assertIn("VsDevCmd.bat", tools["visual_studio_2022"]["path"])

    def test_available_tools_reports_visual_studio_compiler_when_cl_is_not_on_path(self) -> None:
        """The tool summary should still surface cl.exe from a Visual Studio install."""

        def fake_run(args: list[str], **_: object) -> mock.Mock:
            if "vswhere.exe" in args[0]:
                return mock.Mock(returncode=0, stdout="D:\\VS\n")
            return mock.Mock(returncode=0, stdout="")

        def fake_exists(path: Path) -> bool:
            path_text = str(path)
            return any(
                marker in path_text
                for marker in [
                    "vswhere.exe",
                    "D:\\VS\\Common7\\Tools\\VsDevCmd.bat",
                    "D:\\VS\\VC\\Tools\\MSVC\\14.44.35207\\bin\\Hostx64\\x64\\cl.exe",
                ]
            )

        with mock.patch(
            "control_plane.runtime.shutil.which",
            side_effect=lambda command: "python" if command == "python" else None,
        ):
            with mock.patch("control_plane.runtime.subprocess.run", side_effect=fake_run):
                with mock.patch("pathlib.Path.exists", fake_exists):
                    with mock.patch(
                        "pathlib.Path.glob",
                        return_value=[Path(r"D:\VS\VC\Tools\MSVC\14.44.35207")],
                    ):
                        tools = self.state.available_tools()

        self.assertTrue(tools["cl"]["available"])
        self.assertTrue(tools["cl"]["path"].endswith("cl.exe"))

    def test_run_api_request_reports_connection_errors_cleanly(self) -> None:
        """API proxy failures should return a browser-friendly error payload instead of raising."""

        response = self.state.run_api_request(
            host="127.0.0.1",
            port=65534,
            method="GET",
            path="/api/v1/health",
            body="",
            content_type="application/json",
        )

        self.assertFalse(response["ok"])
        self.assertEqual(response["status"], 0)

    def test_run_api_request_successfully_returns_response_details(self) -> None:
        """Successful proxied requests should include status, headers, and body text."""

        server = ThreadingHTTPServer(("127.0.0.1", 0), _OkHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            response = self.state.run_api_request(
                host="127.0.0.1",
                port=server.server_address[1],
                method="GET",
                path="/health",
                body="",
                content_type="application/json",
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertTrue(response["ok"])
        self.assertEqual(response["status"], 200)
        self.assertIn('"status":"ok"', response["body"])

    def test_run_smoke_checks_aggregates_results(self) -> None:
        """Smoke checks should report failure when any required probe fails."""

        # The smoke helper runs three probes. One failing probe should force the
        # overall result to fail so the dashboard cannot show a false green.
        responses = [
            {"status": 200},
            {"status": 200},
            {"status": 500},
        ]
        with mock.patch.object(self.state, "run_api_request", side_effect=responses):
            result = self.state.run_smoke_checks("127.0.0.1", 8080)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["checks"]), 3)

    def test_summary_includes_expected_sections(self) -> None:
        """summary should combine diagnostics, jobs, logs, docs, and app state."""

        payload = self.state.summary()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("docs", payload)
        self.assertIn("clientStudio", payload["docs"])
        self.assertIn("generatedCodeDocs", payload["docs"])
        self.assertIn("tools", payload)


if __name__ == "__main__":
    unittest.main()
