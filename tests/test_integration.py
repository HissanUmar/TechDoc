"""End-to-end integration tests for the agentic framework."""

import time

from agentic_framework.supervisor import Supervisor
from agentic_framework.worker import AgentWorker
from agentic_framework.agent import AgentBase
from agentic_framework.state import InMemoryStateStore
from agentic_framework.message_bus import SimpleMessageBus
from agentic_framework.schemas import SchemaValidator
from agentic_framework.clarification import ClarificationEngine
from agentic_framework.hf_client import HfClient


# -- Concrete Agent Implementations for Testing ----

class RequirementAnalystAgent(AgentBase):
    """Simulates a requirements analyst that extracts requirements."""

    def process(self, payload):
        user_input = payload.get("user_input", "")
        return {
            "requirements": [
                "Multi-user support",
                "RESTful API",
                "Database persistence",
            ],
            "source": user_input[:30] if user_input else "unknown",
        }


class ArchitectureAgent(AgentBase):
    """Simulates an architect that designs system architecture."""

    def process(self, payload):
        requirements = payload.get("requirements", [])
        return {
            "architecture": "microservices",
            "components": [
                {"name": "API Server", "role": "request handler"},
                {"name": "Database", "role": "data persistence"},
                {"name": "Cache", "role": "performance optimization"},
            ],
            "requirements_count": len(requirements),
        }


class ValidationAgent(AgentBase):
    """Simulates a validation agent that checks consistency."""

    def process(self, payload):
        architecture = payload.get("architecture")
        components = payload.get("components", [])
        return {
            "valid": bool(architecture and len(components) > 0),
            "errors": [],
            "warnings": ["Consider load testing" if len(components) > 2 else ""],
        }


# -- Integration Tests ----

def test_end_to_end_dag_workflow():
    """Test a complete DAG workflow with multiple agents."""
    sup = Supervisor(max_workers=2, retry_attempts=2)
    sup.register_agent("analyst", RequirementAnalystAgent())
    sup.register_agent("architect", ArchitectureAgent())
    sup.register_agent("validator", ValidationAgent())

    # Define DAG: analyst -> architect -> validator
    dag = {
        "analyst": [],
        "architect": ["analyst"],
        "validator": ["architect"],
    }
    payloads = {
        "analyst": {"user_input": "Build a scalable web app"},
        "architect": {"requirements": ["Multi-user", "REST API", "DB"]},
        "validator": {
            "architecture": "microservices",
            "components": [{"name": "API"}, {"name": "DB"}],
        },
    }

    # Execute the DAG
    results = sup.run_workflow(dag, payloads)

    # Verify all nodes executed
    assert "analyst" in results
    assert "architect" in results
    assert "validator" in results

    # Verify results have expected structure
    assert results["analyst"]["requirements"]
    assert results["architect"]["architecture"] == "microservices"
    assert results["validator"]["valid"] is True


def test_state_store_integration():
    """Test state store alongside workflow execution."""
    sup = Supervisor(state_store=InMemoryStateStore())
    sup.register_agent("analyst", RequirementAnalystAgent())

    dag = {"analyst": []}
    results = sup.run_workflow(dag)

    # Store results in state
    version = sup.state.set("workflow_results", results)
    assert version > 0

    # Retrieve and verify
    retrieved = sup.state.get("workflow_results")
    assert retrieved == results

    # Check state history
    history = sup.state.history()
    assert len(history) > 0
    assert history[0][1] == "workflow_results"


def test_message_bus_with_validator():
    """Test message bus orchestration with schema validation."""
    bus = SimpleMessageBus()
    validator = SchemaValidator()
    sup = Supervisor()
    sup.register_agent("analyst", RequirementAnalystAgent())

    # Start worker
    worker = AgentWorker(resolve_agent=lambda name: sup.agents[name], message_bus=bus)
    worker.start()

    # Publish task
    dag = {"analyst": []}
    results = sup.run_workflow_via_bus(dag, {"analyst": {"user_input": "Test"}}, bus=bus)

    worker.stop()

    # Validate result against schema
    validation = validator.validate(results["analyst"], "requirements")
    assert validation["valid"] is True


def test_clarification_in_workflow_context():
    """Test clarification engine identifying ambiguous requirements."""
    engine = ClarificationEngine(max_rounds=3)

    vague_prompt = (
        "We need a fast, scalable system for many users. "
        "It should be reliable and support concurrent logins."
    )

    analysis = engine.analyze(vague_prompt)

    # Should detect vagueness
    assert len(analysis["vague_terms"]) > 0
    assert len(analysis["questions"]) > 0
    assert not analysis["can_proceed"]

    # Answer some questions
    engine.questions = analysis["questions"]
    if len(engine.questions) > 0:
        engine.add_answer(0, "10,000 concurrent users")

    # Check progress
    can_proceed, msg = engine.proceed_or_clarify()
    assert "remain unanswered" in msg or can_proceed


def test_hf_client_in_agent():
    """Test HF client as part of an agent."""
    class LLMAgent(AgentBase):
        def __init__(self):
            super().__init__()
            self.client = HfClient(model="mistralai/Mistral-7B-Instruct-v0.1", token=None)

        def process(self, payload):
            prompt = payload.get("prompt", "hello")
            response = self.client.call_model(prompt)
            return {"llm_output": response["output"], "model": response["model"]}

    agent = LLMAgent()
    output = agent.process({"prompt": "What is your name?"})
    assert "ECHO" in output["llm_output"]
    # Without token, falls back to gpt2 stub
    assert output["model"] == "gpt2"


def test_parallel_agents_with_state():
    """Test parallel execution of independent agents using state."""
    sup = Supervisor(state_store=InMemoryStateStore(), max_workers=3)

    class CounterAgent(AgentBase):
        def __init__(self, name):
            super().__init__()
            self.name = name

        def process(self, payload):
            return {"agent": self.name, "count": 1}

    sup.register_agent("counter_a", CounterAgent("A"))
    sup.register_agent("counter_b", CounterAgent("B"))
    sup.register_agent("counter_c", CounterAgent("C"))

    # All parallel (no dependencies)
    dag = {"counter_a": [], "counter_b": [], "counter_c": []}
    results = sup.run_workflow(dag)

    # Store aggregated result
    total = len(results)
    sup.state.set("parallel_result", {"agents_run": total})

    assert sup.state.get("parallel_result")["agents_run"] == 3


def test_retry_with_state_checkpoint():
    """Test retry logic with state checkpoints."""
    sup = Supervisor(
        state_store=InMemoryStateStore(),
        max_workers=1,
        retry_attempts=3,
        retry_backoff=0.01,
    )

    attempt_count = 0

    class FlakeyAgent(AgentBase):
        def process(self, payload):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise RuntimeError("transient error")
            return {"success": True, "attempts": attempt_count}

    sup.register_agent("flakey", FlakeyAgent())
    dag = {"flakey": []}

    results = sup.run_workflow(dag)

    # Should have succeeded after retries
    assert results["flakey"]["success"] is True
    assert results["flakey"]["attempts"] == 3

    # Store in state for audit
    sup.state.set("retry_audit", {"agent": "flakey", "attempts": attempt_count})
    audit = sup.state.get("retry_audit")
    assert audit["attempts"] == 3
