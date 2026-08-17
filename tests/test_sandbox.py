# test_sandbox.py - exercises sandbox.run_tests() against the fixture repos.
# Requires Docker Desktop's engine to be running.

from pathlib import Path

import pytest

from triage import sandbox

FIXTURES = Path(__file__).parent / "fixtures"


def test_passing_repo_reports_pass():
    result = sandbox.run_tests(str(FIXTURES / "passing_repo"))
    assert result["patch_applied"] is False
    assert result["patch_error"] is None
    assert result["passed"] is True
    assert result["exit_code"] == 0


def test_broken_repo_reports_fail():
    result = sandbox.run_tests(str(FIXTURES / "broken_repo"))
    assert result["passed"] is False
    assert result["exit_code"] != 0
    assert "assert" in result["stdout"].lower() or "failed" in result["stdout"].lower()


def test_broken_repo_passes_after_known_fix():
    patch = (FIXTURES / "broken_repo" / "fix.patch").read_text()
    result = sandbox.run_tests(str(FIXTURES / "broken_repo"), patch=patch)
    assert result["patch_applied"] is True
    assert result["patch_error"] is None
    assert result["passed"] is True


def test_malformed_patch_reports_patch_error_not_test_failure():
    bad_patch = "this is not a valid diff\n"
    result = sandbox.run_tests(str(FIXTURES / "broken_repo"), patch=bad_patch)
    assert result["patch_applied"] is False
    assert result["patch_error"] is not None
    assert result["passed"] is None
