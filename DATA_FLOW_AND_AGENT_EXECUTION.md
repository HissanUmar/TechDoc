# Data Flow & Agent Execution in the Agentic Framework

## Overview

Your framework orchestrates multiple AI agents to incrementally analyze and refine a user's problem statement into actionable requirements, architecture, security analysis, and a final deliverable document. The key insight is understanding **how data flows between agents** and **why agents weren't executing previously**.

---

## 1. Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER INPUT (Streamlit)                          │
│  problem_statement: "Build a web app for a consulting team..."          │
└─────────────┬───────────────────────────────────────────────────────────┘
              │
              ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                 initial_context (Dict[str, Any])                         │
│  {                                                                      │
│    "problem_statement": "Build a web app...",                           │
│    "coverage_threshold": 80,                                            │
│    "clarification_answers": {},  # Populated after user answers        │
│    ...                                                                  │
│  }                                                                      │
└─────────────┬───────────────────────────────────────────────────────────┘
              │
              ↓
    supervisor.run_adaptive_workflow(initial_context, progress_callback)
              │
              ├─────────────────────────────────────────────────────────────┐
              │                                                             │
              ↓                                                             │
    ┌──────────────────────────────────────────────────────┐               │
    │   STEP 1: PLANNER AGENT (bootstrap orchestration)   │               │
    ├──────────────────────────────────────────────────────┤               │
    │ Input: {goal, context, available_agents}             │               │
    │ - goal: problem_statement                            │               │
    │ - context: initial_context (full state)              │               │
    │ - available_agents: ["architecture", "security",     │               │
    │    "performance", "documentation"]                   │               │
    │                                                      │               │
    │ Processing:                                          │               │
    │ - Determines execution order of agents               │               │
    │ - Returns: plan, next_agent, dependencies            │               │
    │                                                      │               │
    │ Output: results["planner"] = {                        │               │
    │   "plan": ["architecture", "security",               │               │
    │            "performance", "documentation"],          │               │
    │   "next_agent": "architecture",                      │               │
    │   "dependencies": [...],                             │               │
    │   "summary": "Plan generated..."                     │               │
    │ }                                                    │               │
    │                                                      │               │
    │ ⚠️ KEY FIX: Planner now receives available_agents   │               │
    │   and is constrained to return only valid names!     │               │
    └──────────────────────────────────────────────────────┘               │
              │                                                            │
              ↓                                                            │
    ┌──────────────────────────────────────────────────────┐               │
    │   STEP 2: REQUIREMENTS AGENT (hardcoded, always)    │               │
    ├──────────────────────────────────────────────────────┤               │
    │ Input: {                                             │               │
    │   "user_input": problem_statement,                   │               │
    │   "clarification_answers": {}  # Empty first time    │               │
    │ }                                                    │               │
    │                                                      │               │
    │ Processing:                                          │               │
    │ - Parses user requirements                           │               │
    │ - Identifies gaps and assumptions                    │               │
    │ - Calculates completeness_score (0-100)              │               │
    │ - Returns questions if score < 70                    │               │
    │                                                      │               │
    │ Output: results["requirements"] = {                  │               │
    │   "requirements": [...],                             │               │
    │   "assumptions": [...],                              │               │
    │   "questions": [...],                                │               │
    │   "completeness_score": 75,                          │               │
    │   "critical_gaps": [...],                            │               │
    │   "summary": "..."                                   │               │
    │ }                                                    │               │
    │                                                      │               │
    │ Branching:                                           │               │
    │ IF completeness_score < 70 AND no clarifications:    │               │
    │   → PAUSE workflow                                   │               │
    │   → Show clarification form to user                  │               │
    │   → Wait for user answers                            │               │
    │   → Resume with clarification_answers               │               │
    │ ELSE:                                                │               │
    │   → Continue to next_candidates from planner         │               │
    └──────────────────────────────────────────────────────┘               │
              │                                                            │
              ↓                                                            │
    ┌──────────────────────────────────────────────────────┐               │
    │   STEP 3: LOOP THROUGH PLANNER'S CANDIDATES         │               │
    │   (architecture, security, performance)              │               │
    ├──────────────────────────────────────────────────────┤               │
    │ For each candidate in next_candidates:               │               │
    │                                                      │               │
    │   ┌────────────────────────────────────────────┐    │               │
    │   │ ARCHITECTURE AGENT (if in plan)            │    │               │
    │   ├────────────────────────────────────────────┤    │               │
    │   │ Input: {                                   │    │               │
    │   │   "initial_context": initial_context,      │    │               │
    │   │   "workflow_results": {                     │    │               │
    │   │     "planner": {...},                       │    │               │
    │   │     "requirements": {...}                   │    │               │
    │   │   }                                         │    │               │
    │   │ }                                           │    │               │
    │   │                                             │    │               │
    │   │ Processing:                                 │    │               │
    │   │ - Receives requirements from workflow_results
    │   │ - Designs system architecture               │    │               │
    │   │ - Returns components, deployment model      │    │               │
    │   │                                             │    │               │
    │   │ Output: results["architecture"] = {         │    │               │
    │   │   "architecture_type": "microservices",     │    │               │
    │   │   "components": [...],                      │    │               │
    │   │   "deployment_model": "cloud",              │    │               │
    │   │   "tradeoffs": [...],                       │    │               │
    │   │   "summary": "..."                          │    │               │
    │   │ }                                           │    │               │
    │   └────────────────────────────────────────────┘    │               │
    │                        ↓                            │               │
    │   ┌────────────────────────────────────────────┐    │               │
    │   │ REVIEWER (monitors, does NOT gate)         │    │               │
    │   ├────────────────────────────────────────────┤    │               │
    │   │ Input: {                                   │    │               │
    │   │   "workflow_results": {                     │    │               │
    │   │     "planner": {...},                       │    │               │
    │   │     "requirements": {...},                  │    │               │
    │   │     "architecture": {...}                   │    │               │
    │   │   }                                         │    │               │
    │   │ }                                           │    │               │
    │   │                                             │    │               │
    │   │ Processing:                                 │    │               │
    │   │ - Reviews all accumulated results           │    │               │
    │   │ - Calculates coverage_score (0-100)         │    │               │
    │   │ - Identifies gaps                           │    │               │
    │   │ - Decides: "proceed" or "clarify"           │    │               │
    │   │                                             │    │               │
    │   │ Emits event: {                              │    │               │
    │   │   "event": "review_result",                 │    │               │
    │   │   "ready": false,                           │    │               │
    │   │   "decision": "proceed",                    │    │               │
    │   │   "coverage_score": 75,                     │    │               │
    │   │   "gaps": [...]                             │    │               │
    │   │ }                                           │    │               │
    │   │                                             │    │               │
    │   │ ⚠️ KEY FIX: Reviewer NO LONGER breaks loop  │    │               │
    │   │ Loop continues to security & performance    │    │               │
    │   └────────────────────────────────────────────┘    │               │
    │                                                      │               │
    │   ┌────────────────────────────────────────────┐    │               │
    │   │ SECURITY AGENT (if in plan)                │    │               │
    │   ├────────────────────────────────────────────┤    │               │
    │   │ Input: {                                   │    │               │
    │   │   "initial_context": initial_context,      │    │               │
    │   │   "workflow_results": {                     │    │               │
    │   │     "planner": {...},                       │    │               │
    │   │     "requirements": {...},                  │    │               │
    │   │     "architecture": {...}                   │    │               │
    │   │   }                                         │    │               │
    │   │ }                                           │    │               │
    │   │                                             │    │               │
    │   │ Processing:                                 │    │               │
    │   │ - Receives architecture from workflow_results
    │   │ - Analyzes security posture                 │    │               │
    │   │ - Returns vulnerabilities, recommendations  │    │               │
    │   │                                             │    │               │
    │   │ Output: results["security"] = {             │    │               │
    │   │   "security_score": 8,                      │    │               │
    │   │   "vulnerabilities": [...],                 │    │               │
    │   │   "recommendations": [...],                 │    │               │
    │   │   "compliant": true,                        │    │               │
    │   │   "summary": "..."                          │    │               │
    │   │ }                                           │    │               │
    │   └────────────────────────────────────────────┘    │               │
    │                        ↓                            │               │
    │   [REVIEWER again - still does NOT gate]            │               │
    │                                                      │               │
    │   ┌────────────────────────────────────────────┐    │               │
    │   │ PERFORMANCE AGENT (if in plan)             │    │               │
    │   ├────────────────────────────────────────────┤    │               │
    │   │ Input: {                                   │    │               │
    │   │   "initial_context": initial_context,      │    │               │
    │   │   "workflow_results": {                     │    │               │
    │   │     "planner": {...},                       │    │               │
    │   │     "requirements": {...},                  │    │               │
    │   │     "architecture": {...},                  │    │               │
    │   │     "security": {...}                       │    │               │
    │   │   }                                         │    │               │
    │   │ }                                           │    │               │
    │   │                                             │    │               │
    │   │ Processing:                                 │    │               │
    │   │ - Receives architecture from workflow_results
    │   │ - Analyzes performance bottlenecks          │    │               │
    │   │ - Returns latency, throughput, optimizations
    │   │                                             │    │               │
    │   │ Output: results["performance"] = {          │    │               │
    │   │   "estimated_latency_ms": 150,              │    │               │
    │   │   "throughput_rps": 1000,                   │    │               │
    │   │   "bottlenecks": [...],                     │    │               │
    │   │   "optimization_suggestions": [...],        │    │               │
    │   │   "summary": "..."                          │    │               │
    │   │ }                                           │    │               │
    │   └────────────────────────────────────────────┘    │               │
    │                                                      │               │
    │ [REVIEWER final check - still does NOT gate]        │               │
    │                                                      │               │
    │ Exit loop when next_candidates exhausted             │               │
    │ (Emit stop event: reason="plan_exhausted")           │               │
    └──────────────────────────────────────────────────────┘               │
              │                                                            │
              ↓                                                            │
    ┌──────────────────────────────────────────────────────┐               │
    │   STEP 4: DOCUMENTATION AGENT (final synthesis)     │               │
    ├──────────────────────────────────────────────────────┤               │
    │ Input: {                                             │               │
    │   "workflow_results": {                              │               │
    │     "planner": {...},                                │               │
    │     "requirements": {...},                           │               │
    │     "architecture": {...},          ← ALL agents!    │               │
    │     "security": {...},              ← Have run       │               │
    │     "performance": {...},           ← Now            │               │
    │     "reviewer": {...}                                │               │
    │   }                                                  │               │
    │ }                                                    │               │
    │                                                      │               │
    │ Processing:                                          │               │
    │ - Reads ALL results from workflow_results            │               │
    │ - Synthesizes problem statement + requirements       │               │
    │ - Includes architecture summary                      │               │
    │ - Includes security summary          ← NOW HAVE!     │               │
    │ - Includes performance summary        ← NOW HAVE!    │               │
    │ - Returns readable markdown document                 │               │
    │                                                      │               │
    │ Output: results["documentation"] = {                 │               │
    │   "documentation": "# Project Overview\n...",        │               │
    │   "sections": [...],                                 │               │
    │   "format": "markdown",                              │               │
    │   "summary": "..."                                   │               │
    │ }                                                    │               │
    └──────────────────────────────────────────────────────┘               │
              │                                                            │
              └───────────────────────────────────────────────────────────┘
                         ↓
         Return (results_dict, execution_order_list)
                         ↓
              Display in Streamlit "Document" tab
                         ↓
         ✅ COMPLETE FINAL DOCUMENT with all summaries!
```

---

## 2. Data Mutation Points

### 2.1 `results` Dictionary (Accumulated State)

```python
results = {}  # Initially empty

# After planner
results["planner"] = {
    "plan": ["architecture", "security", "performance", "documentation"],
    "next_agent": "architecture",
    ...
}

# After requirements
results["requirements"] = {
    "requirements": [
        "Multi-user authentication",
        "RESTful API endpoints",
        ...
    ],
    "completeness_score": 75,
    "critical_gaps": [...],
    ...
}

# After architecture
results["architecture"] = {
    "architecture_type": "microservices",
    "components": [...],
    ...
}

# After each reviewer check
results["reviewer"] = {
    "coverage_score": 85,
    "ready": false,
    "decision": "proceed",
    ...
}

# After security
results["security"] = {
    "security_score": 8,
    "vulnerabilities": [...],
    ...
}

# After performance
results["performance"] = {
    "estimated_latency_ms": 150,
    "bottlenecks": [...],
    ...
}

# Final documentation reads from full results
results["documentation"] = {
    "documentation": "# Final document with all summaries...",
    ...
}
```

### 2.2 Payload Construction

Each agent receives a payload with:
- `initial_context`: Never changes; original user input + config
- `workflow_results`: Grows with each executed agent

```python
# For architecture agent:
payload = {
    "initial_context": initial_context,  # Original problem statement
    "workflow_results": {
        "planner": {...},
        "requirements": {...}
    }
}

# For security agent (after architecture runs):
payload = {
    "initial_context": initial_context,
    "workflow_results": {
        "planner": {...},
        "requirements": {...},
        "architecture": {...}  # ← Architecture result now available
    }
}

# For documentation (final):
payload = {
    "initial_context": initial_context,
    "workflow_results": {
        "planner": {...},
        "requirements": {...},
        "architecture": {...},
        "security": {...},
        "performance": {...},
        "reviewer": {...}
    }
}
```

---

## 3. Why Agents Weren't Executing (Problems & Fixes)

### Problem #1: Planner Returned Invalid Agent Names ❌
**What happened:**
- Planner suggested `["Understand the goal", "Produce a compact agent plan"]`
- Supervisor looked for agents named "Understand the goal" → NOT FOUND
- Supervisor skipped them with `skip: not_registered`
- Only requirements executed; architecture/security/performance never ran

**Root cause:**
- `planner_prompt()` didn't list available agents
- Planner model had no constraints; it invented generic step names

**Fix:** ✅
```python
# Before: planner_prompt didn't mention available agents
# After: 
def planner_prompt(goal: str, context: Dict[str, Any], available_agents: List[str] | None = None):
    agents_list = ", ".join(available_agents or ["architecture", "security", ...])
    return f"""...
AVAILABLE AGENTS:
{agents_list}

Rules:
- Choose only from AVAILABLE AGENTS above
- next_agent: must be one of the available agents
...
"""
```

**Impact:** Planner now returns valid agent names like `"architecture"`, `"security"`, `"performance"` instead of generic steps.

---

### Problem #2: Reviewer Gate Stopped Pipeline Early ❌
**What happened:**
1. Architecture agent runs → `results["architecture"] = {...}`
2. Reviewer is invoked immediately
3. Reviewer sees requirements + architecture, calculates `coverage_score = 80`
4. Supervisor checks: `if coverage_score >= threshold (80): break`
5. Loop breaks → Security and Performance agents **never execute**
6. Documentation gets only requirements + architecture (missing security/performance)

**Root cause:**
- Reviewer was gating the pipeline with an early exit
- Loop should execute all agents from planner's plan, then final review

**Fix:** ✅
```python
# Before:
if "reviewer" in self.agents:
    rev_res = self.start_agent("reviewer", rev_payload)
    coverage_score = rev_res.get("coverage_score", 0)
    if coverage_score >= coverage_threshold:
        _emit("stop", reason="coverage_sufficient")
        break  # ← WRONG: exits loop prematurely

# After:
if "reviewer" in self.agents:
    rev_res = self.start_agent("reviewer", rev_payload)
    coverage_score = rev_res.get("coverage_score", 0)
    _emit("review_result", coverage_score=coverage_score, ...)
    # Note: Do NOT break. Let planner's full sequence execute.
```

**Impact:** All agents from planner's sequence now execute. Reviewer monitors but doesn't interrupt.

---

## 4. Updated Workflow Semantics

### Before the Fixes
```
Planner invoked
  ↓ (returns invalid step names like "Understand the goal")
  ↓
Requirements invoked
  ↓
Reviewer invoked (after architecture runs)
  ↓
coverage_score >= 80 → BREAK LOOP
  ↓
No security/performance → No summaries
  ↓
Final document incomplete
```

### After the Fixes
```
Planner invoked (receives available_agents constraint)
  ↓ (returns valid names like ["architecture", "security", "performance"])
  ↓
Requirements invoked
  ↓
For each agent in planner's plan:
  Architecture agent runs
    ↓
  Reviewer checks coverage (but doesn't break)
    ↓
  Security agent runs
    ↓
  Reviewer checks coverage (but doesn't break)
    ↓
  Performance agent runs
    ↓
  Reviewer checks coverage (but doesn't break)
    ↓
All agents executed with full results
  ↓
Documentation reads from complete workflow_results
  ↓
Final document has ALL summaries ✅
```

---

## 5. Key Data Flow Insights

### 5.1 Agents Only See What's in workflow_results
Agents are **read-only** on history. If an agent hasn't executed yet:
- Its output is not in `workflow_results`
- Later agents won't see it

Example:
- Performance agent cannot read security results if security hasn't run yet
- This is why planner decides the **order** (dependency resolution)

### 5.2 Clarification Pause/Resume

If requirements completeness is low:
```
requirements runs
  ↓
completeness_score = 65 (< 70)
  ↓
Supervisor emits: stop, reason="clarification_needed"
  ↓
Streamlit shows clarification form to user
  ↓
User answers questions
  ↓
Supervisor invoked AGAIN with:
{
  "problem_statement": "...",
  "clarification_answers": {
    "Who are the user roles?": "admin and contributors"
  }
}
  ↓
Requirements runs AGAIN, consuming clarification_answers
  ↓
Completeness improves (now 85 ≥ 70)
  ↓
Continue to architecture, security, performance
```

### 5.3 Coverage Threshold ≠ Completion Gate

The `coverage_threshold` (default 80) is now **informational only**:
- Reviewer calculates how much of the problem is covered
- Supervisor **emits this as a progress event** for UI display
- Supervisor **does NOT use this to break the loop**
- Planner's full sequence always executes

This respects the design principle: **"Reviewer assesses completeness tolerance, not binary readiness"**.

---

## 6. Testing & Verification

All tests updated to reflect new behavior:

✅ `test_adaptive_workflow_streams_progress_and_stops_when_ready`
- Expects all agents (including documentation) to execute
- Expects stop reason to be "plan_exhausted" (not "coverage_sufficient")

✅ `test_adaptive_workflow_pauses_for_clarification_then_resumes_with_answers`
- Expects clarification pause/resume to work
- Expects architecture to execute after clarification

✅ `test_adaptive_workflow_honors_completeness_tolerance`
- Expects reviewer monitoring to emit coverage_score
- Expects pipeline to continue (no gate)

---

## 7. Quick Reference: Agent Responsibilities

| Agent | Input | Output | When Executes |
|-------|-------|--------|---------------|
| **Planner** | goal, context, available_agents | plan, next_agent | Bootstrap (always first) |
| **Requirements** | user_input, clarification_answers | requirements, completeness_score, critical_gaps, questions | Always, after planner |
| **Architecture** | initial_context, workflow_results | components, deployment_model, tradeoffs | If in planner's plan |
| **Security** | initial_context, workflow_results | vulnerabilities, recommendations, security_score | If in planner's plan |
| **Performance** | initial_context, workflow_results | bottlenecks, latency, throughput | If in planner's plan |
| **Reviewer** | workflow_results | coverage_score, decision, gaps | After each analysis agent |
| **Documentation** | workflow_results (full) | final markdown document | Last, after all analyses |

---

## Summary

**Data flows left-to-right through agents, with each agent reading accumulated `workflow_results` and appending its own analysis.** The planner decides the sequence, requirements is always second, then loop through optional analyses, then documentation.

**Two critical bugs were fixed:**
1. **Planner constraint**: Now receives and respects available_agents list
2. **Reviewer gate removal**: Now monitors but doesn't prematurely exit the loop

**Result:** All agents execute in order, producing complete final documentation with architecture/security/performance summaries. ✅
