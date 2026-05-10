# Planner Agent Name Mapping Fix

## Problems Identified

### 1. Missing Architecture/Security/Performance Summaries
The final document showed:
```
Architecture Summary
No architecture summary available.

Security Summary
No security summary available.

Performance Summary
No performance summary available.
```

### 2. Planner Returned Non-Agent Names
The execution trace showed:
```
Skipping Understand the goal: not_registered
Skipping Produce a compact agent plan: not_registered
Stopping: plan_exhausted
```

## Root Cause

The `planner_prompt()` did not explicitly list or constrain the planner to use actual registered agent names. The planner model returned generic step names like:
- "Understand the goal"
- "Produce a compact agent plan"

The supervisor correctly skipped these as "not_registered" because they don't exist in the agent registry. Once the invalid candidates were exhausted, the workflow stopped with "plan_exhausted".

## Solution

Three files were updated to fix this:

### 1. `agent_prompts.py` — Updated `planner_prompt()`
Added `available_agents` parameter and explicitly list agents in the prompt:

```python
def planner_prompt(goal: str, context: Dict[str, Any], available_agents: List[str] | None = None) -> str:
    if available_agents is None:
        available_agents = ["requirements", "architecture", "security", "performance", "documentation"]
    agents_list = ", ".join(available_agents)
    return f"""You are the Planner.
    
AVAILABLE AGENTS:
{agents_list}

Rules:
- Choose only from the AVAILABLE AGENTS list above.
- plan: list of agent names (must be chosen from the available agents list)
- next_agent: string (must be one of the available agents)
...
```

**Impact:** Planner now knows which agents exist and is instructed to choose only from them.

### 2. `agents/planner.py` — Updated `PlannerAgent.process()`
Now extracts `available_agents` from the payload and passes to the prompt:

```python
def process(self, payload: Dict[str, Any]):
    goal = payload.get("goal", "")
    context = payload.get("context", {})
    available_agents = payload.get("available_agents", [...])  # ← NEW
    prompt = planner_prompt(goal, context, available_agents)    # ← Pass agents
    ...
```

**Impact:** Planner agent can now receive the list of available agents from the supervisor.

### 3. `supervisor.py` — Updated `run_adaptive_workflow()`
Now passes `available_agents` when invoking the planner:

```python
if "planner" in self.agents:
    _emit("decision", agent="planner", reason="bootstrap workflow from the user problem statement")
    available_agents = [n for n in list(self.agents.keys()) if n not in {"planner", "reviewer", "documentation"}]
    plan_res = _run("planner", {
        "goal": initial_context.get("problem_statement", ""), 
        "context": initial_context, 
        "available_agents": available_agents  # ← NEW
    })
```

**Impact:** Supervisor now explicitly tells the planner which agents are registered and can be executed.

## Expected Outcome

After these changes:

1. **Planner receives the actual list of available agents** from the supervisor
2. **Planner's output will include agent names from the registry** (e.g., "architecture", "security", "performance")
3. **Supervisor will validate and execute these agents successfully** instead of skipping them
4. **Architecture, security, and performance analyses will execute** and provide summaries
5. **Final document will include all summaries** (no more "No X summary available")

## Verification

All existing tests pass (7/7):
```
tests/test_supervisor.py::test_simple_dag_execution PASSED
tests/test_supervisor.py::test_retry_succeeds_after_transient_failure PASSED
tests/test_supervisor.py::test_retry_exhausts_and_raises PASSED
tests/test_supervisor.py::test_adaptive_workflow_streams_progress_and_stops_when_ready PASSED
tests/test_supervisor.py::test_adaptive_workflow_uses_fallback_plan_when_planner_absent PASSED
tests/test_supervisor.py::test_adaptive_workflow_pauses_for_clarification_then_resumes_with_answers PASSED
tests/test_supervisor.py::test_adaptive_workflow_honors_completeness_tolerance PASSED
```

All modified files compile without syntax errors: ✅
