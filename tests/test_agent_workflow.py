from bughound_agent import BugHoundAgent
from llm_client import MockClient


def test_workflow_runs_in_offline_mode_and_returns_shape():
    agent = BugHoundAgent(client=None)  # heuristic-only
    code = "def f():\n    print('hi')\n    return True\n"
    result = agent.run(code)

    assert isinstance(result, dict)
    assert "issues" in result
    assert "fixed_code" in result
    assert "risk" in result
    assert "logs" in result

    assert isinstance(result["issues"], list)
    assert isinstance(result["fixed_code"], str)
    assert isinstance(result["risk"], dict)
    assert isinstance(result["logs"], list)
    assert len(result["logs"]) > 0


def test_offline_mode_detects_print_issue():
    agent = BugHoundAgent(client=None)
    code = "def f():\n    print('hi')\n    return True\n"
    result = agent.run(code)

    assert any(issue.get("type") == "Code Quality" for issue in result["issues"])


def test_offline_mode_proposes_logging_fix_for_print():
    agent = BugHoundAgent(client=None)
    code = "def f():\n    print('hi')\n    return True\n"
    result = agent.run(code)

    fixed = result["fixed_code"]
    assert "logging" in fixed
    assert "logging.info(" in fixed


def test_mock_client_forces_llm_fallback_to_heuristics_for_analysis():
    # MockClient returns non-JSON for analyzer prompts, so agent should fall back.
    agent = BugHoundAgent(client=MockClient())
    code = "def f():\n    print('hi')\n    return True\n"
    result = agent.run(code)

    assert any(issue.get("type") == "Code Quality" for issue in result["issues"])
    # Ensure we logged the fallback path
    assert any("Falling back to heuristics" in entry.get("message", "") for entry in result["logs"])


def test_clean_file_with_no_issues_is_not_auto_fixed():
    """
    Guardrail (Part 4): a file with no detectable issues must NOT be flagged
    as safe to auto-apply a fix. Before the guardrail, 0 issues -> score 100
    -> level "low" -> should_autofix=True, which greenlit a non-existent fix.
    Runs fully offline (client=None), asserts a DECISION.
    """
    agent = BugHoundAgent(client=None)
    clean_code = "import logging\n\ndef add(a, b):\n    logging.info('adding')\n    return a + b\n"
    result = agent.run(clean_code)

    assert result["issues"] == []
    # The fix should be a no-op (identical to input)...
    assert result["fixed_code"].strip() == clean_code.strip()
    # ...and the agent must NOT recommend auto-applying it.
    assert result["risk"]["should_autofix"] is False


def test_comments_only_file_is_not_auto_fixed():
    """A comments-only file has no issues and must not be auto-fixed."""
    agent = BugHoundAgent(client=None)
    result = agent.run("# just a comment\n# another comment\n")

    assert result["issues"] == []
    assert result["risk"]["should_autofix"] is False
