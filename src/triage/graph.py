# graph.py - LangGraph state machine wiring Patcher <-> Tester into a bounded
# retry loop.
#
# Two separate retry budgets, mirroring the blueprint's distinction between a
# malformed diff (re-prompt for formatting, cheap) and a diff that applies
# but doesn't fix the bug (re-prompt with test failure output, the real
# retry loop):
#   - format_retry_count / max_format_retries: `git apply` rejected the diff.
#   - retry_count / max_retries: the diff applied but tests still failed.

import difflib
from pathlib import Path
from typing import Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from . import config, patcher, sandbox


def _unified_diff(target_file: str, old_contents: str, new_contents: str) -> str:
    # Models often drop the trailing newline when asked to reproduce a whole
    # file. difflib then emits a diff line with no line terminator, which
    # git apply rejects as corrupt unless paired with a `\ No newline at end
    # of file` marker (not worth implementing) - so just match the
    # original's convention instead.
    if old_contents.endswith("\n") and not new_contents.endswith("\n"):
        new_contents += "\n"
    diff_lines = difflib.unified_diff(
        old_contents.splitlines(keepends=True),
        new_contents.splitlines(keepends=True),
        fromfile=f"a/{target_file}",
        tofile=f"b/{target_file}",
    )
    return "".join(diff_lines)


class RepairState(TypedDict):
    repo_path: str
    target_file: str
    issue_description: str
    current_diff: Optional[str]
    last_attempt_contents: Optional[str]
    last_result: Optional[dict]
    retry_count: int
    format_retry_count: int
    max_retries: int
    max_format_retries: int
    history: list
    status: str  # "in_progress" | "passed" | "failed"


def patcher_node(state: RepairState) -> dict:
    file_path = Path(state["repo_path"]) / state["target_file"]
    original_contents = file_path.read_text(encoding="utf-8")

    last_attempt = None
    last_error = None
    last_result = state.get("last_result")
    if last_result is not None:
        last_attempt = state["last_attempt_contents"]
        last_error = last_result.get("patch_error") or last_result.get("stdout")

    new_contents = patcher.propose_patch(
        target_file=state["target_file"],
        file_contents=original_contents,
        issue_description=state["issue_description"],
        last_attempt=last_attempt,
        last_error=last_error,
    )
    diff = _unified_diff(state["target_file"], original_contents, new_contents)
    return {"current_diff": diff, "last_attempt_contents": new_contents}


def tester_node(state: RepairState) -> dict:
    result = sandbox.run_tests(state["repo_path"], patch=state["current_diff"])
    history_entry = {"diff": state["current_diff"], "result": result}
    return {
        "last_result": result,
        "history": state["history"] + [history_entry],
    }


def route_after_test(state: RepairState) -> str:
    result = state["last_result"]
    if result["patch_error"] is not None:
        if state["format_retry_count"] < state["max_format_retries"]:
            return "retry_format"
        return "give_up"
    if result["passed"]:
        return "done"
    if state["retry_count"] < state["max_retries"]:
        return "retry_test"
    return "give_up"


def _bump_format_retry(state: RepairState) -> dict:
    return {"format_retry_count": state["format_retry_count"] + 1}


def _bump_retry(state: RepairState) -> dict:
    return {"retry_count": state["retry_count"] + 1}


def _mark_done(state: RepairState) -> dict:
    return {"status": "passed"}


def _mark_failed(state: RepairState) -> dict:
    return {"status": "failed"}


def build_graph():
    graph = StateGraph(RepairState)
    graph.add_node("patcher", patcher_node)
    graph.add_node("tester", tester_node)
    graph.add_node("bump_format_retry", _bump_format_retry)
    graph.add_node("bump_retry", _bump_retry)
    graph.add_node("mark_done", _mark_done)
    graph.add_node("mark_failed", _mark_failed)

    graph.add_edge(START, "patcher")
    graph.add_edge("patcher", "tester")
    graph.add_conditional_edges(
        "tester",
        route_after_test,
        {
            "retry_format": "bump_format_retry",
            "retry_test": "bump_retry",
            "done": "mark_done",
            "give_up": "mark_failed",
        },
    )
    graph.add_edge("bump_format_retry", "patcher")
    graph.add_edge("bump_retry", "patcher")
    graph.add_edge("mark_done", END)
    graph.add_edge("mark_failed", END)
    return graph.compile()


def run_repair(
    repo_path: str,
    target_file: str,
    issue_description: str,
    max_retries: Optional[int] = None,
    max_format_retries: int = 2,
) -> RepairState:
    app = build_graph()
    initial_state: RepairState = {
        "repo_path": repo_path,
        "target_file": target_file,
        "issue_description": issue_description,
        "current_diff": None,
        "last_attempt_contents": None,
        "last_result": None,
        "retry_count": 0,
        "format_retry_count": 0,
        "max_retries": max_retries if max_retries is not None else config.MAX_RETRIES,
        "max_format_retries": max_format_retries,
        "history": [],
        "status": "in_progress",
    }
    return app.invoke(initial_state)
