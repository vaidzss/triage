# sandbox.py - Docker-based Test Verification agent backend.
#
# Copies a repo, optionally applies a unified diff via `git apply`, then runs
# an install+test command inside an ephemeral, disposable container and
# returns a structured pass/fail result. `git apply` failures (malformed
# diffs) are reported distinctly from test failures so callers can re-prompt
# the Patch Engineer for reformatting without burning a test-run retry.

import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

import docker
from docker.errors import APIError

from . import config


class PatchApplyError(Exception):
    """Raised when `git apply` rejects the diff."""


def _apply_patch(repo_dir: Path, patch: str) -> None:
    patch_file = repo_dir / f".triage-patch-{uuid.uuid4().hex}.diff"
    # newline="" prevents Path.write_text() from translating \n -> \r\n on
    # Windows, which would corrupt the diff and make git apply reject it.
    patch_file.write_text(patch, encoding="utf-8", newline="")
    try:
        result = subprocess.run(
            ["git", "apply", "--whitespace=fix", patch_file.name],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise PatchApplyError(result.stderr.strip() or result.stdout.strip())
    finally:
        patch_file.unlink(missing_ok=True)


def run_tests(
    repo_path: str,
    patch: Optional[str] = None,
    test_command: str = "pytest -q",
    install_command: Optional[str] = "pip install -q -r requirements.txt",
    base_image: Optional[str] = None,
    timeout: Optional[int] = None,
) -> dict:
    """Run a repo's test suite (optionally after applying `patch`) in a fresh,
    disposable Docker container.

    Returns:
      {
        "patch_applied": bool,
        "patch_error": str | None,     # set (only) when `git apply` failed
        "passed": bool | None,          # None if the patch failed to apply
        "stdout": str,          # merged stdout+stderr (container.logs() demux
        "stderr": str,          #   isn't supported by this docker-py version)
        "exit_code": int | None,
        "duration_seconds": float,
      }
    """
    base_image = base_image or config.SANDBOX_BASE_IMAGE
    timeout = timeout or config.SANDBOX_TIMEOUT_SECONDS

    work_dir = Path(tempfile.mkdtemp(prefix="triage-sandbox-"))
    try:
        sandbox_repo = work_dir / "repo"
        shutil.copytree(repo_path, sandbox_repo)

        if patch:
            try:
                _apply_patch(sandbox_repo, patch)
            except PatchApplyError as exc:
                return {
                    "patch_applied": False,
                    "patch_error": str(exc),
                    "passed": None,
                    "stdout": "",
                    "stderr": "",
                    "exit_code": None,
                    "duration_seconds": 0.0,
                }

        command_parts = [install_command] if install_command else []
        command_parts.append(test_command)
        full_command = " && ".join(command_parts)

        client = docker.from_env()
        start = time.monotonic()
        container = client.containers.run(
            base_image,
            command=["sh", "-c", full_command],
            working_dir="/workspace",
            volumes={str(sandbox_repo): {"bind": "/workspace", "mode": "rw"}},
            detach=True,
        )
        try:
            wait_result = container.wait(timeout=timeout)
        except Exception as exc:
            try:
                container.kill()
            except APIError:
                pass
            exit_code = None
            stdout = ""
            stderr = f"sandbox timed out after {timeout}s or errored: {exc}"
        else:
            exit_code = wait_result.get("StatusCode")
            # This docker-py version's Container.logs() has no `demux` support
            # (it forwards straight to the low-level API, which doesn't accept
            # it), so stdout/stderr come back merged into one stream.
            logs = container.logs(stdout=True, stderr=True)
            stdout = logs.decode("utf-8", errors="replace")
            stderr = ""
        duration = time.monotonic() - start
        try:
            container.remove(force=True)
        except APIError:
            pass

        return {
            "patch_applied": bool(patch),
            "patch_error": None,
            "passed": exit_code == 0,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "duration_seconds": duration,
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
