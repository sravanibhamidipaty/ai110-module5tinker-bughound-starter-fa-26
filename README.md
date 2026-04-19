# 🐶 BugHound

BugHound is a small, agent-style debugging tool. It analyzes a Python code snippet, proposes a fix, and runs basic reliability checks before deciding whether the fix is safe to apply automatically.

---

## What BugHound Does

Given a short Python snippet, BugHound:

1. **Analyzes** the code for potential issues  
   - Uses heuristics in offline mode  
   - Uses Gemini when API access is enabled  

2. **Proposes a fix**  
   - Either heuristic-based or LLM-generated  
   - Attempts minimal, behavior-preserving changes  

3. **Assesses risk**  
   - Scores the fix  
   - Flags high-risk changes  
   - Decides whether the fix should be auto-applied or reviewed by a human  

4. **Shows its work**  
   - Displays detected issues  
   - Shows a diff between original and fixed code  
   - Logs each agent step

---

## Setup

### 1. Create a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# or
.venv\Scripts\activate      # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Running in Offline (Heuristic) Mode

No API key required.

```bash
streamlit run bughound_app.py
```

In the sidebar, select:

* **Model mode:** Heuristic only (no API)

This mode uses simple pattern-based rules and is useful for testing the workflow without network access.

---

## Running with Gemini

### 1. Set up your API key

Copy the example file:

```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key:

```text
GEMINI_API_KEY=your_real_key_here
```

### 2. Run the app

```bash
streamlit run bughound_app.py
```

In the sidebar, select:

* **Model mode:** Gemini (requires API key)
* Choose a Gemini model and temperature

BugHound will now use Gemini for analysis and fix generation, while still applying local reliability checks.

---

## Running Tests

Tests focus on **reliability logic** and **agent behavior**, not the UI.

```bash
pytest
```

You should see tests covering:

* Risk scoring and guardrails
* Heuristic fallbacks when LLM output is invalid
* End-to-end agent workflow shape

## TF Summary
The core concept students need to understand is how a multi-file agentic system divides responsibility like how bughound_agent.py decides what to do, risk_assessor.py decides whether it's safe to do it, and the prompts shape how the AI behaves and that reliability means the system behaves predictably even when the AI gives bad output, like logging a fallback instead of silently producing a wrong answer. Students are most likely to struggle with deciding what to change to make and why it helps. For example, knowing that adding a new import rule to risk_assessor.py matters because it catches over-editing, not just because it changes a number. The hardest part isn't writing the code; it's reasoning backwards from a failure like the agent auto-fixed something it shouldn't have to the right layer to fix it like risk asessor vs. agent workflow vs. prompt. AI assistance is most helpful for drafting boilerplate like test structure or regex patterns, but most misleading when it suggests changes that look correct like adding type hints without flagging that those changes alter the function's public interface. A guardrail, like refusing to auto-fix when new imports appear, is not about the AI refusing to answer but rather it is about the system refusing to act without human sign-off when a structural threshold is crossed. To guide a student without giving the answer, I would ask if this fix were merged automatically and a caller broke, which file would change so that can't happen again and how would you prove it works? That question forces them to connect the failure, the layer and the test together rather than seraching for a line to edit.