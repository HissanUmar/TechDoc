# Multi-Agent AI Software Engineering System (TRS)

A production-ready agentic framework for orchestrating specialized AI agents in complex workflows. Supervisor-based DAG execution with fault tolerance, state management, schema validation, and requirement clarification.

## Features

- **Supervisor-based DAG Orchestration**: Kahn's algorithm for topological sorting, parallel execution with ThreadPoolExecutor, configurable retry with exponential backoff
- **Fault-Tolerant Execution**: Per-node timeouts, automatic retries (default: 3 attempts), exception propagation with detailed error context
- **Thread-Safe State Management**: Versioned InMemoryStateStore with compare-and-set (CAS) semantics, event history, snapshots, and restore
- **Message Bus Integration**: Topic-based pub/sub for decoupling supervisor from workers, async task execution
- **Schema Validation**: JSON Schema support with fallback basic validation, custom schema registration
- **HuggingFace Integration**: Optional integration with HF Inference API, graceful degradation to echo stub when unavailable
- **Requirement Clarification**: Automated detection of vague terms, missing actors, priority-ranked clarification questions, round limiting

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────┐
│                      Supervisor                          │
│  DAG orchestration, parallel execution, retry logic      │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
   ┌────▼───────┐           ┌──────▼─────┐
   │ Agent Pool  │           │ Message Bus │
   └────────────┘           └──────┬──────┘
                                   │
                            ┌──────▼──────┐
                            │ AgentWorker  │
                            │ (background) │
                            └──────────────┘

┌─────────────────────────────────────────────────────────┐
│              Supporting Services                        │
├─────────────────────────────────────────────────────────┤
│ • InMemoryStateStore (versioned, CAS, history)         │
│ • SchemaValidator (JSON schema + fallback)             │
│ • HfClient (HuggingFace integration)                   │
│ • ClarificationEngine (vague term detection)           │
└─────────────────────────────────────────────────────────┘
```

### Execution Modes

1. **Direct Mode** (`run_workflow`): Supervisor directly executes agents in topological order
2. **Event-Driven Mode** (`run_workflow_via_bus`): Agents consume from message bus, enables background workers

## Installation

### Requirements

- Python 3.10+
- pytest (testing)

### Optional

- `huggingface_hub` (for HF Inference API integration)
- `jsonschema` (for JSON schema validation)

### Setup

```bash
# Clone/navigate to workspace
cd /Users/misc/Documents/TechnicalDoucmentation

# Install in editable mode
pip install -e .

# Install optional dependencies
pip install huggingface_hub jsonschema
```

### Environment Configuration

Create `.env.local` for local development credentials:

```bash
# .env.local
HF_API_TOKEN=your_huggingface_token_here
```

The HfClient reads `HF_API_TOKEN` from environment automatically.

## Quick Start

### 1. Create Custom Agent

```python
from agentic_framework.agent import AgentBase

class MyAnalyzerAgent(AgentBase):
    """Custom agent that analyzes input data."""
    
    def process(self, payload):
        data = payload.get("data", [])
        return {
            "analysis": f"Analyzed {len(data)} items",
            "status": "complete"
        }
```

### 2. Run Workflow

```python
from agentic_framework.supervisor import Supervisor

# Create supervisor
sup = Supervisor(max_workers=4, retry_attempts=3)

# Register agents
sup.register_agent("analyzer", MyAnalyzerAgent())

# Define DAG (empty list = no dependencies)
dag = {"analyzer": []}

# Execute
results = sup.run_workflow(dag, {"analyzer": {"data": [1, 2, 3]}})
print(results["analyzer"])  # {'analysis': 'Analyzed 3 items', 'status': 'complete'}
```

### 3. Multi-Agent Workflow

```python
# Define multi-agent DAG with dependencies
dag = {
    "requirements": [],                    # Entry point
    "design": ["requirements"],            # Depends on requirements
    "validation": ["design"],              # Depends on design
}

payloads = {
    "requirements": {"user_input": "Build API"},
    "design": {"framework": "REST"},
    "validation": {"check_security": True},
}

results = sup.run_workflow(dag, payloads)
```

## API Reference

### Supervisor

```python
Supervisor(
    state_store=None,           # InMemoryStateStore instance (created if None)
    max_workers=4,              # ThreadPoolExecutor max threads
    retry_attempts=3,           # Failed node retry count
    retry_backoff=1.0,         # Exponential backoff multiplier (seconds)
    agent_timeout=None,         # Per-agent timeout (seconds, None=unlimited)
)
```

**Methods:**

- `register_agent(name: str, agent: AgentBase)` - Register agent by name
- `run_workflow(dag: dict, payloads: dict) -> dict` - Execute DAG synchronously
- `run_workflow_via_bus(dag, payloads, bus) -> dict` - Execute via message bus
- `state.get(key, default=None)` - Retrieve state value
- `state.set(key, value) -> int` - Set state, returns version
- `state.cas(key, expected_version, value) -> (bool, int)` - Compare-and-set
- `state.snapshot() -> (int, dict)` - Get (version, dict) snapshot
- `state.restore(version)` - Restore to specific version
- `state.history() -> list` - Get [(version, key, value), ...] history

### AgentBase

Base class for all agents. Override `process()`:

```python
class CustomAgent(AgentBase):
    def process(self, payload: dict) -> dict:
        """
        Args:
            payload: Input data dict from supervisor
        
        Returns:
            dict: Result to be stored in workflow results
        
        Raises:
            Exception: Triggers supervisor retry logic
        """
        return {"result": "processed"}
```

### ClarificationEngine

Detect ambiguous requirements and generate prioritized questions:

```python
from agentic_framework.clarification import ClarificationEngine

engine = ClarificationEngine(max_rounds=5)

# Analyze for vague terms and missing actors
analysis = engine.analyze("We need a fast, scalable system for many users")

# Returns:
# {
#     "vague_terms": ["fast", "many"],
#     "missing_actors": [...],
#     "questions": [
#         {"text": "How many concurrent users?", "priority": 9, ...},
#         ...
#     ],
#     "can_proceed": False
# }

# Answer questions
engine.questions = analysis["questions"]
engine.add_answer(0, "10,000 concurrent users")

# Check if ready to proceed
can_proceed, msg = engine.proceed_or_clarify()

# Get summary for audit trail
summary = engine.summary()
```

### SchemaValidator

Validate data against JSON schemas:

```python
from agentic_framework.schemas import SchemaValidator

validator = SchemaValidator()

# Validate against built-in schemas
result = validator.validate(
    {"requirements": ["auth", "logging"]},
    "requirements"  # Built-in schema name
)
# Returns: {"valid": bool, "errors": [str], "schema_name": str}

# Register custom schema
validator.register_schema("my_schema", {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "count": {"type": "integer"}
    },
    "required": ["name"]
})

result = validator.validate({"name": "test", "count": 5}, "my_schema")
```

### SimpleMessageBus

Topic-based pub/sub for async communication:

```python
from agentic_framework.message_bus import SimpleMessageBus

bus = SimpleMessageBus()

# Publish
bus.publish("tasks", {"node": "analyzer", "payload": {...}})

# Consume (blocking, optional timeout)
msg = bus.consume("tasks", timeout=5.0)

# Check if empty
is_empty = bus.empty("tasks")
```

### HfClient

HuggingFace model integration with fallback:

```python
from agentic_framework.hf_client import HfClient

client = HfClient(model="gpt2", token=None)  # Reads HF_API_TOKEN from env

response = client.call_model(
    "What is AI?",
    {"max_tokens": 50, "temperature": 0.7}
)

# Returns: {
#     "model": "gpt2",
#     "output": "...",  # Generated text
#     "raw": {...}       # Raw API response
# }
```

### InMemoryStateStore

Thread-safe, versioned state management:

```python
from agentic_framework.state import InMemoryStateStore

state = InMemoryStateStore()

# Basic get/set
v1 = state.set("key1", "value1")  # Returns version number
val = state.get("key1")            # "value1"

# Compare-and-set (optimistic concurrency)
success, v2 = state.cas("key1", v1, "new_value")
if success:
    print(f"Updated to version {v2}")

# Snapshots
version, data = state.snapshot()
state.restore(version)

# History for audit
history = state.history()  # [(version, key, value), ...]
```

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_integration.py

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_supervisor.py::test_linear_dag_execution
```

### Test Coverage

- **test_supervisor.py** (4 tests): DAG execution, retries, error handling
- **test_state.py** (4 tests): State management, versioning, CAS, snapshots
- **test_worker.py** (2 tests): Background task execution
- **test_message_bus.py** (1 test): Message bus integration
- **test_schemas.py** (6 tests): Schema validation, custom schemas
- **test_clarification.py** (7 tests): Vague term detection, questions, rounds
- **test_hf_client.py** (1 test): HF client with fallback
- **test_integration.py** (7 tests): End-to-end workflows

**Total: 32 tests**

## Usage Patterns

### Pattern 1: Sequential Processing

```python
dag = {
    "step1": [],
    "step2": ["step1"],
    "step3": ["step2"],
}

results = sup.run_workflow(dag, payloads)
# Executes in order: step1 → step2 → step3
```

### Pattern 2: Parallel Branches

```python
dag = {
    "entry": [],
    "branch_a": ["entry"],
    "branch_b": ["entry"],
    "merge": ["branch_a", "branch_b"],
}

# Supervisor executes: entry → {branch_a, branch_b} (parallel) → merge
```

### Pattern 3: Requirement Clarification Workflow

```python
engine = ClarificationEngine(max_rounds=5)
analysis = engine.analyze(user_requirements)

while not analysis["can_proceed"]:
    # Interactive: collect answers from user
    for i, question in enumerate(analysis["questions"]):
        answer = input(f"Q{i}: {question['text']}")
        engine.add_answer(i, answer)
    
    can_proceed, msg = engine.proceed_or_clarify()
    if can_proceed:
        break
    analysis = engine.analyze(user_requirements)  # Re-analyze

# Proceed with clarified requirements
```

### Pattern 4: Event-Driven Execution

```python
bus = SimpleMessageBus()
worker = AgentWorker(resolve_agent=lambda name: sup.agents[name], message_bus=bus)
worker.start()  # Background processing

# Supervisor publishes tasks to bus
results = sup.run_workflow_via_bus(dag, payloads, bus=bus)

worker.stop()
```

## Layout

```
.
├── README.md                           # This file
├── pyproject.toml                      # Project metadata and dependencies
├── .gitignore                          # Git ignore rules
├── .env.local                          # Local credentials (not committed)
├── main.py                             # CLI entrypoint
├── src/
│   └── agentic_framework/
│       ├── __init__.py                 # Package exports
│       ├── agent.py                    # AgentBase class
│       ├── supervisor.py               # DAG orchestration
│       ├── state.py                    # InMemoryStateStore
│       ├── message_bus.py              # SimpleMessageBus
│       ├── worker.py                   # AgentWorker background processor
│       ├── hf_client.py                # HuggingFace integration
│       ├── schemas.py                  # SchemaValidator and schema definitions
│       ├── clarification.py            # ClarificationEngine
│       └── cli.py                      # CLI demo
└── tests/
    ├── conftest.py                     # pytest configuration
    ├── test_supervisor.py              # Supervisor tests
    ├── test_agent.py                   # Agent interface tests
    ├── test_state.py                   # State management tests
    ├── test_message_bus.py             # Message bus tests
    ├── test_worker.py                  # Worker tests
    ├── test_hf_client.py               # HF client tests
    ├── test_schemas.py                 # Schema validation tests
    ├── test_clarification.py           # Clarification engine tests
    └── test_integration.py             # End-to-end integration tests
```

## Contributing

Follow these patterns when extending the framework:

1. **Custom Agents**: Subclass `AgentBase`, implement `process(payload)`
2. **Schemas**: Register with `SchemaValidator.register_schema(name, schema)`
3. **Testing**: Add tests in `tests/` directory, use pytest fixtures from `conftest.py`
4. **State Access**: Use `supervisor.state` for shared state, follow CAS pattern for concurrent access

## Error Handling

- **Agent Exceptions**: Supervisor retries per `retry_attempts` config, raises `WorkflowExecutionError` after exhaustion
- **DAG Validation**: Invalid DAGs raise `DAGValidationError` before execution
- **State CAS Failures**: Returns `(False, version)` on conflict, caller can retry
- **Schema Validation**: Returns `{"valid": False, "errors": [descriptions]}` without raising

## Performance Considerations

- **Parallel Execution**: Supervisor uses ThreadPoolExecutor; CPU-bound agents should release GIL (use subprocesses for pure compute)
- **State Snapshots**: Safe for long-running workflows; history grows unbounded (consider cleanup for production)
- **Message Bus**: Uses thread-safe queue.Queue; suitable for inter-process communication via pickle serialization
- **Retry Backoff**: Exponential backoff (1.0s default) prevents overwhelming transient errors

## License

MIT
