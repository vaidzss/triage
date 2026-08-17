# test_graph_single_bug.py - Phase 2 checkpoint: the Patcher<->Tester graph
# should converge to a passing patch on a known, simple bug.
# Requires Docker Desktop running and Ollama serving a tool-capable model
# (see src/triage/config.py).

from pathlib import Path

from triage import graph

FIXTURES = Path(__file__).parent / "fixtures"


def test_graph_converges_on_known_bug():
    result = graph.run_repair(
        repo_path=str(FIXTURES / "broken_repo"),
        target_file="calc.py",
        issue_description=(
            "test_calc.py::test_add fails: add(2, 3) is expected to equal 5 "
            "but the current implementation of add() in calc.py returns the "
            "wrong value."
        ),
    )

    assert result["status"] == "passed", result["history"]
    assert result["last_result"]["passed"] is True
