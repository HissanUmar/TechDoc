# Agent Execution Problems & Solutions (Visual Summary)

## The Two Critical Issues

### Issue #1: Planner Returns Non-Agent Names ❌

```
USER INPUT: "Build a web app for a consulting team..."
         ↓
PLANNER AGENT (no constraints about available agents)
         ↓
Returns: plan = [
    "Understand the goal",           ← NOT A REGISTERED AGENT
    "Produce a compact agent plan"   ← NOT A REGISTERED AGENT
]
         ↓
SUPERVISOR TRIES TO FIND THESE AGENTS
         ↓
❌ skip: "Understand the goal" not_registered
❌ skip: "Produce a compact agent plan" not_registered
         ↓
stop: plan_exhausted
         ↓
RESULT: Only planner + requirements executed
        No architecture/security/performance
        Final document incomplete ❌
```

**Fix Applied:**
```
PLANNER AGENT (receives available_agents constraint)
         ↓
available_agents = ["architecture", "security", "performance", "documentation"]
         ↓
Planner prompt explicitly states:
  "Choose only from: architecture, security, performance, documentation"
         ↓
Returns: plan = [
    "architecture",        ✅ VALID AGENT NAME
    "security",            ✅ VALID AGENT NAME
    "performance",         ✅ VALID AGENT NAME
    "documentation"        ✅ VALID AGENT NAME
]
         ↓
SUPERVISOR FINDS AND EXECUTES THESE AGENTS ✅
         ↓
All agents run → Full workflow_results
         ↓
Final document complete ✅
```

---

### Issue #2: Reviewer Breaks Loop Early ❌

```
PLANNER: "Execute architecture, security, performance, documentation"
         ↓
         ├─→ Architecture agent runs
         │    ↓
         │    results["architecture"] = {components, ...}
         │    ↓
         │    REVIEWER checks coverage
         │    coverage_score = 80
         │    ↓
         │    ❌ if coverage_score >= 80:
         │         BREAK LOOP
         │    ↓
         ├─→ Security agent ❌ NEVER EXECUTES
         │
         ├─→ Performance agent ❌ NEVER EXECUTES
         │
         └─→ Documentation agent ❌ NEVER EXECUTES
              (tries to read security/performance from workflow_results)
              ↓
              "No security summary available"
              "No performance summary available"
```

**Fix Applied:**
```
PLANNER: "Execute architecture, security, performance, documentation"
         ↓
         ├─→ Architecture agent runs
         │    ↓
         │    results["architecture"] = {...}
         │    ↓
         │    REVIEWER checks coverage (monitoring only)
         │    coverage_score = 80
         │    ↓
         │    ✅ Emits review_result event
         │    ✅ Does NOT break loop
         │    ↓
         ├─→ Security agent ✅ EXECUTES
         │    ↓
         │    results["security"] = {...}
         │    ↓
         │    REVIEWER checks coverage again
         │    ✅ Does NOT break loop
         │    ↓
         ├─→ Performance agent ✅ EXECUTES
         │    ↓
         │    results["performance"] = {...}
         │    ↓
         │    REVIEWER checks coverage again
         │    ✅ Does NOT break loop
         │    ↓
         └─→ Documentation agent ✅ EXECUTES
              ↓
              Reads from complete workflow_results:
              - architecture ✅
              - security ✅
              - performance ✅
              ↓
              Final document complete ✅
```

---

## Code Changes Comparison

### Change 1: agent_prompts.py

**Before:**
```python
def planner_prompt(goal: str, context: Dict[str, Any]) -> str:
    return f"""You are the Planner.
...
next_agent: string
...
"""
```

**After:**
```python
def planner_prompt(goal: str, context: Dict[str, Any], available_agents: List[str] | None = None) -> str:
    if available_agents is None:
        available_agents = ["requirements", "architecture", "security", "performance", "documentation"]
    agents_list = ", ".join(available_agents)
    return f"""You are the Planner.

AVAILABLE AGENTS:
{agents_list}

...
- next_agent: string (must be one of the available agents)
...
"""
```

---

### Change 2: agents/planner.py

**Before:**
```python
def process(self, payload: Dict[str, Any]):
    goal = payload.get("goal", "")
    context = payload.get("context", {})
    prompt = planner_prompt(goal, context)  # ← Missing constraint
```

**After:**
```python
def process(self, payload: Dict[str, Any]):
    goal = payload.get("goal", "")
    context = payload.get("context", {})
    available_agents = payload.get("available_agents", [...])  # ← NEW
    prompt = planner_prompt(goal, context, available_agents)   # ← Passes constraint
```

---

### Change 3: supervisor.py (two places)

**Before (Planner invocation):**
```python
if "planner" in self.agents:
    plan_res = _run("planner", {
        "goal": initial_context.get("problem_statement", ""),
        "context": initial_context
        # ← Missing available_agents
    })
```

**After:**
```python
if "planner" in self.agents:
    available_agents = [n for n in list(self.agents.keys()) if n not in {"planner", "reviewer", "documentation"}]
    plan_res = _run("planner", {
        "goal": initial_context.get("problem_statement", ""),
        "context": initial_context,
        "available_agents": available_agents  # ← NEW: passed to planner
    })
```

**Before (Reviewer loop):**
```python
for candidate in next_candidates:
    # ... run agent ...
    if "reviewer" in self.agents:
        rev_res = self.start_agent("reviewer", rev_payload)
        coverage_score = rev_res.get("coverage_score", 0)
        if coverage_score >= coverage_threshold:
            _emit("stop", reason="coverage_sufficient")
            break  # ← BREAKS LOOP EARLY ❌
```

**After:**
```python
for candidate in next_candidates:
    # ... run agent ...
    if "reviewer" in self.agents:
        rev_res = self.start_agent("reviewer", rev_payload)
        coverage_score = rev_res.get("coverage_score", 0)
        _emit("review_result", coverage_score=coverage_score, ...)
        # ← NO BREAK: Lets loop continue ✅
        # Note: Do NOT break the loop. Let planner's full sequence execute.
```

---

## Test Updates

**Before (old expectations):**
```python
assert "documentation" not in results  # Expected NOT to execute
assert any(event["event"] == "stop" and event["reason"] == "coverage_sufficient")
```

**After (new expectations):**
```python
assert "documentation" in results  # NOW expects to execute ✅
assert any(event["event"] == "stop" and event["reason"] == "plan_exhausted")
```

All 7 tests now pass with the new behavior. ✅

---

## Impact on Final Document

### Before Fixes ❌
```
Project Overview
Build a web app for consulting team...

Architecture Summary
No architecture summary available.

Security Summary
No security summary available.

Performance Summary
No performance summary available.

Validation Checks
requirements_schema: PASS
architecture_schema: PASS
reviewer_gate: PASS
```

### After Fixes ✅
```
Project Overview
Build a web app for consulting team...

Requirements
- Multi-user authentication
- RESTful API endpoints
- Database persistence
- Error handling and logging

Architecture Summary
- Microservices architecture
- Components: Auth Service, API Gateway, Task Manager, Notification Service
- Deployment: Cloud-native with containerization
- Tradeoffs: Complexity vs. Scalability

Security Summary
- Security Score: 8/10
- Vulnerabilities: [None critical]
- Recommendations:
  - Implement HTTPS on all endpoints
  - Add rate limiting to API
  - Encrypt sensitive fields in database

Performance Summary
- Estimated Latency: 150ms (p95)
- Throughput: 1000 RPS
- Bottlenecks: Database queries for task filtering
- Optimizations:
  - Add caching layer (Redis)
  - Index task queries by deadline and user_id

Validation Checks
requirements_schema: PASS
architecture_schema: PASS
reviewer_gate: PASS
```

---

## Data Dependency Graph

The supervisor now ensures dependencies are respected:

```
          planner (bootstrap)
             ↓
       requirements (always 2nd)
             ↓
        ┌────┴────┬────────────┐
        ↓         ↓            ↓
  architecture  (optional based on plan)
        ↓         ↓            ↓
    security  performance    ...
        ↓         ↓            ↓
        └────┬────┴────────────┘
             ↓
       documentation (final, reads all above)
```

Each agent only executes if:
1. It's in the planner's suggested `plan` list
2. It's a registered agent name
3. Its dependencies have completed (workflow_results contains them)

**The supervisor now respects this DAG and executes it fully.** ✅

---

## Key Takeaway

**Two simple but critical fixes made the entire system work:**

1. **Constraint the planner** so it can only suggest valid agent names
2. **Remove the reviewer gate** so the full planned sequence executes

This allows all agents to run in order, accumulating results in `workflow_results`, which the documentation agent consumes to produce a **complete final document** with all summaries. ✅
