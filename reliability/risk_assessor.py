from typing import Dict, List


def assess_risk(
    original_code: str,
    fixed_code: str,
    issues: List[Dict[str, str]],
) -> Dict[str, object]:
    """
    Simple, explicit risk assessment used as a guardrail layer.

    Returns a dict with:
    - score: int from 0 to 100
    - level: "low" | "medium" | "high"
    - reasons: list of strings explaining deductions
    - should_autofix: bool
    """

    reasons: List[str] = []
    score = 100

    if not fixed_code.strip():
        return {
            "score": 0,
            "level": "high",
            "reasons": ["No fix was produced."],
            "should_autofix": False,
        }

    original_lines = original_code.strip().splitlines()
    fixed_lines = fixed_code.strip().splitlines()

    # ----------------------------
    # Issue severity based risk
    # ----------------------------
    for issue in issues:
        severity = str(issue.get("severity", "")).lower()

        if severity == "high":
            score -= 40
            reasons.append("High severity issue detected.")
        elif severity == "medium":
            score -= 20
            reasons.append("Medium severity issue detected.")
        elif severity == "low":
            score -= 5
            reasons.append("Low severity issue detected.")

    # ----------------------------
    # Structural change checks
    # ----------------------------
    if len(fixed_lines) < len(original_lines) * 0.5:
        score -= 20
        reasons.append("Fixed code is much shorter than original.")

    # ----------------------------
    # NEW risk signal (Part 3): large diffs are riskier to auto-apply.
    # Even a "low severity" fix that rewrites most of the file changes a lot
    # of behavior surface, so a big net line change should push us toward
    # caution / human review rather than silent auto-fix.
    # ----------------------------
    line_delta = abs(len(fixed_lines) - len(original_lines))
    original_len = max(1, len(original_lines))
    if line_delta > original_len * 0.5:
        score -= 25
        reasons.append(
            f"Large change: {line_delta} lines differ from a "
            f"{original_len}-line original (big diff, review recommended)."
        )

    if "return" in original_code and "return" not in fixed_code:
        score -= 30
        reasons.append("Return statements may have been removed.")

    if "except:" in original_code and "except:" not in fixed_code:
        # This is usually good, but still risky.
        score -= 5
        reasons.append("Bare except was modified, verify correctness.")

    original_imports = {
        line.strip()
        for line in original_lines
        if line.strip().startswith("import ") or line.strip().startswith("from ")
    }
    fixed_imports = {
        line.strip()
        for line in fixed_lines
        if line.strip().startswith("import ") or line.strip().startswith("from ")
    }
    new_imports = fixed_imports - original_imports
    if new_imports:
        score -= 10
        reasons.append("Fix introduces new imports not present in original.")

    # ----------------------------
    # Clamp score
    # ----------------------------
    score = max(0, min(100, score))

    # ----------------------------
    # Risk level
    # ----------------------------
    if score >= 75:
        level = "low"
    elif score >= 40:
        level = "medium"
    else:
        level = "high"

    # ----------------------------
    # Auto-fix policy
    # ----------------------------
    should_autofix = level == "low"

    # GUARDRAIL (Part 4): never recommend auto-applying a "fix" when there are
    # no issues, or when the fixed code is identical to the original. Without
    # this, a clean file (0 issues) scores 100 -> "low" -> should_autofix=True,
    # which greenlights applying a change that does not exist. Auto-fix should
    # only be offered when there is an actual, non-empty change to apply.
    no_issues = len(issues) == 0
    no_change = fixed_code.strip() == original_code.strip()
    if no_issues or no_change:
        should_autofix = False
        reasons.append(
            "No auto-fix offered: nothing to change "
            "(no issues found or fix is identical to the original)."
        )

    if not reasons:
        reasons.append("No significant risks detected.")

    return {
        "score": score,
        "level": level,
        "reasons": reasons,
        "should_autofix": should_autofix,
    }
