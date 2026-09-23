# BugHound Mini Model Card (Reflection)

Fill this out after you run BugHound in **both** modes (Heuristic and Gemini).

---

## 1) What is this system?

**Name:** BugHound  
**Purpose:** Analyze a Python snippet, propose a fix, and run reliability checks before suggesting whether the fix should be auto-applied.

**Intended users:** Students learning agentic workflows and AI reliability concepts.

---

## 2) How does it work?

BugHound runs a five-step agentic loop:

1. **PLAN** — Logs that a scan+fix workflow is starting. No real decision-making yet; just sets up the agent state.
2. **ANALYZE** — Detects issues in the code. In heuristic mode this is three regex/string checks (bare `except:`, `print(`, `TODO`). In Gemini mode the full code is sent to the LLM with a structured prompt asking for a JSON array of issues; if the response isn't valid JSON the agent silently falls back to heuristics.
3. **ACT** — Proposes a rewrite. Heuristics do mechanical substitutions (swap `except:`, prepend `import logging`, replace `print(`). Gemini rewrites the whole snippet guided by the detected issue list.
4. **TEST** — `assess_risk` scores the proposed fix (0–100) by deducting points for issue severity and structural changes (code shrinkage, missing `return` statements, modified bare `except`). Score ≥ 75 → low risk; ≥ 40 → medium; < 40 → high.
5. **REFLECT** — If risk level is `"low"`, the agent recommends auto-applying the fix. Otherwise it flags the fix for human review. The fix is never actually applied by the agent itself.

---

## 3) Inputs and outputs

**Inputs tested:**

| File | Shape |
|---|---|
| `cleanish.py` | Short 5-line module-level function using `logging`, no obvious problems |
| `flaky_try_except.py` | 9-line function with a bare `except:` and an unclosed file handle |
| `mixed_issues.py` | 9-line function mixing `print`, a bare `except:`, and a `TODO` comment |
| `print_spam.py` | 7-line function with multiple `print` calls, no exception handling |

**Outputs observed:**

- *Heuristic mode* detected: bare `except:` (High), `print(` usage (Low), `TODO` comments (Medium) — only when those exact string patterns were present.
- *Gemini mode* detected: all of the above plus missing `logging.basicConfig()` configuration, missing docstrings, missing type hints, and semantic issues like silently swallowing `ZeroDivisionError`.
- Fixes ranged from prepending `import logging` and swapping `except:` (heuristic) to full rewrites with docstrings, type annotations, and `logging.basicConfig` calls (Gemini).
- Risk scores: `cleanish.py` scored 100/low in heuristic mode (no issues found) and 70/medium in Gemini mode (3 issues including one Medium).

---

## 4) Reliability and safety rules

**Rule 1 — Return statement removal check**
`assess_risk` checks whether `return` appears in the original code but not in the fixed code, and deducts 30 points if so.
*Why it matters:* A fix that accidentally drops a return statement changes the function's output from a value to `None`, which is a silent behavioral regression.
*False positive:* A fix that refactors a function to use `yield` instead of `return` would trigger this check unfairly, even though the behavior is intentional.
*False negative:* It only checks whether the string `"return"` appears anywhere in the fixed code. A fix that removes one of several `return` branches (e.g., removes an early-return guard) would not be caught.

**Rule 2 — Code length shrinkage check**
If the fixed code has fewer than 50% of the lines of the original, 20 points are deducted.
*Why it matters:* Dramatically shorter output is a signal that the LLM may have truncated its response or hallucinated a minimal stub rather than a real rewrite.
*False positive:* A legitimate refactor that collapses a verbose `if/else` chain into a one-liner list comprehension could trip this threshold even when the fix is correct.
*False negative:* An LLM that rewrites a 20-line function into a 15-line version with subtly wrong logic would score no penalty here, even if the logic change is dangerous.

---

## 5) Observed failure modes

**1. BugHound missed an issue it should have caught — `cleanish.py` in heuristic mode**

```python
import logging

def add(a, b):
    logging.info("Adding two numbers")
    return a + b
```

The heuristic analyzer found **zero issues** and originally scored the code 100/low, recommending auto-apply of no changes — a false sense of confidence that the code was "safe to auto-fix" when there was nothing to fix. (This is the exact failure the Part 4 guardrail below now blocks: with no issues or an unchanged fix, `should_autofix` is forced to `False`.) The agent trace also revealed a second concern: when the LLM returns a non-JSON response, the agent silently falls back to heuristics without signaling that its analyzer degraded to a less capable fallback.

**2. BugHound suggested a fix that felt unnecessary — `cleanish.py` in Gemini mode**

```python
import logging

def add(a, b):
    logging.info("Adding two numbers")
    return a + b
```

Gemini flagged missing type hints and a missing docstring as issues (Low severity), then rewrote the function with full `Args`/`Returns` docstring blocks, `int` type annotations, and a `logging.basicConfig()` call at module level. This tripled the line count of a 5-line file, changed the function signature, and added module-level side effects — none of which was flagged by the risk assessor because the `return` statement was preserved and the code didn't shrink.

---

## 6) Heuristic vs Gemini comparison

| Dimension | Heuristic mode | Gemini mode |
|---|---|---|
| Issues in `cleanish.py` | 0 (silent fallback after unparseable mock output) | 3 (missing logging config, missing docstring, missing type hints) |
| Issues in `flaky_try_except.py` | 1 — bare `except:` (High) | Bare `except:` + unclosed file handle + no logging config |
| Issues in `mixed_issues.py` | 3 — `print(`, bare `except:`, `TODO` | Same 3 plus semantic note about silently returning 0 on division error |
| Fix style | Mechanical substitutions only; preserves structure | Full rewrite with documentation, type hints, and configuration |
| Risk scorer agreement | Agreed with intuition — no issues → low risk | Partially agreed; scored 70/medium for `cleanish.py`, which felt overly cautious for style-only issues |

**Key insight:** Gemini is significantly more analytic — it reasons about intent, style, and runtime behavior, not just surface patterns. However, it also proposes larger, more invasive changes, which the risk scorer does not adequately penalize since it only checks structural signals (line count, `return` presence) and not semantic change magnitude.

---

## 7) Human-in-the-loop decision

**Scenario:** Gemini rewrites a function and changes its signature — adding or removing parameters, adding type annotations that narrow accepted types, or renaming arguments.

- **Trigger:** After `propose_fix`, diff the original and fixed function signatures using a regex like `r"def \w+\("`. If any function signature changed, block auto-fix regardless of score.
- **Where to implement:** In `assess_risk` (`reliability/risk_assessor.py`) as a new structural check, so it applies regardless of whether the fixer was the LLM or heuristics.
- **Message to show:** *"Fix modifies one or more function signatures. This may break existing callers. Human review required before applying."*

---

## 8) Improvement idea

**Add a "fallback transparency" flag to the output.**

Currently, when the LLM returns unparseable output the agent silently falls back to heuristics and the user sees "Found 0 issues" with no indication that the LLM failed. This creates false confidence — the cleanest-looking result (`cleanish.py` scoring 100/low) was actually produced by a degraded analyzer.

The fix is small: add a boolean field `"used_fallback": true/false` to the `analyze` return value, thread it through the result dict, and display a visible warning in the UI when it is `true` — e.g., *"LLM output was not valid JSON — results reflect heuristic analysis only, not LLM analysis."*

This requires no new ML, no new rules, and no restructuring. It directly addresses the most dangerous failure mode observed: an analyzer that looks identical to a working one but is running in a degraded state.

---

## 9) Design changes I made (one per part)

Each part of this tinker required one deliberate design decision. Here is what I
changed, where, and the before/after effect I verified.

**Part 2 — Reliability: validate LLM severity against a schema.**
`bughound_agent._normalize_issues` previously accepted whatever `severity` the
model returned (defaulting off-schema values to `"Unknown"`), which could feed
garbage into the risk scorer that keys on `Low/Medium/High`. I changed it to
validate against an allowed set and coerce off-schema values (e.g. `"critical"`,
`"5"`) to `"Medium"` with a logged trace entry.
*Before:* `severity="critical"` passed through unchanged.
*After:* coerced to `"Medium"` + `Off-schema severity 'critical' ... coercing` log.

**Part 3 — Safety: add a large-diff caution signal.**
`reliability/risk_assessor.py` had no penalty for a fix that rewrites most of a
file — it only checked shrinkage, removed returns, and new imports. I added a
signal: if the net line delta exceeds 50% of the original size, deduct 25 points.
*Before:* a low-severity issue + large rewrite scored 85 → low → `should_autofix=True`.
*After:* same input scores 60 → medium → `should_autofix=False` (defers to human).

**Part 4 — Guardrail: never auto-fix when there is nothing to fix.**
A clean file (0 issues) scored 100 → low → `should_autofix=True`, greenlighting a
non-existent change. I added a rule in `assess_risk`: if `issues` is empty OR the
fixed code equals the original, force `should_autofix=False`.
*Before:* `cleanish.py` → `should_autofix=True`.
*After:* `should_autofix=False` with reason "nothing to change." Backed by two
offline tests (`test_clean_file_with_no_issues_is_not_auto_fixed`,
`test_comments_only_file_is_not_auto_fixed`) that fail without the guardrail and
pass with it. Full suite: 11 tests passing.

**Environment note:** the starter `requirements.txt` listed `google-generativeai`,
but `llm_client.py` imports the newer `google-genai` SDK (`from google import genai`),
so Gemini mode was broken out of the box until `google-genai` was installed.
